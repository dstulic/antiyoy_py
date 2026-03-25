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
    )
    return cfg


def make_env(cfg: TrainConfig, rank: int = 0):
    """Return a callable that creates one AntiyoyEnv."""
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


def train(cfg: TrainConfig) -> None:
    import torch
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
    from stable_baselines3.common.vec_env import SubprocVecEnv
    from stable_baselines3.common.callbacks import CheckpointCallback

    # Large discrete action spaces (N^2 + N*7 + 1) cause float32 softmax
    # rounding to violate PyTorch's strict Simplex check.
    torch.distributions.Distribution.set_default_validate_args(False)

    os.makedirs(cfg.model_dir, exist_ok=True)
    os.makedirs(cfg.log_dir, exist_ok=True)
    os.makedirs(cfg.tensorboard_log, exist_ok=True)

    # Vectorised training environments
    env = SubprocVecEnv([make_env(cfg, i) for i in range(cfg.n_envs)])

    # Single evaluation environment
    eval_env = SubprocVecEnv([make_env(cfg, cfg.n_envs)])

    algo_cls = MaskablePPO
    if cfg.algorithm == "MaskableA2C":
        from sb3_contrib import MaskableA2C
        algo_cls = MaskableA2C

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
        CheckpointCallback(
            save_freq=max(cfg.save_freq // cfg.n_envs, 1),
            save_path=cfg.model_dir,
            name_prefix="antiyoy",
        ),
        MaskableEvalCallback(
            eval_env,
            best_model_save_path=os.path.join(cfg.model_dir, "best"),
            log_path=cfg.log_dir,
            eval_freq=max(cfg.eval_freq // cfg.n_envs, 1),
            n_eval_episodes=cfg.eval_episodes,
            deterministic=True,
        ),
    ]

    print(f"Training {cfg.algorithm} for {cfg.total_timesteps} timesteps")
    diff_label = cfg.opponent_difficulty.value if cfg.opponent_difficulty else "campaign"
    print(f"  levels={cfg.level_indices}  difficulty={diff_label}")
    print(f"  n_envs={cfg.n_envs}  lr={cfg.learning_rate}")

    model.learn(total_timesteps=cfg.total_timesteps, callback=callbacks)

    final_path = os.path.join(cfg.model_dir, "antiyoy_final")
    model.save(final_path)
    print(f"Final model saved to {final_path}")

    env.close()
    eval_env.close()


def main() -> int:
    cfg = _parse_args()
    train(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
