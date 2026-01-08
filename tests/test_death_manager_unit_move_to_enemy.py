"""Integration test for DeathManager - unit moving to enemy hex should not die."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType, EventType
from save_load.decoder import _build_adjacency_graph
from core.events import EventUnitMove


def create_test_game_state_for_unit_move_to_enemy():
    """
    Create a game state with a unit that can move to an enemy hex.
    
    Layout:
    - Red province: (0,0) with CITY, (1,0) with PEASANT
    - Blue hex (enemy): (2,0) - adjacent to red hex
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create red province with unit
    hex1 = game_state.add_hex(0, 0, HColor.RED)
    hex1.piece = PieceType.CITY
    
    hex2 = game_state.add_hex(1, 0, HColor.RED)
    hex2.piece = PieceType.PEASANT
    
    # Create blue hex (enemy) - adjacent to red hex
    hex3 = game_state.add_hex(2, 0, HColor.BLUE)
    
    # Build adjacency graph
    _build_adjacency_graph(game_state)
    
    # Create player entities
    from core.player_entity import PlayerEntity
    red_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    red_player.set_name("RedPlayer")
    blue_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.BLUE)
    blue_player.set_name("BluePlayer")
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(red_player)
    game_state.entities_manager.entities.append(blue_player)
    
    # Build provinces
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Set money for the red province
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces) == 1, f"Should have 1 red province initially, got {len(red_provinces)}"
    red_provinces[0].set_money(100)
    
    return game_state


def test_unit_moves_to_enemy_hex_and_survives():
    """
    Test that when a unit moves to an enemy hex (color transfer),
    the unit does NOT die and is correctly added to the province.
    
    This tests the fix for the regression where units were instantly
    dying when stepping on enemy hexes.
    """
    game_state = create_test_game_state_for_unit_move_to_enemy()
    
    # Get the hexes
    hex2 = game_state.get_hex(1, 0)  # Red hex with peasant
    hex3 = game_state.get_hex(2, 0)  # Blue hex (enemy)
    
    # Verify initial state
    assert hex2.color == HColor.RED, "Hex2 should be red initially"
    assert hex2.piece == PieceType.PEASANT, "Hex2 should have peasant"
    assert hex2.get_province() is not None, "Hex2 should be in a province"
    red_province_id = hex2.get_province().get_id()
    
    assert hex3.color == HColor.BLUE, "Hex3 should be blue initially"
    assert hex3.piece is None, "Hex3 should be empty"
    assert hex3.get_province() is not None, "Hex3 should be in a blue province"
    blue_province_id = hex3.get_province().get_id()
    
    # Verify hexes are adjacent
    assert hex2 in hex3.adjacent_hexes, "Hex2 and hex3 should be adjacent"
    assert hex3 in hex2.adjacent_hexes, "Hex2 and hex3 should be adjacent"
    
    # Mark unit as ready (required for non-quick events)
    if hex2 not in game_state.readiness_manager.ready_hexes:
        game_state.readiness_manager.ready_hexes.append(hex2)
    
    # Move unit from hex2 to hex3 (color transfer should occur)
    move_event = game_state.events_manager.factory.create_event(EventType.UNIT_MOVE)
    assert isinstance(move_event, EventUnitMove), "Should create EventUnitMove"
    move_event.set_start(hex2)
    move_event.set_finish(hex3)
    move_event.set_color_transfer_enabled(True)
    
    # Apply the move event
    game_state.events_manager.apply_event(move_event)
    
    # Verify the unit survived (didn't become a grave)
    assert hex3.piece == PieceType.PEASANT, f"Unit should survive! Got {hex3.piece} instead of PEASANT"
    assert hex3.piece != PieceType.GRAVE, "Unit should NOT be a grave"
    
    # Verify color transfer occurred
    assert hex3.color == HColor.RED, f"Hex3 should be red after color transfer, got {hex3.color}"
    
    # Verify the hex is now in the red province
    assert hex3.get_province() is not None, "Hex3 should be in a province after move"
    assert hex3.get_province().get_id() == red_province_id, \
        f"Hex3 should be in red province {red_province_id}, got {hex3.get_province().get_id()}"
    
    # Verify hex3 is adjacent to hexes of the same color (red)
    assert hex3.is_adjacent_to_hexes_of_same_color(), \
        "Hex3 should be adjacent to hexes of the same color (red)"
    
    # Verify hex2 is now empty
    assert hex2.piece is None, "Hex2 should be empty after unit moved"
    assert hex2.unit_id == -1, "Hex2 should have no unit_id after move"


