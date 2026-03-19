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
    
    def is_unit_ready_on_built(self) -> bool:
        """Mock method for unit readiness on build."""
        return True
    
    def get_tree_reward(self) -> int:
        """Mock method for tree reward."""
        return 5
    
    def can_hex_be_captured(self, hex_obj, strength: int) -> bool:
        """Mock method for checking if hex can be captured."""
        # Simple logic: allow capture if hex has enemy unit or static piece
        # In real game, this would check defense values
        if hex_obj.has_unit():
            # Can capture enemy units (simplified - always allow)
            return True
        if hex_obj.has_static_piece():
            # Can capture cities/towers if strength >= defense
            # Simplified: always allow for testing
            return True
        # Empty hexes or trees can be captured
        return True


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
    
    def get_province_by_color(self, color):
        """Get province by color (returns first matching)."""
        for province in self.provinces:
            if province.get_color() == color:
                return province
        return None


class MockEntitiesManager:
    """Mock entities manager for testing."""
    
    def __init__(self, current_color: HColor):
        self.current_color = current_color
        self._entities = {}
    
    def get_current_entity(self):
        from core.player_entity import PlayerEntity
        from core.enums import EntityType
        entity = PlayerEntity(None, EntityType.HUMAN, self.current_color)
        # Cache the entity
        self._entities[self.current_color] = entity
        return entity
    
    def get_current_color(self) -> HColor:
        return self.current_color
    
    def get_entity(self, color: HColor):
        """Get entity by color."""
        if color in self._entities:
            return self._entities[color]
        # Create entity if not cached
        from core.player_entity import PlayerEntity
        from core.enums import EntityType
        entity = PlayerEntity(None, EntityType.HUMAN, color)
        self._entities[color] = entity
        return entity


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
    
    def create_event(self, event_type, author=None):
        """Create event; author is accepted for compatibility with real EventsFactory."""
        from core.events import EventPieceBuild
        from core.enums import EventType
        if event_type == EventType.PIECE_BUILD or (hasattr(event_type, 'value') and event_type.value == "piece_build"):
            event = EventPieceBuild()
            if self.game_state:
                event.core_model = self.game_state
            if author is not None and hasattr(event, 'set_author'):
                event.set_author(author)
            return event
        return None


class MockFogOfWarManager:
    """Mock fog of war manager for testing."""
    
    def __init__(self, enabled=False):
        self.enabled = enabled
    
    def apply_update(self):
        pass


class MockReadinessManager:
    """Mock readiness manager for testing."""
    
    def __init__(self):
        self.ready_hexes = []
    
    def is_ready(self, hex_obj):
        """Check if hex is ready."""
        return hex_obj in self.ready_hexes
    
    def set_ready(self, hex_obj, value: bool):
        """Set hex readiness."""
        if value and hex_obj not in self.ready_hexes:
            self.ready_hexes.append(hex_obj)
        elif not value and hex_obj in self.ready_hexes:
            self.ready_hexes.remove(hex_obj)


class MockMoveZoneManager:
    """Mock move zone manager for testing."""
    
    def __init__(self, game_state):
        self.game_state = game_state
        self.hexes = []
        self._limit = 4
        self._strength = 0
        self._start_hex = None
        self._start_entity = None
        # Store a real MoveZoneManager instance for actual calculations
        from core.move_zone_manager import MoveZoneManager
        self._real_manager = MoveZoneManager(game_state)
    
    def update(self, start_hex, limit, strength):
        """Update movement zone using real MoveZoneManager."""
        from save_load.decoder import _build_adjacency_graph
        
        self._limit = limit
        self._strength = strength
        self._start_hex = start_hex
        
        # Get start entity
        if self.game_state.entities_manager:
            self._start_entity = self.game_state.entities_manager.get_entity(start_hex.color)
        
        # Ensure adjacency is built
        if not start_hex.adjacent_hexes:
            _build_adjacency_graph(self.game_state)
        
        # Use the real MoveZoneManager for calculations
        self._real_manager.update(start_hex, limit, strength)
        self.hexes = self._real_manager.hexes
    
    def clear(self):
        """Clear movement zone."""
        self.hexes.clear()
        self._real_manager.clear()
    
    def contains(self, hex_obj):
        """Check if hex is in movement zone."""
        return hex_obj in self.hexes


