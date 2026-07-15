# Project Development Notes

Chronological history of work on the Antiyoy Python project.

---

## Phase 1: Game Engine Port

The project is a Python port of the original Antiyoy Android/Java game. The core game engine was ported including:

- **Core game logic**: Hex grid, provinces (flood-fill based territory grouping), adjacency graph, move zone computation (wave propagation), economics (income/consumption per province).
- **Event system**: `AbstractEvent` base class with types like `UNIT_MOVE`, `PIECE_BUILD`, `PIECE_ADD`, `PIECE_DELETE`, `HEX_CHANGE_COLOR`, `SET_MONEY`, `TURN_END`, etc. Events flow through `EventsManager` with validation and listener notification.
- **AI system**: `AIManager` with `BalancerAI` ported from the original, supporting difficulty levels (easy, average, hard, expert, balancer).
- **Save/load system**: `GameStateEncoder`/`GameStateDecoder` with a section-based format (`#hexes:`, `#provinces:`, `#turn:`, etc.). Includes `SECTION_ORIGINAL_LEVEL_CODE` for replay file support.
- **Campaign**: 156 campaign levels ported from the original game, stored in `campaign/levels.py`.
- **Command system**: `CommandExecutor`/`CommandValidator` for player actions (move, build, end turn).
- **Web interface**: Flask app with canvas-based hex grid rendering, pan/zoom, fog of war, game sessions.
- **Test suite**: 400+ unit tests covering core logic, events, provinces, save/load, AI.

### Key files from the port

| Directory | Purpose |
|---|---|
| `core/` | Game state, hex, province, events, rulesets, turns, economics, fog of war, death manager, game end |
| `campaign/` | 156 level codes, campaign manager with difficulty progression |
| `save_load/` | Encoder, decoder, format parser |
| `ai/` | BalancerAI (ported from Java), AI manager |
| `commands/` | Command types, validator, executor |
| `web/` | Flask app, templates, static assets (JS/CSS), canvas hex renderer |
| `tests/` | Unit tests + visual tests |

---

## Phase 2: Replay System

### Problem

The game needed a replay system so completed games could be reviewed step by step. Initial attempts to re-derive game state by re-applying recorded events proved brittle — subtle interdependencies between events, province merges, and hidden state caused persistent mismatches (wrong hex colors, missing pieces).

### Solution: Snapshot-based replay

Instead of re-applying events, the system records the full game state at every notable event during live gameplay. This guarantees perfect replay.

#### Recording (during gameplay)

- `HistoryManager` listens for events via `on_event_applied()`.
- After every notable event and every `TURN_END`, it captures a `ReplaySnapshot` containing: hex state, provinces (id/money/color), turn/lap, entities, and the event encoding (for animations).
- New event types added: `TURN_BEGIN`, `LAP_BEGIN`, `PLAYER_TURN_STATS` — to capture turn boundaries and per-player economic stats.

#### Diff-based storage optimization

Full snapshots of a 384-hex map are ~6.5 KB each. With ~12 snapshots per turn, a 400-turn game would be ~32 MB in memory and ~43 MB on disk.

The system stores only hex diffs: the first snapshot is full, subsequent ones store only changed hexes (prefixed with `D:`). Typically 1-3 hexes change per event.

**Results on the largest map (level 69, 384 hexes, 5 players, 438 turns):**

| Metric | Full snapshots | Diff snapshots | Reduction |
|---|---|---|---|
| In-memory | ~31.6 MB | 1.86 MB | 94.1% |
| Replay file on disk | ~43.3 MB | 2.67 MB | 93.8% |
| Average per snapshot | 6,476 B | 390 B | 94.0% |

#### Replay playback (frontend)

The backend API (`/api/replay/content`) computes full-state steps from the diff snapshots, then converts them to a compact diff format for the frontend:
- Sends `initial_state` (full hex list) + `step_diffs[]` (only changed hexes per step, plus animation data and entity stats).
- A 384-hex, 7739-step replay sends ~6.8 MB JSON instead of ~60+ MB.

The frontend (`replay.js`) maintains a running `hexMap` patched forward/backward via diffs:
- **Forward**: applies hex changes, stores reverse patch for undo.
- **Backward**: applies stored reverse patch (instant).
- **Jump to beginning**: rebuilds from initial state.
- **Scrubber**: range slider for seeking to any position.
- **Play/Pause**: auto-advance with configurable speed multiplier (vertical slider between pause/play buttons). All other controls auto-pause playback.

#### Files modified/created for replay

| File | Changes |
|---|---|
| `core/history_manager.py` | `ReplaySnapshot` class, diff computation (`_compute_hex_diff`), `_prev_hex_map` tracking, snapshot recording in `on_event_applied` |
| `core/enums.py` | Added `TURN_BEGIN`, `LAP_BEGIN`, `PLAYER_TURN_STATS` to `EventType` |
| `core/events.py` | New event classes: `EventTurnBegin`, `EventLapBegin`, `EventPlayerTurnStats`. Extended `EventTurnEnd` with `turn_index_after`/`lap_after`. Fixed `EventUnitMove.is_valid()` for replay, `EventPieceBuild.apply_change()` for color transfer |
| `save_load/format.py` | Added `SECTION_REPLAY_SNAPSHOTS` |
| `save_load/encoder.py` | Encodes replay snapshots as base64 section |
| `save_load/decoder.py` | Decodes replay snapshots, fixed `_decode_hexes` to set pieces directly (bypass event validation during cloning) |
| `save_load/replay_steps.py` | Full rewrite: builds steps from diff-based snapshots with incremental hex reconstruction, animation extraction from event encodings, income computation from hex data |
| `save_load/replay.py` | Replay file saving |
| `commands/executor.py` | Sets `current_color` on `EventTurnEnd` before apply |
| `web/app.py` | Added `_steps_to_diff_format()`, updated `/api/replay/content` to send diff-based response |
| `web/static/js/replay.js` | Diff-based state management (hexMap + reversePatches), scrubber, play/pause with speed control, auto-pause on manual navigation |
| `web/static/css/replay.css` | Replay UI styling, scrubber, speed slider |
| `web/templates/replay.html` | Replay page with control bar, scrubber, speed slider |
| `tools/ai_playthrough.py` | Generates replay files from AI-vs-AI games |
| `tools/verify_replay_perfect.py` | Verifies replayed end state matches saved state |

