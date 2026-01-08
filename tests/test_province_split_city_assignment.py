"""Integration test for province splitting city assignment."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType, EventType
from core.events import EventHexChangeColor
from save_load.decoder import _build_adjacency_graph
from commands.types import BuildPieceCommand
from commands.executor import CommandExecutor
from commands.validator import CommandValidator


def create_test_game_state_for_split_without_city():
    """
    Create a game state with a province that will be split.
    The split will create a new province without a city, which should get one.
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a large province: horizontal line of red hexes
    # Hexes: (0,0), (1,0), (2,0), (3,0), (4,0)
    # City at (0,0) only
    red_hexes = []
    for i in range(5):
        hex = game_state.add_hex(i, 0, HColor.RED)
        if i == 0:
            hex.piece = PieceType.CITY  # City only at the start
        red_hexes.append(hex)
    
    # Build adjacency graph
    _build_adjacency_graph(game_state)
    
    # Create player entity
    from core.player_entity import PlayerEntity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    player.set_name("RedPlayer")
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)
    
    # Build provinces
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Set money for the province
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces) == 1, f"Should have 1 red province initially, got {len(red_provinces)}"
    red_provinces[0].set_money(100)
    
    return game_state


def test_province_split_adds_city_to_new_province():
    """Test that when a province is split, new provinces without cities get one."""
    game_state = create_test_game_state_for_split_without_city()
    
    # Verify initial state: one red province with a city at (0,0)
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces) == 1, f"Should have 1 red province initially, got {len(red_provinces)}"
    
    initial_province = red_provinces[0]
    initial_city_count = sum(1 for hex in initial_province.get_hexes() if hex.piece == PieceType.CITY)
    assert initial_city_count == 1, f"Initial province should have 1 city, got {initial_city_count}"
    
    # Split the province by changing the middle hex to gray
    # This will split the province into two clusters: (0,0), (1,0) and (3,0), (4,0)
    # The cluster with (0,0) has the city, so it becomes the successor
    # The cluster with (3,0), (4,0) becomes a new province without a city
    
    hex_middle = game_state.get_hex(2, 0)
    assert hex_middle is not None, "Middle hex should exist"
    assert hex_middle.color == HColor.RED, "Middle hex should be red initially"
    
    # Change the middle hex to gray to split the province
    # Set previous color manually (on_event_validated doesn't handle HEX_CHANGE_COLOR)
    game_state.provinces_manager._previous_color = hex_middle.color
    
    from core.events import EventHexChangeColor
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex_middle)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    # Verify the province was split
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    # After splitting, we should have 2 provinces (the original one and a new one)
    # But if the clusters are too small (< 2 hexes), they won't become provinces
    # Let's check what we actually have
    print(f"Red provinces after split: {len(red_provinces_after)}")
    for i, province in enumerate(red_provinces_after):
        hexes = province.get_hexes()
        print(f"  Province {i}: {len(hexes)} hexes: {[(h.coordinate1, h.coordinate2) for h in hexes]}")
        cities = [h for h in hexes if h.piece == PieceType.CITY]
        print(f"    Cities: {[(h.coordinate1, h.coordinate2) for h in cities]}")
    
    # We should have at least 1 province (the successor)
    assert len(red_provinces_after) >= 1, f"Should have at least 1 red province after split, got {len(red_provinces_after)}"
    
    # Find the new province (the one without the original city at 0,0)
    new_province = None
    for province in red_provinces_after:
        has_original_city = any(hex.coordinate1 == 0 and hex.coordinate2 == 0 and hex.piece == PieceType.CITY
                               for hex in province.get_hexes())
        if not has_original_city:
            new_province = province
            break
    
    # The new province should exist if the split created a cluster with >= 2 hexes
    # The split should create: cluster 1: (0,0), (1,0) and cluster 2: (3,0), (4,0)
    # Both have 2 hexes, so both should become provinces
    if new_province is None:
        # If no new province, check if the split actually happened
        # Maybe the clusters are too small or the split logic didn't work
        hex0 = game_state.get_hex(0, 0)
        hex3 = game_state.get_hex(3, 0)
        if hex0 and hex3:
            province0 = hex0.get_province()
            province3 = hex3.get_province()
            if province0 and province3 and province0 != province3:
                # Split did happen, but maybe the new province wasn't created
                # Let's check if hex3's province is the new one
                new_province = province3
            else:
                # Split didn't happen or both hexes are in the same province
                assert False, f"Split didn't happen as expected. Hex0 province: {province0}, Hex3 province: {province3}"
    
    # The new province should exist and should have a city (added by our logic)
    assert new_province is not None, "New province should exist after split"
    
    # Count cities in the new province
    new_province_city_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.CITY)
    assert new_province_city_count == 1, f"New province should have exactly 1 city (added by split logic), got {new_province_city_count}"
    
    # Verify all provinces have exactly one city
    for province in red_provinces_after:
        city_count = sum(1 for hex in province.get_hexes() if hex.piece == PieceType.CITY)
        assert city_count == 1, f"Each province should have exactly 1 city, got {city_count} for province {province.get_id()}"


if __name__ == "__main__":
    test_province_split_adds_city_to_new_province()
    print("Test passed!")
