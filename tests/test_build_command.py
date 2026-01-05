"""Unit tests for build piece command validation and execution."""

import pytest
from commands.types import BuildPieceCommand
from commands.validator import CommandValidator
from commands.executor import CommandExecutor
from core.game_state import GameState
from core.enums import HColor, PieceType
from core.hex import Hex
from core.province import Province


class MockRuleset:
    """Mock ruleset for testing."""
    
    def __init__(self):
        self.buildable_pieces = {PieceType.PEASANT, PieceType.FARM, PieceType.TOWER, PieceType.STRONG_TOWER}
        self.prices = {
            PieceType.PEASANT: 10,
            PieceType.FARM: 15,
            PieceType.TOWER: 20,
            PieceType.STRONG_TOWER: 30,
        }
    
    def is_buildable(self, piece_type: PieceType) -> bool:
        return piece_type in self.buildable_pieces
    
    def get_price(self, province, piece_type: PieceType) -> int:
        return self.prices.get(piece_type, 0)


class MockProvincesManager:
    """Mock provinces manager for testing."""
    
    def __init__(self, provinces):
        self.provinces = provinces
    
    def find_province_slowly(self, hex_obj: Hex):
        for province in self.provinces:
            if hex_obj in province.get_hexes():
                return province
        return None
    
    def get_province(self, province_id: int):
        """Get province by ID."""
        for province in self.provinces:
            if province.get_id() == province_id:
                return province
        return None


class MockEntitiesManager:
    """Mock entities manager for testing."""
    
    def __init__(self, current_color: HColor):
        self.current_color = current_color
    
    def get_current_entity(self):
        from core.player_entity import PlayerEntity
        from core.enums import EntityType
        entity = PlayerEntity(None, EntityType.HUMAN, self.current_color)
        return entity
    
    def get_current_color(self) -> HColor:
        return self.current_color


class MockEventsManager:
    """Mock events manager for testing."""
    
    def __init__(self, game_state=None):
        self.applied_events = []
        self.factory = MockEventFactory(game_state)
        self.game_state = game_state
    
    def apply_event(self, event):
        # Set core_model if not set
        if event and not event.core_model and self.game_state:
            event.core_model = self.game_state
        self.applied_events.append(event)
        # Actually apply the change if it's a valid event
        # The executor sets all event fields before calling apply_event,
        # so we can safely call apply_change() here
        if event and hasattr(event, 'apply_change'):
            # Only apply if event has required fields set
            if hasattr(event, 'hex') and event.hex and hasattr(event, 'piece_type') and event.piece_type:
                event.apply_change()


class MockEventFactory:
    """Mock event factory for testing."""
    
    def __init__(self, game_state=None):
        self.game_state = game_state
    
    def create_event(self, event_type):
        from core.events import EventPieceBuild
        from core.enums import EventType
        if event_type == EventType.PIECE_BUILD or (hasattr(event_type, 'value') and event_type.value == "piece_build"):
            event = EventPieceBuild()
            if self.game_state:
                event.core_model = self.game_state
            return event
        return None


class MockFogOfWarManager:
    """Mock fog of war manager for testing."""
    
    def __init__(self, enabled=False):
        self.enabled = enabled
    
    def apply_update(self):
        pass


def create_mock_game_state(hexes, provinces, current_color: HColor, ruleset=None):
    """Create a mock game state for testing."""
    game_state = GameState.__new__(GameState)
    game_state.hexes = hexes
    game_state.ruleset = ruleset or MockRuleset()
    game_state.provinces_manager = MockProvincesManager(provinces)
    game_state.entities_manager = MockEntitiesManager(current_color)
    game_state.events_manager = MockEventsManager(game_state)
    game_state.fog_of_war_manager = MockFogOfWarManager(enabled=False)
    
    # Mock get_hex method
    def get_hex(c1, c2):
        for hex_obj in hexes:
            if hex_obj.coordinate1 == c1 and hex_obj.coordinate2 == c2:
                return hex_obj
        return None
    
    game_state.get_hex = get_hex
    
    # Mock get_id_for_new_unit
    game_state.unit_id_counter = 1
    def get_id_for_new_unit():
        result = game_state.unit_id_counter
        game_state.unit_id_counter += 1
        return result
    
    game_state.get_id_for_new_unit = get_id_for_new_unit
    
    return game_state


