#!/usr/bin/env python3
"""Automated level-by-level curriculum trainer.

For each level in order this script:
  1. Trains the model on that level with win-rate early stopping (by shelling
     out to ``python -m ml.train``, resuming from the previous level's
     checkpoint so learning carries forward).
  2. Renames the resulting ml_models/antiyoy_final -> ml_models/level_XX so
     each solved level keeps its own checkpoint.
  3. Plays that level_XX model until it wins and records a snapshot of the
     agent's win condition (turns, economy, army, defense) to a CSV.
  4. Advances to the next level, resuming from ml_models/level_XX.

If a level cannot be solved (no win within --stat-attempts after training),
the curriculum stops so you can intervene.

Examples:
    # Continue the curriculum onto levels 2..5, starting from the current model
    python -m tools.curriculum_train --levels 2 3 4 5 \
        --resume ml_models/antiyoy_final --model-details max_map_action_space

    # Record stats only (no training), loading ml_models/level_XX per level
    python -m tools.curriculum_train --levels 0 1 \
        --model-details max_map_action_space --record-only
"""

import argparse
import csv
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.config import MAX_CAMPAIGN_HEXES  # noqa: E402
from ml.win_stats import WIN_STAT_FIELDS  # noqa: E402

CSV_FIELDS = ["timestamp", "model_details", "level_index"] + WIN_STAT_FIELDS

MODEL_DIR = PROJECT_ROOT / "ml_models"
# ml.train saves the working checkpoint here on every run.
FINAL_CHECKPOINT_ZIP = MODEL_DIR / "antiyoy_final.zip"


def _level_model_base(level: int) -> str:
    """Path (without .zip) of the per-level checkpoint, e.g. ml_models/level_02."""
    return f"ml_models/level_{level:02d}"


def _load_fastest_wins(csv_path: Path) -> dict:
    """Map level_index -> smallest winning turn_count from a playthrough CSV
    (columns: level_index, difficulty, result, turn_count)."""
    fastest: dict = {}
    if not csv_path.exists():
        print(f"  note: {csv_path} not found; using default eval turns.", flush=True)
        return fastest
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("result") or "").strip().lower() != "win":
                continue
            try:
                lvl = int(row["level_index"])
                turns = int(row["turn_count"])
            except (KeyError, ValueError, TypeError):
                continue
            if turns <= 0:
                continue
            if lvl not in fastest or turns < fastest[lvl]:
                fastest[lvl] = turns
    return fastest


MIN_TURN_CAP = 200
MAX_TURN_CAP = 500


def _turn_cap_for_level(level: int, fastest: dict, default: int) -> int:
    """Per-level turn cap: fastest recorded win + 50%, clipped to
    [MIN_TURN_CAP, MAX_TURN_CAP]. Falls back to ``default`` (also clipped)
    when the level has no recorded win. Used for both training and eval."""
    best = fastest.get(level)
    turns = int(math.ceil(best * 1.5)) if best else default
    return max(MIN_TURN_CAP, min(MAX_TURN_CAP, turns))