#### Replay status overlay

- Shows `Turn: Y-X` (lap-turn_index).
- Entity stats table: Type, Hex %, Money, Income.
- `▸` marker on the current player's row (with en-space placeholder on inactive rows to prevent text jumping).
- Income computed from hex data using game rules: empty hex = 1, farm = 5, palm/pine = 0, minus unit/tower upkeep.
- Hex % uses total hex count (including gray) as denominator, matching the live game.

### Tools

- `tools/ai_playthrough.py` — runs an AI game and saves a replay file.
- `tools/run_playthrough_batch.py` — batch runner for multiple levels/difficulties with CSV output and plots.
- `tools/verify_replay_perfect.py` — validates replay correctness by comparing final replayed state to saved state.

---

## Phase 3: ML Training

Reference notes for continuing ML training work in any environment.

## Architecture Overview

The ML system is a Gymnasium environment (`ml/env.py`) that wraps the game engine. It uses Stable-Baselines3 with action masking (`sb3-contrib`) for reinforcement learning.

### ML Package Structure

| File | Purpose |
|---|---|
| `ml/env.py` | `AntiyoyEnv` -- Gymnasium wrapper, handles game loop, opponent AI, resets |
| `ml/observation.py` | `FlatObservationEncoder` -- converts game state to ~120-float numpy array |
| `ml/action_space.py` | `ActionMapper` -- maps discrete indices to commands, generates action masks |
| `ml/reward.py` | `DefaultRewardCalculator` -- terminal +1/-1 win/loss, optional ownership shaping |
| `ml/config.py` | `TrainConfig` dataclass with all hyperparameters (training + eval) |
| `ml/train.py` | Training entry point, `make_env`/`make_eval_env`, SubprocVecEnv, MaskablePPO, callbacks |
| `ml/ml_ai.py` | `MlAI` -- loads trained model for inference as an in-game AI player |

### Action Space

Fixed-size discrete space: `1 + N*N + N*7` where N = max hex count across configured levels.

- Index 0: EndTurn
- 1 to N*N: MoveUnit (source hex, destination hex)
- N*N+1 to N*N+N*7: BuildPiece (hex, piece type: peasant/spearman/baron/knight/tower/strong_tower/farm)

Invalid actions are masked out. EndTurn is always valid (prevents all-zeros mask crash).

### Observation Space

Flat vector (~120 floats) encoding: global state (turn, ownership %), agent summary (provinces, money, income, unit counts), opponent summary, per-province details (money, income, hex count, frontline hexes). Pluggable via `ObservationEncoder` interface.

### Reward

- Win: +1.0
- Loss: -1.0
- Truncation (max turns): -0.5
- Per-step shaping (optional): `shaping_weight * delta_ownership_pct`
- Invalid/failed action: -0.01 penalty

### Game Integration

- `EntityType.AI_ML` added to `core/enums.py`, included in `is_ai()`.
- `AIManager` in `ai/ai_manager.py` lazily loads `MlAI` when entity type is `AI_ML`.
- ML env replaces the human player entity and runs opponent AIs internally via `ai_manager.process_ai_turns()`.

## Key Design Decisions

### Multi-step environment
Each `step()` is one atomic action. The agent takes multiple actions per turn (move units, build pieces) then explicitly chooses EndTurn to pass control to opponents. This maps naturally to PPO's sequential decision-making.

### Fixed action space across levels
Different levels have different hex counts. The env scans all configured levels at init to find the max hex count and uses that for a fixed action space. Smaller levels simply have unused action indices masked as invalid.

### History/undo disabled during training
`UndoManager` and `HistoryManager` serialize the full game state on every event for undo/replay support. This consumed ~50% of per-step time. The env removes both as event listeners in `_init_game()` since training doesn't need undo. This brought 500-step runtime from 11.7s to 3.7s (3.2x speedup).

### Verbose suppression
Game engine prints AI turn info to stdout. The env defaults to `verbose=False` and redirects stdout to `/dev/null` during opponent turns.

### PyTorch distribution validation disabled
With large action spaces (23K+), float32 softmax rounding violates PyTorch's strict Simplex constraint. `train.py` calls `torch.distributions.Distribution.set_default_validate_args(False)`.

## Performance Profile (post-optimization, 500 steps)

| Component | Time | Notes |
|---|---|---|
| Opponent AI (balancer) | ~2.5s | Decision-making + command execution |
| MoveZoneManager.update | ~2.1s | Wave propagation for movement zones |
| Province._propagate | ~1.6s | Flood-fill (uses deque, was list.pop(0)) |
| Action mask computation | ~0.5s | Iterates ready units + build options |
| **Total** | **~3.7s** | ~135 steps/sec single-env |

