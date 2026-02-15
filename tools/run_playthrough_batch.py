#!/usr/bin/env python3
"""
Run ai_playthrough for configurable levels and difficulties.
Collect results to CSV and plot turn count vs level index.

Usage:
    python tools/run_playthrough_batch.py [--level-min 0] [--level-max 10] [--difficulties ...]
    python tools/run_playthrough_batch.py --level-min 0 --level-max 5 --difficulties expert balancer
    python -m tools.run_playthrough_batch --csv out.csv --plot out.png

Requires: matplotlib (pip install matplotlib)
"""

import argparse
import csv
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Project root when run from tools/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Hardcoded colors for plot (easy not in batch but defined for consistency)
DIFFICULTY_COLORS = {
    "easy": "yellow",
    "average": "green",
    "hard": "blue",
    "expert": "purple",
    "balancer": "red",
}


def run_one_playthrough(level: int, difficulty: str, turn_interval: int = 99999) -> tuple[str, int]:
    """
    Run ai_playthrough for one (level, difficulty). Return (result, turn_count).
    turn_count: actual for win, -1 for loss, 0 for other.
    """
    script = PROJECT_ROOT / "tools" / "ai_playthrough.py"
    cmd = [
        sys.executable,
        str(script),
        "--level", str(level),
        "--ai", difficulty,
        "--turn", str(turn_interval),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = proc.stdout + "\n" + proc.stderr
    result = "other"
    turn_count = 0
    for line in out.splitlines():
        m = re.match(r"result:\s*(\w+)", line.strip(), re.IGNORECASE)
        if m:
            result = m.group(1).lower()
            continue
        m = re.match(r"turn count:\s*(\d+)", line.strip(), re.IGNORECASE)
        if m:
            turn_count = int(m.group(1))
            break
    if result == "loss":
        turn_count = -1
    elif result == "other":
        turn_count = 0
    return result, turn_count


def _run_one_task(
    level: int, difficulty: str, turn_interval: int, start_times: dict | None = None
) -> tuple[int, str, str, int]:
    """Wrapper for parallel execution: (level, difficulty, result, turn_count)."""
    if start_times is not None:
        start_times[(level, difficulty)] = time.time()
    result, turn_count = run_one_playthrough(level, difficulty, turn_interval)
    return (level, difficulty, result, turn_count)


def run_batch(
    csv_path: Path,
    levels: list[int],
    difficulties: list[str],
    turn_interval: int = 99999,
    jobs: int = 1,
) -> list[dict]:
    """Run all (level, difficulty) combinations (optionally in parallel); write CSV; return rows in order."""
    tasks = [(level, difficulty) for level in levels for difficulty in difficulties]
    if jobs <= 1:
        results = []
        for level, difficulty in tasks:
            print(f"  level={level} difficulty={difficulty} ... ", end="", flush=True)
            result, turn_count = run_one_playthrough(level, difficulty, turn_interval)
            results.append((level, difficulty, result, turn_count))
            print(f"result={result} turn_count={turn_count}")
    else:
        results = [None] * len(tasks)
        task_index = {(level, diff): i for i, (level, diff) in enumerate(tasks)}
        pending = set(tasks)
        start_times: dict[tuple[int, str], float] = {}
        done = 0
        max_runtime = 600  # same as subprocess timeout in run_one_playthrough
        stop_event = threading.Event()

        def heartbeat():
            while not stop_event.wait(10):
                snapshot = sorted(pending)
                if not snapshot:
                    continue
                now = time.time()
                for level, difficulty in snapshot:
                    elapsed = int(now - start_times.get((level, difficulty), now))
                    print(f"level={level} difficulty={difficulty} {elapsed}s/{max_runtime}s")

        t = threading.Thread(target=heartbeat, daemon=True)
        t.start()
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            future_to_key = {
                executor.submit(_run_one_task, level, difficulty, turn_interval, start_times): (level, difficulty)
                for level, difficulty in tasks
            }
            for future in as_completed(future_to_key):
                level, difficulty = future_to_key[future]
                pending.discard((level, difficulty))
                try:
                    level, difficulty, result, turn_count = future.result()
                    results[task_index[(level, difficulty)]] = (level, difficulty, result, turn_count)
                except Exception as e:
                    results[task_index[(level, difficulty)]] = (level, difficulty, "other", 0)
                    print(f"  level={level} difficulty={difficulty} error: {e}", file=sys.stderr)
                done += 1
                still_running = ", ".join(f"level={l}/diff={d}" for l, d in sorted(pending))
                print(f"  [{done}/{len(tasks)}] level={level} difficulty={difficulty} result={result} turn_count={turn_count}")
                # if pending:
                    # print(f"       completed={done} remaining={len(tasks) - done} | still running: {still_running}")
        stop_event.set()
    rows = [
        {"level_index": level, "difficulty": difficulty, "result": result, "turn_count": turn_count}
        for level, difficulty, result, turn_count in results
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["level_index", "difficulty", "result", "turn_count"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def plot_results(rows: list[dict], plot_path: Path, difficulties: list[str]) -> None:
    """Plot turn_count vs level_index, one line per difficulty with hardcoded colors."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping plot. pip install matplotlib", file=sys.stderr)
        return
    by_diff: dict[str, list[tuple[int, int]]] = {d: [] for d in difficulties}
    for r in rows:
        by_diff[r["difficulty"]].append((r["level_index"], r["turn_count"]))
    plt.figure()
    for difficulty in difficulties:
        points = sorted(by_diff[difficulty], key=lambda p: p[0])
        if not points:
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        color = DIFFICULTY_COLORS.get(difficulty, "gray")
        plt.plot(xs, ys, "o-", label=difficulty, color=color)
    plt.xlabel("level index")
    plt.ylabel("turn count")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()
    print(f"Saved plot to {plot_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch run ai_playthrough and collect CSV + plot.")
    parser.add_argument("--csv", type=Path, default=Path("playthrough_results.csv"), help="Output CSV path")
    parser.add_argument("--plot", type=Path, default=Path("playthrough_results.png"), help="Output plot path")
    parser.add_argument("--no-plot", action="store_true", help="Skip generating the plot")
    parser.add_argument("--turn", type=int, default=99999, help="Turn interval for ai_playthrough (default: no mid-game output)")
    parser.add_argument("--level-min", type=int, default=0, help="Minimum level index (inclusive)")
    parser.add_argument("--level-max", type=int, default=10, help="Maximum level index (inclusive)")
    parser.add_argument(
        "--difficulties",
        nargs="+",
        default=["average", "hard", "expert", "balancer"],
        choices=["easy", "average", "hard", "expert", "balancer"],
        metavar="DIFF",
        help="AI difficulties to run (default: average hard expert balancer)",
    )
    parser.add_argument(
        "--jobs", "-j",
        type=int,
        default=1,
        metavar="N",
        help="Run up to N games in parallel (default: 1)",
    )
    args = parser.parse_args()
    levels = list(range(args.level_min, args.level_max + 1))
    if not levels:
        print("Error: --level-min must be <= --level-max", file=sys.stderr)
        return 1
    csv_path = args.csv if args.csv.is_absolute() else PROJECT_ROOT / args.csv
    plot_path = args.plot if args.plot.is_absolute() else PROJECT_ROOT / args.plot
    if args.jobs < 1:
        print("Error: --jobs must be >= 1", file=sys.stderr)
        return 1
    print(f"Running playthroughs: levels {args.level_min}-{args.level_max}, difficulties {' '.join(args.difficulties)}, jobs={args.jobs}")
    rows = run_batch(csv_path, levels, args.difficulties, turn_interval=args.turn, jobs=args.jobs)
    print(f"Wrote {len(rows)} rows to {csv_path}")
    if not args.no_plot:
        plot_results(rows, plot_path, args.difficulties)
    return 0


if __name__ == "__main__":
    sys.exit(main())
