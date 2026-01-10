"""Integration test for province merging city name consistency."""

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


def create_test_game_state_with_two_provinces_different_names():
    """Create a game state with two separate provinces, each with a city and different names."""
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
    
    # Set different city names for the two provinces
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces) == 2, "Should have 2 provinces initially, got {}".format(len(red_provinces))
    
    # Find which province has which city
    province1 = None
    province2 = None
    for province in red_provinces:
        for hex in province.get_hexes():
            if hex.coordinate1 == 0 and hex.coordinate2 == 0:
                province1 = province
            elif hex.coordinate1 == 2 and hex.coordinate2 == 0:
                province2 = province
    
    assert province1 is not None, "Province1 should exist"
    assert province2 is not None, "Province2 should exist"
    
    # Set distinct city names
    province1.set_city_name("ProvinceOne")
    province2.set_city_name("ProvinceTwo")
    
    return game_state, province1, province2


def test_province_merge_keeps_city_name_from_kept_city():
    """Test that when provinces merge, the merged province keeps the name of the province whose city is kept."""
    game_state, province1, province2 = create_test_game_state_with_two_provinces_different_names()
    
    # Determine which province is larger (will be the one that survives the merge)
    # Both have 2 hexes, so we'll make province1 larger by adding a hex
    # Actually, let's check which one has the city with more adjacent farms
    # For simplicity, let's make province1 larger by ensuring it has more hexes
    # Actually, both have 2 hexes, so the merge logic will pick one arbitrarily
    # Let's instead track which city is kept and verify the name matches
    
    # Get the hexes
    hex1 = game_state.get_hex(0, 0)
    hex3 = game_state.get_hex(2, 0)
    
    # Store the city names before merge
    name1 = province1.get_city_name()
    name2 = province2.get_city_name()
    
    # Determine which province is larger (will be kept)
    # If they're the same size, the merge logic picks the first one encountered
    # Let's make province1 larger by adding an extra hex
    extra_hex = game_state.add_hex(0, 2, HColor.RED)
    _build_adjacency_graph(game_state)
    province1.add_hex(extra_hex)
    
    # Now province1 is larger, so it will be kept during merge
    # The city from province1 should be kept (since it has more adjacent farms or is in the larger province)
    # But actually, the city removal logic picks based on adjacent farms, not province size
    # So we need to ensure province1's city has more adjacent farms
    
    # Add farms adjacent to province1's city to ensure it's kept
    farm_hex1 = game_state.add_hex(-1, 0, HColor.RED)
    farm_hex1.piece = PieceType.FARM
    farm_hex2 = game_state.add_hex(0, -1, HColor.RED)
    farm_hex2.piece = PieceType.FARM
    _build_adjacency_graph(game_state)
    province1.add_hex(farm_hex1)
    province1.add_hex(farm_hex2)
    
    # Now merge the provinces by building a unit on the gap hex
    hex_gap = game_state.get_hex(1, 0)
    assert hex_gap is not None, "Gap hex should exist"
    assert hex_gap.color == HColor.GRAY, "Gap hex should be gray initially"
    
    province1.set_money(100)  # Give it money to build
    game_state.provinces_manager._previous_color = HColor.GRAY
    
    # Build a peasant on the gap hex (this will change its color to red and merge provinces)
    build_command = BuildPieceCommand(
        hex=hex_gap,
        piece_type=PieceType.PEASANT,
        province_id=province1.get_id(),
        province_hex=hex1
    )
    
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Current entity should exist"
    player_color = current_entity.color
    
    validator = CommandValidator(game_state)
    is_valid, error = validator.validate(build_command, player_color)
    assert is_valid, f"Build command should be valid: {error}"
    
    executor = CommandExecutor(game_state)
    success, error = executor.execute(build_command, player_color)
    assert success, f"Build command should succeed: {error}"
    
    # Verify we now have one merged province
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces_after) == 1, f"Should have 1 province after merge, got {len(red_provinces_after)}"
    
    merged_province = red_provinces_after[0]
    
    # Find which city remains
    remaining_city_hex = None
    for hex in merged_province.get_hexes():
        if hex.piece == PieceType.CITY:
            remaining_city_hex = hex
            break
    
    assert remaining_city_hex is not None, "Merged province should have exactly 1 city"
    
    # The merged province's city name should match the province whose city was kept
    # Since we set up province1's city to have more adjacent farms, it should be kept
    # So the merged province should have province1's name
    merged_name = merged_province.get_city_name()
    
    # Verify the name matches the province whose city was kept
    # If the remaining city is from province1 (hex1), the name should be name1
    # If the remaining city is from province2 (hex3), the name should be name2
    if remaining_city_hex == hex1:
        assert merged_name == name1, f"Merged province name should be '{name1}' (from province whose city was kept), got '{merged_name}'"
    elif remaining_city_hex == hex3:
        assert merged_name == name2, f"Merged province name should be '{name2}' (from province whose city was kept), got '{merged_name}'"
    else:
        # This shouldn't happen, but if it does, we need to investigate
        assert False, f"Remaining city hex is unexpected: {remaining_city_hex}"


if __name__ == "__main__":
    test_province_merge_keeps_city_name_from_kept_city()
    print("Test passed!")