### Optimizations applied
- Switched `WaveWorker.propagation_list` from `list` (O(n) pop) to `deque` (O(1) popleft)
- Moved dict/set literals to class-level constants in `core_utils.py` and `ruleset.py`
- Removed history/undo event listeners during training

### Further optimization opportunities (not yet implemented)
- Remove redundant distance-check filter in `MoveZoneManager.update()` (lines 107-122)
- Track dirty hexes instead of resetting all hex flags on every `update()` call
- Return `Province._hexes` directly instead of copying on every `get_hexes()` call
- Cython/Numba for hot loops (`move_zone_manager.condition`, `get_defense_value_hex`)

## Training Tips

### Estimating runtime
At ~36 FPS (4 envs, pre-optimization) or ~100+ FPS (post-optimization):
- 100K timesteps: ~15-30 min
- 1M timesteps: ~2.5-8 hours
Actual speed depends on map size and opponent AI complexity.

### Difficulty progression
`--difficulty campaign` (default) uses the game's built-in progression:

| Levels | Difficulty |
|---|---|
| 0-11 | Easy |
| 12-23 | Average |
| 24-59 | Hard |
| 60-119 | Expert |
| 120+ | Balancer |

### TensorBoard metrics
Key tags to monitor:
- `rollout/ep_rew_mean` -- average episode reward (is the agent improving?)
- `rollout/ep_len_mean` -- average episode length
- `train/entropy_loss` -- exploration level (more negative = more random)
- `train/explained_variance` -- value function accuracy (closer to 1 = better)

Requires `Monitor` wrapper (already added in `make_env`).

Note: `rollout/ep_rew_mean` and `rollout/ep_len_mean` come from **training** episodes completing during data collection (via the `Monitor` wrapper), not from the eval callback. The eval callback logs under `eval/mean_reward` and `eval/mean_ep_length`.

### Evaluation callback

`MaskableEvalCallback` periodically pauses training to run the current policy on a separate set of eval environments. It plays `eval_episodes` full games deterministically, logs mean reward/length, and saves the best model.

**The eval hang problem**: with an untrained deterministic policy, eval episodes can run for hundreds of thousands of steps — the agent dithers without making progress, and games always run to the turn limit. With a single eval env, this could take hours.

**Mitigations implemented** (all configurable via CLI):

| Setting | Default | CLI flag | Purpose |
|---|---|---|---|
| `eval_max_turns` | 50 | `--eval-max-turns` | Separate turn limit for eval (vs 500 for training) |
| `eval_max_steps` | 5000 | `--eval-max-steps` | Hard cap on `step()` calls per eval episode |
| `n_eval_envs` | 5 | `--n-eval-envs` | Parallel eval environments |
| `no_eval` | false | `--no-eval` | Disable eval entirely (useful for short test runs) |

Eval envs are built by `make_eval_env()` in `train.py`, which passes the tighter limits to `AntiyoyEnv`. The `max_steps` parameter in `AntiyoyEnv` truncates the episode after N total `step()` calls regardless of turn count, providing a hard bound on eval time even when an episode never finishes a turn.

**Bug fix — `max_steps` bypass**: the original `max_steps` check was at the bottom of `step()`, after two early-return paths (invalid action decode → `None`, failed command execution). An untrained policy producing mostly invalid actions would hit these early returns on every step, incrementing `_step_count` but never reaching the truncation check. Episodes ran to 30,000-60,000+ steps despite a 5,000 limit. Fixed by moving the `max_steps` check to the top of `step()`, before any early returns.

Worst case with defaults: 5 episodes x 5000 steps split across 5 workers = sub-second eval rounds.

### Training diagnostics

`DiagnosticsCallback` in `train.py` logs timestamps at every phase boundary:

```
[20:12:00] ROLLOUT 5 START (collecting 16384 steps)
[20:12:06] ROLLOUT 5 END (6.3s)  total_timesteps=81920  — gradient update next
[20:12:16] ROLLOUT 6 START (collecting 16384 steps)
```

- Gap between ROLLOUT END and next ROLLOUT START = gradient update time (~1-10s depending on batch_size/n_epochs).
- `TimedEvalCallback` wraps `MaskableEvalCallback` with `EVAL START`/`EVAL END` timestamps and duration.
- Eval envs have `log_progress=True`, printing step counts, turn counts, and EndTurn/opponent timing from each subprocess every 500 steps. Useful for diagnosing whether eval is progressing slowly vs truly stuck.

### Gradient update tuning

With `n_steps=2048`, `n_envs=8`, `batch_size=64`, `n_epochs=10`: each gradient update does `10 * (16384/64) = 2560` mini-batch steps, taking ~10 seconds. Increasing `batch_size` to 256 and reducing `n_epochs` to 5 would cut this to ~320 steps (~1-2s). High `clip_fraction` (>0.3) indicates the policy changes too much per update — fewer epochs can improve stability.

### Playing against the trained model (web UI)

The campaign AI selector dropdown includes "ML Model" as an option alongside difficulty levels. When selected:

1. `_apply_entity_difficulties()` in `web/app.py` swaps the entity's type from `AI_BALANCER` to `AI_ML`
2. `AIManager.get_ai_for_entity()` sees `EntityType.AI_ML` and returns the lazy-loaded `MlAI`
3. `MlAI` loads the model from `ml_models/best/best_model.zip` (default path)
4. A validation check at game init verifies the model file exists before starting

