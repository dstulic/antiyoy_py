"""Unit tests for core/death_manager.py."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.death_manager import DeathManager
from core.province import Province
from core.hex import Hex
from core.enums import HColor, PieceType, EventType, EntityType
from core.events import EventTurnEnd, EventsManager, EventsFactory, EventPieceBuild
from typing import Optional


class MockRuleset:
    """Mock ruleset for testing."""

    def get_hex_income(self, piece_type: Optional[PieceType]) -> int:
        """Get hex income."""
        if piece_type is None:
            return 1
        if piece_type in (PieceType.PINE, PieceType.PALM):
            return 0
        if piece_type == PieceType.FARM:
            return 5
        return 1

    def get_consumption(self, piece_type: Optional[PieceType]) -> int:
        """Get consumption."""
        if piece_type is None:
            return 0
        consumption_map = {
            PieceType.PEASANT: 2,
            PieceType.SPEARMAN: 6,
            PieceType.BARON: 18,
            PieceType.KNIGHT: 36,
            PieceType.TOWER: 1,
            PieceType.STRONG_TOWER: 6,
        }
        return consumption_map.get(piece_type, 0)


class MockTurnsManager:
    """Mock turns manager for testing."""
    
    def __init__(self, lap=0, turn_index=0, game_state=None):
        """Initialize mock turns manager."""
        self.lap = lap
        self.turn_index = turn_index
        self.core_model = game_state
    
    def do_switch_turn_index(self):
        """Switch to next turn."""
        if self.is_turn_index_in_end_of_lap():
            self.turn_index = 0
            self.lap += 1
        else:
            self.turn_index += 1
    
    def is_turn_index_in_end_of_lap(self) -> bool:
        """Check if turn index is at end of lap."""
        if (
            self.core_model
            and self.core_model.entities_manager
            and self.core_model.entities_manager.entities
        ):
            return self.turn_index == len(self.core_model.entities_manager.entities) - 1
        return False


class MockEntitiesManager:
    """Mock entities manager for testing."""
    
    def __init__(self, current_color: HColor, game_state=None):
        """Initialize mock entities manager."""
        from core.player_entity import PlayerEntity
        self.entities = [
            PlayerEntity(None, EntityType.HUMAN, HColor.RED),
            PlayerEntity(None, EntityType.HUMAN, HColor.BLUE)
        ]
        self.core_model = game_state
        # Initialize turn_index based on current_color
        if game_state and game_state.turns_manager:
            game_state.turns_manager.turn_index = 0 if current_color == HColor.RED else 1
    
    def get_current_entity(self):
        """Get current entity based on turn index."""
        if (
            not self.entities
            or not self.core_model
            or not self.core_model.turns_manager
        ):
            return None
        turn_index = self.core_model.turns_manager.turn_index
        if 0 <= turn_index < len(self.entities):
            return self.entities[turn_index]
        return None
    
    def get_current_color(self) -> HColor:
        """Get current color."""
        entity = self.get_current_entity()
        return entity.color if entity else HColor.GRAY


class MockProvincesManager:
    """Mock provinces manager for testing."""
    
    def __init__(self, provinces):
        """Initialize mock provinces manager."""
        self.provinces = provinces
    
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


class MockGameState:
    """Mock game state for testing."""

    def __init__(self, ruleset=None, lap=0, turn_index=0, current_color=HColor.RED, provinces=None, hexes=None):
        """Initialize mock game state."""
        self.ruleset = ruleset
        self.hexes = hexes or []
        # Create turns manager with reference to self
        self.turns_manager = MockTurnsManager(lap=lap, turn_index=turn_index, game_state=self)
        # Create entities manager with reference to self
        self.entities_manager = MockEntitiesManager(current_color=current_color, game_state=self)
        self.provinces_manager = MockProvincesManager(provinces=provinces or [])
        # Create events manager
        self.events_manager = EventsManager(self)
        self.events_manager.factory = EventsFactory(self.events_manager)
        # Create game end manager (real one, but it won't mark games as ended for single-player scenarios)
        from core.game_end_manager import GameEndManager
        self.game_end_manager = GameEndManager(self)

    def get_hex_ownership_stats(self, player_color: Optional[HColor] = None) -> dict:
        """Return hex ownership stats for game end checks (mock)."""
        total_hexes = len(self.hexes) if self.hexes else 0
        player_hexes = 0
        if self.hexes and player_color:
            for h in self.hexes:
                if h.color == player_color and h.get_province() is not None:
                    player_hexes += 1
        percentage = (player_hexes / total_hexes * 100) if total_hexes > 0 else 0.0
        return {
            'total_hexes': total_hexes,
            'player_hexes': player_hexes,
            'percentage': percentage,
        }


class TestDeathManager:
    """Tests for DeathManager class."""

    def test_initialization(self):
        """Test DeathManager initialization."""
        game_state = MockGameState()
        manager = DeathManager(game_state)
        assert manager.game_state == game_state
        assert manager.aggressive_event_validated is False

    def test_negative_money_resets_to_zero_and_kills_units(self):
        """Test that provinces with negative money have money reset to 0 and units killed."""
        ruleset = MockRuleset()
        
        # Create a province with units and negative money (BLUE, which becomes current after RED's turn ends)
        province = Province()
        province.set_id(1)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.BLUE)
        hex1.piece = PieceType.PEASANT
        hex1.unit_id = 1
        province.add_hex(hex1)
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.BLUE)
        hex2.piece = PieceType.SPEARMAN
        hex2.unit_id = 2
        province.add_hex(hex2)
        hex3 = Hex(coordinate1=2, coordinate2=0, color=HColor.BLUE)
        hex3.piece = PieceType.CITY  # Not a unit, should not be killed
        province.add_hex(hex3)
        
        # Set negative money
        province.set_money(-10)
        
        # Create game state with RED as current (turn_index=0)
        # After turn end, BLUE becomes current (turn_index=1)
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[province],
            hexes=[hex1, hex2, hex3]
        )
        
        manager = DeathManager(game_state)
        
        # Apply turn end event (switches from RED to BLUE)
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify money was reset to 0 (BLUE is now current, so BLUE's province is checked)
        assert province.get_money() == 0
        
        # Verify units were killed (converted to graves)
        assert hex1.piece == PieceType.GRAVE
        assert hex2.piece == PieceType.GRAVE
        
        # Verify non-unit piece was not affected
        assert hex3.piece == PieceType.CITY

    def test_positive_money_does_not_kill_units(self):
        """Test that provinces with positive money do not have units killed."""
        ruleset = MockRuleset()
        
        # Create a province with units and positive money
        province = Province()
        province.set_id(1)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PEASANT
        hex1.unit_id = 1
        province.add_hex(hex1)
        
        province.set_money(100)
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[province],
            hexes=[hex1]
        )
        
        manager = DeathManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify money was not changed
        assert province.get_money() == 100
        
        # Verify unit was not killed
        assert hex1.piece == PieceType.PEASANT

    def test_only_current_entity_provinces_checked(self):
        """Test that only provinces owned by current entity (after turn switch) are checked."""
        ruleset = MockRuleset()
        
        # Create two provinces - one red, one blue
        red_province = Province()
        red_province.set_id(1)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PEASANT
        hex1.unit_id = 1
        red_province.add_hex(hex1)
        red_province.set_money(-10)
        
        blue_province = Province()
        blue_province.set_id(2)
        hex2 = Hex(coordinate1=10, coordinate2=10, color=HColor.BLUE)
        hex2.piece = PieceType.PEASANT
        hex2.unit_id = 2
        blue_province.add_hex(hex2)
        blue_province.set_money(-10)
        
        # Create game state with RED as current (turn_index=0)
        # After turn end, BLUE becomes current (turn_index=1)
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[red_province, blue_province],
            hexes=[hex1, hex2]
        )
        
        manager = DeathManager(game_state)
        
        # Apply turn end event (switches from RED to BLUE)
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # After turn switch, BLUE is current, so BLUE's provinces should be checked
        # Verify blue province was reset and units killed (BLUE is now current)
        assert blue_province.get_money() == 0
        assert hex2.piece == PieceType.GRAVE
        
        # Verify red province was NOT affected (RED is not current after switch)
        assert red_province.get_money() == -10
        assert hex1.piece == PieceType.PEASANT

    def test_lonely_units_killed(self):
        """Test that units not in any province are killed."""
        ruleset = MockRuleset()
        
        # Create a hex with a unit that's not in any province
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PEASANT
        hex1.unit_id = 1
        # hex1 is not added to any province
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[],
            hexes=[hex1]
        )
        
        manager = DeathManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify lonely unit was killed
        assert hex1.piece == PieceType.GRAVE

    def test_lonely_units_not_in_province_but_has_province_reference(self):
        """Test that units with province reference are not considered lonely."""
        ruleset = MockRuleset()
        
        # Create a province
        province = Province()
        province.set_id(1)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PEASANT
        hex1.unit_id = 1
        province.add_hex(hex1)  # This sets hex1._province
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[province],
            hexes=[hex1]
        )
        
        manager = DeathManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify unit was NOT killed (it's in a province)
        assert hex1.piece == PieceType.PEASANT

    def test_neutral_hexes_ignored(self):
        """Test that neutral (gray) hexes are ignored when checking for lonely units."""
        ruleset = MockRuleset()
        
        # Create a gray hex with a unit (should be ignored)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.GRAY)
        hex1.piece = PieceType.PEASANT
        hex1.unit_id = 1
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[],
            hexes=[hex1]
        )
        
        manager = DeathManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify neutral hex unit was NOT killed
        assert hex1.piece == PieceType.PEASANT

    def test_empty_hexes_ignored(self):
        """Test that empty hexes are ignored when checking for lonely units."""
        ruleset = MockRuleset()
        
        # Create an empty hex
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        # No piece
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[],
            hexes=[hex1]
        )
        
        manager = DeathManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify empty hex was not affected
        assert hex1.piece is None

    def test_non_unit_pieces_not_killed(self):
        """Test that non-unit pieces (towers, cities, etc.) are not killed."""
        ruleset = MockRuleset()
        
        # Create a hex with a tower (not a unit)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.TOWER
        # Not in any province
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[],
            hexes=[hex1]
        )
        
        manager = DeathManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify tower was NOT killed (only units are killed)
        assert hex1.piece == PieceType.TOWER

    def test_zero_money_does_not_kill_units(self):
        """Test that provinces with exactly 0 money do not have units killed."""
        ruleset = MockRuleset()
        
        # Create a province with units and zero money
        province = Province()
        province.set_id(1)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PEASANT
        hex1.unit_id = 1
        province.add_hex(hex1)
        
        province.set_money(0)
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[province],
            hexes=[hex1]
        )
        
        manager = DeathManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify money was not changed
        assert province.get_money() == 0
        
        # Verify unit was not killed (only negative money triggers killing)
        assert hex1.piece == PieceType.PEASANT
