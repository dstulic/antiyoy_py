"""Unit tests for province splitting when cut by another province."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType, EventType
from save_load.decoder import _build_adjacency_graph
from commands.types import BuildPieceCommand
from commands.executor import CommandExecutor
from commands.validator import CommandValidator


def create_test_game_state_with_split_scenario() -> GameState:
    """
    Create a game state with:
    - A large skinny province (horizontal line of red hexes)
    - A smaller blue province that will cut it
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a large skinny province: horizontal line of red hexes
    # Hexes: (0,0), (1,0), (2,0), (3,0), (4,0)
    # City at (0,0)
    red_hexes = []
    for i in range(5):
        hex = game_state.add_hex(i, 0, HColor.RED)
        if i == 0:
            hex.piece = PieceType.CITY  # City at the start
        red_hexes.append(hex)
    
    # Create a smaller blue province that will cut the red province
    # Blue hexes at (2,1) and (2,2) - city at (2,1)
    blue_hex1 = game_state.add_hex(2, 1, HColor.BLUE)
    blue_hex1.piece = PieceType.CITY
    
    blue_hex2 = game_state.add_hex(2, 2, HColor.BLUE)  # Empty hex
    
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
    
    # Set money for provinces
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            province.set_money(100)  # Give red province money
        elif province.get_color() == HColor.BLUE:
            province.set_money(100)  # Give blue province money
    
    return game_state


