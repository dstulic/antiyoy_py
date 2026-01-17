"""Integration tests for saving and loading games."""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType
from save_load.decoder import _build_adjacency_graph
from save_load.encoder import GameStateEncoder
from save_load.decoder import GameStateDecoder
from commands.types import BuildPieceCommand
from commands.executor import CommandExecutor
from commands.validator import CommandValidator


def create_test_game_state() -> GameState:
    """Create a test game state."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a red province with a city and a unit
    hex1 = game_state.add_hex(0, 0, HColor.RED)
    hex1.piece = PieceType.CITY
    
    hex2 = game_state.add_hex(1, 0, HColor.RED)
    
    hex3 = game_state.add_hex(2, 0, HColor.RED)
    
    _build_adjacency_graph(game_state)
    
    from core.player_entity import PlayerEntity
    red_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(red_player)
    
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Set money
    for province in game_state.provinces_manager.provinces:
        province.set_money(150)
    
    return game_state


def test_save_and_load_game_state():
    """Test that saving and loading preserves game state."""
    original_state = create_test_game_state()
    
    # Build a unit before saving
    red_province = None
    for province in original_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Should have a red province"
    
    hex2 = original_state.get_hex(1, 0)
    executor = CommandExecutor(original_state)
    validator = CommandValidator(original_state)
    
    build_cmd = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd, HColor.RED)
    assert is_valid, f"Build should be valid: {error}"
    
    success, error = executor.execute(build_cmd, HColor.RED)
    assert success, f"Build should succeed: {error}"
    
    # Save the game state
    encoder = GameStateEncoder()
    level_code = encoder.encode(original_state)
    
    assert level_code is not None, "Level code should not be None"
    assert len(level_code) > 0, "Level code should not be empty"
    
    # Load the game state
    decoder = GameStateDecoder()
    loaded_state, _ = decoder.decode(level_code)
    
    assert loaded_state is not None, "Loaded state should not be None"
    
    # Verify hexes
    assert len(loaded_state.hexes) == len(original_state.hexes), "Hex count should match"
    
    # Verify pieces
    loaded_hex2 = loaded_state.get_hex(1, 0)
    assert loaded_hex2 is not None, "Loaded hex2 should exist"
    assert loaded_hex2.piece == PieceType.PEASANT, "Loaded hex2 should have a peasant"
    
    # Verify provinces
    loaded_red_provinces = [p for p in loaded_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(loaded_red_provinces) > 0, "Should have red provinces after load"
    
    loaded_red_province = loaded_red_provinces[0]
    assert loaded_red_province.get_money() == 140, f"Province money should be 140 (150 - 10), got {loaded_red_province.get_money()}"
    
    # Verify turn info
    assert loaded_state.turns_manager.turn_index == original_state.turns_manager.turn_index, "Turn index should match"
    assert loaded_state.turns_manager.lap == original_state.turns_manager.lap, "Lap should match"
    
    # Verify readiness state
    assert loaded_hex2 in loaded_state.readiness_manager.ready_hexes, "Unit should be ready after load"


def test_save_and_load_with_multiple_actions():
    """Test saving and loading after multiple game actions."""
    original_state = create_test_game_state()
    
    red_province = None
    for province in original_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    executor = CommandExecutor(original_state)
    validator = CommandValidator(original_state)
    
    # Build a unit
    hex2 = original_state.get_hex(1, 0)
    build_cmd = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.SPEARMAN,
        province_id=red_province.get_id()
    )
    executor.execute(build_cmd, HColor.RED)
    
    # Move the unit
    hex3 = original_state.get_hex(2, 0)
    from commands.types import MoveUnitCommand
    move_cmd = MoveUnitCommand(
        start_hex=hex2,
        finish_hex=hex3,
        color_transfer_enabled=True
    )
    executor.execute(move_cmd, HColor.RED)
    
    # Save
    encoder = GameStateEncoder()
    level_code = encoder.encode(original_state)
    
    # Load
    decoder = GameStateDecoder()
    loaded_state, _ = decoder.decode(level_code)
    
    # Verify unit is on hex3
    loaded_hex3 = loaded_state.get_hex(2, 0)
    assert loaded_hex3.piece == PieceType.SPEARMAN, "Unit should be on hex3 after load"
    
    # Verify hex2 is empty
    loaded_hex2 = loaded_state.get_hex(1, 0)
    assert loaded_hex2.piece is None, "Hex2 should be empty after load"
    
    # Verify unit is not ready (it moved)
    assert loaded_hex3 not in loaded_state.readiness_manager.ready_hexes, "Unit should not be ready after move"


def test_save_and_load_preserves_rng_state():
    """Test that RNG state is preserved across save/load."""
    original_state = create_test_game_state()
    
    # Set RNG state
    original_state.tree_manager.random.seed(12345)
    original_state.set_rng_state(original_state.tree_manager.random.getstate())
    
    # Save
    encoder = GameStateEncoder()
    level_code = encoder.encode(original_state)
    
    # Load
    decoder = GameStateDecoder()
    loaded_state, _ = decoder.decode(level_code)
    
    # Verify RNG state is restored
    assert loaded_state._rng_state is not None, "RNG state should be restored"
    assert loaded_state._rng_state == original_state._rng_state, "RNG state should match"


def test_multiple_save_load_cycles():
    """Test multiple save/load cycles preserve state correctly."""
    original_state = create_test_game_state()
    
    red_province = None
    for province in original_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    executor = CommandExecutor(original_state)
    
    # First action: build unit
    hex2 = original_state.get_hex(1, 0)
    build_cmd = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    executor.execute(build_cmd, HColor.RED)
    
    # First save/load cycle
    encoder = GameStateEncoder()
    decoder = GameStateDecoder()
    level_code1 = encoder.encode(original_state)
    state1, _ = decoder.decode(level_code1)
    
    # Second action: build another unit
    hex3 = state1.get_hex(2, 0)
    red_province1 = None
    for province in state1.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province1 = province
            break
    
    executor1 = CommandExecutor(state1)
    build_cmd2 = BuildPieceCommand(
        hex=hex3,
        piece_type=PieceType.PEASANT,
        province_id=red_province1.get_id()
    )
    executor1.execute(build_cmd2, HColor.RED)
    
    # Second save/load cycle
    level_code2 = encoder.encode(state1)
    state2, _ = decoder.decode(level_code2)
    
    # Verify both units exist
    loaded_hex2 = state2.get_hex(1, 0)
    loaded_hex3 = state2.get_hex(2, 0)
    assert loaded_hex2.piece == PieceType.PEASANT, "First unit should exist"
    assert loaded_hex3.piece == PieceType.PEASANT, "Second unit should exist"


def test_save_and_load_preserves_history():
    """Test that saving and loading preserves history events."""
    original_state = create_test_game_state()
    
    # Build a unit to create history
    red_province = None
    for province in original_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Should have a red province"
    
    hex2 = original_state.get_hex(1, 0)
    executor = CommandExecutor(original_state)
    validator = CommandValidator(original_state)
    
    build_cmd = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd, HColor.RED)
    assert is_valid, f"Build should be valid: {error}"
    
    success, error = executor.execute(build_cmd, HColor.RED)
    assert success, f"Build should succeed: {error}"
    
    # Verify history was created
    history_manager = original_state.history_manager
    assert history_manager is not None, "History manager should exist"
    assert len(history_manager.current_turn_events) > 0, "Should have current turn events"
    
    # Save the game state
    encoder = GameStateEncoder()
    level_code = encoder.encode(original_state)
    
    assert level_code is not None, "Level code should not be None"
    assert "#events_list:" in level_code, "Level code should contain events_list section"
    
    # Load the game state
    decoder = GameStateDecoder()
    loaded_state, _ = decoder.decode(level_code)
    
    assert loaded_state is not None, "Loaded state should not be None"
    assert hasattr(loaded_state, 'history_manager'), "Loaded state should have history_manager"
    assert loaded_state.history_manager is not None, "History manager should not be None"
    
    # Verify history was loaded
    loaded_history = loaded_state.history_manager
    assert len(loaded_history.events_list) > 0, "Should have events in history after load"
    
    # Verify the build event is in history
    build_events = [he for he in loaded_history.events_list 
                    if he.event.get_type().value == "piece_build"]
    assert len(build_events) > 0, "Should have a build event in loaded history"


def test_save_and_load_preserves_history_with_author_info():
    """Test that saving and loading preserves history with author information."""
    original_state = create_test_game_state()
    
    # Set player name
    red_player = None
    for entity in original_state.entities_manager.entities:
        if entity.color == HColor.RED:
            red_player = entity
            red_player.set_name("TestRedPlayer")
            break
    
    assert red_player is not None, "Should have a red player"
    
    # Build a unit to create history
    red_province = None
    for province in original_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    hex2 = original_state.get_hex(1, 0)
    executor = CommandExecutor(original_state)
    validator = CommandValidator(original_state)
    
    build_cmd = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd, HColor.RED)
    assert is_valid, f"Build should be valid: {error}"
    
    success, error = executor.execute(build_cmd, HColor.RED)
    assert success, f"Build should succeed: {error}"
    
    # Verify history has author info
    history_manager = original_state.history_manager
    build_events = [he for he in history_manager.current_turn_events 
                    if he.event.get_type().value == "piece_build"]
    assert len(build_events) > 0, "Should have a build event"
    assert build_events[0].author_color == HColor.RED, "Author color should be RED"
    assert build_events[0].author_name == "TestRedPlayer", "Author name should be preserved"
    
    # Save and load
    encoder = GameStateEncoder()
    level_code = encoder.encode(original_state)
    
    decoder = GameStateDecoder()
    loaded_state, _ = decoder.decode(level_code)
    
    # Verify author info is preserved
    loaded_history = loaded_state.history_manager
    loaded_build_events = [he for he in loaded_history.events_list 
                          if he.event.get_type().value == "piece_build"]
    assert len(loaded_build_events) > 0, "Should have a build event in loaded history"
    assert loaded_build_events[0].author_color == HColor.RED, "Author color should be preserved"
    assert loaded_build_events[0].author_name == "TestRedPlayer", "Author name should be preserved"


def test_save_and_load_preserves_multiple_history_events():
    """Test that saving and loading preserves multiple history events."""
    original_state = create_test_game_state()
    
    red_province = None
    for province in original_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    executor = CommandExecutor(original_state)
    validator = CommandValidator(original_state)
    
    # Build first unit
    hex2 = original_state.get_hex(1, 0)
    build_cmd1 = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd1, HColor.RED)
    assert is_valid, f"Build should be valid: {error}"
    success, error = executor.execute(build_cmd1, HColor.RED)
    assert success, f"Build should succeed: {error}"
    
    # Build second unit
    hex3 = original_state.get_hex(2, 0)
    build_cmd2 = BuildPieceCommand(
        hex=hex3,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd2, HColor.RED)
    assert is_valid, f"Build should be valid: {error}"
    success, error = executor.execute(build_cmd2, HColor.RED)
    assert success, f"Build should succeed: {error}"
    
    # Verify we have multiple events
    history_manager = original_state.history_manager
    build_events = [he for he in history_manager.current_turn_events 
                    if he.event.get_type().value == "piece_build"]
    assert len(build_events) >= 2, "Should have at least 2 build events"
    
    # Save and load
    encoder = GameStateEncoder()
    level_code = encoder.encode(original_state)
    
    decoder = GameStateDecoder()
    loaded_state, _ = decoder.decode(level_code)
    
    # Verify multiple events are preserved
    loaded_history = loaded_state.history_manager
    loaded_build_events = [he for he in loaded_history.events_list 
                          if he.event.get_type().value == "piece_build"]
    assert len(loaded_build_events) >= 2, "Should have at least 2 build events in loaded history"


def test_save_and_load_preserves_history_across_turns():
    """Test that saving and loading preserves history across multiple turns."""
    original_state = create_test_game_state()
    
    red_province = None
    for province in original_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    executor = CommandExecutor(original_state)
    validator = CommandValidator(original_state)
    
    # Build a unit
    hex2 = original_state.get_hex(1, 0)
    build_cmd = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_cmd, HColor.RED)
    assert is_valid, f"Build should be valid: {error}"
    success, error = executor.execute(build_cmd, HColor.RED)
    assert success, f"Build should succeed: {error}"
    
    # End turn to move events to events_list
    from commands.types import EndTurnCommand
    end_turn_cmd = EndTurnCommand()
    is_valid, error = validator.validate(end_turn_cmd, HColor.RED)
    if is_valid:
        executor.execute(end_turn_cmd, HColor.RED)
    
    # Verify events moved to events_list
    history_manager = original_state.history_manager
    assert len(history_manager.events_list) > 0, "Should have events in events_list after turn end"
    assert len(history_manager.current_turn_events) == 0, "Current turn events should be empty after turn end"
    
    # Save and load
    encoder = GameStateEncoder()
    level_code = encoder.encode(original_state)
    
    decoder = GameStateDecoder()
    loaded_state, _ = decoder.decode(level_code)
    
    # Verify history is preserved
    loaded_history = loaded_state.history_manager
    assert len(loaded_history.events_list) > 0, "Should have events in events_list after load"
    assert len(loaded_history.events_list) == len(history_manager.events_list), "Event count should match"


def test_save_and_load_empty_history():
    """Test that saving and loading works correctly with empty history."""
    original_state = create_test_game_state()
    
    # Don't perform any actions - history should be empty
    history_manager = original_state.history_manager
    assert len(history_manager.events_list) == 0, "Events list should be empty"
    assert len(history_manager.current_turn_events) == 0, "Current turn events should be empty"
    
    # Save and load
    encoder = GameStateEncoder()
    level_code = encoder.encode(original_state)
    
    decoder = GameStateDecoder()
    loaded_state, _ = decoder.decode(level_code)
    
    # Verify empty history is handled correctly
    loaded_history = loaded_state.history_manager
    assert loaded_history is not None, "History manager should exist"
    # Empty history is acceptable - just verify it doesn't crash


if __name__ == "__main__":
    test_save_and_load_game_state()
    print("✓ test_save_and_load_game_state passed")
    
    test_save_and_load_with_multiple_actions()
    print("✓ test_save_and_load_with_multiple_actions passed")
    
    test_save_and_load_preserves_rng_state()
    print("✓ test_save_and_load_preserves_rng_state passed")
    
    test_multiple_save_load_cycles()
    print("✓ test_multiple_save_load_cycles passed")
    
    test_save_and_load_preserves_history()
    print("✓ test_save_and_load_preserves_history passed")
    
    test_save_and_load_preserves_history_with_author_info()
    print("✓ test_save_and_load_preserves_history_with_author_info passed")
    
    test_save_and_load_preserves_multiple_history_events()
    print("✓ test_save_and_load_preserves_multiple_history_events passed")
    
    test_save_and_load_preserves_history_across_turns()
    print("✓ test_save_and_load_preserves_history_across_turns passed")
    
    test_save_and_load_empty_history()
    print("✓ test_save_and_load_empty_history passed")
    
    print("\nAll tests passed!")
