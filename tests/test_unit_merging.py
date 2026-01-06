"""Integration tests for unit merging functionality."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType
from save_load.decoder import _build_adjacency_graph
from commands.types import BuildPieceCommand, MoveUnitCommand
from commands.executor import CommandExecutor
from commands.validator import CommandValidator
from core.core_utils import get_merge_result, get_strength


def create_test_game_state_for_merging() -> GameState:
    """Create a game state with a province and units for testing merging."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a province with a city and some units
    # Hex layout:
    # (0,0) - city
    # (1,0) - empty (will have unit)
    # (2,0) - empty (will have unit to merge with)
    # (3,0) - empty (for moving unit)
    
    hex_city = game_state.add_hex(0, 0, HColor.RED)
    hex_city.piece = PieceType.CITY
    
    hex1 = game_state.add_hex(1, 0, HColor.RED)  # Will have a peasant
    hex2 = game_state.add_hex(2, 0, HColor.RED)  # Will have a peasant to merge with
    hex3 = game_state.add_hex(3, 0, HColor.RED)  # For moving unit
    
    # Build adjacency graph
    _build_adjacency_graph(game_state)
    
    # Create player entity
    from core.player_entity import PlayerEntity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    player.set_name("TestPlayer")
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)
    
    # Build provinces
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Set money for province
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            province.set_money(200)  # Enough to build multiple units
            break
    
    return game_state


def test_merge_on_build():
    """Test merging units when building a new unit on an existing unit."""
    game_state = create_test_game_state_for_merging()
    
    # Get the red province
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Red province should exist"
    
    # Get hexes
    hex_city = game_state.get_hex(0, 0)
    hex1 = game_state.get_hex(1, 0)
    hex2 = game_state.get_hex(2, 0)
    
    # Build a peasant on hex1
    build_command1 = BuildPieceCommand(
        hex=hex1,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Current entity should exist"
    player_color = current_entity.color
    
    validator = CommandValidator(game_state)
    executor = CommandExecutor(game_state)
    
    is_valid, error = validator.validate(build_command1, player_color)
    assert is_valid, f"First build should be valid: {error}"
    
    success, error = executor.execute(build_command1, player_color)
    assert success, f"First build should succeed: {error}"
    
    # Verify peasant was built
    assert hex1.piece == PieceType.PEASANT, f"Hex1 should have peasant, got {hex1.piece}"
    assert hex1.has_unit(), "Hex1 should have a unit"
    
    # Build another peasant on hex2
    build_command2 = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_command2, player_color)
    assert is_valid, f"Second build should be valid: {error}"
    
    success, error = executor.execute(build_command2, player_color)
    assert success, f"Second build should succeed: {error}"
    
    # Verify second peasant was built
    assert hex2.piece == PieceType.PEASANT, f"Hex2 should have peasant, got {hex2.piece}"
    
    # Now build a peasant on hex2 (should merge: peasant + peasant = spearman)
    initial_money = red_province.get_money()
    build_command3 = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_command3, player_color)
    assert is_valid, f"Merge build should be valid: {error}"
    
    success, error = executor.execute(build_command3, player_color)
    assert success, f"Merge build should succeed: {error}"
    
    # Verify merge happened: peasant + peasant = spearman (strength 1 + 1 = 2)
    assert hex2.piece == PieceType.SPEARMAN, f"Hex2 should have spearman after merge, got {hex2.piece}"
    
    # Verify money was deducted (peasant costs 10)
    assert red_province.get_money() == initial_money - 10, f"Money should be deducted for merge build"
    
    # Verify hex1 still has its peasant (not affected by merge)
    assert hex1.piece == PieceType.PEASANT, f"Hex1 should still have peasant, got {hex1.piece}"