**Action space mismatch fix**: `MlAI` derives the hex count N from the loaded model's `action_space.n` (via the formula `1 + N^2 + N*7`), not from the live game's hex count. During training, the env uses the *max* hex count across all configured levels for a fixed action space. If `MlAI` used the current game's hex count instead, the action mask size would mismatch the model's expected action space, causing a silent exception in `process_ai_turn()` and a stalled game. Actions for non-existent hex indices are safely masked as invalid by `ActionMapper`.

### Resume training
Not yet implemented. Each run starts fresh. To add: load model with `algo_cls.load(path, env=env)` and continue `.learn()`. Action/observation space must match between runs.

### Apple Silicon (M4 Mac)
PyTorch MPS (Metal GPU) is available natively but **hurts performance** for this workload. With small MLP policies, CPU-to-GPU transfer overhead on MPS outweighs compute gains. In testing, MPS dropped training FPS from ~2128 to ~616-871. The bottleneck is CPU-bound game engine code (province flood-fill, move zone propagation), not neural network inference. The default device is CPU; use `--device mps` to override if experimenting with larger networks.

MPS is not accessible from Docker — Docker on macOS runs a Linux VM without Metal drivers.

### Training session logging & energy tracking

Every training run (whether completed or interrupted with Ctrl+C) is logged to `training_sessions.json` in the project root — a pretty-printed JSON array with one entry per session. This tracks model identity, hyperparameters, hardware, resource utilization, energy estimates, and the archived model path.

#### Model registry

`ml/model_registry.yaml` maintains a list of named approaches. Each entry has a key, name, and human-readable description. The active approach is set via `--model-details <key>` (default: `first_approach`, configurable in `TrainConfig.model_details`). The key and description are written into the session log.

#### Resource monitoring

`ResourceMonitor` in `ml/training_logger.py` runs a background daemon thread that samples every 5 seconds:
- CPU % and RAM usage via `psutil`
- NVIDIA GPU utilization % and power draw (watts) via `pynvml` when available

The log records avg/peak for all metrics plus sample count.

#### Energy estimation

Two backends, selected automatically:

| Platform | Backend | What it measures |
|---|---|---|
| Linux (NVIDIA) | CodeCarbon | Real power via Intel RAPL (CPU) + pynvml (GPU) → kWh + CO2 |
| macOS | TDP estimate | `chip_TDP × avg_cpu_util% × hours / 1000` |

CodeCarbon is skipped on macOS because it tries `sudo powermetrics` which prompts for a password. The TDP fallback uses `sysctl -n machdep.cpu.brand_string` to identify the chip (M1 through M4, all tiers) and look up its package TDP. The `energy_source` field in the log always records which method was used (e.g. `"codecarbon"` or `"tdp_estimate (45W)"`).

#### Best model archival

After each session, `TrainingLogger._archive_best_model()` copies `ml_models/best/best_model.zip` to `final_models/{model_details}_{timestamp}.zip` with collision avoidance. The path is recorded in the session log. If no best model exists (e.g. eval was disabled or no eval completed), the field is null.

#### Ctrl+C handling

`train()` wraps `model.learn()` in `try/except KeyboardInterrupt/finally`. On interrupt:
1. The model is saved to `ml_models/antiyoy_final`
2. The training logger fires (writes log entry, archives best model, prints summary)
3. `SubprocVecEnv.close()` is wrapped in try/except for `EOFError`/`BrokenPipeError` — Ctrl+C kills child processes before the parent can shut them down cleanly, and the recv() on an already-dead pipe would otherwise crash

#### Console summary

After every session, a summary block is printed:

```
========================================================
  Training Session Summary
========================================================
  Model details:   first_approach
  Algorithm:       MaskablePPO
  Status:          INTERRUPTED (109,936 / 10,000,000 timesteps)
  Duration:        1m 03s

  CPU avg/peak:    23.6% / 29.9%
  RAM avg/peak:    23656.9 MB / 23923.3 MB
  GPU util:        N/A
  GPU power:       N/A

  Energy:          0.0001 kWh  (tdp_estimate (45W))

  Archived model:  final_models/first_approach_20260327_035810.zip

  Log:             training_sessions.json
========================================================
```

## Training run history

#### "First Win" — first working model (success)

Our first model that reliably wins games, archived as `final_models/first_approach_20260327_040810.zip` (`display_name: "First Win"`). Training setup:

- **Algorithm**: MaskablePPO, MlpPolicy
- **Levels**: 0-2 (campaign difficulty = easy), 8 parallel envs on CPU
- **Action space**: auto-detected from the training levels (max 66 hexes → action space of 4,819)
- **Hyperparameters**: `lr=3e-4`, `n_steps=2048`, `batch_size=256`, `n_epochs=5`, `gamma=0.99`, `gae_lambda=0.95`, `clip_range=0.2`, `ent_coef=0.01`, `vf_coef=0.5`, `shaping_weight=0.1`
- **Budget**: 10M timesteps (completed: 10,010,624)
- **Duration**: ~1h 37m (5,836s) on an Apple M4 Pro at roughly 1,700 FPS

Because the action space was sized to levels 0-2, this model can only play maps with ≤66 hexes.

#### Expanded action space retrain (failed)

To lift the map-size restriction, we retrained with the *same logic* but an expanded, fixed action space (`action_space_hexes=384`, the max across all campaign levels → action space of 150,145) on levels 0-10, targeting 100M timesteps.

- **Duration**: ~20h 5m (72,293s), interrupted at 16,007,168 / 100,000,000 timesteps
- **Result**: dead in the water — the model never won a single game

**Why it failed**: the run collapsed into a local minimum with no path out.