def _promote_checkpoint(level: int) -> str:
    """Rename ml_models/antiyoy_final.zip -> ml_models/level_XX.zip after a
    successful training run. Returns the new checkpoint base path."""
    if not FINAL_CHECKPOINT_ZIP.exists():
        raise FileNotFoundError(
            f"Expected {FINAL_CHECKPOINT_ZIP} after training, but it is missing."
        )
    dst_zip = MODEL_DIR / f"level_{level:02d}.zip"
    FINAL_CHECKPOINT_ZIP.replace(dst_zip)
    print(f"  renamed {FINAL_CHECKPOINT_ZIP.name} -> {dst_zip.name}", flush=True)
    return _level_model_base(level)


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    levels = p.add_mutually_exclusive_group(required=True)
    levels.add_argument("--levels", type=int, nargs="+",
                        help="Explicit ordered list of level indices to train.")
    levels.add_argument("--level-range", type=int, nargs=2, metavar=("START", "END"),
                        help="Inclusive range of levels, e.g. --level-range 2 10.")

    p.add_argument("--resume", type=str, default=None, metavar="PATH",
                   help="Initial checkpoint the FIRST level trains from (e.g. "
                        "ml_models/antiyoy_final); later levels chain from "
                        "ml_models/level_XX. Omit to train fresh. Ignored with "
                        "--record-only (which loads ml_models/level_XX).")
    p.add_argument("--model-details", type=str, default="max_map_action_space",
                   help="Model registry key / label recorded with each row.")
    p.add_argument("--csv", type=str, default="model_win_stats.csv",
                   help="Output CSV (appended to). Default: model_win_stats.csv")
    p.add_argument("--record-only", action="store_true",
                   help="Skip training; just play the --resume model on each "
                        "level and record win stats.")

    # Training passthrough
    p.add_argument("--timesteps", type=int, default=1_000_000,
                   help="Per-level training budget (additional steps on resume).")
    p.add_argument("--difficulty", type=str, default="campaign",
                   help="Opponent difficulty passed to ml.train: 'campaign' "
                        "(default), 'noop' (passive opponents), or an explicit "
                        "difficulty (easy/average/hard/...).")
    p.add_argument("--ent-coef", type=float, default=0.02)
    p.add_argument("--gamma", type=float, default=0.99,
                   help="Discount factor passed to ml.train (default: 0.99). "
                        "Lower => more myopic (weights near-term shaping).")
    p.add_argument("--territory-weight", type=float, default=None,
                   help="Passthrough to ml.train --territory-weight (uses "
                        "ml.train's default when omitted).")
    p.add_argument("--opponent-weight", type=float, default=None,
                   help="Passthrough to ml.train --opponent-weight.")
    p.add_argument("--income-weight", type=float, default=None,
                   help="Passthrough to ml.train --income-weight.")
    p.add_argument("--treasury-weight", type=float, default=None,
                   help="Passthrough to ml.train --treasury-weight.")
    p.add_argument("--truncation-penalty", type=float, default=None,
                   help="Passthrough to ml.train --truncation-penalty.")
    p.add_argument("--invalid-action-penalty", type=float, default=None,
                   help="Passthrough to ml.train --invalid-action-penalty.")
    p.add_argument("--time-cost", type=float, default=None,
                   help="Passthrough to ml.train --time-cost (per-step cost).")
    p.add_argument("--opponent-income-tax", type=float, nargs="+", default=None,
                   metavar="RATE",
                   help="Passthrough to ml.train --opponent-income-tax "
                        "(one value = constant handicap; several = "
                        "mixed-difficulty training across parallel envs).")
    p.add_argument("--win-rate-threshold", type=float, default=0.6)
    p.add_argument("--early-stop-patience", type=int, default=3)
    p.add_argument("--n-envs", type=int, default=8)
    p.add_argument("--eval-max-turns", type=int, default=200,
                   help="Fallback turn cap (training and eval) when the level "
                        "has no recorded win in --playthrough-csv. Otherwise the "
                        "cap is the fastest recorded win + 50%%, clipped to "
                        f"[{MIN_TURN_CAP}, {MAX_TURN_CAP}].")
    p.add_argument("--playthrough-csv", type=str, default="playthrough_results.csv",
                   help="CSV of balancer-AI playthroughs used to derive the "
                        "per-level eval turn cap (default: playthrough_results.csv).")
    p.add_argument("--action-space-hexes", type=int, default=MAX_CAMPAIGN_HEXES)

    # Stat playthrough
    p.add_argument("--stat-attempts", type=int, default=20,
                   help="Max games to play looking for a win to record.")
    p.add_argument("--stat-max-turns", type=int, default=400,
                   help="Turn cap per stat-playthrough game.")
    return p.parse_args()


def _resolve_levels(args) -> list:
    if args.level_range:
        return list(range(args.level_range[0], args.level_range[1] + 1))
    return list(args.levels)


