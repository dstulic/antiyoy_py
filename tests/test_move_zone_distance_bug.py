"""Test for MoveZoneManager distance bug where hexes beyond 4 hexes are included."""

import pytest
from core.game_state import GameState
from core.enums import RulesType, EntityType, HColor, PieceType
from save_load.decoder import _build_adjacency_graph
from core.player_entity import PlayerEntity


def calculate_hex_distance(hex1, hex2):
    """Calculate distance between two hexes using axial coordinates."""
    dq = hex2.coordinate1 - hex1.coordinate1
    dr = hex2.coordinate2 - hex1.coordinate2
    return (abs(dq) + abs(dq + dr) + abs(dr)) // 2


def test_move_zone_never_exceeds_4_hexes_from_specific_start():
    """
    Test that reproduces the bug where hexes at distance 5 are included.
    
    Based on the warning:
    - Start: (-4, -2)
    - Targets at distance 5: (1, -3), (0, -1), (-1, 0), (1, -2)
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create start hex at (-4, -2) with a unit
    start_hex = game_state.add_hex(-4, -2, HColor.RED)
    start_hex.piece = PieceType.PEASANT
    
    # Create a path from start to the problematic hexes
    # We need to create a chain that would allow reaching distance 5 if the bug exists
    
    # Create hexes along a path that could lead to distance 5
    # Path: (-4, -2) -> (-3, -2) -> (-2, -2) -> (-1, -2) -> (0, -2) -> (1, -2)
    # This is 5 hexes away
    hexes_chain = []
    for i in range(-3, 2):  # -3, -2, -1, 0, 1
        hex = game_state.add_hex(i, -2, HColor.RED)
        hexes_chain.append(hex)
    
    # Also create the problematic target hexes
    target_hexes = [
        game_state.add_hex(1, -3, HColor.RED),  # Distance 5
        game_state.add_hex(0, -1, HColor.RED),   # Distance 5
        game_state.add_hex(-1, 0, HColor.RED),   # Distance 5
        game_state.add_hex(1, -2, HColor.RED),   # Distance 5
    ]
    
    _build_adjacency_graph(game_state)
    
    # Create player entity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)
    
    # Build provinces
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Calculate move zone
    game_state.move_zone_manager.update_for_unit(start_hex)
    
    # Check that no hexes beyond 4 hexes are included
    violations = []
    for move_hex in game_state.move_zone_manager.hexes:
        if move_hex == start_hex:
            continue
        distance = calculate_hex_distance(start_hex, move_hex)
        counter = getattr(move_hex, 'counter', None)
        if distance > 4:
            violations.append({
                'hex': (move_hex.coordinate1, move_hex.coordinate2),
                'distance': distance,
                'counter': counter
            })
    
    assert len(violations) == 0, \
        f"Found {len(violations)} hexes beyond 4 hexes: {violations}"
    
    # Also verify that the specific problematic hexes are NOT in the move zone
    for target_hex in target_hexes:
        distance = calculate_hex_distance(start_hex, target_hex)
        assert distance == 5, f"Expected distance 5, got {distance}"
        assert target_hex not in game_state.move_zone_manager.hexes, \
            f"Hex at {target_hex.coordinate1}, {target_hex.coordinate2} should not be in move zone (distance {distance})"


def test_move_zone_counter_values_are_correct():
    """
    Test that counter values are correctly set and never exceed the limit.
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a simple chain
    start_hex = game_state.add_hex(0, 0, HColor.RED)
    start_hex.piece = PieceType.PEASANT
    
    # Create hexes up to distance 4
    for i in range(1, 5):
        game_state.add_hex(i, 0, HColor.RED)
    
    # Create a hex at distance 5 (should not be included)
    hex_at_5 = game_state.add_hex(5, 0, HColor.RED)
    
    _build_adjacency_graph(game_state)
    
    # Create player entity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)
    
    # Build provinces
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Calculate move zone
    game_state.move_zone_manager.update_for_unit(start_hex)
    
    # Verify counter values are correct
    # Start hex should have counter = 4 (limit)
    assert start_hex.counter == 4, f"Start hex counter should be 4, got {start_hex.counter}"
    
    # Check counters for all hexes in move zone
    for move_hex in game_state.move_zone_manager.hexes:
        distance = calculate_hex_distance(start_hex, move_hex)
        counter = getattr(move_hex, 'counter', None)
        
        # Counter should be between 0 and 4
        assert 0 <= counter <= 4, \
            f"Hex at {move_hex.coordinate1}, {move_hex.coordinate2} has invalid counter {counter} (distance {distance})"
        
        # Counter should be approximately (4 - distance), but can be off by 1 due to path differences
        # The important thing is that counter should never be > 4 or < 0
        assert counter is not None, f"Hex at {move_hex.coordinate1}, {move_hex.coordinate2} has no counter"
    
    # Hex at distance 5 should not be in move zone
    assert hex_at_5 not in game_state.move_zone_manager.hexes, \
        "Hex at distance 5 should not be in move zone"
    
    # Verify counter was reset (should be 0, not 994 or some other weird value)
    assert hex_at_5.counter == 0, \
        f"Hex at distance 5 should have counter 0 (was reset), got {hex_at_5.counter}"
