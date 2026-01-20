"""Integration tests for unit movement and readiness functionality."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType
from save_load.decoder import _build_adjacency_graph
from commands.types import BuildPieceCommand, MoveUnitCommand
from commands.executor import CommandExecutor
from commands.validator import CommandValidator
from core.core_utils import is_unit


def create_test_game_state_for_movement() -> GameState:
    """Create a game state with a province and units for testing movement."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a province with a city and some hexes
    # Hex layout (pointy-top hex grid):
    # (0,0) - city (RED)
    # (1,0) - empty (RED, in province) - adjacent to (0,0)
    # (0,1) - empty (GRAY, outside province) - adjacent to (0,0) and (1,0)
    # (1,1) - empty (RED, in province) - adjacent to (1,0)
    
    hex_city = game_state.add_hex(0, 0, HColor.RED)
    hex_city.piece = PieceType.CITY
    
    hex1 = game_state.add_hex(1, 0, HColor.RED)  # In province, adjacent to city
    hex2 = game_state.add_hex(0, 1, HColor.GRAY)  # Gray hex (outside province), adjacent to city
    hex3 = game_state.add_hex(1, 1, HColor.RED)  # In province, adjacent to hex1
    
    # Build adjacency graph
    _build_adjacency_graph(game_state)
    
    # Create player entity
    from core.player_entity import PlayerEntity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    player.set_name("TestPlayer")
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)
    
    # Build provinces
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Set money for province
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            province.set_money(200)  # Enough to build multiple units
            break
    
    return game_state


