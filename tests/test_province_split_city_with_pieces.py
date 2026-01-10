"""Integration tests for province splitting city assignment with existing pieces."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType, EventType
from core.events import EventHexChangeColor
from save_load.decoder import _build_adjacency_graph


def create_test_game_state_for_split_with_pieces(piece_type: PieceType):
    """
    Create a game state with a province that will be split.
    The right side (which will become the new province) has all hexes with the same piece type.
    
    Layout:
    - Left side: (0,0) with CITY, (1,0) empty
    - Middle: (2,0) - will be changed to gray to split
    - Right side: (3,0), (4,0) - both with the specified piece_type
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create hexes
    hex0 = game_state.add_hex(0, 0, HColor.RED)
    hex0.piece = PieceType.CITY  # City on left side
    
    hex1 = game_state.add_hex(1, 0, HColor.RED)  # Empty on left side
    
    hex2 = game_state.add_hex(2, 0, HColor.RED)  # Middle - will be split point
    
    hex3 = game_state.add_hex(3, 0, HColor.RED)
    hex3.piece = piece_type  # Right side - all with same piece
    
    hex4 = game_state.add_hex(4, 0, HColor.RED)
    hex4.piece = piece_type  # Right side - all with same piece
    
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


def test_province_split_adds_city_when_all_hexes_have_peasant():
    """Test that when a province is split and the new province has all peasants, a city is correctly added."""
    game_state = create_test_game_state_for_split_with_pieces(PieceType.PEASANT)
    
    # Verify initial state
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces) == 1, f"Should have 1 red province initially, got {len(red_provinces)}"
    
    hex3 = game_state.get_hex(3, 0)
    hex4 = game_state.get_hex(4, 0)
    assert hex3.piece == PieceType.PEASANT, "Hex3 should have peasant"
    assert hex4.piece == PieceType.PEASANT, "Hex4 should have peasant"
    
    # Split the province
    hex_middle = game_state.get_hex(2, 0)
    game_state.provinces_manager._previous_color = hex_middle.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex_middle)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    # Find the new province (right side)
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    new_province = None
    for province in red_provinces_after:
        has_original_city = any(hex.coordinate1 == 0 and hex.coordinate2 == 0 and hex.piece == PieceType.CITY
                               for hex in province.get_hexes())
        if not has_original_city:
            new_province = province
            break
    
    assert new_province is not None, "New province should exist after split"
    
    # Verify the new province has exactly one city
    city_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"New province should have exactly 1 city, got {city_count}"
    
    # Verify the remaining hexes still have peasants (one was replaced by city)
    hexes_in_new_province = new_province.get_hexes()
    peasant_count = sum(1 for hex in hexes_in_new_province if hex.piece == PieceType.PEASANT)
    # Should have 1 peasant (one was replaced by city)
    assert peasant_count == 1, f"New province should have 1 peasant (one replaced by city), got {peasant_count}"
    
    # Verify total hex count is correct (2 hexes: 1 city + 1 peasant)
    assert len(hexes_in_new_province) == 2, f"New province should have 2 hexes, got {len(hexes_in_new_province)}"


def test_province_split_adds_city_when_all_hexes_have_spearman():
    """Test that when a province is split and the new province has all spearmen, a city is correctly added."""
    game_state = create_test_game_state_for_split_with_pieces(PieceType.SPEARMAN)
    
    hex_middle = game_state.get_hex(2, 0)
    game_state.provinces_manager._previous_color = hex_middle.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex_middle)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    new_province = None
    for province in red_provinces_after:
        has_original_city = any(hex.coordinate1 == 0 and hex.coordinate2 == 0 and hex.piece == PieceType.CITY
                               for hex in province.get_hexes())
        if not has_original_city:
            new_province = province
            break
    
    assert new_province is not None, "New province should exist"
    city_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"Should have 1 city, got {city_count}"
    spearman_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.SPEARMAN)
    assert spearman_count == 1, f"Should have 1 spearman (one replaced by city), got {spearman_count}"


