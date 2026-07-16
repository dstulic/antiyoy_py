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
from typing import Optional

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
                        choices=["campaign", "noop"] + [d.value for d in Difficulty],
                        help="Opponent AI difficulty. 'campaign' (default) "
                             "uses the level-appropriate difficulty. 'noop' makes "
                             "opponents passive (they end every turn without "
                             "moving) — the first rung of the curriculum ladder.")
    parser.add_argument("--n-envs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--ent-coef", type=float, default=0.01,
                        help="Entropy coefficient (exploration; default: 0.01)")
    parser.add_argument("--gamma", type=float, default=0.99,
                        help="Discount factor (default: 0.99). Lower values make "
                             "the agent more myopic, weighting near-term shaping "
                             "over distant terminal rewards.")
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--territory-weight", type=float, default=0.5,
                        help="Weight on the per-step ownership-percentage delta "
                             "(default: 0.5)")
    parser.add_argument("--opponent-weight", type=float, default=0.0,
                        help="Weight on the per-step opponent ownership-percentage "
                             "DECLINE (rewards shrinking the enemy / penalises "
                             "letting them grow; default: 0.0 = off)")
    parser.add_argument("--income-weight", type=float, default=0.004,
                        help="Weight on the per-step economy delta (default: 0.004)")
    parser.add_argument("--treasury-weight", type=float, default=0.0,
                        help="Slice of the agent's treasury folded into the "
                             "economy potential (0.0=off). Makes over-spending / "
                             "idle-army upkeep and expensive-unit-for-cheap-job "
                             "net-negative; keep small (~0.1-0.25) as treasury "
                             "dwarfs a single hex (default: 0.0)")
    parser.add_argument("--truncation-penalty", type=float, default=-1.0,
                        help="Terminal reward when the episode truncates with no "
                             "winner (default: -1.0)")
    parser.add_argument("--invalid-action-penalty", type=float, default=0.0,
                        help="Penalty magnitude for invalid/failed actions "
                             "(default: 0.0)")
    parser.add_argument("--time-cost", type=float, default=0.0,
                        help="Constant magnitude subtracted from every step's "
                             "reward; penalises long games and per-turn action "
                             "churn (default: 0.0 = off)")
    parser.add_argument("--opponent-income-tax", type=float, nargs="+",
                        default=[0.0], metavar="RATE",
                        help="Fraction(s) of each opponent's positive per-turn "
                             "income withheld before it hits their treasury "
                             "(0.0=off, 1.0=keep nothing). Opponents keep their "
                             "normal AI logic but a weaker economy. Pass ONE "
                             "value for a constant handicap, or SEVERAL for "
                             "mixed-difficulty training (each parallel env is "
                             "pinned to one value, so every batch spans the "
                             "range: the agent tastes wins at high tax and is "
                             "challenged at low tax). The agent's income is "
                             "always exempt (default: 0.0 = off).")
    parser.add_argument("--resume", type=str, default=None, metavar="PATH",
                        help="Resume training from a saved model checkpoint "
                             "(requires matching --action-space-hexes).")
    parser.add_argument("--early-stop", action="store_true",
                        help="Stop training once the win rate is sustained above "
                             "--win-rate-threshold for --early-stop-patience evals.")
    parser.add_argument("--win-rate-threshold", type=float, default=0.6,
                        help="Win-rate target for early stopping (default: 0.6)")
    parser.add_argument("--early-stop-patience", type=int, default=3,
                        help="Consecutive evals at/above the win-rate threshold "
                             "required to early-stop (default: 3)")
    parser.add_argument("--log-dir", type=str, default="ml_logs")
    parser.add_argument("--model-dir", type=str, default="ml_models")
    parser.add_argument("--device", type=str, default=None,
                        choices=["cpu", "cuda", "mps"],
                        help="Override device selection (default: auto-detect)")
    parser.add_argument("--no-eval", action="store_true",
                        help="Disable evaluation callback (useful for short runs)")
    parser.add_argument("--eval-max-turns", type=int, default=200,
                        help="Max turns per eval episode (default: 200)")
    parser.add_argument("--eval-max-steps", type=int, default=5000,
                        help="Max steps per eval episode (default: 5000)")
    parser.add_argument("--n-eval-envs", type=int, default=5,
                        help="Number of parallel eval environments (default: 5). "
                             "Eval env i is pinned to the i-th --opponent-income-tax "
                             "value, so set this to the number of tax values to "
                             "evaluate the WHOLE difficulty spread (otherwise only "
                             "the first N taxes — the easiest — are ever measured).")
    parser.add_argument("--eval-episodes", type=int, default=5,
                        help="Episodes per evaluation (default: 5). SB3 spreads "
                             "these across the eval envs, so use a multiple of "
                             "--n-eval-envs to sample every tax rung evenly "
                             "(e.g. 2x for less noise).")
    parser.add_argument("--model-details", type=str, default="first_approach",
                        help="Key into ml/model_registry.yaml describing "
                             "this approach (default: first_approach)")
    parser.add_argument("--action-space-hexes", type=int, default=None,
                        help="Fix action space to support maps up to N hexes "
                             "(default: 384 = max campaign level). Override to "
                             "shrink for faster training on small maps only.")
    parser.add_argument("--run-name", type=str, default=None,
                        help="TensorBoard run/folder name. Defaults to the algo "
                             "name (e.g. MaskablePPO); on --resume that reuses "
                             "the latest folder. Set a distinct name to keep an "
                             "experiment in its own TB folder.")
    parser.add_argument("--reset-timesteps", action="store_true",
                        help="When resuming, reset the timestep counter to 0 so "
                             "the new run's x-axis starts at 0 (weights are still "
                             "loaded). Off by default (resumes keep the count).")
    args = parser.parse_args()

    noop_opponents = args.difficulty == "noop"
    if args.difficulty in ("campaign", "noop"):
        difficulty = None
    else:
        difficulty = Difficulty(args.difficulty)
    levels = list(range(args.level_range[0], args.level_range[1] + 1)) if args.level_range else args.levels

    cfg = TrainConfig(
        algorithm=args.algo,
        total_timesteps=args.timesteps,
        level_indices=levels,
        opponent_difficulty=difficulty,
        noop_opponents=noop_opponents,
        opponent_income_tax=args.opponent_income_tax,
        n_envs=args.n_envs,
        seed=args.seed,
        learning_rate=args.lr,
        ent_coef=args.ent_coef,
        gamma=args.gamma,
        max_turns=args.max_turns,
        territory_weight=args.territory_weight,
        opponent_weight=args.opponent_weight,
        income_weight=args.income_weight,
        treasury_weight=args.treasury_weight,
        truncation_penalty=args.truncation_penalty,
        invalid_action_penalty=args.invalid_action_penalty,
        time_cost=args.time_cost,
        resume_path=args.resume,
        reset_timesteps=args.reset_timesteps,
        early_stop=args.early_stop,
        win_rate_threshold=args.win_rate_threshold,
        early_stop_patience=args.early_stop_patience,
        log_dir=args.log_dir,
        model_dir=args.model_dir,
        device_override=args.device,
        no_eval=args.no_eval,
        eval_max_turns=args.eval_max_turns,
        eval_max_steps=args.eval_max_steps,
        n_eval_envs=args.n_eval_envs,
        eval_episodes=args.eval_episodes,
        model_details=args.model_details,
        run_name=args.run_name,
        **({"action_space_hexes": args.action_space_hexes} if args.action_space_hexes else {}),
    )
    return cfg


