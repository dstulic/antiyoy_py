#!/usr/bin/env python3
"""Measure a trained model's win rate against opponents at different income-tax
handicaps, to locate the "frontier" difficulty for curriculum tuning.

For each tax value it plays N games on a level and reports win rate, average
turns-to-win, and final ownership %.  Use it to pick a moving-window
``--opponent-income-tax`` set that straddles the frontier.

Example:
    python -m tools.eval_tax_breakdown --model ml_models/antiyoy_final.zip \
        --level 5 --games 12 --taxes 0.99 0.95 0.9 0.85 0.8 0.7 0.5 0.0
"""

import argparse
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.config import MAX_CAMPAIGN_HEXES  # noqa: E402


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="ml_models/antiyoy_final.zip")
    p.add_argument("--level", type=int, default=5)
    p.add_argument("--games", type=int, default=12,
                   help="Games played per tax value (default: 12).")
    p.add_argument("--taxes", type=float, nargs="+",
                   default=[0.99, 0.95, 0.9, 0.85, 0.8, 0.7, 0.5, 0.0],
                   help="Opponent income-tax values to probe.")
    p.add_argument("--difficulty", default="easy",
                   help="Opponent difficulty (default: easy).")
    p.add_argument("--max-turns", type=int, default=400)
    p.add_argument("--action-space-hexes", type=int, default=MAX_CAMPAIGN_HEXES)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--deterministic", action="store_true",
                   help="Greedy actions (default: sample, matching eval).")
    return p.parse_args()


def _play(model, env, seed, deterministic):
    obs, info = env.reset(seed=seed)
    done = False
    while not done:
        masks = env.action_masks()
        action, _ = model.predict(
            obs, action_masks=masks, deterministic=deterministic
        )
        obs, _r, terminated, truncated, info = env.step(int(action))
        done = terminated or truncated
    return info


def _mmm(values, fmt="{:.0f}"):
    """Format a min/avg/max triple, or '-' when there are no samples."""
    if not values:
        return "-"
    lo, avg, hi = min(values), statistics.mean(values), max(values)
    return f"{fmt.format(lo)}/{fmt.format(avg)}/{fmt.format(hi)}"


def main() -> int:
    args = _parse_args()
    from sb3_contrib import MaskablePPO
    import torch
    from core.enums import Difficulty
    from ml.env import AntiyoyEnv

    torch.distributions.Distribution.set_default_validate_args(False)
    print(f"Loading {args.model}", flush=True)
    model = MaskablePPO.load(args.model, device="cpu")

    print(f"\nLevel {args.level}, {args.games} games/tax, "
          f"difficulty={args.difficulty}, "
          f"{'greedy' if args.deterministic else 'sampled'} actions", flush=True)
    print("(min/avg/max shown for turn and ownership columns)\n", flush=True)
    header = (f"{'tax':>6} | {'win%':>5} | {'win turns (m/a/M)':>18} | "
              f"{'lose turns (m/a/M)':>18} | {'lose own% (m/a/M)':>20}")
    print(header)
    print("-" * len(header))

    for tax in args.taxes:
        env = AntiyoyEnv(
            level_indices=[args.level],
            opponent_difficulty=Difficulty(args.difficulty),
            opponent_income_tax=tax,
            action_space_hexes=args.action_space_hexes,
            max_turns=args.max_turns,
        )
        wins = 0
        win_turns, lose_turns, lose_own = [], [], []
        try:
            for g in range(args.games):
                info = _play(model, env, args.seed + g, args.deterministic)
                turns = int(info.get("turn_count", 0))
                if info.get("agent_won"):
                    wins += 1
                    win_turns.append(turns)
                else:
                    lose_turns.append(turns)
                    lose_own.append(float(info.get("ownership_pct", 0.0)))
        finally:
            try:
                env.close()
            except Exception:
                pass
        win_pct = 100.0 * wins / args.games
        print(f"{tax:>6.2f} | {win_pct:>4.0f}% | {_mmm(win_turns):>18} | "
              f"{_mmm(lose_turns):>18} | {_mmm(lose_own, '{:.1f}'):>20}",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
