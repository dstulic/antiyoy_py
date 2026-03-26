# ML Development Notes

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
