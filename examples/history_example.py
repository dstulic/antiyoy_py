"""Example script to demonstrate event history encoding format."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType
from save_load.decoder import _build_adjacency_graph
from commands.types import BuildPieceCommand, MoveUnitCommand, EndTurnCommand
from commands.executor import CommandExecutor
from commands.validator import CommandValidator


def create_example_game_state() -> GameState:
    """Create an example game state with two players."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create red province
    hex1 = game_state.add_hex(0, 0, HColor.RED)
    hex1.piece = PieceType.CITY
    
    hex2 = game_state.add_hex(1, 0, HColor.RED)
    
    # Create blue province
    hex3 = game_state.add_hex(2, 0, HColor.BLUE)
    hex3.piece = PieceType.CITY
    
    hex4 = game_state.add_hex(3, 0, HColor.BLUE)
    
    # Add a gray hex for movement
    hex5 = game_state.add_hex(4, 0, HColor.GRAY)
    
    _build_adjacency_graph(game_state)
    
    from core.player_entity import PlayerEntity
    red_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    red_player.set_name("RedPlayer")
    blue_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.BLUE)
    blue_player.set_name("BluePlayer")
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(red_player)
    game_state.entities_manager.entities.append(blue_player)
    
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Set money
    for province in game_state.provinces_manager.provinces:
        province.set_money(200)
    
    return game_state


def main():
    """Demonstrate event history encoding."""
    print("Creating example game state...")
    game_state = create_example_game_state()
    history_manager = game_state.history_manager
    
    executor = CommandExecutor(game_state)
    validator = CommandValidator(game_state)
    
    print("\n=== Example Event History ===\n")
    
    # Red player builds a peasant
    print("1. Red player builds a peasant")
    red_province = game_state.provinces_manager.get_province_by_color(HColor.RED)
    hex2 = game_state.get_hex(1, 0)
    
    build_cmd = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd, HColor.RED)
    if is_valid:
        executor.execute(build_cmd, HColor.RED)
        print(f"   Current turn events: {len(history_manager.current_turn_events)}")
    
    # Red player moves the unit
    print("\n2. Red player moves unit to gray hex")
    game_state.readiness_manager.set_ready(hex2, True)
    hex5 = game_state.get_hex(4, 0)
    
    move_cmd = MoveUnitCommand(
        start_hex=hex2,
        finish_hex=hex5,
        color_transfer_enabled=True
    )
    
    is_valid, error = validator.validate(move_cmd, HColor.RED)
    if is_valid:
        executor.execute(move_cmd, HColor.RED)
        print(f"   Current turn events: {len(history_manager.current_turn_events)}")
    
    # Red player ends turn
    print("\n3. Red player ends turn")
    end_turn_cmd = EndTurnCommand()
    is_valid, error = validator.validate(end_turn_cmd, HColor.RED)
    if is_valid:
        executor.execute(end_turn_cmd, HColor.RED)
        print(f"   Completed turn events: {len(history_manager.events_list)}")
        print(f"   Current turn events: {len(history_manager.current_turn_events)}")
    
    # Blue player builds a spearman
    print("\n4. Blue player builds a spearman")
    blue_province = game_state.provinces_manager.get_province_by_color(HColor.BLUE)
    hex4 = game_state.get_hex(3, 0)
    
    build_cmd2 = BuildPieceCommand(
        hex=hex4,
        piece_type=PieceType.SPEARMAN,
        province_id=blue_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd2, HColor.BLUE)
    if is_valid:
        executor.execute(build_cmd2, HColor.BLUE)
        print(f"   Current turn events: {len(history_manager.current_turn_events)}")
    
    # Get encoded history
    print("\n=== Encoded Event History ===\n")
    encoded = history_manager.encode_events_list()
    print(encoded)
    
    print("\n=== Parsed Event History ===\n")
    # Parse the encoded string
    if encoded:
        events = encoded.split(",")
        for i, event_str in enumerate(events, 1):
            if event_str.strip():
                # Split event and author
                if "|author:" in event_str:
                    event_part, author_part = event_str.split("|author:", 1)
                    print(f"Event {i}:")
                    print(f"  Event: {event_part}")
                    print(f"  Author: {author_part}")
                else:
                    print(f"Event {i}: {event_str}")
    
    print("\n=== Event History Details ===\n")
    all_events = history_manager.get_all_events()
    for i, history_event in enumerate(all_events, 1):
        print(f"Event {i}:")
        print(f"  Type: {history_event.event.get_type().value}")
        print(f"  Encoding: {history_event.event.encode()}")
        print(f"  Author Color: {history_event.author_color.value if history_event.author_color else 'None'}")
        print(f"  Author Name: {history_event.author_name or 'None'}")
        print(f"  Full Encoding: {history_event.encode()}")
        print()


if __name__ == "__main__":
    main()
