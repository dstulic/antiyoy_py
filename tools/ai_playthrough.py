#!/usr/bin/env python3
"""
Command-line utility to run a campaign level with the "human" player controlled by an AI.

Usage:
    python tools/ai_playthrough.py --level 1 --ai expert
    python -m tools.ai_playthrough -l 0 -a hard

Prints turn count and a hex-ownership table every N turns (default 20); when the game ends, prints the result and exits.
"""

import argparse
import sys

# Ensure project root (antiyoy_py) is on path when run from tools/
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from campaign.levels import get_level_code
from save_load.decoder import GameStateDecoder
from save_load.replay import save_replay
from core.game_state import GameState
from core.game_manager import GameManager, GameMode
from core.enums import EventType, Difficulty


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Run a campaign level with the human player played by an AI."
    )
    parser.add_argument(
        "--level", "-l",
        type=int,
        default=1,
        help="Campaign level index (default: 1)",
    )
    parser.add_argument(
        "--ai", "-a",
        type=str,
        default="expert",
        choices=[d.value for d in Difficulty],
        help="AI difficulty to use for the human player (default: expert)",
    )
    parser.add_argument(
        "--turn", "-t",
        type=int,
        default=20,
        help="Print turn count and hex table every N turns (default: 20)",
    )
    return parser.parse_args()


def _print_hex_table(game_state: GameState) -> None:
    """Print a small table of player, hexes, and %% (total hexes, victory at 80%%)."""
    entities = game_state.entities_manager.entities or []
    if not entities:
        return
    total_hexes = game_state.get_hex_ownership_stats(entities[0].color)["total_hexes"]
    rows = []
    for entity in entities:
        stats = game_state.get_hex_ownership_stats(entity.color)
        label = "Human" if entity.is_human() else "AI"
        name = f"{entity.color.value} ({label})"
        rows.append((name, stats["player_hexes"], stats["percentage"]))
    col_player = max(14, max(len(r[0]) for r in rows))
    col_hexes = 5
    col_pct = 5
    sep = "  "
    header = f"  {'Player':<{col_player}}  {'Hexes':>{col_hexes}}  {'%':>{col_pct}}"
    line = "  " + "-" * col_player + sep + "-" * col_hexes + sep + "-" * col_pct
    print(line)
    print(header)
    print(line)
    for name, hexes, pct in rows:
        print(f"  {name:<{col_player}}  {hexes:>{col_hexes}}  {pct:>{col_pct}.1f}")
    print(line)
    print(f"  (total hexes: {total_hexes}, victory at 80%)")
    print()


def _init_game(level_index: int) -> tuple[GameState, GameManager] | None:
    """Decode level, init money/fog/difficulties; return (game_state, game_manager) or None."""
    level_code = get_level_code(level_index)
    if not level_code or level_code == "-":
        print(f"Error: No level code for level {level_index}.", file=sys.stderr)
        return None

    decoder = GameStateDecoder()
    result = decoder.decode(level_code)
    if isinstance(result, tuple):
        game_state, _ = result
    else:
        game_state = result

    if game_state is None:
        print("Error: Failed to decode game state.", file=sys.stderr)
        return None

    from core.events import SYSTEM_AUTHOR
    # Starting money for provinces that have 0
    for province in game_state.provinces_manager.provinces:
        if province.get_money() == 0:
            event = game_state.events_manager.factory.create_event(EventType.SET_MONEY, author=SYSTEM_AUTHOR)
            if event:
                event.province_id = province.get_id()
                event.money = 10
                game_state.events_manager.apply_event(event)

    if game_state.fog_of_war_manager and game_state.fog_of_war_manager.enabled:
        game_state.fog_of_war_manager.apply_update()

    # Apply campaign default difficulty for all AI entities (human stays human)
    from campaign.manager import CampaignManager
    campaign_manager = CampaignManager()
    default_difficulty = campaign_manager.get_difficulty(level_index)
    for entity in (game_state.entities_manager.entities or []):
        if entity.is_artificial_intelligence():
            entity.set_ai_difficulty(default_difficulty)

    game_manager = GameManager(game_state, GameMode.CAMPAIGN)
    return game_state, game_manager


def _run_game(
    game_state: GameState,
    game_manager: GameManager,
    human_ai_difficulty: Difficulty,
    turn_interval: int,
    level_index: int,
) -> None:
    """Run the game loop: human is played by an AI; every turn_interval turns print count and hex table; print result on end."""
    turn_count = 0
    ai_manager = game_state.ai_manager
    game_end_manager = game_state.game_end_manager
    hex_count = len(game_state.hexes)
    n_entities = len(game_state.entities_manager.entities or [])
    max_turns = (hex_count * 10 * n_entities) if n_entities else 1

    while True:
        game_manager.update()
        if game_end_manager.is_game_ended():
            break

        if turn_count >= max_turns:
            print(f"Max turns reached ({max_turns}).", file=sys.stderr)
            break

        current_entity = game_state.entities_manager.get_current_entity()
        if not current_entity:
            break

        if current_entity.is_human():
            ai = ai_manager.get_balancer_ai()
            if ai:
                ai.set_difficulty(human_ai_difficulty)
                ai.perform()
            else:
                print("Warning: No balancer AI available; skipping human turn.", file=sys.stderr)
                from commands.types import EndTurnCommand
                from commands.executor import CommandExecutor
                executor = CommandExecutor(game_state)
                executor.execute(EndTurnCommand(), current_entity.color)
        elif current_entity.is_artificial_intelligence():
            ai_manager.process_ai_turn()
        else:
            break

        turn_count += 1
        if turn_interval > 0 and turn_count % turn_interval == 0:
            print(f"Turn {turn_count}")
            _print_hex_table(game_state)

    # Final state and result (from the human-played-by-AI perspective)
    game_manager.update()
    winner_entity = game_end_manager.get_winner()
    human_entity = None
    for e in (game_state.entities_manager.entities or []):
        if e.is_human():
            human_entity = e
            break
    if winner_entity:
        if human_entity and winner_entity.color == human_entity.color:
            result = "win"
        else:
            result = "loss"
    else:
        result = "other"
    print(f"\nresult: {result}")
    print(f"turn count: {turn_count}")

    # Save replay when game end condition is reached
    source_details = f"{level_index}-{human_ai_difficulty.value}-{turn_count}"
    replays_dir = PROJECT_ROOT / "replays"
    saved_path = save_replay(
        game_state,
        source="ai",
        source_details=source_details,
        campaign_level_index=level_index,
        replays_dir=str(replays_dir),
    )
    if saved_path:
        print(f"replay saved: {saved_path}")
    else:
        print("warning: failed to save replay", file=sys.stderr)


def main() -> int:
    args = _parse_args()
    level_index = args.level
    try:
        human_difficulty = Difficulty(args.ai)
    except ValueError:
        print(f"Error: Invalid difficulty '{args.ai}'. Use: easy, average, hard, expert, balancer.", file=sys.stderr)
        return 1

    pair = _init_game(level_index)
    if pair is None:
        return 1
    game_state, game_manager = pair

    _run_game(game_state, game_manager, human_difficulty, turn_interval=args.turn, level_index=level_index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
