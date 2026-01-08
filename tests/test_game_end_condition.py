"""Unit tests for game end condition."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType
from save_load.decoder import _build_adjacency_graph
from commands.types import BuildPieceCommand, EndTurnCommand
from commands.executor import CommandExecutor
from commands.validator import CommandValidator


def create_test_game_state() -> GameState:
    """Create a test game state with two players."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create two separate provinces (red and blue)
    hex1 = game_state.add_hex(0, 0, HColor.RED)
    hex1.piece = PieceType.CITY
    
    hex2 = game_state.add_hex(1, 0, HColor.RED)
    
    hex3 = game_state.add_hex(2, 0, HColor.BLUE)
    hex3.piece = PieceType.CITY
    
    hex4 = game_state.add_hex(3, 0, HColor.BLUE)
    
    _build_adjacency_graph(game_state)
    
    from core.player_entity import PlayerEntity
    red_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    blue_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.BLUE)
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


def test_game_not_ended_initially():
    """Test that game is not ended initially."""
    game_state = create_test_game_state()
    
    assert not game_state.game_end_manager.is_game_ended(), "Game should not be ended initially"
    assert game_state.game_end_manager.can_make_turn(), "Should be able to make turns initially"
    assert game_state.game_end_manager.get_winner() is None, "Should have no winner initially"


def test_game_ends_when_all_provinces_one_color():
    """Test that game ends when all provinces are one color."""
    game_state = create_test_game_state()
    
    # Initially, we have red and blue provinces - game should not be ended
    assert not game_state.game_end_manager.is_game_ended(), "Game should not be ended with multiple colors"
    
    # Capture all blue hexes with red units to make all provinces red
    blue_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.BLUE]
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    
    assert len(blue_provinces) > 0, "Should have blue provinces"
    assert len(red_provinces) > 0, "Should have red provinces"
    
    # Manually change hex colors to red to simulate all provinces being red
    hex3 = game_state.get_hex(2, 0)
    hex4 = game_state.get_hex(3, 0)
    
    # Directly change colors (simulating capture)
    hex3.color = HColor.RED
    hex4.color = HColor.RED
    
    # Rebuild provinces to reflect color changes
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Manually trigger game end check by calling the method directly
    # (normally this would be triggered by TURN_END event)
    game_state.game_end_manager._check_game_end()
    
    # Game should now be ended
    assert game_state.game_end_manager.is_game_ended(), "Game should be ended when all provinces are one color"
    assert not game_state.game_end_manager.can_make_turn(), "Should not be able to make turns after game ends"
    
    winner = game_state.game_end_manager.get_winner()
    assert winner is not None, "Should have a winner"
    assert winner.color == HColor.RED, "Winner should be red player"


def test_no_turns_after_game_ends():
    """Test that no turns can be made after game ends."""
    game_state = create_test_game_state()
    
    # Manually set game as ended
    game_state.game_end_manager.game_ended = True
    game_state.game_end_manager.winner_color = HColor.RED
    
    validator = CommandValidator(game_state)
    
    # Try to build a unit - should fail
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    if red_provinces:
        hex2 = game_state.get_hex(1, 0)
        build_cmd = BuildPieceCommand(
            hex=hex2,
            piece_type=PieceType.PEASANT,
            province_id=red_provinces[0].get_id()
        )
        
        is_valid, error = validator.validate(build_cmd, HColor.RED)
        assert not is_valid, "Should not be able to build after game ends"
        assert "Game has ended" in error, f"Error should mention game ended, got: {error}"
    
    # Try to end turn - should fail
    end_turn_cmd = EndTurnCommand()
    is_valid, error = validator.validate(end_turn_cmd, HColor.RED)
    assert not is_valid, "Should not be able to end turn after game ends"
    assert "Game has ended" in error, f"Error should mention game ended, got: {error}"


if __name__ == "__main__":
    test_game_not_ended_initially()
    print("✓ test_game_not_ended_initially passed")
    
    test_game_ends_when_all_provinces_one_color()
    print("✓ test_game_ends_when_all_provinces_one_color passed")
    
    test_no_turns_after_game_ends()
    print("✓ test_no_turns_after_game_ends passed")
    
    print("\nAll tests passed!")
