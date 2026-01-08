"""Integration test for death manager with real game state."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType, EventType
from core.events import EventTurnEnd, EventPieceBuild
from core.core_utils import is_unit
from save_load.decoder import _build_adjacency_graph
from commands.types import BuildPieceCommand
from commands.executor import CommandExecutor
from commands.validator import CommandValidator


def create_test_game_state() -> GameState:
    """Create a minimal game state for testing."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create two adjacent hexes for a province
    hex1 = game_state.add_hex(0, 0, HColor.RED)
    hex1.piece = PieceType.CITY  # City for income
    
    hex2 = game_state.add_hex(1, 0, HColor.RED)  # Adjacent hex (empty, will have knight)
    
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
    
    # Set initial money for province (enough to buy a knight)
    # Knight costs 40, so we need at least 40
    # But we also need to account for negative profit after building
    # Income: 1 (city) + 1 (hex with knight) = 2
    # Consumption after knight: 36 (knight)
    # Profit: 2 - 36 = -34 per turn
    # So if we start with 40, after buying knight (40-40=0), next turn: 0 + (-34) = -34
    # We want to ensure it goes negative enough to trigger death
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            province.set_money(40)  # Enough to buy knight (costs 40)
            break
    
    return game_state


def test_death_manager_integration():
    """Test death manager with real game state - buy knight, go to next turn, verify death."""
    game_state = create_test_game_state()
    
    # Get the red province
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Red province should exist"
    
    # Get the empty hex (where we'll place the knight)
    hex2 = game_state.get_hex(1, 0)
    assert hex2 is not None, "Hex2 should exist"
    assert hex2.piece is None, "Hex2 should be empty"
    
    # Verify initial money
    initial_money = red_province.get_money()
    assert initial_money == 40, f"Initial money should be 40, got {initial_money}"
    
    # Build a knight on hex2 using command executor
    build_command = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.KNIGHT,
        province_id=red_province.get_id()
    )
    
    # Get current entity color
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Current entity should exist"
    player_color = current_entity.color
    
    # Validate command
    validator = CommandValidator(game_state)
    is_valid, error = validator.validate(build_command, player_color)
    assert is_valid, f"Build command should be valid: {error}"
    
    # Execute command
    executor = CommandExecutor(game_state)
    success, error = executor.execute(build_command, player_color)
    assert success, f"Build command should succeed: {error}"
    
    # Verify knight was built
    assert hex2.piece == PieceType.KNIGHT, f"Knight should be built, got {hex2.piece}"
    
    # Verify money was spent (knight costs 40)
    money_after_build = red_province.get_money()
    assert money_after_build == 0, f"Money after build should be 0, got {money_after_build}"
    
    # Calculate expected profit for next turn:
    # Income: 1 (city) + 1 (empty hex with knight) = 2
    # Consumption: 36 (knight)
    # Profit: 2 - 36 = -34
    
    # Now go to next turn
    # First, we need to be on lap > 0 for economics to apply
    game_state.turns_manager.lap = 1
    game_state.turns_manager.turn_index = 0  # RED's turn
    
    # End turn (this will switch to next entity, but we only have one entity)
    # Actually, with one entity, turn_index will go back to 0 and lap will increment
    turn_end_event = EventTurnEnd()
    turn_end_event.set_core_model(game_state)
    game_state.events_manager.apply_event(turn_end_event)
    
    # After turn end:
    # 1. Turn switches (but with one entity, it cycles back)
    # 2. Economics applies profit: 0 + (-34) = -34
    # 3. DeathManager checks current entity's provinces for negative money
    # 4. If negative, resets to 0 and kills units (converts to grave)
    
    # Verify money was reset to 0 (DeathManager should have caught the negative money)
    final_money = red_province.get_money()
    assert final_money == 0, f"Money should be reset to 0 by DeathManager, got {final_money}"
    
    # Verify knight was converted to grave
    assert hex2.piece == PieceType.GRAVE, f"Knight should be converted to grave, got {hex2.piece}"


if __name__ == "__main__":
    test_death_manager_integration()
    print("Test passed!")