def tax_for_rank(taxes, rank: int) -> float:
    """Pick one income-tax value for a given env rank (stratified, wrapping).

    With a single-element list this is a constant handicap; with several the
    parallel envs are spread across the values so every rollout batch contains
    the whole difficulty range (persistent win signal + generalisation).
    """
    if not taxes:
        return 0.0
    return float(taxes[rank % len(taxes)])


def make_env(cfg: TrainConfig, rank: int = 0):
    """Return a callable that creates one AntiyoyEnv for training."""
    def _init():
        from ml.env import AntiyoyEnv
        from ml.reward import DefaultRewardCalculator
        from stable_baselines3.common.monitor import Monitor

        env = AntiyoyEnv(
            level_indices=cfg.level_indices,
            opponent_difficulty=cfg.opponent_difficulty,
            noop_opponents=cfg.noop_opponents,
            opponent_income_tax=tax_for_rank(cfg.opponent_income_tax, rank),
            max_turns=cfg.max_turns,
            reward_calculator=DefaultRewardCalculator(
                territory_weight=cfg.territory_weight,
                opponent_weight=cfg.opponent_weight,
                income_weight=cfg.income_weight,
                treasury_weight=cfg.treasury_weight,
                truncation_penalty=cfg.truncation_penalty,
            ),
            action_space_hexes=cfg.action_space_hexes,
            invalid_action_penalty=cfg.invalid_action_penalty,
            time_cost=cfg.time_cost,
        )
        env = Monitor(env)
        env.reset(seed=cfg.seed + rank)
        return env
    return _init