- `eval/mean_reward` stayed pinned at ~-0.495 (every eval episode truncated; zero wins)
- `train/entropy_loss` collapsed from ~-3.0 early on to ~-1.4 (exploration died)
- `value_loss` and `policy_gradient_loss` fell to near zero — the value function had simply learned to predict -0.5 everywhere, leaving no learning signal
- The 31x larger action space (150,145 vs 4,819) dropped throughput from ~1,700 FPS to ~220 FPS, so 20 hours only bought ~16M steps
- The unchanged `ent_coef=0.01` and tiny `shaping_weight=0.1` gave nowhere near enough exploration pressure or intermediate signal to escape the truncation trap in such a large action space on harder/larger maps

Takeaway: expanding the action space and the level range simultaneously, without also increasing exploration and reward shaping, produced a model with no wins after 20 hours. See the action-space-and-reward-strategy plan for the follow-up approach (train small first, then expand via weight surgery, plus reward tuning).

---

## Phase: Reward rework and manual curriculum

Following the failed retrain above, the reward function was reworked and a manual, level-by-level curriculum workflow was added.

### Reworked reward function (`ml/reward.py`)

The reward is a sparse terminal signal with **self-relative** per-step shaping — every shaping term is measured against the agent's *own previous state*, never against opponents. This is near potential-based: the per-step deltas telescope to `final - initial` over an episode, so total shaping is bounded, doesn't distort the optimal policy, is low variance, and still captures opponent pressure indirectly (losing hexes/income yields a negative delta).

Two orthogonal shaping signals:

| Signal | Formula | Notes |
|---|---|---|
| Territory | `territory_weight * (pct_t - pct_{t-1}) / 100` | `pct = agent_hexes / total_hexes`. Map-normalised to [0,100]. Opponents expanding into neutral land does not move it — only gaining/losing your own hexes does. |
| Economy | `income_weight * (economy_t - economy_{t-1})` | `economy = income - hex_count = 4*farms - trees`. The base +1/hex cancels (no double-counting with territory); unit upkeep excluded (military not punished); per-object values are constants so the signal is map-size invariant. |

Terminal reward overrides shaping:

| Outcome | Reward |
|---|---|
| Win | `+1.0` |
| Loss (opponent wins) | `-1.0` |
| Truncation (max turns/steps, no winner) | `-1.0` (configurable) |

Truncation is penalised as heavily as a loss so stalling to run out the clock is no better than losing — this removes the stall-to-truncation local minimum that killed the previous run.

Defaults: `territory_weight=0.5`, `income_weight=0.004` (a farm ≈ `+0.016`, one hex on the level-0 map ≈ `+0.025`), both an order of magnitude below the `±1.0` terminal so shaping guides without drowning the win/loss signal. `income_scale` and reward clipping were considered and dropped — `scale` is redundant with `income_weight`, and the worst realistic single-step swing (~0.15) is already well under the terminal.

Design decisions that were rejected: opponent-differential shaping (comparing territory/economy against other players) was rejected as noisy — opponent metrics swing wildly turn to turn, and early game a fast-starting opponent makes the differential a demoralising moving target.

### Configurable penalties and success info

- `AntiyoyEnv` now takes `invalid_action_penalty` (default `0.0`): the old hardcoded `-0.01` for invalid/failed actions is gone, since invalid actions are already wasted steps.
- `env._make_info()` now emits `info["is_success"]` (= agent won), which sb3's eval collects into its success buffer to compute win rate.

### Manual curriculum workflow (win-rate early stop + resume)

Rather than a single long run or an automated driver, training now proceeds level by level under manual control. Two `ml/train.py` features enable this:

- **`--early-stop`**: a `WinRateEarlyStop` eval callback logs `eval/win_rate` (from `is_success`) and stops training once the win rate stays at/above `--win-rate-threshold` (default `0.6`) for `--early-stop-patience` consecutive evals (default `3`).
- **`--resume PATH`**: loads a saved checkpoint, re-attaches it to the (possibly different) `--levels`, and continues with `reset_num_timesteps=False`. Resume requires a matching `--action-space-hexes`; the fixed default of 384 (max across all campaign levels) guarantees this across every level, so a model trained on small maps can be continued on any larger level without reshaping the action space.

Typical flow:

```bash
# 1. Learn level 0 until it reliably wins
python -m ml.train --levels 0 --early-stop

# 2. Continue the same model on level 1
python -m ml.train --resume ml_models/antiyoy_final --levels 1 --early-stop

# 3. Consolidate across levels seen so far
python -m ml.train --resume ml_models/antiyoy_final --levels 0 1 2 --early-stop
```

New CLI flags: `--territory-weight`, `--income-weight`, `--truncation-penalty`, `--invalid-action-penalty`, `--ent-coef`, `--resume`, `--early-stop`, `--win-rate-threshold`, `--early-stop-patience` (the old `--shaping-weight` was removed). `TrainingLogger` now records `territory_weight`/`income_weight` in place of `shaping_weight`.

An automated curriculum driver (looping over levels with periodic consolidation) is intentionally deferred until this manual flow is proven.

---

## Phase: Curriculum progress and the level-5 wall

### Levels 0–4: solved

