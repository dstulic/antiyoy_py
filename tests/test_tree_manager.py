"""Unit tests for core/tree_manager.py."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tree_manager import TreeManager
from core.province import Province
from core.hex import Hex
from core.enums import HColor, PieceType, EventType, EntityType
from core.events import EventTurnEnd, EventsManager, EventsFactory
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


class TestTreeManager:
    """Tests for TreeManager class."""

    def test_initialization(self):
        """Test TreeManager initialization."""
        game_state = MockGameState()
        manager = TreeManager(game_state)
        assert manager.game_state == game_state

    def test_graves_converted_to_trees(self):
        """Test that graves are converted to trees at turn end."""
        ruleset = MockRuleset()
        
        # Create a province with a grave (BLUE, which will be current after RED's turn ends)
        province = Province()
        province.set_id(1)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.BLUE)
        hex1.piece = PieceType.GRAVE
        province.add_hex(hex1)
        
        # Create game state with RED as current (turn_index=0)
        # After turn end, BLUE will be current (turn_index=1)
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[province],
            hexes=[hex1]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event (switches from red to blue)
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify grave was converted to a tree (palm by default)
        # Blue is now current, so blue graves are processed
        assert hex1.piece in (PieceType.PALM, PieceType.PINE)
        assert hex1.piece != PieceType.GRAVE

    def test_graves_converted_to_pine_with_6_adjacent_hexes(self):
        """Test that graves on hexes with 6 adjacent hexes become pine trees."""
        ruleset = MockRuleset()
        
        # Create a hex with 6 adjacent hexes (BLUE, which will be current after RED's turn ends)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.BLUE)
        hex1.piece = PieceType.GRAVE
        
        # Create 6 adjacent hexes
        adj_hexes = []
        for i in range(6):
            adj_hex = Hex(coordinate1=i+1, coordinate2=0, color=HColor.GRAY)
            adj_hexes.append(adj_hex)
            hex1.add_adjacent_hex(adj_hex)
        
        province = Province()
        province.set_id(1)
        province.add_hex(hex1)
        
        # Create game state with RED as current (turn_index=0)
        # After turn end, BLUE will be current (turn_index=1)
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[province],
            hexes=[hex1] + adj_hexes
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event (switches from red to blue)
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify grave was converted to pine (6 adjacent hexes)
        # Blue is now current, so blue graves are processed
        assert hex1.piece == PieceType.PINE

    def test_graves_converted_to_palm_with_fewer_adjacent_hexes(self):
        """Test that graves on hexes with fewer than 6 adjacent hexes become palm trees."""
        ruleset = MockRuleset()
        
        # Create a hex with 3 adjacent hexes (BLUE, which will be current after RED's turn ends)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.BLUE)
        hex1.piece = PieceType.GRAVE
        
        # Create 3 adjacent hexes
        adj_hexes = []
        for i in range(3):
            adj_hex = Hex(coordinate1=i+1, coordinate2=0, color=HColor.GRAY)
            adj_hexes.append(adj_hex)
            hex1.add_adjacent_hex(adj_hex)
        
        province = Province()
        province.set_id(1)
        province.add_hex(hex1)
        
        # Create game state with RED as current (turn_index=0)
        # After turn end, BLUE will be current (turn_index=1)
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[province],
            hexes=[hex1] + adj_hexes
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event (switches from red to blue)
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify grave was converted to palm (fewer than 6 adjacent hexes)
        # Blue is now current, so blue graves are processed
        assert hex1.piece == PieceType.PALM

    def test_only_current_entity_graves_converted(self):
        """Test that only graves owned by current entity (after turn switch) are converted."""
        ruleset = MockRuleset()
        
        # Create two graves - one red, one blue
        # After RED's turn ends, BLUE becomes current, so blue graves are processed
        red_hex = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        red_hex.piece = PieceType.GRAVE
        red_province = Province()
        red_province.set_id(1)
        red_province.add_hex(red_hex)
        
        blue_hex = Hex(coordinate1=10, coordinate2=10, color=HColor.BLUE)
        blue_hex.piece = PieceType.GRAVE
        blue_province = Province()
        blue_province.set_id(2)
        blue_province.add_hex(blue_hex)
        
        # Create game state with RED as current (turn_index=0)
        # After turn end, BLUE will be current (turn_index=1)
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[red_province, blue_province],
            hexes=[red_hex, blue_hex]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event (switches from red to blue)
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify blue grave was converted (blue is now current)
        assert blue_hex.piece in (PieceType.PALM, PieceType.PINE)
        
        # Verify red grave was NOT converted (red is not current after switch)
        assert red_hex.piece == PieceType.GRAVE

    def test_money_subtracted_for_first_entity(self):
        """Test that 1 money is subtracted when converting grave to tree for first entity."""
        ruleset = MockRuleset()
        
        # Create a province with a grave and positive money (RED, first entity)
        # Note: After turn end, RED is still first entity (entities[0])
        province = Province()
        province.set_id(1)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.GRAVE
        province.add_hex(hex1)
        province.set_money(100)  # Positive money
        
        # Create game state with RED as current (turn_index=0)
        # After turn end, BLUE becomes current, but RED is still first entity (entities[0])
        # So money is subtracted for RED graves when RED is current again
        # Actually, let's test when RED is current after a turn cycle
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=1,  # BLUE's turn
            current_color=HColor.BLUE,
            provinces=[province],
            hexes=[hex1]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event (switches from blue back to red)
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify grave was converted to tree (red is now current)
        assert hex1.piece in (PieceType.PALM, PieceType.PINE)
        
        # Verify 1 money was subtracted (burial cost, RED is first entity)
        assert province.get_money() == 99

    def test_money_not_subtracted_for_non_first_entity(self):
        """Test that money is NOT subtracted when converting grave for non-first entity."""
        ruleset = MockRuleset()
        
        # Create a province with a grave and positive money (BLUE, second entity)
        province = Province()
        province.set_id(1)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.BLUE)
        hex1.piece = PieceType.GRAVE
        province.add_hex(hex1)
        province.set_money(100)  # Positive money
        
        # Create game state with RED as current (turn_index=0)
        # After turn end, BLUE becomes current (turn_index=1, not first entity)
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[province],
            hexes=[hex1]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event (switches from red to blue)
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify grave was converted to tree (blue is now current)
        assert hex1.piece in (PieceType.PALM, PieceType.PINE)
        
        # Verify money was NOT subtracted (BLUE is not first entity)
        assert province.get_money() == 100

    def test_money_not_subtracted_if_province_has_zero_money(self):
        """Test that money is NOT subtracted if province has 0 or negative money."""
        ruleset = MockRuleset()
        
        # Create a province with a grave and zero money (RED, first entity)
        province = Province()
        province.set_id(1)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.GRAVE
        province.add_hex(hex1)
        province.set_money(0)  # Zero money
        
        # Create game state with BLUE as current (turn_index=1)
        # After turn end, RED becomes current (turn_index=0, first entity)
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=1,
            current_color=HColor.BLUE,
            provinces=[province],
            hexes=[hex1]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event (switches from blue back to red)
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify grave was converted to tree (red is now current)
        assert hex1.piece in (PieceType.PALM, PieceType.PINE)
        
        # Verify money was NOT subtracted (province has 0 money)
        assert province.get_money() == 0

    def test_money_not_subtracted_if_hex_not_in_province(self):
        """Test that money is NOT subtracted if hex is not in a province."""
        ruleset = MockRuleset()
        
        # Create a grave hex not in any province (BLUE, which will be current after RED's turn ends)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.BLUE)
        hex1.piece = PieceType.GRAVE
        
        # Create game state with RED as current (turn_index=0)
        # After turn end, BLUE will be current (turn_index=1)
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[],
            hexes=[hex1]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event (switches from red to blue)
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify grave was converted to tree (blue is now current)
        assert hex1.piece in (PieceType.PALM, PieceType.PINE)
        
        # No money subtraction test needed (no province)

    def test_lonely_cities_converted_to_trees(self):
        """Test that lonely cities (not in any province) are converted to trees."""
        ruleset = MockRuleset()
        
        # Create a lonely city (RED, not in any province)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.CITY
        # Don't add to any province - it's lonely
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[],  # No provinces
            hexes=[hex1]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify lonely city was converted to tree
        assert hex1.piece in (PieceType.PALM, PieceType.PINE)
        assert hex1.piece != PieceType.CITY

    def test_cities_in_provinces_not_converted(self):
        """Test that cities in provinces are NOT converted to trees."""
        ruleset = MockRuleset()
        
        # Create a city in a province (RED)
        province = Province()
        province.set_id(1)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.CITY
        province.add_hex(hex1)
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[province],
            hexes=[hex1]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify city was NOT converted (it's in a province)
        assert hex1.piece == PieceType.CITY

    def test_gray_cities_not_converted(self):
        """Test that gray (neutral) cities are NOT converted to trees."""
        ruleset = MockRuleset()
        
        # Create a gray city (not in any province)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.GRAY)
        hex1.piece = PieceType.CITY
        # Don't add to any province - it's lonely, but gray
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[],
            hexes=[hex1]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify gray city was NOT converted
        assert hex1.piece == PieceType.CITY

    def test_non_city_pieces_not_converted(self):
        """Test that non-city pieces are NOT converted to trees."""
        ruleset = MockRuleset()
        
        # Create a lonely unit (not in any province)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PEASANT
        # Don't add to any province - it's lonely
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[],
            hexes=[hex1]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify unit was NOT converted (only cities are converted)
        assert hex1.piece == PieceType.PEASANT

    def test_lonely_cities_all_colors_converted(self):
        """Test that lonely cities of all colors (except gray) are converted."""
        ruleset = MockRuleset()
        
        # Create lonely cities of different colors
        red_hex = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        red_hex.piece = PieceType.CITY
        
        blue_hex = Hex(coordinate1=10, coordinate2=10, color=HColor.BLUE)
        blue_hex.piece = PieceType.CITY
        
        green_hex = Hex(coordinate1=20, coordinate2=20, color=HColor.GREEN)
        green_hex.piece = PieceType.CITY
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[],
            hexes=[red_hex, blue_hex, green_hex]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify all lonely cities were converted (regardless of color)
        assert red_hex.piece in (PieceType.PALM, PieceType.PINE)
        assert blue_hex.piece in (PieceType.PALM, PieceType.PINE)
        assert green_hex.piece in (PieceType.PALM, PieceType.PINE)

    def test_lonely_city_with_6_adjacent_hexes_becomes_pine(self):
        """Test that lonely cities on hexes with 6 adjacent hexes become pine trees."""
        ruleset = MockRuleset()
        
        # Create a lonely city with 6 adjacent hexes
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.CITY
        
        # Create 6 adjacent hexes
        adj_hexes = []
        for i in range(6):
            adj_hex = Hex(coordinate1=i+1, coordinate2=0, color=HColor.GRAY)
            adj_hexes.append(adj_hex)
            hex1.add_adjacent_hex(adj_hex)
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[],
            hexes=[hex1] + adj_hexes
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify lonely city was converted to pine (6 adjacent hexes)
        assert hex1.piece == PieceType.PINE

    def test_lonely_city_money_not_subtracted(self):
        """Test that money is NOT subtracted when converting lonely cities (not in province)."""
        ruleset = MockRuleset()
        
        # Create a province with money (but the city is not in it)
        province = Province()
        province.set_id(1)
        province.set_money(100)
        
        # Create a lonely city (not in the province)
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.CITY
        # Don't add to province - it's lonely
        
        # Create game state
        game_state = MockGameState(
            ruleset=ruleset,
            lap=1,
            turn_index=0,
            current_color=HColor.RED,
            provinces=[province],
            hexes=[hex1]
        )
        
        manager = TreeManager(game_state)
        
        # Apply turn end event
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event)
        
        # Verify lonely city was converted to tree
        assert hex1.piece in (PieceType.PALM, PieceType.PINE)
        
        # Verify money was NOT subtracted (lonely city is not in a province)
        assert province.get_money() == 100