def test_merge_on_move():
    """Test merging units when moving a unit onto another unit."""
    game_state = create_test_game_state_for_merging()
    
    # Get the red province
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Red province should exist"
    
    # Get hexes
    hex1 = game_state.get_hex(1, 0)
    hex2 = game_state.get_hex(2, 0)
    hex3 = game_state.get_hex(3, 0)
    
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Current entity should exist"
    player_color = current_entity.color
    
    validator = CommandValidator(game_state)
    executor = CommandExecutor(game_state)
    
    # Build a peasant on hex1
    build_command1 = BuildPieceCommand(
        hex=hex1,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_command1, player_color)
    assert is_valid, f"First build should be valid: {error}"
    
    success, error = executor.execute(build_command1, player_color)
    assert success, f"First build should succeed: {error}"
    
    # Build a peasant on hex2
    build_command2 = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_command2, player_color)
    assert is_valid, f"Second build should be valid: {error}"
    
    success, error = executor.execute(build_command2, player_color)
    assert success, f"Second build should succeed: {error}"
    
    # Verify both peasants exist
    assert hex1.piece == PieceType.PEASANT, f"Hex1 should have peasant, got {hex1.piece}"
    assert hex2.piece == PieceType.PEASANT, f"Hex2 should have peasant, got {hex2.piece}"
    
    # Store unit IDs before merge
    hex1_unit_id = hex1.unit_id
    hex2_unit_id = hex2.unit_id
    
    # Move hex1 unit to hex2 (should merge: peasant + peasant = spearman)
    move_command = MoveUnitCommand(
        start_hex=hex1,
        finish_hex=hex2,
        color_transfer_enabled=True
    )
    
    is_valid, error = validator.validate(move_command, player_color)
    assert is_valid, f"Merge move should be valid: {error}"
    
    success, error = executor.execute(move_command, player_color)
    assert success, f"Merge move should succeed: {error}"
    
    # Verify merge happened
    assert hex1.piece is None, f"Hex1 should be empty after merge, got {hex1.piece}"
    assert hex1.unit_id == -1, f"Hex1 should have no unit_id after merge, got {hex1.unit_id}"
    assert hex2.piece == PieceType.SPEARMAN, f"Hex2 should have spearman after merge, got {hex2.piece}"
    assert hex2.unit_id != -1, f"Hex2 should have a unit_id after merge"
    assert hex2.unit_id != hex1_unit_id, f"Hex2 should have a new unit_id after merge"
    assert hex2.unit_id != hex2_unit_id, f"Hex2 should have a new unit_id after merge"
    
    # Verify both hexes are still in the same province
    assert hex1.get_province() == red_province, "Hex1 should still be in province"
    assert hex2.get_province() == red_province, "Hex2 should still be in province"


def test_merge_peasant_spearman():
    """Test merging peasant + spearman = baron (strength 1 + 2 = 3)."""
    game_state = create_test_game_state_for_merging()
    
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Red province should exist"
    
    hex1 = game_state.get_hex(1, 0)
    hex2 = game_state.get_hex(2, 0)
    
    current_entity = game_state.entities_manager.get_current_entity()
    player_color = current_entity.color
    
    validator = CommandValidator(game_state)
    executor = CommandExecutor(game_state)
    
    # Build a peasant on hex1
    build_command1 = BuildPieceCommand(
        hex=hex1,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    executor.execute(build_command1, player_color)
    
    # Build a spearman on hex2
    build_command2 = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.SPEARMAN,
        province_id=red_province.get_id()
    )
    executor.execute(build_command2, player_color)
    
    # Verify initial state
    assert hex1.piece == PieceType.PEASANT, "Hex1 should have peasant"
    assert hex2.piece == PieceType.SPEARMAN, "Hex2 should have spearman"
    
    # Build a peasant on hex2 (should merge: peasant + spearman = baron)
    build_command3 = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    success, error = executor.execute(build_command3, player_color)
    assert success, f"Merge build should succeed: {error}"
    
    # Verify merge: peasant (1) + spearman (2) = baron (3)
    assert hex2.piece == PieceType.BARON, f"Hex2 should have baron after merge, got {hex2.piece}"


def test_merge_spearman_spearman():
    """Test merging spearman + spearman = knight (strength 2 + 2 = 4)."""
    game_state = create_test_game_state_for_merging()
    
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Red province should exist"
    
    hex1 = game_state.get_hex(1, 0)
    hex2 = game_state.get_hex(2, 0)
    
    current_entity = game_state.entities_manager.get_current_entity()
    player_color = current_entity.color
    
    validator = CommandValidator(game_state)
    executor = CommandExecutor(game_state)
    
    # Build a spearman on hex1
    build_command1 = BuildPieceCommand(
        hex=hex1,
        piece_type=PieceType.SPEARMAN,
        province_id=red_province.get_id()
    )
    executor.execute(build_command1, player_color)
    
    # Build a spearman on hex2
    build_command2 = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.SPEARMAN,
        province_id=red_province.get_id()
    )
    executor.execute(build_command2, player_color)
    
    # Verify initial state
    assert hex1.piece == PieceType.SPEARMAN, "Hex1 should have spearman"
    assert hex2.piece == PieceType.SPEARMAN, "Hex2 should have spearman"
    
    # Move spearman to spearman (should merge: spearman + spearman = knight)
    move_command = MoveUnitCommand(
        start_hex=hex1,
        finish_hex=hex2,
        color_transfer_enabled=True
    )
    
    success, error = executor.execute(move_command, player_color)
    assert success, f"Merge move should succeed: {error}"
    
    # Verify merge: spearman (2) + spearman (2) = knight (4, max strength)
    assert hex2.piece == PieceType.KNIGHT, f"Hex2 should have knight after merge, got {hex2.piece}"
    assert hex1.piece is None, "Hex1 should be empty after merge"


if __name__ == "__main__":
    test_merge_on_build()
    print("✓ test_merge_on_build passed")
    
    test_merge_on_move()
    print("✓ test_merge_on_move passed")
    
    test_merge_peasant_spearman()
    print("✓ test_merge_peasant_spearman passed")
    
    test_merge_spearman_spearman()
    print("✓ test_merge_spearman_spearman passed")
    
    print("\nAll tests passed!")
