"""Unit tests for defense logic - units, towers, and cities only protect their own province."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType
from save_load.decoder import _build_adjacency_graph
from commands.types import BuildPieceCommand
from commands.executor import CommandExecutor
from commands.validator import CommandValidator


def create_test_game_state_for_defense() -> GameState:
    """Create a game state with two adjacent provinces of the same color."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create two red provinces that are adjacent but separate
    # Layout: 
    # Province 1: (0,0) city, (0,1) empty - vertical
    # Province 2: (2,0) empty, (2,1) tower - vertical, separated by blue hex at (1,0)
    
    hex0 = game_state.add_hex(0, 0, HColor.RED)
    hex0.piece = PieceType.CITY
    
    hex01 = game_state.add_hex(0, 1, HColor.RED)
    
    # Blue hex to separate provinces (between the two red provinces)
    blue_separator = game_state.add_hex(1, 0, HColor.BLUE)
    blue_separator.piece = PieceType.CITY
    
    hex2 = game_state.add_hex(2, 0, HColor.RED)
    
    hex21 = game_state.add_hex(2, 1, HColor.RED)
    hex21.piece = PieceType.TOWER
    
    # Create another blue hex for the blue player
    blue_hex = game_state.add_hex(1, 1, HColor.BLUE)
    blue_hex.piece = PieceType.CITY
    
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
    
    # Verify we have 2 red provinces
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces) == 2, f"Should have 2 red provinces, got {len(red_provinces)}"
    
    # Set money
    for province in game_state.provinces_manager.provinces:
        province.set_money(200)
    
    return game_state


def test_unit_does_not_protect_different_province():
    """Test that a unit next to an enemy unit but in different province doesn't protect the target hex."""
    game_state = create_test_game_state_for_defense()
    
    # Find the two red provinces
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    province1 = red_provinces[0]  # Province with city
    province2 = red_provinces[1]  # Province with tower
    
    # Find hex2 (empty hex in province2, adjacent to province1)
    hex2 = game_state.get_hex(2, 0)
    assert hex2 is not None, "Hex2 should exist"
    assert hex2.get_province() == province2, "Hex2 should be in province2"
    
    # Build a unit in province1, adjacent to hex2
    hex01 = game_state.get_hex(0, 1)
    assert hex01.get_province() == province1, "Hex01 should be in province1"
    
    executor = CommandExecutor(game_state)
    build_cmd = BuildPieceCommand(
        hex=hex01,
        piece_type=PieceType.SPEARMAN,  # Strength 2
        province_id=province1.get_id()
    )
    executor.execute(build_cmd, HColor.RED)
    
    # Verify hex2 is NOT protected by the spearman in province1
    # hex2 should have defense 0 (empty hex) or defense from its own province (tower at hex21)
    defense = game_state.ruleset.get_defense_value_hex(hex2)
    # Defense should come from hex21 (tower in same province), not hex01 (unit in different province)
    assert defense == 2, f"Hex2 defense should be 2 (from tower in same province), got {defense}"
    
    # Verify a peasant (strength 1) can capture hex2 (defense 2, but peasant can't capture)
    # Actually, peasant can't capture hex2 because defense is 2 > 1
    # But a spearman (strength 2) also can't capture because defense 2 is not > 2
    # A baron (strength 3) should be able to capture
    can_capture_peasant = game_state.ruleset.can_hex_be_captured(hex2, 1)
    assert not can_capture_peasant, "Peasant should not be able to capture hex2 (defense 2)"
    
    can_capture_baron = game_state.ruleset.can_hex_be_captured(hex2, 3)
    assert can_capture_baron, "Baron should be able to capture hex2 (defense 2 < 3)"


