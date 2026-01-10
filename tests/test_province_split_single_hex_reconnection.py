"""Integration test for province split resulting in single hex that should reconnect."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType, EventType
from core.events import EventHexChangeColor, EventUnitMove
from save_load.decoder import _build_adjacency_graph


def create_test_game_state_for_single_hex_split():
    """
    Create a game state where a province split results in a single hex.
    
    Layout:
    - Red province: (0,0) with CITY, (1,0) empty, (2,0) empty
    - When (1,0) is changed to gray, the province splits into:
      - Cluster 1: (0,0) - has city, becomes successor province
      - Cluster 2: (2,0) - single hex, no city, should be removed (too small)
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create red province: horizontal line
    hex0 = game_state.add_hex(0, 0, HColor.RED)
    hex0.piece = PieceType.CITY
    
    hex1 = game_state.add_hex(1, 0, HColor.RED)  # Will be changed to gray
    
    hex2 = game_state.add_hex(2, 0, HColor.RED)  # Single hex after split
    
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


def test_single_hex_after_split_reconnects_when_province_expands():
    """
    Test that when a province split results in a single hex (which is removed
    from the province), and then the province expands to be adjacent to that hex,
    the hex should be added back to the province.
    """
    game_state = create_test_game_state_for_single_hex_split()
    
    # Get the hexes
    hex0 = game_state.get_hex(0, 0)  # City hex
    hex1 = game_state.get_hex(1, 0)  # Middle hex - will be changed to gray
    hex2 = game_state.get_hex(2, 0)  # Single hex after split
    
    # Verify initial state: all hexes in one province
    initial_province = hex0.get_province()
    assert initial_province is not None, "Hex0 should be in a province"
    assert hex1.get_province() == initial_province, "Hex1 should be in same province"
    assert hex2.get_province() == initial_province, "Hex2 should be in same province"
    
    # Split the province by changing hex1 to gray
    game_state.provinces_manager._previous_color = hex1.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex1)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    # After split:
    # - hex0 should be in a province (successor province with city)
    # - hex1 should be gray (not in any province)
    # - hex2 should NOT be in a province (single hex, too small, removed)
    print(f"\nAfter split:")
    print(f"  hex0.color = {hex0.color}, province = {hex0.get_province().get_id() if hex0.get_province() else None}")
    print(f"  hex1.color = {hex1.color}, province = {hex1.get_province().get_id() if hex1.get_province() else None}")
    print(f"  hex2.color = {hex2.color}, province = {hex2.get_province().get_id() if hex2.get_province() else None}")
    
    assert hex0.get_province() is not None, "Hex0 should still be in a province"
    assert hex1.color == HColor.GRAY, "Hex1 should be gray"
    assert hex2.get_province() is None, "Hex2 should NOT be in a province (single hex removed)"
    assert hex2.color == HColor.RED, "Hex2 should still be red"
    
    # Now expand the province by changing hex1 back to red (via unit move or color change)
    # This simulates the province expanding to be adjacent to hex2
    # First, let's add a unit to hex0's province
    hex0.piece = PieceType.PEASANT  # Replace city with unit for movement
    
    # Mark unit as ready
    if hex0 not in game_state.readiness_manager.ready_hexes:
        game_state.readiness_manager.ready_hexes.append(hex0)
    
    # Move unit from hex0 to hex1 (capturing gray hex)
    move_event = game_state.events_manager.factory.create_event(EventType.UNIT_MOVE)
    if isinstance(move_event, EventUnitMove):
        move_event.set_start(hex0)
        move_event.set_finish(hex1)
        move_event.set_color_transfer_enabled(True)
    game_state.events_manager.apply_event(move_event)
    
    print(f"\nAfter expanding to hex1:")
    print(f"  hex0.color = {hex0.color}, province = {hex0.get_province().get_id() if hex0.get_province() else None}")
    print(f"  hex1.color = {hex1.color}, province = {hex1.get_province().get_id() if hex1.get_province() else None}")
    print(f"  hex2.color = {hex2.color}, province = {hex2.get_province().get_id() if hex2.get_province() else None}")
    print(f"  hex2 is_adjacent_to_hexes_of_same_color? {hex2.is_adjacent_to_hexes_of_same_color()}")
    
    # Now hex1 should be red and in the province
    assert hex1.color == HColor.RED, "Hex1 should be red after unit move"
    assert hex1.get_province() is not None, "Hex1 should be in a province"
    
    # The bug: hex2 should now be added to the province because it's adjacent to hex1 (same color)
    # But it's probably not being added
    assert hex2.get_province() is not None, \
        f"BUG: Hex2 should be added to province when adjacent to hex1! " \
        f"hex2.color={hex2.color}, hex1.color={hex1.color}, " \
        f"adjacent={hex2 in hex1.adjacent_hexes}, " \
        f"is_adjacent_to_same_color={hex2.is_adjacent_to_hexes_of_same_color()}"


def test_single_hex_after_split_reconnects_via_color_change():
    """
    Test the same scenario but using a direct color change event instead of unit move.
    """
    game_state = create_test_game_state_for_single_hex_split()
    
    hex0 = game_state.get_hex(0, 0)
    hex1 = game_state.get_hex(1, 0)
    hex2 = game_state.get_hex(2, 0)
    
    # Split the province
    game_state.provinces_manager._previous_color = hex1.color
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex1)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    # Verify hex2 is not in a province
    assert hex2.get_province() is None, "Hex2 should NOT be in a province after split"
    assert hex2.color == HColor.RED, "Hex2 should still be red"
    
    # Change hex1 back to red (simulating province expansion)
    game_state.provinces_manager._previous_color = hex1.color
    change_color_event2 = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event2, EventHexChangeColor):
        change_color_event2.set_hex(hex1)
        change_color_event2.set_color(HColor.RED)
    game_state.events_manager.apply_event(change_color_event2)
    
    print(f"\nAfter changing hex1 back to red:")
    print(f"  hex1.color = {hex1.color}, province = {hex1.get_province().get_id() if hex1.get_province() else None}")
    print(f"  hex2.color = {hex2.color}, province = {hex2.get_province().get_id() if hex2.get_province() else None}")
    print(f"  hex2 is_adjacent_to_hexes_of_same_color? {hex2.is_adjacent_to_hexes_of_same_color()}")
    
    # The bug: hex2 should now be added to the province
    assert hex2.get_province() is not None, \
        f"BUG: Hex2 should be added to province when hex1 becomes red! " \
        f"hex2.is_adjacent_to_hexes_of_same_color()={hex2.is_adjacent_to_hexes_of_same_color()}"


if __name__ == "__main__":
    test_single_hex_after_split_reconnects_when_province_expands()
    print("\n" + "="*50)
    test_single_hex_after_split_reconnects_via_color_change()
    print("Tests completed!")
