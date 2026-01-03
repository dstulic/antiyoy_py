"""Unit tests for core/hex.py."""

import pytest
from core.hex import Hex
from core.enums import HColor, PieceType
from core.core_utils import is_unit


class TestHex:
    """Tests for Hex class."""

    def test_hex_initialization(self):
        """Test hex initialization with default values."""
        hex = Hex()
        assert hex.coordinate1 == 0
        assert hex.coordinate2 == 0
        assert hex.color == HColor.GRAY
        assert hex.piece is None
        assert hex.unit_id == -1
        assert len(hex.adjacent_hexes) == 0
        assert hex.flag is False
        assert hex.fog is False

    def test_hex_initialization_with_params(self):
        """Test hex initialization with parameters."""
        hex = Hex(coordinate1=5, coordinate2=10, color=HColor.RED)
        assert hex.coordinate1 == 5
        assert hex.coordinate2 == 10
        assert hex.color == HColor.RED

    def test_has_piece(self):
        """Test has_piece() method."""
        hex = Hex()
        assert hex.has_piece() is False
        hex.set_piece(PieceType.PEASANT)
        assert hex.has_piece() is True

    def test_is_empty(self):
        """Test is_empty() method."""
        hex = Hex()
        assert hex.is_empty() is True
        hex.set_piece(PieceType.PEASANT)
        assert hex.is_empty() is False

    def test_has_unit(self):
        """Test has_unit() method."""
        hex = Hex()
        assert hex.has_unit() is False
        hex.set_piece(PieceType.PEASANT)
        assert hex.has_unit() is True
        hex.set_piece(PieceType.CITY)
        assert hex.has_unit() is False

    def test_has_tree(self):
        """Test has_tree() method."""
        hex = Hex()
        assert hex.has_tree() is False
        hex.set_piece(PieceType.PINE)
        assert hex.has_tree() is True
        hex.set_piece(PieceType.PALM)
        assert hex.has_tree() is True
        hex.set_piece(PieceType.CITY)
        assert hex.has_tree() is False

    def test_has_tower(self):
        """Test has_tower() method."""
        hex = Hex()
        assert hex.has_tower() is False
        hex.set_piece(PieceType.TOWER)
        assert hex.has_tower() is True
        hex.set_piece(PieceType.STRONG_TOWER)
        assert hex.has_tower() is True
        hex.set_piece(PieceType.CITY)
        assert hex.has_tower() is False

    def test_has_static_piece(self):
        """Test has_static_piece() method."""
        hex = Hex()
        assert hex.has_static_piece() is False
        hex.set_piece(PieceType.CITY)
        assert hex.has_static_piece() is True
        hex.set_piece(PieceType.PEASANT)
        assert hex.has_static_piece() is False

    def test_set_piece(self):
        """Test set_piece() method."""
        hex = Hex()
        hex.set_piece(PieceType.PEASANT)
        assert hex.piece == PieceType.PEASANT
        hex.set_piece(None)
        assert hex.piece is None

    def test_set_unit_id(self):
        """Test set_unit_id() method."""
        hex = Hex()
        assert hex.unit_id == -1
        hex.set_unit_id(5)
        assert hex.unit_id == 5

    def test_set_color(self):
        """Test set_color() method."""
        hex = Hex()
        assert hex.color == HColor.GRAY
        hex.set_color(HColor.RED)
        assert hex.color == HColor.RED
        hex.set_color(HColor.RED)  # Same color
        assert hex.color == HColor.RED

    def test_get_color(self):
        """Test get_color() method."""
        hex = Hex(color=HColor.BLUE)
        assert hex.get_color() == HColor.BLUE

    def test_is_colored(self):
        """Test is_colored() method."""
        hex = Hex()
        assert hex.is_colored() is False
        hex.set_color(HColor.RED)
        assert hex.is_colored() is True

    def test_is_neutral(self):
        """Test is_neutral() method."""
        hex = Hex()
        assert hex.is_neutral() is True
        hex.set_color(HColor.RED)
        assert hex.is_neutral() is False

    def test_has_coordinates(self):
        """Test has_coordinates() method."""
        hex = Hex(coordinate1=5, coordinate2=10)
        assert hex.has_coordinates(5, 10) is True
        assert hex.has_coordinates(5, 11) is False
        assert hex.has_coordinates(6, 10) is False

    def test_has_same_coordinates_as(self):
        """Test has_same_coordinates_as() method."""
        hex1 = Hex(coordinate1=5, coordinate2=10)
        hex2 = Hex(coordinate1=5, coordinate2=10)
        hex3 = Hex(coordinate1=6, coordinate2=10)
        assert hex1.has_same_coordinates_as(hex2) is True
        assert hex1.has_same_coordinates_as(hex3) is False

    def test_copy_from(self):
        """Test copy_from() method."""
        hex1 = Hex()
        hex1.set_piece(PieceType.PEASANT)
        hex1.set_unit_id(5)
        hex1.set_color(HColor.RED)
        hex2 = Hex()
        hex2.copy_from(hex1)
        assert hex2.piece == PieceType.PEASANT
        assert hex2.unit_id == 5
        assert hex2.color == HColor.RED

    def test_add_adjacent_hex(self):
        """Test add_adjacent_hex() method."""
        hex1 = Hex()
        hex2 = Hex()
        hex1.add_adjacent_hex(hex2)
        assert hex2 in hex1.adjacent_hexes
        assert hex1 in hex2.adjacent_hexes

    def test_is_linked_to(self):
        """Test is_linked_to() method."""
        hex1 = Hex()
        hex2 = Hex()
        assert hex1.is_linked_to(hex2) is False
        hex1.add_adjacent_hex(hex2)
        assert hex1.is_linked_to(hex2) is True

    def test_is_adjacent_to_hexes_of_same_color(self):
        """Test is_adjacent_to_hexes_of_same_color() method."""
        hex1 = Hex(color=HColor.RED)
        hex2 = Hex(color=HColor.RED)
        hex3 = Hex(color=HColor.BLUE)
        hex1.add_adjacent_hex(hex2)
        hex1.add_adjacent_hex(hex3)
        assert hex1.is_adjacent_to_hexes_of_same_color() is True
        hex1.remove_adjacent_hex = lambda h: hex1.adjacent_hexes.remove(h) if h in hex1.adjacent_hexes else None
        # Remove hex2 to test negative case
        hex1.adjacent_hexes = [hex3]
        assert hex1.is_adjacent_to_hexes_of_same_color() is False

    def test_encode(self):
        """Test encode() method."""
        hex = Hex(coordinate1=5, coordinate2=10, color=HColor.RED)
        encoded = hex.encode()
        assert encoded == "5 10 red"
        hex.set_piece(PieceType.PEASANT)
        hex.set_unit_id(3)
        encoded = hex.encode()
        assert encoded == "5 10 red peasant 3"

    def test_province_management(self):
        """Test province management methods."""
        hex = Hex()
        province = object()  # Mock province
        assert hex.get_province() is None
        hex.on_added_to_province(province)
        assert hex.get_province() == province
        hex.on_removed_from_province(province)
        assert hex.get_province() is None

    def test_farm_diversity_index(self):
        """Test farm diversity index calculation."""
        hex1 = Hex(coordinate1=0, coordinate2=0)
        hex2 = Hex(coordinate1=1, coordinate2=1)
        # Index should be between 0 and 2
        assert 0 <= hex1.farm_diversity_index <= 2
        assert 0 <= hex2.farm_diversity_index <= 2

    def test_string_representations(self):
        """Test string and repr representations."""
        hex = Hex(coordinate1=5, coordinate2=10, color=HColor.RED)
        str_repr = str(hex)
        assert "5 10 red" in str_repr
        repr_str = repr(hex)
        assert "Hex" in repr_str
        assert "c1=5" in repr_str
        assert "c2=10" in repr_str