def test_tower_protects_only_same_province():
    """Test that a tower only protects hexes in its own province."""
    game_state = create_test_game_state_for_defense()
    
    # Find the two red provinces
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    province1 = red_provinces[0]  # Province with city
    province2 = red_provinces[1]  # Province with tower
    
    # Find hex01 (in province1, adjacent to province2 with tower)
    hex01 = game_state.get_hex(0, 1)
    assert hex01.get_province() == province1, "Hex01 should be in province1"
    
    # Find hex21 (tower in province2)
    hex21 = game_state.get_hex(2, 1)
    assert hex21.get_province() == province2, "Hex21 should be in province2"
    assert hex21.piece == PieceType.TOWER, "Hex21 should have a tower"
    
    # hex01 should NOT be protected by the tower in province2 (different province)
    defense = game_state.ruleset.get_defense_value_hex(hex01)
    # Defense should come from hex0 (city in same province), not hex21 (tower in different province)
    assert defense == 1, f"Hex01 defense should be 1 (from city in same province), got {defense}"
    
    # Verify a peasant (strength 1) can capture hex01 (defense 1, but 1 is not > 1)
    can_capture_peasant = game_state.ruleset.can_hex_be_captured(hex01, 1)
    assert not can_capture_peasant, "Peasant should not be able to capture hex01 (defense 1, need > 1)"
    
    # A spearman (strength 2) should be able to capture
    can_capture_spearman = game_state.ruleset.can_hex_be_captured(hex01, 2)
    assert can_capture_spearman, "Spearman should be able to capture hex01 (defense 1 < 2)"


def test_city_protects_only_same_province():
    """Test that a city only protects hexes in its own province."""
    game_state = create_test_game_state_for_defense()
    
    # Find the two red provinces
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    province1 = red_provinces[0]  # Province with city
    province2 = red_provinces[1]  # Province with tower
    
    # Find hex2 (in province2, adjacent to province1 with city)
    hex2 = game_state.get_hex(2, 0)
    assert hex2.get_province() == province2, "Hex2 should be in province2"
    
    # Find hex0 (city in province1)
    hex0 = game_state.get_hex(0, 0)
    assert hex0.get_province() == province1, "Hex0 should be in province1"
    assert hex0.piece == PieceType.CITY, "Hex0 should have a city"
    
    # hex2 should NOT be protected by the city in province1 (different province)
    defense = game_state.ruleset.get_defense_value_hex(hex2)
    # Defense should come from hex21 (tower in same province), not hex0 (city in different province)
    assert defense == 2, f"Hex2 defense should be 2 (from tower in same province), got {defense}"
    
    # Verify a spearman (strength 2) can't capture hex2 (defense 2, but 2 is not > 2)
    can_capture_spearman = game_state.ruleset.can_hex_be_captured(hex2, 2)
    assert not can_capture_spearman, "Spearman should not be able to capture hex2 (defense 2, need > 2)"
    
    # A baron (strength 3) should be able to capture
    can_capture_baron = game_state.ruleset.can_hex_be_captured(hex2, 3)
    assert can_capture_baron, "Baron should be able to capture hex2 (defense 2 < 3)"


def test_unit_protects_same_province():
    """Test that a unit DOES protect hexes in its own province."""
    game_state = create_test_game_state_for_defense()
    
    # Find province1 (with city)
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    province1 = red_provinces[0]
    
    # Build a spearman in province1
    hex01 = game_state.get_hex(0, 1)
    executor = CommandExecutor(game_state)
    build_cmd = BuildPieceCommand(
        hex=hex01,
        piece_type=PieceType.SPEARMAN,  # Strength 2
        province_id=province1.get_id()
    )
    executor.execute(build_cmd, HColor.RED)
    
    # Find an empty hex in province1 (if any) or check hex01 itself
    # hex01 now has a spearman, so it should have defense 2
    defense = game_state.ruleset.get_defense_value_hex(hex01)
    assert defense == 2, f"Hex01 defense should be 2 (from spearman itself), got {defense}"
    
    # Verify a peasant (strength 1) can't capture hex01
    can_capture_peasant = game_state.ruleset.can_hex_be_captured(hex01, 1)
    assert not can_capture_peasant, "Peasant should not be able to capture hex01 (defense 2 > 1)"
    
    # A baron (strength 3) should be able to capture
    can_capture_baron = game_state.ruleset.can_hex_be_captured(hex01, 3)
    assert can_capture_baron, "Baron should be able to capture hex01 (defense 2 < 3)"


if __name__ == "__main__":
    test_unit_does_not_protect_different_province()
    print("✓ test_unit_does_not_protect_different_province passed")
    
    test_tower_protects_only_same_province()
    print("✓ test_tower_protects_only_same_province passed")
    
    test_city_protects_only_same_province()
    print("✓ test_city_protects_only_same_province passed")
    
    test_unit_protects_same_province()
    print("✓ test_unit_protects_same_province passed")
    
    print("\nAll tests passed!")
