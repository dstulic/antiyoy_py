"""Test that building a unit (PIECE_BUILD) causes provinces without a city to get one.

When a unit is built on a gray hex, the hex changes color and is added to a province.
If that province (or any province) has no city, _fix_provinces_without_cities should
run after PIECE_BUILD so the province gets a city. Without that fix, the province
stays without a city until some other event triggers the fix (e.g. next turn).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType, EventType
from core.events import EventPieceBuild
from save_load.decoder import _build_adjacency_graph


def create_game_state_province_without_city_then_build_on_gray():
    """
    Create a game state where:
    - Red has two hexes (0,0) and (1,0), no city on either.
    - Gray hex (2,0) is adjacent to (1,0).
    - After builder.apply() we have one red province (2 hexes) with no city.
    - We will build a unit on the gray hex; the hex becomes red and joins the province.
    - The province should then get a city (via _fix_provinces_without_cities after PIECE_BUILD).
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)

    hex0 = game_state.add_hex(0, 0, HColor.RED)
    hex1 = game_state.add_hex(1, 0, HColor.RED)
    hex_gray = game_state.add_hex(2, 0, HColor.GRAY)
    # No pieces (no city)
    assert hex0.piece is None and hex1.piece is None

    _build_adjacency_graph(game_state)

    from core.player_entity import PlayerEntity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)

    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()

    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces) == 1, "expected one red province"
    province = red_provinces[0]
    assert len(province.get_hexes()) == 2, "province should have 2 hexes"
    has_city = any(h.piece == PieceType.CITY for h in province.get_hexes())
    assert not has_city, "setup: province must have no city yet"

    province.set_money(100)
    return game_state


def test_build_unit_on_gray_hex_province_without_city_gets_city():
    """
    When we build a unit on a gray hex, the hex joins our province.
    If the province had no city, it must get one after the build
    (i.e. _fix_provinces_without_cities must run after PIECE_BUILD).
    """
    game_state = create_game_state_province_without_city_then_build_on_gray()

    province = next(p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED)
    hex_gray = game_state.get_hex(2, 0)
    assert hex_gray.color == HColor.GRAY, "gray hex must exist"

    # Build a unit on the gray hex (so it becomes red and joins the province)
    build_event = game_state.events_manager.factory.create_event(EventType.PIECE_BUILD)
    assert build_event is not None and isinstance(build_event, EventPieceBuild)
    build_event.set_hex(hex_gray)
    build_event.set_piece_type(PieceType.PEASANT)
    build_event.set_province_id(province.get_id())
    build_event.set_unit_id(game_state.get_id_for_new_unit())
    build_event.set_author(game_state.entities_manager.get_current_entity())

    game_state.events_manager.apply_event(build_event)

    # Province now has 3 hexes (0,0), (1,0), (2,0). It must have a city.
    province_after = next(
        (p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED),
        None,
    )
    assert province_after is not None, "red province must still exist"
    city_count = sum(1 for h in province_after.get_hexes() if h.piece == PieceType.CITY)
    assert city_count == 1, (
        f"After building unit on gray hex, province without a city must get one. "
        f"Got {city_count} cities (expected 1). "
        f"Fix: call _fix_provinces_without_cities() after PIECE_BUILD in ProvincesManager.on_event_applied."
    )


if __name__ == "__main__":
    test_build_unit_on_gray_hex_province_without_city_gets_city()
    print("✓ test_build_unit_on_gray_hex_province_without_city_gets_city passed")
