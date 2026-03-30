#!/usr/bin/env python3
"""Training entry-point using stable-baselines3 with action masking.

Usage:
    python -m ml.train
    python -m ml.train --algo MaskablePPO --timesteps 2000000 --levels 0 1 3
    python -m ml.train --difficulty campaign --n-envs 8
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.enums import Difficulty  # noqa: E402
from ml.config import TrainConfig  # noqa: E402


def _parse_args() -> TrainConfig:
    parser = argparse.ArgumentParser(description="Train an ML agent for Antiyoy.")
    parser.add_argument("--algo", type=str, default="MaskablePPO",
                        choices=["MaskablePPO", "MaskableA2C"],
                        help="RL algorithm (default: MaskablePPO)")
    parser.add_argument("--timesteps", type=int, default=1_000_000)
    parser.add_argument("--levels", type=int, nargs="+", default=[0, 1],
                        help="Specific level indices to train on (default: 0 1)")
    parser.add_argument("--level-range", type=int, nargs=2, metavar=("START", "END"),
                        help="Inclusive range of levels, e.g. --level-range 0 10. "
                             "Overrides --levels.")
    parser.add_argument("--difficulty", type=str, default="campaign",
                        choices=["campaign"] + [d.value for d in Difficulty],
                        help="Opponent AI difficulty. 'campaign' (default) "
                             "uses the level-appropriate difficulty.")
    parser.add_argument("--n-envs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--max-turns", type=int, default=500)
    parser.add_argument("--shaping-weight", type=float, default=0.1)
    parser.add_argument("--log-dir", type=str, default="ml_logs")
    parser.add_argument("--model-dir", type=str, default="ml_models")
    parser.add_argument("--device", type=str, default=None,
                        choices=["cpu", "cuda", "mps"],
                        help="Override device selection (default: auto-detect)")
    parser.add_argument("--no-eval", action="store_true",
                        help="Disable evaluation callback (useful for short runs)")
    parser.add_argument("--eval-max-turns", type=int, default=50,
                        help="Max turns per eval episode (default: 50)")
    parser.add_argument("--eval-max-steps", type=int, default=5000,
                        help="Max steps per eval episode (default: 5000)")
    parser.add_argument("--n-eval-envs", type=int, default=5,
                        help="Number of parallel eval environments (default: 4)")
    parser.add_argument("--model-details", type=str, default="first_approach",
                        help="Key into ml/model_registry.yaml describing "
                             "this approach (default: first_approach)")
    args = parser.parse_args()

    difficulty = None if args.difficulty == "campaign" else Difficulty(args.difficulty)
    levels = list(range(args.level_range[0], args.level_range[1] + 1)) if args.level_range else args.levels

    cfg = TrainConfig(
        algorithm=args.algo,
        total_timesteps=args.timesteps,
        level_indices=levels,
        opponent_difficulty=difficulty,
        n_envs=args.n_envs,
        seed=args.seed,
        learning_rate=args.lr,
        max_turns=args.max_turns,
        shaping_weight=args.shaping_weight,
        log_dir=args.log_dir,
        model_dir=args.model_dir,
        device_override=args.device,
        no_eval=args.no_eval,
        eval_max_turns=args.eval_max_turns,
        eval_max_steps=args.eval_max_steps,
        n_eval_envs=args.n_eval_envs,
        model_details=args.model_details,
    )
    return cfg


def make_env(cfg: TrainConfig, rank: int = 0):
    """Return a callable that creates one AntiyoyEnv for training."""
    def _init():
        from ml.env import AntiyoyEnv
        from ml.reward import DefaultRewardCalculator
        from stable_baselines3.common.monitor import Monitor

        env = AntiyoyEnv(
            level_indices=cfg.level_indices,
            opponent_difficulty=cfg.opponent_difficulty,
            max_turns=cfg.max_turns,
            reward_calculator=DefaultRewardCalculator(shaping_weight=cfg.shaping_weight),
        )
        env = Monitor(env)
        env.reset(seed=cfg.seed + rank)
        return env
    return _init


def make_eval_env(cfg: TrainConfig, rank: int = 0):
    """Return a callable that creates one AntiyoyEnv for evaluation,
    using tighter turn/step limits to prevent runaway episodes."""
    def _init():
        from ml.env import AntiyoyEnv
        from ml.reward import DefaultRewardCalculator
        from stable_baselines3.common.monitor import Monitor

        env = AntiyoyEnv(
            level_indices=cfg.level_indices,
            opponent_difficulty=cfg.opponent_difficulty,
            max_turns=cfg.eval_max_turns,
            max_steps=cfg.eval_max_steps,
            reward_calculator=DefaultRewardCalculator(shaping_weight=cfg.shaping_weight),
            # log_progress=True,
        )
        env = Monitor(env)
        env.reset(seed=cfg.seed + rank)
        return env
    return _init


def train(cfg: TrainConfig) -> None:
    import time
    from datetime import datetime

    import torch
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
    from stable_baselines3.common.vec_env import SubprocVecEnv
    from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback

    from ml.training_logger import TrainingLogger

    def _now():
        return datetime.now().strftime("%H:%M:%S")

    class DiagnosticsCallback(BaseCallback):
        """Logs timestamps at every training phase boundary."""

        def __init__(self):
            super().__init__(verbose=0)
            self._rollout_t0 = None
            self._iter = 0

        def _on_training_start(self):
            print(f"[{_now()}] TRAIN_LOOP START", flush=True)

        def _on_rollout_start(self):
            self._iter += 1
            self._rollout_t0 = time.time()
            print(f"[{_now()}] ROLLOUT {self._iter} START "
                  f"(collecting {self.model.n_steps * self.training_env.num_envs} steps)",
                  flush=True)

        def _on_rollout_end(self):
            elapsed = time.time() - self._rollout_t0 if self._rollout_t0 else 0
            print(f"[{_now()}] ROLLOUT {self._iter} END ({elapsed:.1f}s)  "
                  f"total_timesteps={self.num_timesteps}  — gradient update next",
                  flush=True)

        def _on_step(self):
            return True

        def _on_training_end(self):
            print(f"[{_now()}] TRAIN_LOOP END  total_timesteps={self.num_timesteps}",
                  flush=True)

    class TimedEvalCallback(MaskableEvalCallback):
        """MaskableEvalCallback that prints timestamps before/after eval."""

        def _on_step(self) -> bool:
            if self.eval_freq > 0 and self.n_calls % self.eval_freq == 0:
                print(f"[{_now()}] EVAL START at {self.num_timesteps} timesteps "
                      f"({self.n_eval_episodes} episodes, {self.eval_env.num_envs} envs)",
                      flush=True)
                t0 = time.time()
                result = super()._on_step()
                elapsed = time.time() - t0
                print(f"[{_now()}] EVAL END ({elapsed:.1f}s)", flush=True)
                return result
            return True

    # Large discrete action spaces (N^2 + N*7 + 1) cause float32 softmax
    # rounding to violate PyTorch's strict Simplex check.
    torch.distributions.Distribution.set_default_validate_args(False)

    os.makedirs(cfg.model_dir, exist_ok=True)
    os.makedirs(cfg.log_dir, exist_ok=True)
    os.makedirs(cfg.tensorboard_log, exist_ok=True)

    # Vectorised training environments
    env = SubprocVecEnv([make_env(cfg, i) for i in range(cfg.n_envs)])

    eval_env = None
    if not cfg.no_eval:
        eval_env = SubprocVecEnv([
            make_eval_env(cfg, cfg.n_envs + i) for i in range(cfg.n_eval_envs)
        ])

    algo_cls = MaskablePPO
    if cfg.algorithm == "MaskableA2C":
        from sb3_contrib import MaskableA2C
        algo_cls = MaskableA2C

    if cfg.device_override:
        device = cfg.device_override
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    print(f"Using {device} device")

    model_kwargs = dict(
        policy="MlpPolicy",
        env=env,
        learning_rate=cfg.learning_rate,
        gamma=cfg.gamma,
        gae_lambda=cfg.gae_lambda,
        ent_coef=cfg.ent_coef,
        vf_coef=cfg.vf_coef,
        seed=cfg.seed,
        verbose=1,
        tensorboard_log=cfg.tensorboard_log,
        device=device,
    )
    if cfg.algorithm == "MaskablePPO":
        model_kwargs.update(
            n_steps=cfg.n_steps,
            batch_size=cfg.batch_size,
            n_epochs=cfg.n_epochs,
            clip_range=cfg.clip_range,
        )

    model = algo_cls(**model_kwargs)

    callbacks = [
        DiagnosticsCallback(),
        CheckpointCallback(
            save_freq=max(cfg.save_freq // cfg.n_envs, 1),
            save_path=cfg.model_dir,
            name_prefix="antiyoy",
        ),
    ]
    if eval_env is not None:
        callbacks.append(TimedEvalCallback(
            eval_env,
            best_model_save_path=os.path.join(cfg.model_dir, "best"),
            log_path=cfg.log_dir,
            eval_freq=max(cfg.eval_freq // cfg.n_envs, 1),
            n_eval_episodes=cfg.eval_episodes,
            deterministic=True,
        ))

    print(f"Training {cfg.algorithm} for {cfg.total_timesteps} timesteps")
    diff_label = cfg.opponent_difficulty.value if cfg.opponent_difficulty else "campaign"
    print(f"  levels={cfg.level_indices}  difficulty={diff_label}")
    print(f"  n_envs={cfg.n_envs}  lr={cfg.learning_rate}")
    if eval_env is not None:
        print(f"  eval: {cfg.n_eval_envs} envs, {cfg.eval_episodes} episodes, "
              f"max_turns={cfg.eval_max_turns}, max_steps={cfg.eval_max_steps}")
    else:
        print("  eval: disabled")

    logger = TrainingLogger(cfg, device)
    logger.start()

    completed = False
    try:
        model.learn(total_timesteps=cfg.total_timesteps, callback=callbacks)
        completed = True
    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user (Ctrl+C).")
    finally:
        timesteps = getattr(model, "num_timesteps", 0)

        final_path = os.path.join(cfg.model_dir, "antiyoy_final")
        try:
            model.save(final_path)
            print(f"Model saved to {final_path}")
        except Exception as e:
            print(f"Warning: could not save model: {e}")

        logger.stop(completed=completed, timesteps_completed=timesteps)

        for vec_env in (env, eval_env):
            if vec_env is None:
                continue
            try:
                vec_env.close()
            except (EOFError, BrokenPipeError, ConnectionResetError):
                pass


def main() -> int:
    cfg = _parse_args()
    train(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