def make_eval_env(cfg: TrainConfig, rank: int = 0, tax_rank: Optional[int] = None):
    """Return a callable that creates one AntiyoyEnv for evaluation,
    using tighter turn/step limits to prevent runaway episodes.

    ``tax_rank`` selects which income-tax value this eval env is pinned to
    (defaults to ``rank``); passing a 0-based index lets eval span the full
    tax spread independently of the seed offset."""
    def _init():
        from ml.env import AntiyoyEnv
        from ml.reward import DefaultRewardCalculator
        from stable_baselines3.common.monitor import Monitor

        env = AntiyoyEnv(
            level_indices=cfg.level_indices,
            opponent_difficulty=cfg.opponent_difficulty,
            noop_opponents=cfg.noop_opponents,
            opponent_income_tax=tax_for_rank(
                cfg.opponent_income_tax, rank if tax_rank is None else tax_rank
            ),
            max_turns=cfg.eval_max_turns,
            max_steps=cfg.eval_max_steps,
            reward_calculator=DefaultRewardCalculator(
                territory_weight=cfg.territory_weight,
                opponent_weight=cfg.opponent_weight,
                income_weight=cfg.income_weight,
                treasury_weight=cfg.treasury_weight,
                truncation_penalty=cfg.truncation_penalty,
            ),
            action_space_hexes=cfg.action_space_hexes,
            invalid_action_penalty=cfg.invalid_action_penalty,
            time_cost=cfg.time_cost,
            # log_progress=True,
        )
        env = Monitor(env)
        env.reset(seed=cfg.seed + rank)
        return env
    return _init


