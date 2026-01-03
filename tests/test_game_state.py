"""Unit tests for core/game_state.py."""

import pytest
from core.game_state import GameState
from core.hex import Hex
from core.enums import HColor, RulesType, EntityType
from core.events import EventPieceAdd, EventPieceBuild
from core.enums import PieceType


class TestGameState:
    """Tests for GameState class."""

    def test_game_state_initialization(self):
        """Test game state initialization."""
        game_state = GameState()
        assert len(game_state.hexes) == 0
        assert game_state.current_unit_id == 0
        assert game_state.events_manager is not None
        assert game_state.provinces_manager is not None
        assert game_state.entities_manager is not None
        assert game_state.turns_manager is not None

    def test_add_hex(self):
        """Test adding hex."""
        game_state = GameState()
        hex = game_state.add_hex(5, 10, HColor.RED)
        assert hex.coordinate1 == 5
        assert hex.coordinate2 == 10
        assert hex.color == HColor.RED
        assert hex in game_state.hexes

    def test_get_hex(self):
        """Test getting hex by coordinates."""
        game_state = GameState()
        hex1 = game_state.add_hex(5, 10, HColor.RED)
        hex2 = game_state.get_hex(5, 10)
        assert hex2 == hex1
        assert game_state.get_hex(99, 99) is None

    def test_get_hex_with_same_coordinates(self):
        """Test getting hex with same coordinates."""
        game_state = GameState()
        hex1 = game_state.add_hex(5, 10, HColor.RED)
        hex2 = Hex(coordinate1=5, coordinate2=10, color=HColor.BLUE)
        found = game_state.get_hex_with_same_coordinates(hex2)
        assert found == hex1

    def test_remove_hex(self):
        """Test removing hex."""
        game_state = GameState()
        hex1 = game_state.add_hex(5, 10, HColor.RED)
        hex2 = game_state.add_hex(6, 10, HColor.BLUE)
        hex1.add_adjacent_hex(hex2)
        game_state.remove_hex(hex1)
        assert hex1 not in game_state.hexes
        assert hex1 not in hex2.adjacent_hexes

    def test_set_ruleset(self):
        """Test setting ruleset."""
        game_state = GameState()
        game_state.set_ruleset(RulesType.DEF, 1)
        assert game_state.ruleset is not None
        assert game_state.ruleset.get_rules_type() == RulesType.DEF

    def test_get_id_for_new_unit(self):
        """Test getting ID for new unit."""
        game_state = GameState()
        id1 = game_state.get_id_for_new_unit()
        assert id1 == 0
        id2 = game_state.get_id_for_new_unit()
        assert id2 == 1
        assert game_state.current_unit_id == 2

    def test_on_event_applied(self):
        """Test event applied handler."""
        game_state = GameState()
        hex = game_state.add_hex(0, 0, HColor.RED)
        event = EventPieceAdd()
        event.set_core_model(game_state)
        event.set_hex(hex)
        event.set_piece_type(PieceType.PEASANT)
        event.set_unit_id(5)
        game_state.on_event_applied(event)
        # Should increase current_unit_id
        assert game_state.current_unit_id >= 5

    def test_is_terminal(self):
        """Test is_terminal() method."""
        game_state = GameState()
        # Empty game state
        assert game_state.is_terminal() is False
        # Add entities and provinces
        from core.player_entity import PlayerEntity
        entity1 = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
        entity2 = PlayerEntity(game_state.entities_manager, EntityType.AI_BALANCER, HColor.BLUE)
        game_state.entities_manager.initialize([entity1, entity2])
        # No provinces yet
        assert game_state.is_terminal() is False
        # Add province for one color
        province = game_state.provinces_manager.add_province()
        hex1 = game_state.add_hex(0, 0, HColor.RED)
        province.add_hex(hex1)
        # Still not terminal (other player might have provinces)
        # Actually, with only one color having provinces, it could be terminal
        # But let's test with two colors having provinces
        province2 = game_state.provinces_manager.add_province()
        hex2 = game_state.add_hex(1, 0, HColor.BLUE)
        province2.add_hex(hex2)
        assert game_state.is_terminal() is False  # Two colors have provinces

    def test_get_winner(self):
        """Test get_winner() method."""
        game_state = GameState()
        assert game_state.get_winner() is None  # Not terminal
        # Initialize entities
        from core.player_entity import PlayerEntity
        entity1 = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
        game_state.entities_manager.initialize([entity1])
        # Create terminal state
        province = game_state.provinces_manager.add_province()
        hex1 = game_state.add_hex(0, 0, HColor.RED)
        province.add_hex(hex1)
        # Only one color has provinces
        winner = game_state.get_winner()
        assert winner == HColor.RED

    def test_encode_hexes(self):
        """Test encoding hexes."""
        game_state = GameState()
        assert game_state.encode_hexes() == "-"  # Empty
        hex1 = game_state.add_hex(5, 10, HColor.RED)
        hex1.set_piece(PieceType.CITY)
        encoded = game_state.encode_hexes()
        assert "5 10 red" in encoded

    def test_encode_current_ids(self):
        """Test encoding current IDs."""
        game_state = GameState()
        game_state.current_unit_id = 5
        assert game_state.encode_current_ids() == "5"

    def test_encode_rules(self):
        """Test encoding rules."""
        game_state = GameState()
        game_state.set_ruleset(RulesType.DEF, 1)
        encoded = game_state.encode_rules()
        assert "def" in encoded
        assert "1" in encoded