Using the reworked reward + resume-from-checkpoint chain, the model was trained level by level and **successfully beat levels 0 through 4**, with each solved level promoted to its own checkpoint (`ml_models/level_00.zip` … `level_04.zip`) and win stats recorded to `model_win_stats.csv`. The wins are slow and defensive (128 / 185 / 74 / 325 / 360 turns vs the built-in balancer AI's 83 / 43 / 43 / 77 / 98) — the agent turtles into heavy defense and grinds the game out rather than closing quickly.

Note on "solved": for levels ~3+ the training/eval turn cap (200) is shorter than the agent needs to actually win (its recorded wins take 325–360 turns), so `eval/win_rate` stayed ~0 during training and the levels were **promoted on budget-exhaustion, not early-stop**. The recorded wins come from the separate, more generous 400-turn stat playthrough (`--stat-max-turns`). Combined with `gamma=0.99` over ~4,000-step episodes (~20 agent-steps/turn), the terminal win reward is discounted to ≈0 by the time it reaches early-game decisions (`0.99^4000 ≈ 0`), so the opening is learned almost entirely from the dense shaping, not from reaching a win.

### Level 5: the wall (aggressive-opening problem)

Level 5 is where the chain stalled. It's a **large 100-hex map**: `red` (balancer AI, *easy*) starts dominant (42 hexes — 1 city, 9 farms, 3 towers, but choked by 27 tree hexes), the agent (`aqua`) starts tiny (6 hexes, 10 gold), and there are **52 neutral gray hexes** to grab. It is winnable and not hard *for a human*, but requires **quick expansion into the neutral land in the opening turns** plus economy build-up to snowball past the tree-choked red — exactly the behaviour the current turtle policy does not have.

The agent could not learn it: across a full 1M-step run (and a subsequent 2M-step run with modified params), `rollout/success_rate` and `eval/win_rate` stayed pinned at **0** — the agent never won level 5 even once, so there was no win signal to reinforce. It either stalls to the turn cap or loses. The core difficulty is **strategy discovery in the opening**: if the agent doesn't grab the right gray hexes in roughly the first ~20 turns it's stuck in a long, slow farming game it can't win, and simply giving it more turns reinforces slow play rather than teaching the fast opening. (The built-in balancer AIs *also* lose level 5 at every difficulty, so there's no reference win to calibrate a turn cap against — `_turn_cap_for_level` falls back to the 200 floor.)

Level 6 is genuinely very hard and is **skipped for now**.

### Current experiment params (level 5, resumed from `level_04`)