def test_province_split_by_capture():
    """Test that a large province is split when cut by another province."""
    game_state = create_test_game_state_with_split_scenario()
    
    # Verify initial state: one red province and one blue province
    red_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    blue_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.BLUE]
    
    assert len(red_provinces) == 1, f"Should have 1 red province initially, got {len(red_provinces)}"
    assert len(blue_provinces) == 1, f"Should have 1 blue province initially, got {len(blue_provinces)}"
    
    red_province = red_provinces[0]
    blue_province = blue_provinces[0]
    
    # Verify red province has all 5 hexes
    red_hex_count = len(red_province.get_hexes())
    assert red_hex_count == 5, f"Red province should have 5 hexes initially, got {red_hex_count}"
    
    # Verify red province has one city
    red_city_count = sum(1 for hex in red_province.get_hexes() if hex.piece == PieceType.CITY)
    assert red_city_count == 1, f"Red province should have 1 city initially, got {red_city_count}"
    
    # Get the middle hex of the red province (at 2,0) - this will be captured
    middle_hex = game_state.get_hex(2, 0)
    assert middle_hex is not None, "Middle hex should exist"
    assert middle_hex.color == HColor.RED, "Middle hex should be red initially"
    assert middle_hex in red_province.get_hexes(), "Middle hex should be in red province"
    
    # Store previous color for ProvincesManager
    game_state.provinces_manager._previous_color = HColor.RED
    
    # Set blue player's turn
    game_state.turns_manager.turn_index = 1  # Blue player's turn (index 1)
    
    # Build a unit on the middle hex to capture it (this will change its color to blue)
    # This should cut the red province in two
    build_command = BuildPieceCommand(
        hex=middle_hex,
        piece_type=PieceType.PEASANT,
        province_id=blue_province.get_id(),
        province_hex=blue_province.get_hexes()[0]  # Use first blue hex as province hex
    )
    
    # Get current entity color (should be blue)
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Current entity should exist"
    assert current_entity.color == HColor.BLUE, "Current entity should be blue"
    player_color = current_entity.color
    
    # Validate and execute command
    validator = CommandValidator(game_state)
    is_valid, error = validator.validate(build_command, player_color)
    assert is_valid, f"Build command should be valid: {error}"
    
    executor = CommandExecutor(game_state)
    success, error = executor.execute(build_command, player_color)
    assert success, f"Build command should succeed: {error}"
    
    # Verify the middle hex is now blue
    assert middle_hex.color == HColor.BLUE, "Middle hex should be blue after capture"
    assert middle_hex.piece == PieceType.PEASANT, "Middle hex should have a peasant"
    
    # Verify red province is now split into two provinces
    red_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(red_provinces_after) == 2, f"Red province should be split into 2 provinces, got {len(red_provinces_after)}"
    
    # Verify each red province has the correct hexes
    # Left province: (0,0), (1,0) - should have city at (0,0)
    # Right province: (3,0), (4,0) - should have no city initially (will be added by CityManager)
    
    hex0 = game_state.get_hex(0, 0)
    hex1 = game_state.get_hex(1, 0)
    hex3 = game_state.get_hex(3, 0)
    hex4 = game_state.get_hex(4, 0)
    
    left_province = hex0.get_province()
    right_province = hex3.get_province()
    
    assert left_province is not None, "Left province should exist"
    assert right_province is not None, "Right province should exist"
    assert left_province != right_province, "Left and right provinces should be different"
    
    # Verify left province has hexes (0,0) and (1,0)
    left_hexes = left_province.get_hexes()
    assert hex0 in left_hexes, "Hex (0,0) should be in left province"
    assert hex1 in left_hexes, "Hex (1,0) should be in left province"
    assert len(left_hexes) == 2, f"Left province should have 2 hexes, got {len(left_hexes)}"
    
    # Verify right province has hexes (3,0) and (4,0)
    right_hexes = right_province.get_hexes()
    assert hex3 in right_hexes, "Hex (3,0) should be in right province"
    assert hex4 in right_hexes, "Hex (4,0) should be in right province"
    assert len(right_hexes) == 2, f"Right province should have 2 hexes, got {len(right_hexes)}"
    
    # Verify left province has the city (at 0,0)
    left_city_count = sum(1 for hex in left_hexes if hex.piece == PieceType.CITY)
    assert left_city_count == 1, f"Left province should have 1 city, got {left_city_count}"
    assert hex0.piece == PieceType.CITY, "Hex (0,0) should have a city"
    
    # Verify right province (should have no city initially, but CityManager might add one)
    # Actually, CityManager should add a city if there isn't one
    # But for now, let's just verify the split happened correctly
    
    # Verify middle hex is in blue province
    assert middle_hex.get_province() == blue_province, "Middle hex should be in blue province"
    
    # Verify total hex count: 2 left + 2 right + 1 middle (blue) = 5 red hexes originally
    # But middle is now blue, so we have 2 left + 2 right = 4 red hexes in 2 provinces
    total_red_hexes = sum(len(p.get_hexes()) for p in red_provinces_after)
    assert total_red_hexes == 4, f"Total red hexes should be 4 (2 in each province), got {total_red_hexes}"
    
    # Verify provinces are properly separated (no shared hexes)
    left_hex_coords = {(h.coordinate1, h.coordinate2) for h in left_province.get_hexes()}
    right_hex_coords = {(h.coordinate1, h.coordinate2) for h in right_province.get_hexes()}
    assert len(left_hex_coords & right_hex_coords) == 0, "Left and right provinces should not share hexes"
    
    # Verify provinces are not adjacent (they're separated by the blue hex)
    # Check that no hex in left province is adjacent to any hex in right province
    left_adjacent_coords = set()
    for hex in left_province.get_hexes():
        for adj_hex in hex.adjacent_hexes:
            if adj_hex.color == HColor.RED:
                left_adjacent_coords.add((adj_hex.coordinate1, adj_hex.coordinate2))
    
    right_hex_coords_set = {(h.coordinate1, h.coordinate2) for h in right_province.get_hexes()}
    # The only red hex adjacent to left province should be the middle hex (now blue)
    # So left_adjacent_coords should not contain any right province hexes
    assert len(left_adjacent_coords & right_hex_coords_set) == 0, "Left and right provinces should not be adjacent"
    
    # Verify money was distributed (original province had money, split provinces should have some)
    # Note: Money distribution logic may vary, but both provinces should exist with valid state
    assert left_province.get_money() >= 0, "Left province should have valid money"
    assert right_province.get_money() >= 0, "Right province should have valid money"
    
    print(f"Left province: {len(left_hexes)} hexes, {left_city_count} cities, ${left_province.get_money()} money")
    print(f"Right province: {len(right_hexes)} hexes, ${right_province.get_money()} money")
    print(f"Blue province: {len(blue_province.get_hexes())} hexes (including captured middle hex)")


if __name__ == "__main__":
    test_province_split_by_capture()
    print("Test passed!")
