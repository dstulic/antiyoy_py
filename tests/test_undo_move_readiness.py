"""Unit tests for undo move readiness restoration."""

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


def create_test_game_state() -> GameState:
    """Create a simple game state for testing."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a red province with a unit
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
        province.set_money(200)
    
    return game_state


def test_undo_move_restores_readiness():
    """Test that undoing a move restores the unit's readiness."""
    game_state = create_test_game_state()
    
    # Find the red province
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Should have a red province"
    
    # Build a unit on hex2 (province hex, so it should be ready)
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
    
    # Verify unit is ready after build
    assert hex2 in game_state.readiness_manager.ready_hexes, "Unit should be ready after build on province hex"
    
    # Move the unit to hex3
    hex3 = game_state.get_hex(2, 0)
    move_cmd = MoveUnitCommand(
        start_hex=hex2,
        finish_hex=hex3,
        color_transfer_enabled=True
    )
    
    is_valid, error = validator.validate(move_cmd, HColor.RED)
    assert is_valid, f"Move should be valid: {error}"
    
    success, error = executor.execute(move_cmd, HColor.RED)
    assert success, f"Move should succeed: {error}"
    
    # Verify unit is NOT ready after move
    assert hex3 not in game_state.readiness_manager.ready_hexes, "Unit should NOT be ready after move"
    assert hex2 not in game_state.readiness_manager.ready_hexes, "Hex2 should not be in ready list (unit moved)"
    
    # Undo the move
    can_undo = game_state.undo_manager.can_undo()
    assert can_undo, "Should be able to undo"
    
    success = game_state.undo_manager.undo()
    assert success, "Undo should succeed"
    
    # Verify unit is ready again after undo
    # After undo, the unit should be back on hex2 and ready
    hex2_after_undo = game_state.get_hex(1, 0)
    assert hex2_after_undo.piece == PieceType.PEASANT, "Unit should be back on hex2 after undo"
    assert hex2_after_undo in game_state.readiness_manager.ready_hexes, "Unit should be ready again after undo"
    
    # Verify hex3 is empty after undo
    hex3_after_undo = game_state.get_hex(2, 0)
    assert hex3_after_undo.piece is None, "Hex3 should be empty after undo"


if __name__ == "__main__":
    test_undo_move_restores_readiness()
    print("✓ test_undo_move_restores_readiness passed")
    print("\nAll tests passed!")