The changes target the *shaping* (what's actually visible to early-game decisions) and *exploration*, rather than the terminal reward or turn budget:

| Param | Curriculum default | Level-5 experiment | Rationale |
|---|---|---|---|
| `gamma` | `0.99` | `0.97` | More myopic → weights immediate territory/economy shaping over near-invisible distant terminal reward, sharpening the "expand now" incentive. |
| `territory_weight` | `0.5` | `1.0` | Make land-grabbing the loudest, least-discounted signal. |
| `truncation_penalty` | `-1.0` | `0.0` | On a level it can't yet win, a flat −1 gives no gradient; crediting accumulated expansion lets it climb toward wins. (Trade-off: risks a comfortable no-win "expand-and-survive" equilibrium.) |
| `ent_coef` | `0.02` | `0.05` | More exploration to break the confident turtle prior inherited from levels 0–4 and discover the aggressive opening. |
| `timesteps` | `1M`/level | `2M`(+more) | More cycles to find and reinforce a win. |
| turn cap | 200 | 200 (unchanged) | The bottleneck is discovery, not horizon — more turns would reinforce slow play. |

`gamma` was wired through as a CLI passthrough (`ml.train` and `tools.curriculum_train`) and, like `ent_coef`, is re-applied on `--resume` so it isn't silently restored from the checkpoint. These are treated as an **experiment override, not a new default** — objective knobs (`gamma`, reward weights, truncation) should stay fixed across the curriculum, while budget/capacity knobs (turn/step caps, timesteps, exploration) may scale with level complexity.

**Status / signal to watch**: reward is trending upward but `success_rate` is still 0. The metric that indicates the fix is working is `rollout/success_rate` lifting off zero (ideally with `ep_len_mean` dropping = learning to close quickly). If more cycles still yield zero wins, the bottleneck is exploration/discovery, not budget — next levers would be a higher `ent_coef` or restoring a mild negative truncation so "survive forever" stops being free.

### Level 5 failed again

The model never learned how to win level 5.

### Diagnosis: the end-turn / opponent-growth exploit

A behaviour diagnostic on the stalled level-5 runs showed the agent barely ever *ended its turn* — it spammed thousands of move commands per turn and cycled the same actions. Root cause: with `opponent_weight > 0`, the opponent-decline term penalised **red's autonomous expansion on red's own turn** (which the agent can't control), and that penalty was folded into the *end-turn step's* reward (shaping was computed *after* `_advance_opponents`). So the agent learned the degenerate optimum of **never ending its turn** to avoid ever paying for red's growth.

### Fixes applied (reward/step mechanics)

Three orthogonal fixes, all opt-in via CLI (defaults unchanged so prior behaviour is preserved):

1. **Shaping is computed on the agent's own turn only.** In `env.step`, on an end-turn we now snapshot the shaping delta *before* `_advance_opponents`, then call `reward_calc.sync_baseline(...)` afterwards to absorb the opponents' turn deltas into the baseline without emitting reward. The opponent's autonomous land-grab is therefore no longer attributed to the agent — it only shows up through the terminal loss if red actually reaches 80%. (`RewardCalculator.sync_baseline` is a no-op on the base class; `DefaultRewardCalculator` re-snaps `_prev_agent_hexes/_prev_opp_hexes/_prev_economy`.)
2. **Per-step time cost** (`--time-cost`, default `0.0`): a small constant subtracted from *every* step reward (including invalid/failed actions). Makes long games and per-turn action churn cost something, nudging toward decisive play. Try `~0.002`.
3. **Invalid-action penalty** (`--invalid-action-penalty`, already present, default `0.0`): set `> 0` (e.g. `0.01`) so spamming illegal/failed actions is penalised rather than free.

### Handicap: `noop` opponents (curriculum rung 0)

To get the agent its **first** level-5 win (so there's a win signal to reinforce), added a passive-opponent mode instead of modifying the map (rejected: high effort, low long-term value) or taxing the opponent's money (rejected: fiddly to make it actually starve red given its income of 48 — income timing is inside the AI turn).

`--difficulty noop` makes every opponent **end its turn immediately with no moves** (`env._advance_opponents_noop` submits an `EndTurnCommand` per opponent via the normal executor path — income still accrues, but red never builds or expands). On level 5 this freezes red at its starting 42 hexes: the agent can grab the 52 neutral hexes freely and then grind red's static towers, which is very likely winnable → a real win signal.

This is deliberately the **first rung of a difficulty ladder** the curriculum can climb: `noop → easy → average → hard`, resuming the checkpoint at each rung. All knobs are passthrough in `tools/curriculum_train.py` (`--difficulty`, `--time-cost`, `--territory-weight`, `--opponent-weight`, `--income-weight`, `--truncation-penalty`, `--invalid-action-penalty`).

Example (bootstrap level 5 against a passive opponent, resuming level 4):

```
python -m ml.train --levels 5 --difficulty noop --resume ml_models/level_04.zip \
  --time-cost 0.002 --invalid-action-penalty 0.01 --opponent-weight 1.0 \
  --early-stop --ent-coef 0.05 --gamma 0.97 --timesteps 2000000 \
  --max-turns 200 --eval-max-turns 200
```

### `noop` bootstrap worked — then two false starts on `easy`

The `noop` run **early-stopped as a win** (red frozen at 42 hexes; the agent expands and grinds it down). That checkpoint was promoted to `ml_models/level_05_noop.zip` — the first level-5 win the model ever produced. But resuming it against real `easy` failed twice, each failure teaching something:

1. **`time_cost=0.002` was ~10× too large.** Over a ~5,000-step game it sums to ~−10, dwarfing the ±1 terminal and the ~0.1-scale territory shaping (`0.5/384 ≈ 0.0013` per hex). Eval `mean_reward` of −10.9 decomposed as `4952 steps × 0.002 (−9.9)` + `−1` truncation — i.e. ~91% of the reward *was* the time cost, so the dominant gradient became "make the episode shorter," not "win." A per-step cost must be sized so a **whole game** costs O(1): use `~0.0002` (or `0`). The churn it was meant to fight is already addressed structurally by the shaping-before-opponents fix.
2. **With `time_cost=0`, it reverted to stalling.** Reward flatlined at −0.994 (just the −1 truncation) while `ep_len_mean` exploded to ~10k steps (400 turns × ~25 steps) — the agent wandered to the turn cap with **net-zero shaping** (no expansion). Removing the cost removed the only pressure against free within-turn wandering. `fps` collapsed 100 → 18.

Both confirmed the **`noop → easy` jump is a cliff**: the passive-win policy learned "expand into uncontested land," which has no answer to a red that contests the opening, and with no reachable win there's no gradient to climb.

> **Measurement caveat:** across a reward-function change (adding `time_cost`, changing `gamma`), eval `mean_reward` is on a *new scale* and is not comparable to earlier runs. Judge "did it forget / regress" by **behaviour** and `success_rate`, not raw reward.

### On resume and "forgetting"

`model.load()` restores the full policy **and** value nets (and optimizer state), so at timestep 0 the resumed model plays exactly like the checkpoint — nothing is wiped. But nothing *protects* those weights either; several forces push the policy off them fast: (a) a high `ent_coef` literally rewards a more random policy (de-commits the learned behaviour), (b) the **critic is stale** for the new setting → wrong/noisy advantages → large destabilising early updates, (c) **distribution shift** puts the old policy in states it never saw. Levers to retain more: lower `ent_coef` on resume, lower LR, cap update size with `target_kl`, and — most importantly — **make each curriculum step small** so the distribution shift is small.

### Handicap v2: opponent **income tax** (rejected the delay; the money-tax works)

A *turn-delay* handicap (opponents idle for the first N turns, then activate) was tried and rejected: the opponent banks N turns of unspent income and dumps a huge army the instant it wakes, defeating the purpose.

Instead, `EconomicsManager` now supports an **income tax**: at turn-start income application it withholds a fraction of each opponent's *positive income* (consumption untouched, so a starved opponent can even go upkeep-negative). It's inert by default (`income_tax_rate=0.0`) so real games are unaffected; the ML env installs the rate per episode, **exempting the agent's colour**. Exposed as `--opponent-income-tax` (env: `opponent_income_tax`).

Effectiveness on level 5 (red income 48, unit cost ~10), measured with an idle agent — red hexes reached after N turns:

| tax | @5 turns | @10 | @15 | effect |
|---|---|---|---|---|
| 0.0 | 80 | 80 | 80 | full strength (wins ~turn 5 vs idle agent) |
| 0.4 | 80 | 80 | 80 | **no meaningful handicap** |
| 0.8 | 53 | 68 | 80 | clearly slowed |
| 0.99 | 43 | 43 | 43 | frozen (≈ `noop`) |

Because red's income is ~5× a unit's cost, it takes a **big** tax to bite: the effective band is ~`0.8–0.99`; anything ≤ ~0.7 is effectively full-strength red. So difficulty rungs should cluster in the high band, not spread linearly to 0.

### Approach: **mixed-difficulty (domain-randomised) tax**, not a sequential ladder

Rather than annealing the tax across sequential resumes (which triggers the forgetting above at every step), train against a **variety of taxed opponents at once**. `--opponent-income-tax` accepts several values and each parallel env is **pinned to one** (stratified, in the env factory via `tax_for_rank`), so *every* rollout batch spans the full spread. The agent always "tastes victory" on the high-tax envs (persistent win signal → can't drift away from winning) while the low-tax envs pressure it to generalise. This dissolves the catastrophic-forgetting problem because all difficulties are permanently in the training distribution.

Design choices:
- **Stratified per-env, not per-episode.** Episodes run thousands of steps, so a rollout contains only a handful of episodes; per-episode sampling could miss whole difficulty bands in a batch. Pinning env `i` to `tax[i]` guarantees coverage every update.
- **Include `0.0` (real `easy`) in the set.** The deployment target is then *in-distribution* — no separate "anneal to 0" step; when the agent wins the `0.0` envs it has genuinely solved level 5.
- **No difficulty signal in the observation** (agent can't see the tax). We want one robust difficulty-agnostic policy; the cost is a noisier critic (identical openings → different outcomes → lower `explained_variance`), which PPO tolerates.
- Eval envs stratify 0-based across the same set (`--n-eval-envs` ≥ number of taxes to cover all), so `eval/win_rate` is a **blended** competence metric across the spread.

Current experiment (resumes the `noop` win; `time_cost` recalibrated; `ent_coef` lowered for retention):

```
python -m ml.train --levels 5 --difficulty easy \
  --opponent-income-tax 0.99 0.95 0.9 0.85 0.8 0.7 0.5 0.0 \
  --resume ml_models/level_05_noop.zip --model-details max_map_action_space \
  --n-envs 8 --n-eval-envs 8 \
  --time-cost 0.0002 --invalid-action-penalty 0.01 --opponent-weight 1.0 \
  --early-stop --ent-coef 0.03 --gamma 0.97 --timesteps 3000000 \
  --max-turns 400 --eval-max-turns 400
```

### Replay-based behaviour analysis (the tax-mixed model)

After the mixed-difficulty run "succeeded," we generated `.replay` files and watched them
back rather than trusting stats alone. Tooling added for this:

- `AntiyoyEnv(record_replay=True)` keeps the `history_manager` attached (it's stripped
  during training/eval for speed) so per-event snapshots can be serialised with
  `save_replay` at game end.
- `tools/model_replay.py` plays the model on a level/tax and writes qualifying games to
  `replays/`. `--want {any,win,loss}` + `--min-own` filter which games qualify;
  `--select {first,min-turns,max-turns,min-max,all}` picks which qualifying games to keep.

Per-tax outcomes we captured on level 5 (`antiyoy_final.zip`), which quantify the two
failure modes:

| tax | representative games | read |
|---|---|---|
| 0.90 | 10 wins, 49–120 turns | **2.4× turn spread on a trivial opponent** → no consistent aggressive opening line |
| 0.85 | mixed; loss @27t/17% own | loses when it can't out-expand a slightly stronger red |
| 0.80 | loss @14t/13%, win @164t/80% | either dies in the opening or grinds a marathon economic win |
| 0.75 | losses 10–18t/13–20%, wins @211 & 254t | **no middle ground**: fast death or a very long turtle win |

### Diagnosis: both players win by *stumbling*, not by strategy

Watching the replays, our agent plays at roughly the level of the built-in **`easy`** AI —
the only reason `easy` wins more often is that it **starts with more funds**, not better
play. In quality both are equally poor: the game's outcome is essentially the product of
two agents shuffling units around semi-randomly until one happens to cross 80%.

Concrete behavioural defects observed in our agent (the actionable list to attack next):

1. **Doesn't clear trees aggressively.** Trees are left standing, spread/regrow, and
   quietly drain province income — the economy bleeds instead of compounding. There is no
   incentive in the current reward tying unit-moves to tree removal.
2. **Builds strong units far too early, then wastes them.** It springs for expensive units
   up front but never uses them to **attack towers / push into enemy territory** — they
   wander the map like any cheap unit. Strength is bought but not converted into
   territory, so the up-front economic hit buys nothing.
3. **Only occasional farms.** Economy growth is sporadic rather than a deliberate
   compounding plan, so it can't fund sustained expansion (matches the "marathon or bust"
   split above).
4. **Only occasional towers.** Defensive structure is incidental, not placed to hold or
   contest key hexes.
5. **Movement is effectively random.** Units are moved to clear a tree, grab a neutral
   hex, grab an enemy hex, or not moved at all — with no coherent objective per unit or per
   turn. The "esoteric" look is exactly this: locally-valid actions with no strategy
   stringing them together.

**Implication for reward/curriculum design.** The current shaping rewards *net territory
and economy state*, which a random walk can drift into given enough turns — so a
random-ish policy still climbs reward and "wins" by attrition. That's why reward trends up
while play quality doesn't. The signal is too coarse to distinguish *deliberate* from
*accidental* progress. Directions this analysis points to (not yet implemented):

- Reward **tree removal** directly (income-preserving actions), so the economy stops
  bleeding.
- Reward **using strength**: credit for tower kills / capturing *defended* hexes, not just
  any hex, so buying strong units only pays off when they're actually pushed into the
  enemy.
- Tie the up-front cost of strong units to a payoff horizon (`gamma`/shaping) so early
  over-investment without use is discouraged.
- Consider **per-unit / per-turn objective shaping** rather than only board-state deltas,
  to penalise net-zero wandering that the current potential-based shaping treats as free.
