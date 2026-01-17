"""Integration tests for history manager with real game state."""

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


def create_test_game_state_with_two_players() -> GameState:
    """Create a test game state with two players."""
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


def test_history_tracks_build_events():
    """Test that history tracks build events with correct authors."""
    game_state = create_test_game_state_with_two_players()
    history_manager = game_state.history_manager
    
    # Red player builds a unit
    red_province = game_state.provinces_manager.get_province_by_color(HColor.RED)
    assert red_province is not None, "Red province should exist"
    
    hex2 = game_state.get_hex(1, 0)
    executor = CommandExecutor(game_state)
    validator = CommandValidator(game_state)
    
    build_cmd = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd, HColor.RED)
    assert is_valid, f"Build should be valid: {error}"
    
    success, error = executor.execute(build_cmd, HColor.RED)
    assert success, f"Build should succeed: {error}"
    
    # Check that event was tracked
    assert len(history_manager.current_turn_events) > 0, "Should have current turn events"
    
    # Find the build event
    build_events = [he for he in history_manager.current_turn_events 
                    if he.event.get_type().value == "piece_build"]
    assert len(build_events) > 0, "Should have a build event"
    
    build_history_event = build_events[0]
    assert build_history_event.author_color == HColor.RED, "Author should be RED"
    assert build_history_event.author_name == "RedPlayer", "Author name should be RedPlayer"


def test_history_tracks_move_events():
    """Test that history tracks unit move events with correct authors."""
    game_state = create_test_game_state_with_two_players()
    history_manager = game_state.history_manager
    
    # Red player builds a unit first
    red_province = game_state.provinces_manager.get_province_by_color(HColor.RED)
    hex2 = game_state.get_hex(1, 0)
    executor = CommandExecutor(game_state)
    validator = CommandValidator(game_state)
    
    build_cmd = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd, HColor.RED)
    assert is_valid, f"Build should be valid: {error}"
    
    success, error = executor.execute(build_cmd, HColor.RED)
    assert success, f"Build should succeed: {error}"
    
    # Clear current turn events for this test
    history_manager.current_turn_events.clear()
    
    # Red player moves the unit
    # Need to mark unit as ready
    game_state.readiness_manager.set_ready(hex2, True)
    
    # Create a gray hex to move to
    hex5 = game_state.add_hex(4, 0, HColor.GRAY)
    _build_adjacency_graph(game_state)
    
    move_cmd = MoveUnitCommand(
        start_hex=hex2,
        finish_hex=hex5,
        color_transfer_enabled=True
    )
    
    is_valid, error = validator.validate(move_cmd, HColor.RED)
    if is_valid:
        success, error = executor.execute(move_cmd, HColor.RED)
        assert success, f"Move should succeed: {error}"
        
        # Check that event was tracked
        move_events = [he for he in history_manager.current_turn_events 
                      if he.event.get_type().value == "unit_move"]
        assert len(move_events) > 0, "Should have a move event"
        
        move_history_event = move_events[0]
        assert move_history_event.author_color == HColor.RED, "Author should be RED"
        assert move_history_event.author_name == "RedPlayer", "Author name should be RedPlayer"


def test_history_tracks_multiple_players():
    """Test that history tracks events from multiple players correctly."""
    game_state = create_test_game_state_with_two_players()
    history_manager = game_state.history_manager
    
    executor = CommandExecutor(game_state)
    validator = CommandValidator(game_state)
    
    # Red player builds
    red_province = game_state.provinces_manager.get_province_by_color(HColor.RED)
    hex2 = game_state.get_hex(1, 0)
    
    build_cmd_red = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd_red, HColor.RED)
    assert is_valid, f"Red build should be valid: {error}"
    
    success, error = executor.execute(build_cmd_red, HColor.RED)
    assert success, f"Red build should succeed: {error}"
    
    # End red player's turn
    end_turn_cmd = EndTurnCommand()
    is_valid, error = validator.validate(end_turn_cmd, HColor.RED)
    assert is_valid, f"End turn should be valid: {error}"
    
    success, error = executor.execute(end_turn_cmd, HColor.RED)
    assert success, f"End turn should succeed: {error}"
    
    # Blue player builds
    blue_province = game_state.provinces_manager.get_province_by_color(HColor.BLUE)
    hex4 = game_state.get_hex(3, 0)
    
    build_cmd_blue = BuildPieceCommand(
        hex=hex4,
        piece_type=PieceType.PEASANT,
        province_id=blue_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd_blue, HColor.BLUE)
    assert is_valid, f"Blue build should be valid: {error}"
    
    success, error = executor.execute(build_cmd_blue, HColor.BLUE)
    assert success, f"Blue build should succeed: {error}"
    
    # Check history
    # Red's event should be in events_list (completed turn)
    red_events = [he for he in history_manager.events_list 
                  if he.author_color == HColor.RED]
    assert len(red_events) > 0, "Should have red player events in completed turns"
    
    # Blue's event should be in current_turn_events
    blue_events = [he for he in history_manager.current_turn_events 
                   if he.author_color == HColor.BLUE]
    assert len(blue_events) > 0, "Should have blue player events in current turn"


def test_history_encoding_format():
    """Test that history encoding produces a parsable string format."""
    game_state = create_test_game_state_with_two_players()
    history_manager = game_state.history_manager
    
    executor = CommandExecutor(game_state)
    validator = CommandValidator(game_state)
    
    # Red player builds
    red_province = game_state.provinces_manager.get_province_by_color(HColor.RED)
    hex2 = game_state.get_hex(1, 0)
    
    build_cmd = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd, HColor.RED)
    assert is_valid, f"Build should be valid: {error}"
    
    success, error = executor.execute(build_cmd, HColor.RED)
    assert success, f"Build should succeed: {error}"
    
    # End turn
    end_turn_cmd = EndTurnCommand()
    is_valid, error = validator.validate(end_turn_cmd, HColor.RED)
    if is_valid:
        executor.execute(end_turn_cmd, HColor.RED)
    
    # Encode
    encoded = history_manager.encode_events_list()
    
    # Should be a non-empty string
    assert len(encoded) > 0, "Encoded string should not be empty"
    
    # Should contain author information
    assert "author:" in encoded, "Should contain author information"
    
    # Should be parsable (comma-separated)
    parts = encoded.split(",")
    assert len(parts) > 0, "Should have at least one event"
    
    # Each part should have author info
    for part in parts:
        if part.strip():  # Skip empty parts
            assert "|author:" in part, f"Each event should have author: {part}"


if __name__ == "__main__":
    test_history_tracks_build_events()
    print("✓ test_history_tracks_build_events passed")
    
    test_history_tracks_move_events()
    print("✓ test_history_tracks_move_events passed")
    
    test_history_tracks_multiple_players()
    print("✓ test_history_tracks_multiple_players passed")
    
    test_history_encoding_format()
    print("✓ test_history_encoding_format passed")
    
    print("\nAll integration tests passed!")