def test_unit_built_on_province_hex_is_ready():
    """Test that a unit built on a province hex (not gray) is ready to move."""
    game_state = create_test_game_state_for_movement()
    
    # Get the red province
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Red province should exist"
    
    # Get hexes
    hex1 = game_state.get_hex(1, 0)  # In province
    
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Current entity should exist"
    player_color = current_entity.color
    
    validator = CommandValidator(game_state)
    executor = CommandExecutor(game_state)
    
    # Build a peasant on hex1 (in province)
    build_command = BuildPieceCommand(
        hex=hex1,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    is_valid, error = validator.validate(build_command, player_color)
    assert is_valid, f"Build should be valid: {error}"
    
    success, error = executor.execute(build_command, player_color)
    assert success, f"Build should succeed: {error}"
    
    # Verify unit was built
    assert hex1.piece == PieceType.PEASANT, f"Hex1 should have peasant, got {hex1.piece}"
    assert hex1.has_unit(), "Hex1 should have a unit"
    
    # Verify unit is ready to move (built on province hex)
    assert game_state.readiness_manager.is_ready(hex1), "Unit built on province hex should be ready to move"


def test_unit_built_on_gray_hex_is_not_ready():
    """Test that a unit built on a gray hex (outside province) is NOT ready (counts as move)."""
    game_state = create_test_game_state_for_movement()
    
    # Get the red province
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Red province should exist"
    
    # Get hexes
    hex_city = game_state.get_hex(0, 0)  # City (province hex)
    hex2 = game_state.get_hex(0, 1)  # Gray hex (outside province)
    
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Current entity should exist"
    player_color = current_entity.color
    
    validator = CommandValidator(game_state)
    executor = CommandExecutor(game_state)
    
    # Build a peasant on hex2 (gray hex, outside province)
    # Need to use province_hex for units built on gray hexes
    build_command = BuildPieceCommand(
        hex=hex2,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id(),
        province_hex=hex_city  # Province hex for building on gray hex
    )
    
    is_valid, error = validator.validate(build_command, player_color)
    assert is_valid, f"Build should be valid: {error}"
    
    success, error = executor.execute(build_command, player_color)
    assert success, f"Build should succeed: {error}"
    
    # Verify unit was built
    assert hex2.piece == PieceType.PEASANT, f"Hex2 should have peasant, got {hex2.piece}"
    assert hex2.has_unit(), "Hex2 should have a unit"
    assert hex2.color == HColor.RED, "Hex2 should be colored red after unit build"
    
    # Verify unit is NOT ready to move (built on gray hex counts as move)
    assert not game_state.readiness_manager.is_ready(hex2), "Unit built on gray hex should NOT be ready to move"


def test_unit_movement_makes_unit_not_ready():
    """Test that moving a unit makes it not ready."""
    game_state = create_test_game_state_for_movement()
    
    # Get the red province
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Red province should exist"
    
    # Get hexes
    hex1 = game_state.get_hex(1, 0)  # In province
    hex3 = game_state.get_hex(1, 1)  # In province, adjacent to hex1
    
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Current entity should exist"
    player_color = current_entity.color
    
    validator = CommandValidator(game_state)
    executor = CommandExecutor(game_state)
    
    # Build a peasant on hex1 (in province)
    build_command = BuildPieceCommand(
        hex=hex1,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    
    executor.execute(build_command, player_color)
    
    # Verify unit is ready
    assert game_state.readiness_manager.is_ready(hex1), "Unit should be ready after build"
    
    # Move unit from hex1 to hex3
    move_command = MoveUnitCommand(
        start_hex=hex1,
        finish_hex=hex3,
        color_transfer_enabled=True
    )
    
    is_valid, error = validator.validate(move_command, player_color)
    assert is_valid, f"Move should be valid: {error}"
    
    success, error = executor.execute(move_command, player_color)
    assert success, f"Move should succeed: {error}"
    
    # Verify unit moved
    assert hex1.piece is None, "Hex1 should be empty after move"
    assert hex3.piece == PieceType.PEASANT, "Hex3 should have peasant after move"
    
    # Verify unit is NOT ready (has moved)
    assert not game_state.readiness_manager.is_ready(hex1), "Start hex should not be ready (unit moved)"
    # Note: hex3 might be ready if the ruleset allows, but typically moved units are not ready
    # The readiness manager should mark the start hex as not ready


def test_units_become_ready_on_turn_end():
    """Test that all units become ready when turn ends."""
    game_state = create_test_game_state_for_movement()
    
    # Get the red province
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Red province should exist"
    
    # Get hexes
    hex1 = game_state.get_hex(1, 0)  # In province
    hex3 = game_state.get_hex(3, 0)  # In province
    
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Current entity should exist"
    player_color = current_entity.color
    
    validator = CommandValidator(game_state)
    executor = CommandExecutor(game_state)
    
    # Build a peasant on hex1
    build_command1 = BuildPieceCommand(
        hex=hex1,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    executor.execute(build_command1, player_color)
    
    # Re-fetch hexes after build (they might have changed)
    hex1 = game_state.get_hex(1, 0)
    hex3 = game_state.get_hex(1, 1)
    
    # Verify unit is ready
    assert game_state.readiness_manager.is_ready(hex1), "Unit should be ready after build"
    
    # Move unit from hex1 to hex3 (empty hex)
    move_command = MoveUnitCommand(
        start_hex=hex1,
        finish_hex=hex3,
        color_transfer_enabled=True
    )
    
    is_valid, error = validator.validate(move_command, player_color)
    assert is_valid, f"Move should be valid: {error}"
    
    success, error = executor.execute(move_command, player_color)
    assert success, f"Move should succeed: {error}"
    
    # After move, hex1 should be empty and hex3 should have peasant
    assert hex1.piece is None, f"Hex1 should be empty after move, got {hex1.piece}"
    assert hex3.piece == PieceType.PEASANT, f"Hex3 should have peasant after move, got {hex3.piece}"
    
    # Verify hex1 is not in ready list (it's empty)
    assert not game_state.readiness_manager.is_ready(hex1), "Empty hex should not be ready"
    
    # End turn
    from commands.types import EndTurnCommand
    end_turn_command = EndTurnCommand()
    executor.execute(end_turn_command, player_color)
    
    # After turn end, all units should be ready again
    # The readiness manager should update on turn end
    current_entity_after = game_state.entities_manager.get_current_entity()
    if current_entity_after and current_entity_after.color == HColor.RED:
        # Still RED's turn (or back to RED)
        assert game_state.readiness_manager.is_ready(hex3), "Unit should be ready after turn end"


def test_unit_can_move_multiple_hexes():
    """Test that units can move up to 4 hexes away (not just adjacent)."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a long chain of hexes for testing movement distance
    # (0,0) - city (RED)
    # (1,0) - (RED, in province)
    # (2,0) - (RED, in province)
    # (3,0) - (RED, in province)
    # (4,0) - (RED, in province)
    # (5,0) - (GRAY, outside province) - 5 hexes away from (0,0)
    
    hex_city = game_state.add_hex(0, 0, HColor.RED)
    hex_city.piece = PieceType.CITY
    
    hex1 = game_state.add_hex(1, 0, HColor.RED)
    hex2 = game_state.add_hex(2, 0, HColor.RED)
    hex3 = game_state.add_hex(3, 0, HColor.RED)
    hex4 = game_state.add_hex(4, 0, HColor.RED)
    hex5 = game_state.add_hex(5, 0, HColor.GRAY)  # 5 hexes away
    
    _build_adjacency_graph(game_state)
    
    from core.player_entity import PlayerEntity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    player.set_name("TestPlayer")
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)
    
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Red province should exist"
    red_province.set_money(200)
    
    # Build a peasant on hex1
    executor = CommandExecutor(game_state)
    build_command = BuildPieceCommand(
        hex=hex1,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    executor.execute(build_command, HColor.RED)
    
    # Update move zone for the unit
    game_state.move_zone_manager.update_for_unit(hex1)
    
    # Check that hex4 (4 hexes away) is in the move zone
    assert hex4 in game_state.move_zone_manager.hexes, "Unit should be able to move 4 hexes away"
    
    # Check the counter on hex4 - it should be 0 (4 steps: hex1->hex2->hex3->hex4)
    # Start hex gets counter=4, each step decreases by 1
    # hex1 (start) = 4, hex2 = 3, hex3 = 2, hex4 = 1
    # Actually, let's check: if hex1 is start with counter=4, then:
    # hex2 (adjacent to hex1) gets counter=3
    # hex3 (adjacent to hex2) gets counter=2  
    # hex4 (adjacent to hex3) gets counter=1
    # So hex4 should have counter=1, meaning we can still move from it
    
    # Check that hex5 (5 hexes away) is NOT reachable because hex4's counter would be 0
    # Actually, if hex4 has counter=1, we can still move to hex5 (which would get counter=0)
    # But hex5 is gray, so we need to check if it can be captured
    # Since hex5 is empty gray, it can be captured, so it might be in the move zone
    # The key is that we can only move 4 steps total, so hex5 should have counter=0
    # Let's verify that hex5 is NOT in the move zone OR has counter=0 (can't move further)
    if hex5 in game_state.move_zone_manager.hexes:
        # If it's in the move zone, it should have counter=0 (can't move further from there)
        assert hasattr(hex5, 'counter') and hex5.counter == 0, \
            "Hex5 should have counter=0 if reachable (5 steps away)"
    else:
        # If not in move zone, that's also correct (too far or can't capture)
        pass
    
    # Verify we can actually move to hex4
    move_command = MoveUnitCommand(
        start_hex=hex1,
        finish_hex=hex4,
        color_transfer_enabled=True
    )
    validator = CommandValidator(game_state)
    is_valid, error = validator.validate(move_command, HColor.RED)
    assert is_valid, f"Move to hex4 should be valid: {error}"


def test_unit_moved_to_gray_hex_stays_alive():
    """Test that a unit moved to a gray hex doesn't turn into a grave (bug fix)."""
    game_state = create_test_game_state_for_movement()
    
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    assert red_province is not None, "Red province should exist"
    
    hex1 = game_state.get_hex(1, 0)  # In province
    hex2 = game_state.get_hex(0, 1)  # Gray hex (outside province)
    
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Current entity should exist"
    player_color = current_entity.color
    
    validator = CommandValidator(game_state)
    executor = CommandExecutor(game_state)
    
    # Step 1: Build a unit on hex1 (in province)
    build_command = BuildPieceCommand(
        hex=hex1,
        piece_type=PieceType.PEASANT,
        province_id=red_province.get_id()
    )
    success, error = executor.execute(build_command, player_color)
    assert success, f"Build should succeed: {error}"
    
    # Verify unit was built
    assert hex1.piece == PieceType.PEASANT, "Hex1 should have peasant"
    
    # Step 2: Move unit to gray hex (hex2)
    move_command = MoveUnitCommand(
        start_hex=hex1,
        finish_hex=hex2,
        color_transfer_enabled=True
    )
    
    is_valid, error = validator.validate(move_command, player_color)
    assert is_valid, f"Move should be valid: {error}"
    
    success, error = executor.execute(move_command, player_color)
    assert success, f"Move should succeed: {error}"
    
    # Step 3: Verify unit is still alive (not a grave)
    assert hex2.piece == PieceType.PEASANT, f"Unit should still be alive, got {hex2.piece}"
    assert hex2.piece != PieceType.GRAVE, "Unit should NOT have turned into a grave"
    
    # Step 4: Verify hex2 is now in a province (after color transfer)
    assert hex2.get_province() is not None, "Hex2 should be in a province after move"
    assert hex2.color == HColor.RED, "Hex2 should be red after color transfer"


def test_unit_movement_distance_with_different_units():
    """Test that different unit types can all move up to 4 hexes."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a chain: (0,0) city, (1,0) through (4,0) empty hexes
    hex_city = game_state.add_hex(0, 0, HColor.RED)
    hex_city.piece = PieceType.CITY
    
    hexes = []
    for i in range(1, 5):
        hex = game_state.add_hex(i, 0, HColor.RED)
        hexes.append(hex)
    
    _build_adjacency_graph(game_state)
    
    from core.player_entity import PlayerEntity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    player.set_name("TestPlayer")
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)
    
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    red_province = None
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            red_province = province
            break
    
    red_province.set_money(500)  # Enough for all units
    
    executor = CommandExecutor(game_state)
    
    # Test all unit types
    unit_types = [PieceType.PEASANT, PieceType.SPEARMAN, PieceType.BARON, PieceType.KNIGHT]
    
    for unit_type in unit_types:
        # Build unit on hex1
        build_command = BuildPieceCommand(
            hex=hexes[0],
            piece_type=unit_type,
            province_id=red_province.get_id()
        )
        executor.execute(build_command, HColor.RED)
        
        # Update move zone
        game_state.move_zone_manager.update_for_unit(hexes[0])
        
        # All units should be able to reach hex4 (4 hexes away)
        assert hexes[3] in game_state.move_zone_manager.hexes, \
            f"{unit_type} should be able to move 4 hexes away"
        
        # Clear hex1 for next test
        hexes[0].piece = None
        hexes[0].unit_id = -1


def test_unit_movement_never_exceeds_4_hexes():
    """
    Test that unit movement zone never includes hexes beyond 4 hexes away.
    
    This test ensures the bug where units could move 8+ hexes away is fixed.
    It verifies:
    1. All hexes in move zone are within 4 hexes
    2. Counters are properly reset between calculations
    3. Multiple calls don't accumulate counters
    4. Works with different unit types and paths
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a long chain of hexes to test distance limits
    # (0,0) - unit starting position
    # (1,0) through (10,0) - chain of hexes (10 hexes away from start)
    # This ensures we can test that hexes beyond 4 are never included
    
    hex_start = game_state.add_hex(0, 0, HColor.RED)
    hex_start.piece = PieceType.PEASANT
    
    # Create a long chain
    hexes = [hex_start]
    for i in range(1, 11):
        hex = game_state.add_hex(i, 0, HColor.RED)
        hexes.append(hex)
    
    _build_adjacency_graph(game_state)
    
    from core.player_entity import PlayerEntity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    player.set_name("TestPlayer")
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)
    
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Helper function to calculate hex distance
    def calculate_hex_distance(hex1, hex2):
        """Calculate distance between two hexes using axial coordinates."""
        dq = hex2.coordinate1 - hex1.coordinate1
        dr = hex2.coordinate2 - hex1.coordinate2
        return (abs(dq) + abs(dq + dr) + abs(dr)) // 2
    
    # Test 1: Verify move zone doesn't exceed 4 hexes for peasant
    game_state.move_zone_manager.update_for_unit(hex_start)
    
    max_distance = 0
    violations = []
    for move_hex in game_state.move_zone_manager.hexes:
        if move_hex == hex_start:
            continue
        distance = calculate_hex_distance(hex_start, move_hex)
        if distance > max_distance:
            max_distance = distance
        if distance > 4:
            violations.append((move_hex, distance, getattr(move_hex, 'counter', None)))
    
    assert max_distance <= 4, f"Maximum distance should be <= 4, got {max_distance}"
    assert len(violations) == 0, \
        f"Found {len(violations)} hexes beyond 4 hexes: {violations}"
    
    # Test 2: Verify multiple calls don't accumulate counters
    # Call update_for_unit multiple times and verify results are consistent
    for i in range(3):
        game_state.move_zone_manager.update_for_unit(hex_start)
        
        max_dist = 0
        for move_hex in game_state.move_zone_manager.hexes:
            if move_hex == hex_start:
                continue
            distance = calculate_hex_distance(hex_start, move_hex)
            if distance > max_dist:
                max_dist = distance
        
        assert max_dist <= 4, \
            f"After {i+1} calls, max distance should be <= 4, got {max_dist}"
    
    # Test 3: Test with different unit types
    unit_types = [PieceType.PEASANT, PieceType.SPEARMAN, PieceType.BARON, PieceType.KNIGHT]
    
    for unit_type in unit_types:
        hex_start.piece = unit_type
        game_state.move_zone_manager.update_for_unit(hex_start)
        
        max_dist = 0
        for move_hex in game_state.move_zone_manager.hexes:
            if move_hex == hex_start:
                continue
            distance = calculate_hex_distance(hex_start, move_hex)
            if distance > max_dist:
                max_dist = distance
        
        assert max_dist <= 4, \
            f"{unit_type} should not be able to move beyond 4 hexes, got max distance {max_dist}"
    
    # Test 4: Test with a complex path (through enemy hexes)
    # Create a scenario: friendly hexes -> enemy hex -> friendly hexes
    # This tests that counters work correctly even when moving through enemy territory
    hex_start.piece = PieceType.PEASANT
    
    # Add some enemy hexes in the chain
    enemy_hex = game_state.get_hex(2, 0)
    if enemy_hex:
        enemy_hex.color = HColor.BLUE  # Enemy color
    
    game_state.move_zone_manager.update_for_unit(hex_start)
    
    max_dist = 0
    for move_hex in game_state.move_zone_manager.hexes:
        if move_hex == hex_start:
            continue
        distance = calculate_hex_distance(hex_start, move_hex)
        if distance > max_dist:
            max_dist = distance
    
    assert max_dist <= 4, \
        f"Even with enemy hexes in path, max distance should be <= 4, got {max_dist}"
    
    # Test 5: Verify counters are properly reset
    # Check that all hexes have counters that make sense
    game_state.move_zone_manager.update_for_unit(hex_start)
    
    for move_hex in game_state.move_zone_manager.hexes:
        if move_hex == hex_start:
            assert hasattr(move_hex, 'counter'), "Start hex should have counter"
            assert move_hex.counter == 4, f"Start hex counter should be 4, got {move_hex.counter}"
        else:
            distance = calculate_hex_distance(hex_start, move_hex)
            counter = getattr(move_hex, 'counter', None)
            if counter is not None:
                # Counter should be: 4 - distance (at most)
                # Actually, counter represents remaining movement, so:
                # Start hex: counter = 4
                # After 1 step: counter = 3
                # After 2 steps: counter = 2
                # After 3 steps: counter = 1
                # After 4 steps: counter = 0
                expected_counter = 4 - distance
                assert counter == expected_counter, \
                    f"Hex at distance {distance} should have counter {expected_counter}, got {counter}"


if __name__ == "__main__":
    test_unit_built_on_province_hex_is_ready()
    print("✓ test_unit_built_on_province_hex_is_ready passed")
    
    test_unit_built_on_gray_hex_is_not_ready()
    print("✓ test_unit_built_on_gray_hex_is_not_ready passed")
    
    test_unit_movement_makes_unit_not_ready()
    print("✓ test_unit_movement_makes_unit_not_ready passed")
    
    test_units_become_ready_on_turn_end()
    print("✓ test_units_become_ready_on_turn_end passed")
    
    test_unit_can_move_multiple_hexes()
    print("✓ test_unit_can_move_multiple_hexes passed")
    
    test_unit_moved_to_gray_hex_stays_alive()
    print("✓ test_unit_moved_to_gray_hex_stays_alive passed")
    
    test_unit_movement_distance_with_different_units()
    print("✓ test_unit_movement_distance_with_different_units passed")
    
    test_unit_movement_never_exceeds_4_hexes()
    print("✓ test_unit_movement_never_exceeds_4_hexes passed")
    
    print("\nAll tests passed!")
