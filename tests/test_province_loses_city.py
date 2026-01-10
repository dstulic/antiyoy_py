"""Integration test for province losing its city and needing a new one."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType, EventType
from core.events import EventHexChangeColor
from save_load.decoder import _build_adjacency_graph


def create_test_game_state_province_loses_city():
    """
    Create a game state with a province that has 3 hexes, one with a city.
    When the city hex is lost, the remaining province should get a new city.
    
    Layout:
    - Red province: (0,0) with CITY, (1,0) empty, (2,0) empty
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create red province with 3 hexes
    hex0 = game_state.add_hex(0, 0, HColor.RED)
    hex0.piece = PieceType.CITY  # City at first hex
    
    hex1 = game_state.add_hex(1, 0, HColor.RED)  # Empty
    
    hex2 = game_state.add_hex(2, 0, HColor.RED)  # Empty
    
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


def test_province_gets_city_after_losing_city_hex():
    """
    Test that when a province loses its only city hex (e.g., captured by enemy),
    the remaining province gets a new city.
    """
    game_state = create_test_game_state_province_loses_city()
    
    # Get the hexes
    hex0 = game_state.get_hex(0, 0)  # City hex
    hex1 = game_state.get_hex(1, 0)  # Empty
    hex2 = game_state.get_hex(2, 0)  # Empty
    
    # Verify initial state
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces) == 1, f"Should have 1 red province initially, got {len(red_provinces)}"
    initial_province = red_provinces[0]
    
    # Verify province has a city
    city_count = sum(1 for hex in initial_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"Province should have 1 city initially, got {city_count}"
    assert hex0.piece == PieceType.CITY, "Hex0 should have a city"
    
    # Lose the city hex by changing it to gray (simulating capture)
    game_state.provinces_manager._previous_color = hex0.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex0)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    # After losing the city hex:
    # - hex0 should be gray (not in province)
    # - hex1 and hex2 should still be in the province
    # - The province should have a new city (on hex1 or hex2)
    
    print(f"\nAfter losing city hex:")
    print(f"  hex0.color = {hex0.color}, piece = {hex0.piece}, province = {hex0.get_province().get_id() if hex0.get_province() else None}")
    print(f"  hex1.color = {hex1.color}, piece = {hex1.piece}, province = {hex1.get_province().get_id() if hex1.get_province() else None}")
    print(f"  hex2.color = {hex2.color}, piece = {hex2.piece}, province = {hex2.get_province().get_id() if hex2.get_province() else None}")
    
    # Verify hex0 is gray and not in province
    assert hex0.color == HColor.GRAY, "Hex0 should be gray"
    assert hex0.get_province() is None, "Hex0 should not be in a province"
    
    # Verify remaining hexes are still in a province
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces_after) == 1, f"Should still have 1 red province, got {len(red_provinces_after)}"
    remaining_province = red_provinces_after[0]
    
    assert hex1.get_province() == remaining_province, "Hex1 should be in the remaining province"
    assert hex2.get_province() == remaining_province, "Hex2 should be in the remaining province"
    
    # Verify the province has a city (on hex1 or hex2)
    city_count_after = sum(1 for hex in remaining_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count_after == 1, \
        f"Province should have 1 city after losing original city, got {city_count_after}. " \
        f"Hex1.piece={hex1.piece}, Hex2.piece={hex2.piece}"
    
    # Verify at least one of hex1 or hex2 has a city
    has_city = (hex1.piece == PieceType.CITY or hex2.piece == PieceType.CITY)
    assert has_city, f"At least one of hex1 or hex2 should have a city. Hex1.piece={hex1.piece}, Hex2.piece={hex2.piece}"


if __name__ == "__main__":
    test_province_gets_city_after_losing_city_hex()
    print("Test passed!")