def create_test_hex(c1, c2, color: HColor, piece: PieceType = None):
    """Create a test hex."""
    hex_obj = Hex(c1, c2)
    hex_obj.color = color
    if piece:
        hex_obj.piece = piece
    return hex_obj


def create_test_province(hexes, color: HColor, money: int = 100):
    """Create a test province."""
    province = Province()
    province.set_money(money)
    province.set_id(id(province))  # Use object id as province id
    
    # Add hexes to province (this will link them)
    for hex_obj in hexes:
        province.add_hex(hex_obj)
    
    return province


class TestBuildCommandValidator:
    """Test build command validation."""
    
    def test_validate_build_unit_on_owned_hex(self):
        """Test building a unit on an owned hex."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.RED)
        hex2 = create_test_hex(1, 0, HColor.RED)  # Adjacent to hex1
        
        # Create province with both hexes (hex2 is owned and in province)
        province = create_test_province([hex1, hex2], HColor.RED, money=100)
        hex1.add_adjacent_hex(hex2)
        hex2.add_adjacent_hex(hex1)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1, hex2],
            [province],
            HColor.RED
        )
        
        # Create command
        command = BuildPieceCommand(hex=hex2, piece_type=PieceType.PEASANT)
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert is_valid, f"Command should be valid: {error}"
    
    def test_validate_build_unit_on_gray_hex_adjacent_to_province(self):
        """Test building a unit on a gray hex adjacent to province."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.RED)  # Province hex
        hex2 = create_test_hex(1, 0, HColor.GRAY)  # Gray hex adjacent to province
        
        # Create province
        province = create_test_province([hex1], HColor.RED, money=100)
        hex1.add_adjacent_hex(hex2)
        hex2.add_adjacent_hex(hex1)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1, hex2],
            [province],
            HColor.RED
        )
        
        # Create command with province_hex
        command = BuildPieceCommand(
            hex=hex2,
            piece_type=PieceType.PEASANT,
            province_hex=hex1
        )
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert is_valid, f"Command should be valid: {error}"
    
    def test_validate_build_unit_not_adjacent_to_province(self):
        """Test building a unit on a hex not adjacent to province."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.RED)  # Province hex
        hex2 = create_test_hex(2, 0, HColor.GRAY)  # Not adjacent
        
        # Create province
        province = create_test_province([hex1], HColor.RED, money=100)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1, hex2],
            [province],
            HColor.RED
        )
        
        # Create command
        command = BuildPieceCommand(
            hex=hex2,
            piece_type=PieceType.PEASANT,
            province_hex=hex1
        )
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert not is_valid, "Command should be invalid (hex not adjacent)"
        assert "adjacent" in error.lower()
    
    def test_validate_build_static_piece_on_owned_hex(self):
        """Test building a static piece on an owned hex."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.RED)
        
        # Create province
        province = create_test_province([hex1], HColor.RED, money=100)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1],
            [province],
            HColor.RED
        )
        
        # Create command
        command = BuildPieceCommand(hex=hex1, piece_type=PieceType.FARM)
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert is_valid, f"Command should be valid: {error}"
    
    def test_validate_build_static_piece_on_gray_hex_fails(self):
        """Test building a static piece on a gray hex fails."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.GRAY)
        
        # Create province (gray hexes don't have provinces)
        province = create_test_province([], HColor.RED, money=100)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1],
            [province],
            HColor.RED
        )
        
        # Create command
        command = BuildPieceCommand(hex=hex1, piece_type=PieceType.FARM)
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert not is_valid, "Command should be invalid (static piece on gray hex)"
        assert "province" in error.lower() or "belong" in error.lower()
    
    def test_validate_build_insufficient_funds(self):
        """Test building with insufficient funds fails."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.RED)
        
        # Create province with insufficient funds
        province = create_test_province([hex1], HColor.RED, money=5)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1],
            [province],
            HColor.RED
        )
        
        # Create command (peasant costs 10)
        command = BuildPieceCommand(hex=hex1, piece_type=PieceType.PEASANT)
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert not is_valid, "Command should be invalid (insufficient funds)"
        assert "money" in error.lower()
    
    def test_validate_build_on_hex_with_piece_fails(self):
        """Test building on a hex that already has a piece fails."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.RED, piece=PieceType.TOWER)
        
        # Create province
        province = create_test_province([hex1], HColor.RED, money=100)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1],
            [province],
            HColor.RED
        )
        
        # Create command
        command = BuildPieceCommand(hex=hex1, piece_type=PieceType.FARM)
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert not is_valid, "Command should be invalid (hex has piece)"
        assert "empty" in error.lower()
    
    def test_validate_build_strong_tower_on_tower(self):
        """Test building strong tower on existing tower."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.RED, piece=PieceType.TOWER)
        
        # Create province
        province = create_test_province([hex1], HColor.RED, money=100)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1],
            [province],
            HColor.RED
        )
        
        # Create command
        command = BuildPieceCommand(hex=hex1, piece_type=PieceType.STRONG_TOWER)
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert is_valid, f"Command should be valid: {error}"