def create_mock_game_state(hexes, provinces, current_color: HColor, ruleset=None):
    """Create a mock game state for testing."""
    game_state = GameState.__new__(GameState)
    game_state.hexes = hexes
    game_state.ruleset = ruleset or MockRuleset()
    game_state.provinces_manager = MockProvincesManager(provinces)
    game_state.entities_manager = MockEntitiesManager(current_color)
    game_state.events_manager = MockEventsManager(game_state)
    game_state.fog_of_war_manager = MockFogOfWarManager(enabled=False)
    game_state.readiness_manager = MockReadinessManager()
    # Mock game_end_manager to prevent "Game has ended" errors in tests
    game_state.game_end_manager = MockGameEndManager()
    # Mock move_zone_manager (needed for unit placement validation)
    game_state.move_zone_manager = MockMoveZoneManager(game_state)
    
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
    
    # Ensure adjacency is built for hexes
    from save_load.decoder import _build_adjacency_graph
    _build_adjacency_graph(game_state)
    
    return game_state


class MockGameEndManager:
    """Mock game end manager for testing."""

    def __init__(self):
        self.game_ended = False
        self.dead_players = set()

    def is_player_dead(self, color):
        """Check if player is dead."""
        return color in self.dead_players

    def can_make_turn(self):
        """Check if turn can be made."""
        return not self.game_ended


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
        
        assert not is_valid, "Command should be invalid (hex not reachable)"
        assert "reachable" in error.lower() or "range" in error.lower()
    
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