def train(cfg: TrainConfig) -> None:
    import time
    from datetime import datetime

    import numpy as np
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

    class WinRateEarlyStop(TimedEvalCallback):
        """Early-stops training once the eval win rate stays at/above a
        threshold for a number of consecutive evaluations.

        Win rate is derived from ``info['is_success']`` (populated by the env),
        which sb3 collects into ``self._is_success_buffer`` during eval.
        """

        def __init__(self, *args, win_rate_threshold: float = 0.6,
                     patience: int = 3, **kwargs):
            super().__init__(*args, **kwargs)
            self.win_rate_threshold = win_rate_threshold
            self.patience = patience
            self._consec = 0

        def _on_step(self) -> bool:
            did_eval = self.eval_freq > 0 and self.n_calls % self.eval_freq == 0
            result = super()._on_step()
            if did_eval:
                if self._is_success_buffer:
                    win_rate = float(np.mean(self._is_success_buffer))
                else:
                    win_rate = 0.0
                self.logger.record("eval/win_rate", win_rate)
                if win_rate >= self.win_rate_threshold:
                    self._consec += 1
                else:
                    self._consec = 0
                print(f"[{_now()}] WIN_RATE {win_rate:.2f} "
                      f"(threshold {self.win_rate_threshold:.2f}, "
                      f"{self._consec}/{self.patience} consecutive)", flush=True)
                if self._consec >= self.patience:
                    print(f"[{_now()}] EARLY STOP: win rate >= "
                          f"{self.win_rate_threshold:.2f} for {self.patience} "
                          f"consecutive evals.", flush=True)
                    return False
            return result

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
            make_eval_env(cfg, cfg.n_envs + i, tax_rank=i)
            for i in range(cfg.n_eval_envs)
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

    if cfg.resume_path:
        print(f"Resuming from checkpoint: {cfg.resume_path}")
        model = algo_cls.load(cfg.resume_path, env=env, device=device)
        model.set_env(env)
        # load() restores ent_coef from the checkpoint; re-apply the configured
        # value so it can be annealed across curriculum stages.
        model.ent_coef = cfg.ent_coef
        if isinstance(getattr(model, "ent_coef_tensor", None), torch.Tensor):
            model.ent_coef_tensor = torch.tensor(
                float(cfg.ent_coef), device=model.device
            )
        print(f"  ent_coef set to {cfg.ent_coef}")
        # load() also restores gamma from the checkpoint; re-apply the configured
        # value so the discount can be adjusted when resuming a curriculum stage.
        model.gamma = cfg.gamma
        print(f"  gamma set to {cfg.gamma}")
    else:
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
        eval_kwargs = dict(
            best_model_save_path=os.path.join(cfg.model_dir, "best"),
            log_path=cfg.log_dir,
            eval_freq=max(cfg.eval_freq // cfg.n_envs, 1),
            n_eval_episodes=cfg.eval_episodes,
            # Stochastic eval: a greedy/argmax policy can trap itself repeating
            # a non-terminating action (never ending its turn) and truncate at
            # the step cap, reporting 0% win rate even when the sampled policy
            # wins ~90% of training episodes. Sampling matches how the agent
            # actually plays and makes the win-rate/early-stop signal real.
            deterministic=False,
        )
        if cfg.early_stop:
            callbacks.append(WinRateEarlyStop(
                eval_env,
                win_rate_threshold=cfg.win_rate_threshold,
                patience=cfg.early_stop_patience,
                **eval_kwargs,
            ))
        else:
            callbacks.append(TimedEvalCallback(eval_env, **eval_kwargs))

    print(f"Training {cfg.algorithm} for {cfg.total_timesteps} timesteps")
    if cfg.noop_opponents:
        diff_label = "noop"
    elif cfg.opponent_difficulty:
        diff_label = cfg.opponent_difficulty.value
    else:
        diff_label = "campaign"
    print(f"  levels={cfg.level_indices}  difficulty={diff_label}")
    if any(t > 0 for t in cfg.opponent_income_tax):
        spread = [tax_for_rank(cfg.opponent_income_tax, r) for r in range(cfg.n_envs)]
        print(f"  opponent income tax: {cfg.opponent_income_tax}  "
              f"(per-env: {spread})")
    print(f"  n_envs={cfg.n_envs}  lr={cfg.learning_rate}")
    if eval_env is not None:
        print(f"  eval: {cfg.n_eval_envs} envs, {cfg.eval_episodes} episodes, "
              f"max_turns={cfg.eval_max_turns}, max_steps={cfg.eval_max_steps}")
    else:
        print("  eval: disabled")
    if cfg.early_stop:
        print(f"  early stop: win_rate >= {cfg.win_rate_threshold} "
              f"for {cfg.early_stop_patience} consecutive evals")
    if cfg.resume_path:
        reset_note = " (timestep counter reset to 0)" if cfg.reset_timesteps else ""
        print(f"  resuming from: {cfg.resume_path}{reset_note}")
    print(f"  tensorboard: {cfg.tensorboard_log}/{cfg.run_name or cfg.algorithm}_* ")

    logger = TrainingLogger(cfg, device)
    logger.start()

    completed = False
    try:
        model.learn(
            total_timesteps=cfg.total_timesteps,
            callback=callbacks,
            # Fresh runs always reset; resumes keep the cumulative count unless
            # --reset-timesteps is given (weights are loaded either way).
            reset_num_timesteps=(not cfg.resume_path) or cfg.reset_timesteps,
            tb_log_name=cfg.run_name or cfg.algorithm,
        )
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
