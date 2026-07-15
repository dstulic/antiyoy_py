#!/usr/bin/env python3
"""Collect built-in AI win-condition stats into a CSV comparable to
``model_win_stats.csv`` (produced by ``tools/curriculum_train.py`` for the ML
model).

For each level, the "human" player is driven by a built-in balancer AI at a
given difficulty and the game is run to its natural end.  We record, per level,
only the *fastest* win (smallest turn count) across the difficulties, tagging
the ``model_details`` column with the difficulty that achieved it.

Rules:
  - If a difficulty fails to win 3 levels in a row it is dropped from all
    subsequent levels (--loss-streak-limit to change).
  - Only the single fastest winning difficulty is recorded for each level.

Output columns match model_win_stats.csv exactly:
    timestamp, model_details, level_index, turns, income_per_turn,
    money_in_bank, unit_strength, unit_count, defense_strength, tower_count

Usage:
    python -m tools.run_playthrough_batch --level-min 0 --level-max 20
    python -m tools.run_playthrough_batch --difficulties hard expert balancer -j 4
"""

import argparse
import contextlib
import csv
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.win_stats import WIN_STAT_FIELDS, compute_win_stats  # noqa: E402

CSV_FIELDS = ["timestamp", "model_details", "level_index"] + WIN_STAT_FIELDS
DEFAULT_LOSS_STREAK_LIMIT = 3


def _play_one(level: int, difficulty: str):
    """Run one game with the human played by ``difficulty`` balancer AI.

    Returns (level, difficulty, result, turns, stats_or_None) where result is
    one of 'win' / 'loss' / 'other'.
    """
    from tools.ai_playthrough import _init_game
    from core.enums import Difficulty
    from commands.types import EndTurnCommand
    from commands.executor import CommandExecutor

    with contextlib.redirect_stdout(open(os.devnull, "w")):
        pair = _init_game(level)
        if pair is None:
            return (level, difficulty, "other", 0, None)
        gs, gm = pair
        diff = Difficulty(difficulty)

        turn_count = 0
        hex_count = len(gs.hexes)
        n_entities = len(gs.entities_manager.entities or [])
        max_turns = (hex_count * 10 * n_entities) if n_entities else 1

        while True:
            gm.update()
            if gs.game_end_manager.is_game_ended():
                break
            if turn_count >= max_turns:
                break
            current = gs.entities_manager.get_current_entity()
            if not current:
                break
            if current.is_human():
                ai = gs.ai_manager.get_balancer_ai()
                if ai:
                    ai.set_difficulty(diff)
                    ai.perform()
                else:
                    CommandExecutor(gs).execute(EndTurnCommand(), current.color)
            elif current.is_artificial_intelligence():
                gs.ai_manager.process_ai_turn()
            else:
                break
            turn_count += 1

        gm.update()
        winner = gs.game_end_manager.get_winner()
        human = next(
            (e for e in (gs.entities_manager.entities or []) if e.is_human()), None
        )

    if winner and human and winner.color == human.color:
        stats = compute_win_stats(gs, human.color)
        stats["turns"] = turn_count
        return (level, difficulty, "win", turn_count, stats)
    if winner:
        return (level, difficulty, "loss", turn_count, None)
    return (level, difficulty, "other", turn_count, None)


def _has_level(level: int) -> bool:
    from campaign.levels import get_level_code
    code = get_level_code(level)
    return bool(code) and code != "-"


def run_batch(csv_path: Path, levels: list, difficulties: list,
              jobs: int, loss_streak_limit: int) -> int:
    write_header = not csv_path.exists()
    loss_streak = {d: 0 for d in difficulties}
    active = list(difficulties)
    recorded = 0

    with open(csv_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
            fh.flush()

        with ProcessPoolExecutor(max_workers=max(1, jobs)) as executor:
            for level in levels:
                if not active:
                    print("All difficulties dropped; stopping.", flush=True)
                    break
                if not _has_level(level):
                    print(f"level {level}: no level code, skipping.", flush=True)
                    continue

                futures = {
                    executor.submit(_play_one, level, d): d for d in active
                }
                results: dict = {}
                for fut in as_completed(futures):
                    _lvl, d, result, turns, stats = fut.result()
                    results[d] = (result, turns, stats)

                # Evaluate in stable difficulty order: update streaks, find the
                # fastest win, then prune stalled difficulties.
                best = None  # (difficulty, turns, stats)
                for d in active:
                    result, turns, stats = results[d]
                    if result == "win":
                        loss_streak[d] = 0
                        if best is None or turns < best[1]:
                            best = (d, turns, stats)
                        print(f"  level {level} {d}: win in {turns} turns", flush=True)
                    else:
                        loss_streak[d] += 1
                        print(f"  level {level} {d}: {result} "
                              f"(streak {loss_streak[d]}/{loss_streak_limit})",
                              flush=True)

                for d in list(active):
                    if loss_streak[d] >= loss_streak_limit:
                        active.remove(d)
                        print(f"  dropping '{d}': {loss_streak_limit} levels "
                              f"without a win.", flush=True)

                if best is not None:
                    d, turns, stats = best
                    row = {
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "model_details": d,
                        "level_index": level,
                        **stats,
                    }
                    writer.writerow(row)
                    fh.flush()
                    recorded += 1
                    print(f"  => recorded level {level}: fastest '{d}' "
                          f"({turns} turns)", flush=True)
                else:
                    print(f"  => level {level}: no wins recorded", flush=True)

    return recorded


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--csv", type=Path, default=Path("builtin_win_stats.csv"),
                        help="Output CSV (appended). Default: builtin_win_stats.csv")
    parser.add_argument("--level-min", type=int, default=0)
    parser.add_argument("--level-max", type=int, default=20)
    parser.add_argument(
        "--difficulties", nargs="+",
        default=["average", "hard", "expert", "balancer"],
        choices=["easy", "average", "hard", "expert", "balancer"],
        metavar="DIFF",
        help="Difficulties to run (default: average hard expert balancer).",
    )
    parser.add_argument("--jobs", "-j", type=int, default=4,
                        help="Parallel games per level, across difficulties "
                             "(default: 4).")
    parser.add_argument("--loss-streak-limit", type=int,
                        default=DEFAULT_LOSS_STREAK_LIMIT,
                        help="Drop a difficulty after this many consecutive "
                             "levels without a win (default: 3).")
    args = parser.parse_args()

    if args.level_min > args.level_max:
        print("Error: --level-min must be <= --level-max", file=sys.stderr)
        return 1

    levels = list(range(args.level_min, args.level_max + 1))
    csv_path = args.csv if args.csv.is_absolute() else PROJECT_ROOT / args.csv

    print(f"Recording built-in win stats: levels {args.level_min}-"
          f"{args.level_max}, difficulties {' '.join(args.difficulties)}, "
          f"jobs={args.jobs}", flush=True)
    recorded = run_batch(csv_path, levels, args.difficulties,
                         args.jobs, args.loss_streak_limit)
    print(f"\nDone. Recorded {recorded} level(s) to {csv_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