def test_province_split_adds_city_when_all_hexes_have_baron():
    """Test that when a province is split and the new province has all barons, a city is correctly added."""
    game_state = create_test_game_state_for_split_with_pieces(PieceType.BARON)
    
    hex_middle = game_state.get_hex(2, 0)
    game_state.provinces_manager._previous_color = hex_middle.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex_middle)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    new_province = None
    for province in red_provinces_after:
        has_original_city = any(hex.coordinate1 == 0 and hex.coordinate2 == 0 and hex.piece == PieceType.CITY
                               for hex in province.get_hexes())
        if not has_original_city:
            new_province = province
            break
    
    assert new_province is not None, "New province should exist"
    city_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"Should have 1 city, got {city_count}"
    baron_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.BARON)
    assert baron_count == 1, f"Should have 1 baron (one replaced by city), got {baron_count}"


def test_province_split_adds_city_when_all_hexes_have_knight():
    """Test that when a province is split and the new province has all knights, a city is correctly added."""
    game_state = create_test_game_state_for_split_with_pieces(PieceType.KNIGHT)
    
    hex_middle = game_state.get_hex(2, 0)
    game_state.provinces_manager._previous_color = hex_middle.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex_middle)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    new_province = None
    for province in red_provinces_after:
        has_original_city = any(hex.coordinate1 == 0 and hex.coordinate2 == 0 and hex.piece == PieceType.CITY
                               for hex in province.get_hexes())
        if not has_original_city:
            new_province = province
            break
    
    assert new_province is not None, "New province should exist"
    city_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"Should have 1 city, got {city_count}"
    knight_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.KNIGHT)
    assert knight_count == 1, f"Should have 1 knight (one replaced by city), got {knight_count}"


def test_province_split_adds_city_when_all_hexes_have_tower():
    """Test that when a province is split and the new province has all towers, a city is correctly added."""
    game_state = create_test_game_state_for_split_with_pieces(PieceType.TOWER)
    
    hex_middle = game_state.get_hex(2, 0)
    game_state.provinces_manager._previous_color = hex_middle.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex_middle)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    new_province = None
    for province in red_provinces_after:
        has_original_city = any(hex.coordinate1 == 0 and hex.coordinate2 == 0 and hex.piece == PieceType.CITY
                               for hex in province.get_hexes())
        if not has_original_city:
            new_province = province
            break
    
    assert new_province is not None, "New province should exist"
    city_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"Should have 1 city, got {city_count}"
    tower_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.TOWER)
    assert tower_count == 1, f"Should have 1 tower (one replaced by city), got {tower_count}"


def test_province_split_adds_city_when_all_hexes_have_strong_tower():
    """Test that when a province is split and the new province has all strong towers, a city is correctly added."""
    game_state = create_test_game_state_for_split_with_pieces(PieceType.STRONG_TOWER)
    
    hex_middle = game_state.get_hex(2, 0)
    game_state.provinces_manager._previous_color = hex_middle.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex_middle)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    new_province = None
    for province in red_provinces_after:
        has_original_city = any(hex.coordinate1 == 0 and hex.coordinate2 == 0 and hex.piece == PieceType.CITY
                               for hex in province.get_hexes())
        if not has_original_city:
            new_province = province
            break
    
    assert new_province is not None, "New province should exist"
    city_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"Should have 1 city, got {city_count}"
    strong_tower_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.STRONG_TOWER)
    assert strong_tower_count == 1, f"Should have 1 strong_tower (one replaced by city), got {strong_tower_count}"


def test_province_split_adds_city_when_all_hexes_have_farm():
    """Test that when a province is split and the new province has all farms, a city is correctly added."""
    game_state = create_test_game_state_for_split_with_pieces(PieceType.FARM)
    
    hex_middle = game_state.get_hex(2, 0)
    game_state.provinces_manager._previous_color = hex_middle.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex_middle)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    new_province = None
    for province in red_provinces_after:
        has_original_city = any(hex.coordinate1 == 0 and hex.coordinate2 == 0 and hex.piece == PieceType.CITY
                               for hex in province.get_hexes())
        if not has_original_city:
            new_province = province
            break
    
    assert new_province is not None, "New province should exist"
    city_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"Should have 1 city, got {city_count}"
    farm_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.FARM)
    assert farm_count == 1, f"Should have 1 farm (one replaced by city), got {farm_count}"


