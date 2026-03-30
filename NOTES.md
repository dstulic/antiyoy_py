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

## Dependencies

```
gymnasium
stable-baselines3
sb3-contrib
tensorboard
torch (installed as SB3 dependency)
psutil
codecarbon (optional — Linux only, skipped on macOS)
pyyaml
```

## Files Modified from Base Game

- `core/enums.py` -- added `EntityType.AI_ML`
- `ai/ai_manager.py` -- added `MlAI` lazy loading and `AI_ML` entity handling
- `core/core_utils.py` -- moved dicts to module-level constants
- `core/ruleset.py` -- moved dicts to class-level constants
- `core/province.py` -- switched WaveWorker to deque
- `web/app.py` -- `_apply_entity_difficulties` swaps entity type to `AI_ML` when "ml" selected; model-existence validation in `_assert_all_ai_difficulties_set`
- `web/static/js/campaign.js` -- added "ML Model" option to AI selector dropdown
- `ml/ml_ai.py` -- derives `n_hexes` from loaded model's action space to avoid mask mismatch
- `ml/env.py` -- added `max_steps` truncation (moved check to top of `step()`), `log_progress` diagnostic prints
- `ml/train.py` -- `DiagnosticsCallback`, `TimedEvalCallback`, `make_eval_env`, parallel eval, device override, `TrainingLogger` integration, Ctrl+C handling with graceful SubprocVecEnv cleanup
- `ml/config.py` -- added `eval_max_turns`, `eval_max_steps`, `n_eval_envs`, `no_eval`, `device_override`, `model_details`
- `ml/training_logger.py` -- new: `ResourceMonitor`, `TrainingLogger`, CodeCarbon wrapper, TDP fallback, model archival, session log writing
- `ml/model_registry.yaml` -- new: named approach definitions (key, name, description)
- `training_sessions.json` -- new: append-only session log (pretty-printed JSON array)
- `requirements.txt` -- added ML dependencies, `psutil`, `codecarbon`, `pyyaml`
- `tests/test_enums.py` -- updated for `AI_ML`
- `tests/test_rng_state.py` -- fixed test for duplicate level codes