def test_unit_moves_to_enemy_hex_with_multiple_adjacent_hexes():
    """
    Test that when a unit moves to an enemy hex that has multiple adjacent
    hexes of the same color, the unit survives and the hex is correctly added.
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a larger red province
    hex1 = game_state.add_hex(0, 0, HColor.RED)
    hex1.piece = PieceType.CITY
    
    hex2 = game_state.add_hex(1, 0, HColor.RED)
    hex2.piece = PieceType.PEASANT
    
    hex3 = game_state.add_hex(0, 1, HColor.RED)  # Another red hex
    
    # Create blue hex (enemy) - adjacent to multiple red hexes
    hex4 = game_state.add_hex(1, 1, HColor.BLUE)
    
    # Build adjacency graph
    _build_adjacency_graph(game_state)
    
    # Create player entities
    from core.player_entity import PlayerEntity
    red_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    blue_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.BLUE)
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(red_player)
    game_state.entities_manager.entities.append(blue_player)
    
    # Build provinces
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Mark unit as ready
    if hex2 not in game_state.readiness_manager.ready_hexes:
        game_state.readiness_manager.ready_hexes.append(hex2)
    
    # Move unit from hex2 to hex4
    move_event = game_state.events_manager.factory.create_event(EventType.UNIT_MOVE)
    if isinstance(move_event, EventUnitMove):
        move_event.set_start(hex2)
        move_event.set_finish(hex4)
        move_event.set_color_transfer_enabled(True)
    
    game_state.events_manager.apply_event(move_event)
    
    # Verify the unit survived
    assert hex4.piece == PieceType.PEASANT, f"Unit should survive! Got {hex4.piece}"
    assert hex4.piece != PieceType.GRAVE, "Unit should NOT be a grave"
    
    # Verify color transfer occurred
    assert hex4.color == HColor.RED, f"Hex4 should be red after color transfer"
    
    # Verify the hex is in a red province
    assert hex4.get_province() is not None, "Hex4 should be in a province"
    assert hex4.get_province().get_color() == HColor.RED, "Hex4 should be in red province"


def test_unit_moves_to_gray_hex_and_survives():
    """
    Test that when a unit moves to a gray (neutral) hex, the unit survives.
    Gray hexes should not cause units to die.
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create red province with unit
    hex1 = game_state.add_hex(0, 0, HColor.RED)
    hex1.piece = PieceType.CITY
    
    hex2 = game_state.add_hex(1, 0, HColor.RED)
    hex2.piece = PieceType.PEASANT
    
    # Create gray hex (neutral) - adjacent to red hex
    hex3 = game_state.add_hex(2, 0, HColor.GRAY)
    
    # Build adjacency graph
    _build_adjacency_graph(game_state)
    
    # Create player entities
    from core.player_entity import PlayerEntity
    red_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(red_player)
    
    # Build provinces
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Mark unit as ready
    if hex2 not in game_state.readiness_manager.ready_hexes:
        game_state.readiness_manager.ready_hexes.append(hex2)
    
    # Move unit from hex2 to hex3
    move_event = game_state.events_manager.factory.create_event(EventType.UNIT_MOVE)
    if isinstance(move_event, EventUnitMove):
        move_event.set_start(hex2)
        move_event.set_finish(hex3)
        move_event.set_color_transfer_enabled(True)
    
    game_state.events_manager.apply_event(move_event)
    
    # Verify the unit survived
    assert hex3.piece == PieceType.PEASANT, f"Unit should survive on gray hex! Got {hex3.piece}"
    assert hex3.piece != PieceType.GRAVE, "Unit should NOT be a grave"
    
    # Verify color transfer occurred (gray hex becomes red)
    assert hex3.color == HColor.RED, f"Hex3 should be red after color transfer"


if __name__ == "__main__":
    test_unit_moves_to_enemy_hex_and_survives()
    test_unit_moves_to_enemy_hex_with_multiple_adjacent_hexes()
    test_unit_moves_to_gray_hex_and_survives()
    print("All tests passed!")