def test_province_split_adds_city_when_all_hexes_have_grave():
    """Test that when a province is split and the new province has all graves, a city is correctly added."""
    game_state = create_test_game_state_for_split_with_pieces(PieceType.GRAVE)
    
    hex_middle = game_state.get_hex(2, 0)
    game_state.provinces_manager._previous_color = hex_middle.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex_middle)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    new_province = None
    for province in red_provinces_after:
        has_original_city = any(hex.coordinate1 == 0 and hex.coordinate2 == 0 and hex.piece == PieceType.CITY
                               for hex in province.get_hexes())
        if not has_original_city:
            new_province = province
            break
    
    assert new_province is not None, "New province should exist"
    city_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"Should have 1 city, got {city_count}"
    grave_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.GRAVE)
    assert grave_count == 1, f"Should have 1 grave (one replaced by city), got {grave_count}"


def test_province_split_adds_city_when_all_hexes_have_pine():
    """Test that when a province is split and the new province has all pines, a city is correctly added."""
    game_state = create_test_game_state_for_split_with_pieces(PieceType.PINE)
    
    hex_middle = game_state.get_hex(2, 0)
    game_state.provinces_manager._previous_color = hex_middle.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex_middle)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    new_province = None
    for province in red_provinces_after:
        has_original_city = any(hex.coordinate1 == 0 and hex.coordinate2 == 0 and hex.piece == PieceType.CITY
                               for hex in province.get_hexes())
        if not has_original_city:
            new_province = province
            break
    
    assert new_province is not None, "New province should exist"
    city_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"Should have 1 city, got {city_count}"
    pine_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.PINE)
    assert pine_count == 1, f"Should have 1 pine (one replaced by city), got {pine_count}"


def test_province_split_adds_city_when_all_hexes_have_palm():
    """Test that when a province is split and the new province has all palms, a city is correctly added."""
    game_state = create_test_game_state_for_split_with_pieces(PieceType.PALM)
    
    hex_middle = game_state.get_hex(2, 0)
    game_state.provinces_manager._previous_color = hex_middle.color
    
    change_color_event = game_state.events_manager.factory.create_event(EventType.HEX_CHANGE_COLOR)
    if isinstance(change_color_event, EventHexChangeColor):
        change_color_event.set_hex(hex_middle)
        change_color_event.set_color(HColor.GRAY)
    game_state.events_manager.apply_event(change_color_event)
    
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    new_province = None
    for province in red_provinces_after:
        has_original_city = any(hex.coordinate1 == 0 and hex.coordinate2 == 0 and hex.piece == PieceType.CITY
                               for hex in province.get_hexes())
        if not has_original_city:
            new_province = province
            break
    
    assert new_province is not None, "New province should exist"
    city_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.CITY)
    assert city_count == 1, f"Should have 1 city, got {city_count}"
    palm_count = sum(1 for hex in new_province.get_hexes() if hex.piece == PieceType.PALM)
    assert palm_count == 1, f"Should have 1 palm (one replaced by city), got {palm_count}"


if __name__ == "__main__":
    test_province_split_adds_city_when_all_hexes_have_peasant()
    test_province_split_adds_city_when_all_hexes_have_spearman()
    test_province_split_adds_city_when_all_hexes_have_baron()
    test_province_split_adds_city_when_all_hexes_have_knight()
    test_province_split_adds_city_when_all_hexes_have_tower()
    test_province_split_adds_city_when_all_hexes_have_strong_tower()
    test_province_split_adds_city_when_all_hexes_have_farm()
    test_province_split_adds_city_when_all_hexes_have_grave()
    test_province_split_adds_city_when_all_hexes_have_pine()
    test_province_split_adds_city_when_all_hexes_have_palm()
    print("All tests passed!")