class TestBuildUnitOnEnemyTerritory:
    """Test building units on enemy territory (up to 4 hexes away)."""
    
    def test_build_unit_on_enemy_hex_within_4_hexes(self):
        """Test that a unit can be built on an enemy hex within 4 hexes of province."""
        from core.game_state import GameState
        from core.enums import RulesType, EntityType
        from save_load.decoder import _build_adjacency_graph
        from core.player_entity import PlayerEntity
        
        game_state = GameState()
        game_state.set_ruleset(RulesType.DEF, version_code=1)
        
        # Create red province with city
        red_hex1 = game_state.add_hex(0, 0, HColor.RED)
        red_hex1.piece = PieceType.CITY
        
        # Create chain of hexes: red -> empty -> empty -> empty -> enemy hex
        # This tests that we can build up to 4 hexes away
        hex2 = game_state.add_hex(1, 0, HColor.RED)
        hex3 = game_state.add_hex(2, 0, HColor.RED)
        hex4 = game_state.add_hex(3, 0, HColor.RED)
        enemy_hex = game_state.add_hex(4, 0, HColor.BLUE)  # 4 hexes away
        
        _build_adjacency_graph(game_state)
        
        # Create player entities
        red_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
        blue_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.BLUE)
        if game_state.entities_manager.entities is None:
            game_state.entities_manager.entities = []
        game_state.entities_manager.entities.append(red_player)
        game_state.entities_manager.entities.append(blue_player)
        
        # Build provinces
        game_state.provinces_manager.builder.grant_permission()
        game_state.provinces_manager.builder.apply()
        
        # Get red province
        red_province = None
        for province in game_state.provinces_manager.provinces:
            if province.get_color() == HColor.RED:
                red_province = province
                break
        
        assert red_province is not None, "Red province should exist"
        red_province.set_money(200)
        
        # Add empty red hexes to the province (they should be connected to the city)
        # This ensures they're considered part of the province for movement calculations
        # Only add hexes that exist in this test
        hexes_to_add = []
        if 'hex2' in locals():
            hexes_to_add.append(hex2)
        if 'hex3' in locals():
            hexes_to_add.append(hex3)
        if 'hex4' in locals():
            hexes_to_add.append(hex4)
        if 'hex5' in locals():
            hexes_to_add.append(hex5)
        
        for hex_obj in hexes_to_add:
            if hex_obj not in red_province.get_hexes():
                red_province.add_hex(hex_obj)
        
        # Create command to build unit on enemy hex
        command = BuildPieceCommand(
            hex=enemy_hex,
            piece_type=PieceType.PEASANT,
            province_id=red_province.get_id(),
            province_hex=red_hex1
        )
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert is_valid, f"Command should be valid (enemy hex within 4 hexes): {error}"
        
        # Execute
        executor = CommandExecutor(game_state)
        success, error = executor.execute(command, HColor.RED)
        
        assert success, f"Command should succeed: {error}"
        assert enemy_hex.piece == PieceType.PEASANT, "Enemy hex should have unit after build"
        assert enemy_hex.color == HColor.RED, "Enemy hex should be colored red after capture"
    
    def test_build_unit_on_enemy_hex_beyond_4_hexes_fails(self):
        """Test that a unit cannot be built on an enemy hex beyond 4 hexes away."""
        from core.game_state import GameState
        from core.enums import RulesType, EntityType
        from save_load.decoder import _build_adjacency_graph
        from core.player_entity import PlayerEntity
        
        game_state = GameState()
        game_state.set_ruleset(RulesType.DEF, version_code=1)
        
        # Create red province with city
        red_hex1 = game_state.add_hex(0, 0, HColor.RED)
        red_hex1.piece = PieceType.CITY
        
        # Create chain: red -> empty -> empty -> empty -> empty -> enemy hex (5 hexes away)
        # To test that hex5 is beyond the 4-hex limit, we need to ensure hex5 is NOT in the province
        # Otherwise, the enemy hex would be reachable from hex5 (1 hex away)
        # So we'll make hex5 gray (neutral) so it's not automatically added to the province
        hex2 = game_state.add_hex(1, 0, HColor.RED)
        hex3 = game_state.add_hex(2, 0, HColor.RED)
        hex4 = game_state.add_hex(3, 0, HColor.RED)
        hex5 = game_state.add_hex(4, 0, HColor.GRAY)  # Gray so it's not in the province
        enemy_hex = game_state.add_hex(5, 0, HColor.BLUE)  # 5 hexes away (too far), adjacent to hex5
        
        _build_adjacency_graph(game_state)
        
        # Create player entities
        red_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
        blue_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.BLUE)
        if game_state.entities_manager.entities is None:
            game_state.entities_manager.entities = []
        game_state.entities_manager.entities.append(red_player)
        game_state.entities_manager.entities.append(blue_player)
        
        # Build provinces
        game_state.provinces_manager.builder.grant_permission()
        game_state.provinces_manager.builder.apply()
        
        # Get red province
        red_province = None
        for province in game_state.provinces_manager.provinces:
            if province.get_color() == HColor.RED:
                red_province = province
                break
        
        assert red_province is not None, "Red province should exist"
        red_province.set_money(200)
        
        # Verify that hex5 is NOT in the province (it's gray, so it shouldn't be)
        # This ensures the enemy hex can only be reached through the red hexes,
        # and since it's 5 hexes away from red_hex1, it should be beyond the 4-hex limit
        assert hex5 not in red_province.get_hexes(), "hex5 should not be in the province (it's gray)"
        
        # Create command to build unit on enemy hex (too far)
        command = BuildPieceCommand(
            hex=enemy_hex,
            piece_type=PieceType.PEASANT,
            province_id=red_province.get_id(),
            province_hex=red_hex1
        )
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert not is_valid, "Command should be invalid (enemy hex beyond 4 hexes)"
        assert "reachable" in error.lower() or "range" in error.lower(), \
            f"Error should mention reachability/range, got: {error}"
    
    def test_build_unit_on_enemy_hex_with_enemy_unit(self):
        """Test that a unit can be built on an enemy hex with an enemy unit (capture)."""
        from core.game_state import GameState
        from core.enums import RulesType, EntityType
        from save_load.decoder import _build_adjacency_graph
        from core.player_entity import PlayerEntity
        
        game_state = GameState()
        game_state.set_ruleset(RulesType.DEF, version_code=1)
        
        # Create red province with city
        red_hex1 = game_state.add_hex(0, 0, HColor.RED)
        red_hex1.piece = PieceType.CITY
        
        # Create enemy hex with enemy unit (2 hexes away)
        # Enemy hex must be adjacent to the friendly hex chain
        hex2 = game_state.add_hex(1, 0, HColor.RED)
        enemy_hex = game_state.add_hex(2, 0, HColor.BLUE)  # Adjacent to hex2
        enemy_hex.piece = PieceType.PEASANT  # Enemy unit
        
        _build_adjacency_graph(game_state)
        
        # Create player entities
        red_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
        blue_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.BLUE)
        if game_state.entities_manager.entities is None:
            game_state.entities_manager.entities = []
        game_state.entities_manager.entities.append(red_player)
        game_state.entities_manager.entities.append(blue_player)
        
        # Build provinces
        game_state.provinces_manager.builder.grant_permission()
        game_state.provinces_manager.builder.apply()
        
        # Get red province
        red_province = None
        for province in game_state.provinces_manager.provinces:
            if province.get_color() == HColor.RED:
                red_province = province
                break
        
        assert red_province is not None, "Red province should exist"
        red_province.set_money(200)
        
        # Ensure hex2 is in the province (it should be automatically added, but verify)
        # The move zone needs to propagate through hex2 to reach the enemy hex
        if hex2 not in red_province.get_hexes():
            red_province.add_hex(hex2)
        
        # Create command to build spearman (strength 2) on enemy hex with enemy peasant (defense 1)
        # Spearman can capture peasant (strength 2 > defense 1)
        command = BuildPieceCommand(
            hex=enemy_hex,
            piece_type=PieceType.SPEARMAN,
            province_id=red_province.get_id(),
            province_hex=red_hex1
        )
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert is_valid, f"Command should be valid (spearman can capture peasant): {error}"
        
        # Execute
        executor = CommandExecutor(game_state)
        success, error = executor.execute(command, HColor.RED)
        
        assert success, f"Command should succeed: {error}"
        # The enemy unit should be replaced by our unit
        assert enemy_hex.piece == PieceType.SPEARMAN, "Enemy hex should have our spearman after build"
        assert enemy_hex.color == HColor.RED, "Enemy hex should be colored red after capture"
    
    def test_build_unit_on_enemy_hex_with_city(self):
        """Test that a unit can be built on an enemy hex with a city (if unit strength allows)."""
        from core.game_state import GameState
        from core.enums import RulesType, EntityType
        from save_load.decoder import _build_adjacency_graph
        from core.player_entity import PlayerEntity
        
        game_state = GameState()
        game_state.set_ruleset(RulesType.DEF, version_code=1)
        
        # Create red province with city
        red_hex1 = game_state.add_hex(0, 0, HColor.RED)
        red_hex1.piece = PieceType.CITY
        
        # Create enemy hex with city (2 hexes away)
        # Enemy hex must be adjacent to the friendly hex chain
        hex2 = game_state.add_hex(1, 0, HColor.RED)
        enemy_hex = game_state.add_hex(2, 0, HColor.BLUE)  # Adjacent to hex2
        enemy_hex.piece = PieceType.CITY  # Enemy city (defense 1)
        
        _build_adjacency_graph(game_state)
        
        # Create player entities
        red_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
        blue_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.BLUE)
        if game_state.entities_manager.entities is None:
            game_state.entities_manager.entities = []
        game_state.entities_manager.entities.append(red_player)
        game_state.entities_manager.entities.append(blue_player)
        
        # Build provinces
        game_state.provinces_manager.builder.grant_permission()
        game_state.provinces_manager.builder.apply()
        
        # Get red province
        red_province = None
        for province in game_state.provinces_manager.provinces:
            if province.get_color() == HColor.RED:
                red_province = province
                break
        
        assert red_province is not None, "Red province should exist"
        red_province.set_money(200)
        
        # Ensure hex2 is in the province (it should be automatically added, but verify)
        # The move zone needs to propagate through hex2 to reach the enemy hex
        if hex2 not in red_province.get_hexes():
            red_province.add_hex(hex2)
        
        # Create command to build spearman (strength 2) on enemy city (defense 1)
        # Spearman can capture city (strength 2 > defense 1)
        # Note: Peasant (strength 1) cannot capture city (defense 1) because 1 is not > 1
        command = BuildPieceCommand(
            hex=enemy_hex,
            piece_type=PieceType.SPEARMAN,
            province_id=red_province.get_id(),
            province_hex=red_hex1
        )
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert is_valid, f"Command should be valid (spearman can capture city): {error}"
        
        # Execute
        executor = CommandExecutor(game_state)
        success, error = executor.execute(command, HColor.RED)
        
        assert success, f"Command should succeed: {error}"
        # The city should be replaced by our unit
        assert enemy_hex.piece == PieceType.SPEARMAN, "Enemy hex should have our spearman after build"
        assert enemy_hex.color == HColor.RED, "Enemy hex should be colored red after capture"
    
    def test_build_unit_on_enemy_hex_3_hexes_away(self):
        """Test that a unit can be built on an enemy hex exactly 3 hexes away."""
        from core.game_state import GameState
        from core.enums import RulesType, EntityType
        from save_load.decoder import _build_adjacency_graph
        from core.player_entity import PlayerEntity
        
        game_state = GameState()
        game_state.set_ruleset(RulesType.DEF, version_code=1)
        
        # Create red province with city
        red_hex1 = game_state.add_hex(0, 0, HColor.RED)
        red_hex1.piece = PieceType.CITY
        
        # Create chain: red -> empty -> empty -> enemy hex (3 hexes away)
        # Enemy hex must be adjacent to the last friendly hex in the chain
        hex2 = game_state.add_hex(1, 0, HColor.RED)
        hex3 = game_state.add_hex(2, 0, HColor.RED)
        enemy_hex = game_state.add_hex(3, 0, HColor.BLUE)  # 3 hexes away, adjacent to hex3
        
        _build_adjacency_graph(game_state)
        
        # Create player entities
        red_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
        blue_player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.BLUE)
        if game_state.entities_manager.entities is None:
            game_state.entities_manager.entities = []
        game_state.entities_manager.entities.append(red_player)
        game_state.entities_manager.entities.append(blue_player)
        
        # Build provinces
        game_state.provinces_manager.builder.grant_permission()
        game_state.provinces_manager.builder.apply()
        
        # Get red province
        red_province = None
        for province in game_state.provinces_manager.provinces:
            if province.get_color() == HColor.RED:
                red_province = province
                break
        
        assert red_province is not None, "Red province should exist"
        red_province.set_money(200)
        
        # Add empty red hexes to the province (they should be connected to the city)
        # This ensures they're considered part of the province for movement calculations
        # Only add hexes that exist in this test
        hexes_to_add = []
        if 'hex2' in locals():
            hexes_to_add.append(hex2)
        if 'hex3' in locals():
            hexes_to_add.append(hex3)
        if 'hex4' in locals():
            hexes_to_add.append(hex4)
        if 'hex5' in locals():
            hexes_to_add.append(hex5)
        
        for hex_obj in hexes_to_add:
            if hex_obj not in red_province.get_hexes():
                red_province.add_hex(hex_obj)
        
        # Create command to build unit on enemy hex (3 hexes away)
        command = BuildPieceCommand(
            hex=enemy_hex,
            piece_type=PieceType.PEASANT,
            province_id=red_province.get_id(),
            province_hex=red_hex1
        )
        
        # Validate
        validator = CommandValidator(game_state)
        is_valid, error = validator.validate(command, HColor.RED)
        
        assert is_valid, f"Command should be valid (enemy hex 3 hexes away): {error}"
        
        # Execute
        executor = CommandExecutor(game_state)
        success, error = executor.execute(command, HColor.RED)
        
        assert success, f"Command should succeed: {error}"
        assert enemy_hex.piece == PieceType.PEASANT, "Enemy hex should have unit after build"
        assert enemy_hex.color == HColor.RED, "Enemy hex should be colored red after capture"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
