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


def create_test_game_state_with_multiple_players() -> GameState:
    """Create a test game state with multiple players for win/lose condition tests."""
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
    
    # Add some neutral hexes
    hex5 = game_state.add_hex(4, 0, HColor.GRAY)
    hex6 = game_state.add_hex(5, 0, HColor.GRAY)
    hex7 = game_state.add_hex(6, 0, HColor.GRAY)
    
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


def test_player_loses_when_last_province_lost():
    """Test that a player loses when they lose their last province."""
    game_state = create_test_game_state_with_multiple_players()
    
    # Initially, both players should be alive
    assert not game_state.game_end_manager.check_player_lose(HColor.RED), "Red player should not be dead initially"
    assert not game_state.game_end_manager.check_player_lose(HColor.BLUE), "Blue player should not be dead initially"
    
    # Get red province
    red_province = game_state.provinces_manager.get_province_by_color(HColor.RED)
    assert red_province is not None, "Red province should exist"
    
    # Capture all red hexes by changing their color to blue
    hex1 = game_state.get_hex(0, 0)
    hex2 = game_state.get_hex(1, 0)
    
    # Simulate capture by changing color
    from core.events import EventHexChangeColor
    from core.enums import EventType
    
    # Store previous color for the reduction worker
    game_state.provinces_manager._previous_color = {}
    game_state.provinces_manager._previous_color[hex1] = HColor.RED
    game_state.provinces_manager._previous_color[hex2] = HColor.RED
    
    # Change hex colors to blue (simulating capture)
    hex1.color = HColor.BLUE
    hex2.color = HColor.BLUE
    
    # Rebuild provinces
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Update dead players
    game_state.game_end_manager._update_dead_players()
    
    # Red player should now be dead (no provinces)
    assert game_state.game_end_manager.check_player_lose(HColor.RED), "Red player should be dead after losing last province"
    assert game_state.game_end_manager.is_player_dead(HColor.RED), "Red player should be marked as dead"
    
    # Blue player should still be alive
    assert not game_state.game_end_manager.check_player_lose(HColor.BLUE), "Blue player should still be alive"
    assert not game_state.game_end_manager.is_player_dead(HColor.BLUE), "Blue player should not be marked as dead"


def test_player_wins_by_owning_80_percent_of_hexes():
    """Test that a player wins when they own 80% or more of all hexes."""
    game_state = create_test_game_state_with_multiple_players()
    
    # Initially, red player should not have won
    assert not game_state.game_end_manager.check_player_win(HColor.RED), "Red player should not have won initially"
    
    # Total hexes: 7 (2 red, 2 blue, 3 gray)
    # For red to own 80%, they need: 7 * 0.8 = 5.6, so at least 6 hexes
    # Currently red owns 2 hexes (28.6%)
    
    # Add more hexes and make them red (in provinces)
    # We need red to own at least 6 out of 7 hexes (85.7%)
    # So we need to capture 4 more hexes (blue's 2 + 2 gray)
    
    # Capture blue hexes
    hex3 = game_state.get_hex(2, 0)
    hex4 = game_state.get_hex(3, 0)
    
    # Store previous colors
    game_state.provinces_manager._previous_color = {}
    game_state.provinces_manager._previous_color[hex3] = HColor.BLUE
    game_state.provinces_manager._previous_color[hex4] = HColor.BLUE
    
    # Change to red
    hex3.color = HColor.RED
    hex4.color = HColor.RED
    
    # Capture 2 gray hexes by adding them to red province
    hex5 = game_state.get_hex(4, 0)
    hex6 = game_state.get_hex(5, 0)
    
    game_state.provinces_manager._previous_color[hex5] = HColor.GRAY
    game_state.provinces_manager._previous_color[hex6] = HColor.GRAY
    
    hex5.color = HColor.RED
    hex6.color = HColor.RED
    
    # Rebuild provinces to include new red hexes
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Now red owns: 2 (original) + 2 (from blue) + 2 (from gray) = 6 hexes
    # Total hexes: 7
    # Percentage: 6/7 = 85.7% >= 80%
    
    # Update dead players
    game_state.game_end_manager._update_dead_players()
    
    # Red player should have won
    assert game_state.game_end_manager.check_player_win(HColor.RED), "Red player should win with 80%+ of hexes"
    
    # Blue player should not have won
    assert not game_state.game_end_manager.check_player_win(HColor.BLUE), "Blue player should not have won"