class TestBuildCommandExecutor:
    """Test build command execution."""
    
    def test_execute_build_unit_on_owned_hex(self):
        """Test executing build unit command on owned hex."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.RED)
        hex2 = create_test_hex(1, 0, HColor.RED)
        hex1.add_adjacent_hex(hex2)
        hex2.add_adjacent_hex(hex1)
        
        # Create province with both hexes (hex2 is owned and in province)
        province = create_test_province([hex1, hex2], HColor.RED, money=100)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1, hex2],
            [province],
            HColor.RED
        )
        
        # Create command
        command = BuildPieceCommand(hex=hex2, piece_type=PieceType.PEASANT)
        
        # Execute
        executor = CommandExecutor(game_state)
        success, error = executor.execute(command, HColor.RED)
        
        assert success, f"Command should succeed: {error}"
        assert len(game_state.events_manager.applied_events) == 1
        assert province.get_money() == 90  # 100 - 10
    
    def test_execute_build_unit_on_gray_hex(self):
        """Test executing build unit command on gray hex."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.RED)  # Province hex
        hex2 = create_test_hex(1, 0, HColor.GRAY)  # Gray hex
        hex1.add_adjacent_hex(hex2)
        hex2.add_adjacent_hex(hex1)
        
        # Create province
        province = create_test_province([hex1], HColor.RED, money=100)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1, hex2],
            [province],
            HColor.RED
        )
        
        # Create command with province_hex
        command = BuildPieceCommand(
            hex=hex2,
            piece_type=PieceType.PEASANT,
            province_hex=hex1
        )
        
        # Execute
        executor = CommandExecutor(game_state)
        success, error = executor.execute(command, HColor.RED)
        
        assert success, f"Command should succeed: {error}"
        assert len(game_state.events_manager.applied_events) == 1
        # Check that hex color changed to province color
        assert hex2.color == HColor.RED
        assert hex2.piece == PieceType.PEASANT
    
    def test_execute_build_farm(self):
        """Test executing build farm command."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.RED)
        
        # Create province
        province = create_test_province([hex1], HColor.RED, money=100)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1],
            [province],
            HColor.RED
        )
        
        # Create command
        command = BuildPieceCommand(hex=hex1, piece_type=PieceType.FARM)
        
        # Execute
        executor = CommandExecutor(game_state)
        success, error = executor.execute(command, HColor.RED)
        
        assert success, f"Command should succeed: {error}"
        assert len(game_state.events_manager.applied_events) == 1
        assert hex1.piece == PieceType.FARM
        assert province.get_money() == 85  # 100 - 15
    
    def test_execute_build_strong_tower_on_tower(self):
        """Test executing build strong tower on existing tower."""
        # Create test hexes
        hex1 = create_test_hex(0, 0, HColor.RED, piece=PieceType.TOWER)
        
        # Create province
        province = create_test_province([hex1], HColor.RED, money=100)
        
        # Create game state
        game_state = create_mock_game_state(
            [hex1],
            [province],
            HColor.RED
        )
        
        # Create command
        command = BuildPieceCommand(hex=hex1, piece_type=PieceType.STRONG_TOWER)
        
        # Execute
        executor = CommandExecutor(game_state)
        success, error = executor.execute(command, HColor.RED)
        
        assert success, f"Command should succeed: {error}"
        assert len(game_state.events_manager.applied_events) == 1
        assert hex1.piece == PieceType.STRONG_TOWER
        assert province.get_money() == 70  # 100 - 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
