#!/usr/bin/env python3
"""Play a trained model on a campaign level and save ``.replay`` files so the
games can be watched back in the web viewer.

Unlike ``tools/eval_tax_breakdown`` (which only tallies stats), this keeps the
history manager attached so every move is snapshotted, then writes the matching
games to ``replays/`` via ``save_replay``.

The ``--want`` / ``--min-own`` filters pick which games qualify, and
``--select`` decides which of the qualifying games are actually kept:

  first      keep the first qualifying game (stops early)
  min-turns  keep the qualifying game with the fewest turns
  max-turns  keep the qualifying game with the most turns
  min-max    keep both the fewest- and most-turn qualifying games
  all        keep every qualifying game

Examples:
    # 90% tax: 10 playthroughs, keep the fastest and slowest wins
    python -m tools.model_replay --model ml_models/antiyoy_final.zip \
        --level 5 --tax 0.90 --games 10 --select min-max --label tax90

    # 85% tax: keep the first loss
    python -m tools.model_replay --tax 0.85 --games 30 --want loss --label tax85

    # 75% tax: keep the first loss that still held >20% of the map
    python -m tools.model_replay --tax 0.75 --games 30 --want loss \
        --min-own 20 --label tax75
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.config import MAX_CAMPAIGN_HEXES  # noqa: E402


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default="ml_models/antiyoy_final.zip")
    p.add_argument("--level", type=int, default=5)
    p.add_argument("--tax", type=float, default=0.0,
                   help="Opponent income-tax handicap for this run.")
    p.add_argument("--games", type=int, default=10,
                   help="Max playthroughs to run (default: 10).")
    p.add_argument("--want", choices=["any", "win", "loss"], default="any",
                   help="Only keep games with this outcome (default: any).")
    p.add_argument("--min-own", type=float, default=None,
                   help="Only keep games whose final ownership%% >= this.")
    p.add_argument("--select",
                   choices=["first", "min-turns", "max-turns", "min-max", "all"],
                   default="first",
                   help="Which qualifying games to keep (default: first).")
    p.add_argument("--difficulty", default="easy")
    p.add_argument("--max-turns", type=int, default=400)
    p.add_argument("--action-space-hexes", type=int, default=MAX_CAMPAIGN_HEXES)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--deterministic", action="store_true",
                   help="Greedy actions (default: sample, matching eval).")
    p.add_argument("--label", default="",
                   help="Tag appended to replay filenames.")
    p.add_argument("--replays-dir", default=str(PROJECT_ROOT / "replays"))
    return p.parse_args()


def _qualifies(want, won, own, min_own):
    if want == "win" and not won:
        return False
    if want == "loss" and won:
        return False
    if min_own is not None and own < min_own:
        return False
    return True


def _play_and_save(model, env, seed, deterministic, level, tax, label,
                   replays_dir, idx):
    """Run one full game (env.reset inside) and save its replay. Returns a dict
    describing the outcome plus the saved replay path."""
    from save_load.replay import save_replay

    obs, info = env.reset(seed=seed)
    done = False
    while not done:
        masks = env.action_masks()
        action, _ = model.predict(obs, action_masks=masks,
                                  deterministic=deterministic)
        obs, _r, terminated, truncated, info = env.step(int(action))
        done = terminated or truncated

    turns = int(info.get("turn_count", 0))
    won = bool(info.get("agent_won"))
    own = float(info.get("ownership_pct", 0.0))
    outcome = "win" if won else "loss"
    tax_tag = f"tax{int(round(tax * 100)):02d}"
    details = f"lvl{level}-{tax_tag}-{outcome}-{turns}t-own{own:.0f}-g{idx}"
    if label:
        details += f"-{label}"
    path = save_replay(env.game_state, source="model", source_details=details,
                       campaign_level_index=level, replays_dir=replays_dir)
    return {"turns": turns, "won": won, "own": own, "outcome": outcome,
            "path": path}


def main() -> int:
    args = _parse_args()
    from sb3_contrib import MaskablePPO
    import torch
    from core.enums import Difficulty
    from ml.env import AntiyoyEnv

    torch.distributions.Distribution.set_default_validate_args(False)
    print(f"Loading {args.model}", flush=True)
    model = MaskablePPO.load(args.model, device="cpu")

    env = AntiyoyEnv(
        level_indices=[args.level],
        opponent_difficulty=Difficulty(args.difficulty),
        opponent_income_tax=args.tax,
        action_space_hexes=args.action_space_hexes,
        max_turns=args.max_turns,
        record_replay=True,
    )

    print(f"\nLevel {args.level}, tax={args.tax:.2f}, up to {args.games} games, "
          f"want={args.want}"
          + (f", min_own>={args.min_own:.0f}%" if args.min_own is not None else "")
          + f", select={args.select}\n", flush=True)

    candidates = []
    try:
        for g in range(args.games):
            res = _play_and_save(model, env, args.seed + g, args.deterministic,
                                 args.level, args.tax, args.label,
                                 args.replays_dir, g)
            q = _qualifies(args.want, res["won"], res["own"], args.min_own)
            print(f"  game {g:>2}: {res['outcome']:>4}  turns={res['turns']:>3}  "
                  f"own={res['own']:>4.0f}%  {'[keep]' if q else '[skip]'}",
                  flush=True)
            if q:
                candidates.append(res)
                if args.select == "first":
                    break
            elif res["path"]:
                # Non-qualifying game: drop its replay file.
                try:
                    os.remove(res["path"])
                except OSError:
                    pass
    finally:
        try:
            env.close()
        except Exception:
            pass

    if not candidates:
        print("\nNo qualifying games found — nothing saved.", flush=True)
        return 1

    if args.select in ("first", "all"):
        keep = candidates
    elif args.select == "min-turns":
        keep = [min(candidates, key=lambda c: c["turns"])]
    elif args.select == "max-turns":
        keep = [max(candidates, key=lambda c: c["turns"])]
    else:  # min-max
        lo = min(candidates, key=lambda c: c["turns"])
        hi = max(candidates, key=lambda c: c["turns"])
        keep = [lo] if lo is hi else [lo, hi]

    keep_paths = {c["path"] for c in keep}
    for c in candidates:
        if c["path"] and c["path"] not in keep_paths:
            try:
                os.remove(c["path"])
            except OSError:
                pass

    print("\nSaved replays:", flush=True)
    for c in keep:
        print(f"  {c['outcome']:>4}  turns={c['turns']:>3}  own={c['own']:>4.0f}%"
              f"  ->  {c['path']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
