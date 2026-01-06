"""Unit tests for province merging with city handling."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType, EventType
from core.events import EventHexChangeColor, EventPieceDelete, EventPieceBuild
from save_load.decoder import _build_adjacency_graph
from commands.types import BuildPieceCommand
from commands.executor import CommandExecutor
from commands.validator import CommandValidator


def create_test_game_state_with_two_provinces() -> GameState:
    """Create a game state with two separate provinces, each with a city."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create two separate provinces with a gap between them
    # Province 1: hexes at (0,0) and (0,1) - city at (0,0)
    hex1 = game_state.add_hex(0, 0, HColor.RED)
    hex1.piece = PieceType.CITY
    
    hex2 = game_state.add_hex(0, 1, HColor.RED)  # Empty hex
    
    # Gap: hex at (1,0) will be gray initially
    hex_gap = game_state.add_hex(1, 0, HColor.GRAY)  # Gap hex
    
    # Province 2: hexes at (2,0) and (2,1) - city at (2,0)
    hex3 = game_state.add_hex(2, 0, HColor.RED)
    hex3.piece = PieceType.CITY
    
    hex4 = game_state.add_hex(2, 1, HColor.RED)  # Empty hex
    
    # Build adjacency graph
    _build_adjacency_graph(game_state)
    
    # Create player entity
    from core.player_entity import PlayerEntity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    player.set_name("TestPlayer")
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)
    
    # Build provinces (should create two separate provinces due to gray gap)
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    return game_state


def test_province_merge_removes_extra_cities():
    """Test that when two provinces merge, only one city is kept."""
    game_state = create_test_game_state_with_two_provinces()
    
    # Verify we have two separate provinces initially
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces) == 2, f"Should have 2 provinces initially, got {len(red_provinces)}"
    
    # Count cities in each province
    province1_cities = sum(1 for hex in red_provinces[0].get_hexes() if hex.piece == PieceType.CITY)
    province2_cities = sum(1 for hex in red_provinces[1].get_hexes() if hex.piece == PieceType.CITY)
    assert province1_cities == 1, f"Province 1 should have 1 city, got {province1_cities}"
    assert province2_cities == 1, f"Province 2 should have 1 city, got {province2_cities}"
    
    # Now merge the provinces by building a unit on the gap hex
    # This will change the gap hex from gray to red and trigger a merge
    hex_gap = game_state.get_hex(1, 0)
    assert hex_gap is not None, "Gap hex should exist"
    assert hex_gap.color == HColor.GRAY, "Gap hex should be gray initially"
    
    # Verify adjacency - gap hex should be adjacent to hex1 (0,0) and hex3 (2,0)
    hex1 = game_state.get_hex(0, 0)
    hex3 = game_state.get_hex(2, 0)
    assert hex1 in hex_gap.adjacent_hexes, "Gap hex should be adjacent to hex1"
    assert hex3 in hex_gap.adjacent_hexes, "Gap hex should be adjacent to hex3"
    
    # Get one of the provinces to build from (use the one with hex1)
    province1 = hex1.get_province()
    assert province1 is not None, "Province1 should exist"
    province1.set_money(100)  # Give it money to build
    
    # Store previous color for ProvincesManager (needed for unit builds on gray hexes)
    game_state.provinces_manager._previous_color = HColor.GRAY
    
    # Build a peasant on the gap hex (this will change its color to red and merge provinces)
    # We need to provide the province hex for building on gray hexes
    build_command = BuildPieceCommand(
        hex=hex_gap,
        piece_type=PieceType.PEASANT,
        province_id=province1.get_id(),
        province_hex=hex1  # Provide province hex for gray hex builds
    )
    
    # Get current entity color
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Current entity should exist"
    player_color = current_entity.color
    
    # Validate and execute command
    validator = CommandValidator(game_state)
    is_valid, error = validator.validate(build_command, player_color)
    assert is_valid, f"Build command should be valid: {error}"
    
    executor = CommandExecutor(game_state)
    success, error = executor.execute(build_command, player_color)
    assert success, f"Build command should succeed: {error}"
    
    # Verify we now have one merged province
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces_after) == 1, f"Should have 1 province after merge, got {len(red_provinces_after)}"
    
    # Verify only one city remains in the merged province
    merged_province = red_provinces_after[0]
    city_count = sum(1 for hex in merged_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"Merged province should have exactly 1 city, got {city_count}"
    
    # Verify all hexes are in the merged province
    hex1 = game_state.get_hex(0, 0)
    hex2 = game_state.get_hex(0, 1)
    hex_gap = game_state.get_hex(1, 0)
    hex3 = game_state.get_hex(2, 0)
    hex4 = game_state.get_hex(2, 1)
    
    assert hex1.get_province() == merged_province, "Hex1 should be in merged province"
    assert hex2.get_province() == merged_province, "Hex2 should be in merged province"
    assert hex_gap.get_province() == merged_province, "Gap hex should be in merged province"
    assert hex3.get_province() == merged_province, "Hex3 should be in merged province"
    assert hex4.get_province() == merged_province, "Hex4 should be in merged province"


if __name__ == "__main__":
    test_province_merge_removes_extra_cities()
    print("Test passed!")