def _train_level(args, level: int, resume: str, turn_cap: int) -> None:
    """Shell out to ml.train for one level; raises on non-zero exit.

    ``turn_cap`` is used for both training and eval turn limits."""
    cmd = [
        sys.executable, "-m", "ml.train",
        "--levels", str(level),
        "--early-stop",
        "--model-details", args.model_details,
        "--timesteps", str(args.timesteps),
        "--difficulty", args.difficulty,
        "--ent-coef", str(args.ent_coef),
        "--gamma", str(args.gamma),
        "--win-rate-threshold", str(args.win_rate_threshold),
        "--early-stop-patience", str(args.early_stop_patience),
        "--n-envs", str(args.n_envs),
        "--max-turns", str(turn_cap),
        "--eval-max-turns", str(turn_cap),
        "--action-space-hexes", str(args.action_space_hexes),
    ]
    for flag, value in (
        ("--territory-weight", args.territory_weight),
        ("--opponent-weight", args.opponent_weight),
        ("--income-weight", args.income_weight),
        ("--treasury-weight", args.treasury_weight),
        ("--truncation-penalty", args.truncation_penalty),
        ("--invalid-action-penalty", args.invalid_action_penalty),
        ("--time-cost", args.time_cost),
    ):
        if value is not None:
            cmd += [flag, str(value)]
    if args.opponent_income_tax is not None:
        # nargs="+": pass every rate so the child spans the difficulty spread.
        cmd += ["--opponent-income-tax", *[str(t) for t in args.opponent_income_tax]]
    if resume:
        cmd += ["--resume", resume]
    print(f"\n=== Training level {level} "
          f"(resume={resume or 'fresh'}, turn_cap={turn_cap}) ===",
          flush=True)
    print("  " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)


def _record_level(args, level: int, checkpoint: str, writer, fh) -> bool:
    """Play the checkpoint until a win and append a CSV row. Returns success."""
    from sb3_contrib import MaskablePPO
    import torch
    from ml.win_stats import play_until_win

    torch.distributions.Distribution.set_default_validate_args(False)

    print(f"--- Recording win stats for level {level} "
          f"(checkpoint={checkpoint}) ---", flush=True)
    model = MaskablePPO.load(checkpoint, device="cpu")
    stats = play_until_win(
        model,
        level_index=level,
        action_space_hexes=args.action_space_hexes,
        max_turns=args.stat_max_turns,
        max_attempts=args.stat_attempts,
        verbose=True,
    )
    if stats is None:
        print(f"  WARNING: no win recorded for level {level} within "
              f"{args.stat_attempts} attempts.", flush=True)
        return False

    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model_details": args.model_details,
        "level_index": level,
        **stats,
    }
    writer.writerow(row)
    fh.flush()
    print(f"  recorded: {row}", flush=True)
    return True


def main() -> int:
    args = _parse_args()
    levels = _resolve_levels(args)

    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = PROJECT_ROOT / csv_path
    write_header = not csv_path.exists()

    pt_csv = Path(args.playthrough_csv)
    if not pt_csv.is_absolute():
        pt_csv = PROJECT_ROOT / pt_csv
    fastest_wins = _load_fastest_wins(pt_csv)

    resume = args.resume
    with open(csv_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
            fh.flush()

        for level in levels:
            if not args.record_only:
                turn_cap = _turn_cap_for_level(
                    level, fastest_wins, args.eval_max_turns
                )
                try:
                    _train_level(args, level, resume, turn_cap)
                except subprocess.CalledProcessError as e:
                    print(f"Training failed for level {level} (exit "
                          f"{e.returncode}). Stopping curriculum.", file=sys.stderr)
                    return 1
                # Promote antiyoy_final -> level_XX and chain forward from it.
                checkpoint = _promote_checkpoint(level)
                resume = checkpoint
            else:
                checkpoint = _level_model_base(level)

            solved = _record_level(args, level, checkpoint, writer, fh)
            if not solved and not args.record_only:
                print(f"Level {level} not solved; stopping so you can "
                      f"intervene.", file=sys.stderr)
                return 1

    print(f"\nDone. Win stats written to {csv_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
