"""Tests for capturing cities and towers with units."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType, EventType
from core.events import EventUnitMove
from save_load.decoder import _build_adjacency_graph
from commands.types import MoveUnitCommand
from commands.validator import CommandValidator
from commands.executor import CommandExecutor


def create_test_game_state_for_capture():
    """
    Create a game state with:
    - Red player with units
    - Blue player with isolated city, tower, and strong tower (no adjacent blue hexes)
    """
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Red province with units
    red_hex1 = game_state.add_hex(0, 0, HColor.RED)
    red_hex1.piece = PieceType.CITY
    
    red_hex2 = game_state.add_hex(1, 0, HColor.RED)
    red_hex2.piece = PieceType.PEASANT  # Strength 1
    
    red_hex3 = game_state.add_hex(2, 0, HColor.RED)
    red_hex3.piece = PieceType.SPEARMAN  # Strength 2
    
    red_hex4 = game_state.add_hex(3, 0, HColor.RED)
    red_hex4.piece = PieceType.BARON  # Strength 3
    
    red_hex5 = game_state.add_hex(4, 0, HColor.RED)
    red_hex5.piece = PieceType.KNIGHT  # Strength 4
    
    # Blue province with defensive pieces (adjacent to red units, but isolated from other blue hexes)
    # This ensures defense value equals the piece's own defense
    blue_hex1 = game_state.add_hex(0, 1, HColor.BLUE)  # Isolated city - Defense 1, adjacent to red_hex1
    blue_hex1.piece = PieceType.CITY
    
    blue_hex2 = game_state.add_hex(2, 1, HColor.BLUE)  # Isolated tower - Defense 2, adjacent to red_hex3
    blue_hex2.piece = PieceType.TOWER
    
    blue_hex3 = game_state.add_hex(4, 1, HColor.BLUE)  # Isolated strong tower - Defense 3, adjacent to red_hex5
    blue_hex3.piece = PieceType.STRONG_TOWER
    
    # Blue province base (separate from the isolated pieces, far away)
    blue_hex4 = game_state.add_hex(10, 10, HColor.BLUE)
    blue_hex4.piece = PieceType.CITY  # For province
    
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
    
    # Set money
    for province in game_state.provinces_manager.provinces:
        province.set_money(100)
    
    return game_state


def test_capture_city_with_spearman():
    """Test that a spearman (strength 2) can capture a city (defense 1)."""
    game_state = create_test_game_state_for_capture()
    
    # Get hexes
    spearman_hex = game_state.get_hex(2, 0)  # Red spearman
    city_hex = game_state.get_hex(0, 1)  # Blue city (isolated, adjacent to red_hex1)
    
    assert spearman_hex.piece == PieceType.SPEARMAN, "Should have spearman"
    assert city_hex.piece == PieceType.CITY, "Should have city"
    
    # Check defense value
    defense = game_state.ruleset.get_defense_value_hex(city_hex)
    assert defense == 1, f"City defense should be 1, got {defense}"
    
    # Check if can be captured
    can_capture = game_state.ruleset.can_hex_be_captured(city_hex, 2)  # Spearman strength
    assert can_capture, "Spearman (strength 2) should be able to capture city (defense 1)"
    
    # Mark unit as ready
    if spearman_hex not in game_state.readiness_manager.ready_hexes:
        game_state.readiness_manager.ready_hexes.append(spearman_hex)
    
    # Try to move
    validator = CommandValidator(game_state)
    command = MoveUnitCommand(spearman_hex, city_hex)
    is_valid, error = validator.validate(command, HColor.RED)
    
    assert is_valid, f"Move should be valid, got error: {error}"
    
    # Execute the move
    executor = CommandExecutor(game_state)
    success, error = executor.execute(command, HColor.RED)
    assert success, f"Move should succeed, got error: {error}"
    
    # Verify the city was captured (color changed, unit moved)
    assert city_hex.color == HColor.RED, "City hex should be red after capture"
    assert city_hex.piece == PieceType.SPEARMAN, "City hex should have spearman after capture"


def test_capture_tower_with_baron():
    """Test that a baron (strength 3) can capture a tower (defense 2)."""
    game_state = create_test_game_state_for_capture()
    
    # Get hexes
    baron_hex = game_state.get_hex(3, 0)  # Red baron
    tower_hex = game_state.get_hex(2, 1)  # Blue tower (isolated, adjacent to red_hex3)
    
    assert baron_hex.piece == PieceType.BARON, "Should have baron"
    assert tower_hex.piece == PieceType.TOWER, "Should have tower"
    
    # Check defense value
    defense = game_state.ruleset.get_defense_value_hex(tower_hex)
    assert defense == 2, f"Tower defense should be 2, got {defense}"
    
    # Check if can be captured
    can_capture = game_state.ruleset.can_hex_be_captured(tower_hex, 3)  # Baron strength
    assert can_capture, "Baron (strength 3) should be able to capture tower (defense 2)"
    
    # Mark unit as ready
    if baron_hex not in game_state.readiness_manager.ready_hexes:
        game_state.readiness_manager.ready_hexes.append(baron_hex)
    
    # Try to move
    validator = CommandValidator(game_state)
    command = MoveUnitCommand(baron_hex, tower_hex)
    is_valid, error = validator.validate(command, HColor.RED)
    
    assert is_valid, f"Move should be valid, got error: {error}"
    
    # Execute the move
    executor = CommandExecutor(game_state)
    success, error = executor.execute(command, HColor.RED)
    assert success, f"Move should succeed, got error: {error}"
    
    # Verify the tower was captured
    assert tower_hex.color == HColor.RED, "Tower hex should be red after capture"
    assert tower_hex.piece == PieceType.BARON, "Tower hex should have baron after capture"


def test_capture_strong_tower_with_knight():
    """Test that a knight (strength 4) can capture a strong tower (defense 3)."""
    game_state = create_test_game_state_for_capture()
    
    # Get hexes
    knight_hex = game_state.get_hex(4, 0)  # Red knight
    strong_tower_hex = game_state.get_hex(4, 1)  # Blue strong tower (isolated, adjacent to red_hex5)
    
    assert knight_hex.piece == PieceType.KNIGHT, "Should have knight"
    assert strong_tower_hex.piece == PieceType.STRONG_TOWER, "Should have strong tower"
    
    # Check defense value
    defense = game_state.ruleset.get_defense_value_hex(strong_tower_hex)
    assert defense == 3, f"Strong tower defense should be 3, got {defense}"
    
    # Check if can be captured
    can_capture = game_state.ruleset.can_hex_be_captured(strong_tower_hex, 4)  # Knight strength
    assert can_capture, "Knight (strength 4) should be able to capture strong tower (defense 3)"
    
    # Mark unit as ready
    if knight_hex not in game_state.readiness_manager.ready_hexes:
        game_state.readiness_manager.ready_hexes.append(knight_hex)
    
    # Try to move
    validator = CommandValidator(game_state)
    command = MoveUnitCommand(knight_hex, strong_tower_hex)
    is_valid, error = validator.validate(command, HColor.RED)
    
    assert is_valid, f"Move should be valid, got error: {error}"
    
    # Execute the move
    executor = CommandExecutor(game_state)
    success, error = executor.execute(command, HColor.RED)
    assert success, f"Move should succeed, got error: {error}"
    
    # Verify the strong tower was captured
    assert strong_tower_hex.color == HColor.RED, "Strong tower hex should be red after capture"
    assert strong_tower_hex.piece == PieceType.KNIGHT, "Strong tower hex should have knight after capture"


def test_cannot_capture_city_with_peasant():
    """Test that a peasant (strength 1) cannot capture a city (defense 1)."""
    game_state = create_test_game_state_for_capture()
    
    # Get hexes
    peasant_hex = game_state.get_hex(1, 0)  # Red peasant
    city_hex = game_state.get_hex(0, 1)  # Blue city (isolated)
    
    assert peasant_hex.piece == PieceType.PEASANT, "Should have peasant"
    assert city_hex.piece == PieceType.CITY, "Should have city"
    
    # Check defense value
    defense = game_state.ruleset.get_defense_value_hex(city_hex)
    assert defense == 1, f"City defense should be 1, got {defense}"
    
    # Check if can be captured (should fail: 1 is not > 1)
    can_capture = game_state.ruleset.can_hex_be_captured(city_hex, 1)  # Peasant strength
    assert not can_capture, "Peasant (strength 1) should NOT be able to capture city (defense 1)"
    
    # Try to move (should fail)
    validator = CommandValidator(game_state)
    command = MoveUnitCommand(peasant_hex, city_hex)
    is_valid, error = validator.validate(command, HColor.RED)
    
    assert not is_valid, "Move should NOT be valid for peasant vs city"


def test_cannot_capture_tower_with_spearman():
    """Test that a spearman (strength 2) cannot capture a tower (defense 2)."""
    game_state = create_test_game_state_for_capture()
    
    # Get hexes
    spearman_hex = game_state.get_hex(2, 0)  # Red spearman
    tower_hex = game_state.get_hex(2, 1)  # Blue tower (isolated)
    
    assert spearman_hex.piece == PieceType.SPEARMAN, "Should have spearman"
    assert tower_hex.piece == PieceType.TOWER, "Should have tower"
    
    # Check defense value
    defense = game_state.ruleset.get_defense_value_hex(tower_hex)
    assert defense == 2, f"Tower defense should be 2, got {defense}"
    
    # Check if can be captured (should fail: 2 is not > 2)
    can_capture = game_state.ruleset.can_hex_be_captured(tower_hex, 2)  # Spearman strength
    assert not can_capture, "Spearman (strength 2) should NOT be able to capture tower (defense 2)"
    
    # Try to move (should fail)
    validator = CommandValidator(game_state)
    command = MoveUnitCommand(spearman_hex, tower_hex)
    is_valid, error = validator.validate(command, HColor.RED)
    
    assert not is_valid, "Move should NOT be valid for spearman vs tower"


if __name__ == "__main__":
    test_capture_city_with_spearman()
    test_capture_tower_with_baron()
    test_capture_strong_tower_with_knight()
    test_cannot_capture_city_with_peasant()
    test_cannot_capture_tower_with_spearman()
    print("All tests passed!")
