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
| `ml/config.py` | `TrainConfig` dataclass with all hyperparameters |
| `ml/train.py` | Training entry point, sets up SubprocVecEnv, MaskablePPO, callbacks |
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

### Resume training
Not yet implemented. Each run starts fresh. To add: load model with `algo_cls.load(path, env=env)` and continue `.learn()`. Action/observation space must match between runs.

### Apple Silicon (M4 Mac)
PyTorch MPS (Metal GPU) is not accessible from Docker -- Docker on macOS runs a Linux VM without Metal drivers. Run training natively with a venv for full MPS acceleration. The bottleneck is CPU-bound game engine code, not GPU.

## Dependencies

```
gymnasium
stable-baselines3
sb3-contrib
tensorboard
torch (installed as SB3 dependency)
```

## Files Modified from Base Game

- `core/enums.py` -- added `EntityType.AI_ML`
- `ai/ai_manager.py` -- added `MlAI` lazy loading and `AI_ML` entity handling
- `core/core_utils.py` -- moved dicts to module-level constants
- `core/ruleset.py` -- moved dicts to class-level constants
- `core/province.py` -- switched WaveWorker to deque
- `requirements.txt` -- added ML dependencies
- `tests/test_enums.py` -- updated for `AI_ML`
- `tests/test_rng_state.py` -- fixed test for duplicate level codes