def test_player_wins_when_all_opponents_dead():
    """Test that a player wins when all opponents are dead (have no provinces)."""
    game_state = create_test_game_state_with_multiple_players()
    
    # Initially, neither player should have won
    assert not game_state.game_end_manager.check_player_win(HColor.RED), "Red player should not have won initially"
    assert not game_state.game_end_manager.check_player_win(HColor.BLUE), "Blue player should not have won initially"
    
    # Capture all blue hexes by changing their color to red
    hex3 = game_state.get_hex(2, 0)
    hex4 = game_state.get_hex(3, 0)
    
    # Store previous colors
    game_state.provinces_manager._previous_color = {}
    game_state.provinces_manager._previous_color[hex3] = HColor.BLUE
    game_state.provinces_manager._previous_color[hex4] = HColor.BLUE
    
    # Change to red
    hex3.color = HColor.RED
    hex4.color = HColor.RED
    
    # Rebuild provinces
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Update dead players
    game_state.game_end_manager._update_dead_players()
    
    # Blue player should be dead (no provinces)
    assert game_state.game_end_manager.is_player_dead(HColor.BLUE), "Blue player should be dead"
    assert game_state.game_end_manager.check_player_lose(HColor.BLUE), "Blue player should have lost"
    
    # Red player should have won (all opponents dead)
    assert game_state.game_end_manager.check_player_win(HColor.RED), "Red player should win when all opponents are dead"
    
    # Blue player should not have won
    assert not game_state.game_end_manager.check_player_win(HColor.BLUE), "Blue player should not have won"


def test_player_does_not_win_with_less_than_80_percent():
    """Test that a player does not win with less than 80% of hexes."""
    game_state = create_test_game_state_with_multiple_players()
    
    # Total hexes: 7 (2 red, 2 blue, 3 gray)
    # Capture 1 blue hex (red now owns 3 out of 7 = 42.9%)
    hex3 = game_state.get_hex(2, 0)
    
    game_state.provinces_manager._previous_color = {}
    game_state.provinces_manager._previous_color[hex3] = HColor.BLUE
    hex3.color = HColor.RED
    
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    game_state.game_end_manager._update_dead_players()
    
    # Red should not have won (only 42.9%, less than 80%)
    assert not game_state.game_end_manager.check_player_win(HColor.RED), "Red player should not win with less than 80%"
    
    # Blue still has 1 hex, so not dead
    assert not game_state.game_end_manager.is_player_dead(HColor.BLUE), "Blue player should not be dead"


if __name__ == "__main__":
    test_game_not_ended_initially()
    print("✓ test_game_not_ended_initially passed")
    
    test_game_ends_when_all_provinces_one_color()
    print("✓ test_game_ends_when_all_provinces_one_color passed")
    
    test_no_turns_after_game_ends()
    print("✓ test_no_turns_after_game_ends passed")
    
    test_player_loses_when_last_province_lost()
    print("✓ test_player_loses_when_last_province_lost passed")
    
    test_player_wins_by_owning_80_percent_of_hexes()
    print("✓ test_player_wins_by_owning_80_percent_of_hexes passed")
    
    test_player_wins_when_all_opponents_dead()
    print("✓ test_player_wins_when_all_opponents_dead passed")
    
    test_player_does_not_win_with_less_than_80_percent()
    print("✓ test_player_does_not_win_with_less_than_80_percent passed")
    
    print("\nAll tests passed!")
