"""Unit tests for core/province.py."""

import pytest
from core.province import Province
from core.hex import Hex
from core.enums import HColor, PieceType


class MockRuleset:
    """Mock ruleset for testing."""

    def get_price(self, province, piece_type: PieceType) -> int:
        """Return a mock price."""
        prices = {
            PieceType.PEASANT: 10,
            PieceType.CITY: 20,
            PieceType.TOWER: 15,
        }
        return prices.get(piece_type, 0)


class TestProvince:
    """Tests for Province class."""

    def test_province_initialization(self):
        """Test province initialization."""
        province = Province()
        assert len(province.get_hexes()) == 0
        assert province.get_money() == 0
        assert province.get_city_name() == ""
        assert province.get_id() == -1
        assert province.is_valid() is True

    def test_reset(self):
        """Test province reset."""
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        province.set_money(100)
        province.set_city_name("TestCity")
        province.set_id(5)
        province.reset()
        assert len(province.get_hexes()) == 0
        assert province.get_money() == 0
        assert province.get_city_name() == ""
        assert province.get_id() == -1

    def test_add_hex(self):
        """Test adding hex to province."""
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        assert province.contains(hex1) is True
        assert hex1.get_province() == province

    def test_remove_hex(self):
        """Test removing hex from province."""
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        province.remove_hex(hex1)
        assert province.contains(hex1) is False
        assert hex1.get_province() is None

    def test_get_color(self):
        """Test getting province color."""
        province = Province()
        assert province.get_color() is None  # Empty province
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        assert province.get_color() == HColor.RED

    def test_contains_piece_type(self):
        """Test contains_piece_type() method."""
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.set_piece(PieceType.CITY)
        province.add_hex(hex1)
        assert province.contains_piece_type(PieceType.CITY) is True
        assert province.contains_piece_type(PieceType.TOWER) is False

    def test_count_pieces(self):
        """Test count_pieces() method."""
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.set_piece(PieceType.CITY)
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex2.set_piece(PieceType.CITY)
        hex3 = Hex(coordinate1=2, coordinate2=0, color=HColor.RED)
        hex3.set_piece(PieceType.TOWER)
        province.add_hex(hex1)
        province.add_hex(hex2)
        province.add_hex(hex3)
        assert province.count_pieces(PieceType.CITY) == 2
        assert province.count_pieces(PieceType.TOWER) == 1
        assert province.count_pieces(PieceType.FARM) == 0

    def test_can_afford(self):
        """Test can_afford() method."""
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        province.set_money(15)
        ruleset = MockRuleset()
        assert province.can_afford(PieceType.PEASANT, ruleset) is True  # 10 <= 15
        assert province.can_afford(PieceType.CITY, ruleset) is False  # 20 > 15
        province.set_money(20)
        assert province.can_afford(PieceType.CITY, ruleset) is True

    def test_can_afford_empty_province(self):
        """Test can_afford() with empty province."""
        province = Province()
        ruleset = MockRuleset()
        assert province.can_afford(PieceType.PEASANT, ruleset) is False

    def test_get_first_hex(self):
        """Test get_first_hex() method."""
        province = Province()
        assert province.get_first_hex() is None
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        assert province.get_first_hex() == hex1

    def test_set_get_money(self):
        """Test money getter and setter."""
        province = Province()
        province.set_money(100)
        assert province.get_money() == 100

    def test_set_get_city_name(self):
        """Test city name getter and setter."""
        province = Province()
        province.set_city_name("TestCity")
        assert province.get_city_name() == "TestCity"

    def test_set_get_id(self):
        """Test ID getter and setter."""
        province = Province()
        province.set_id(5)
        assert province.get_id() == 5

    def test_validity(self):
        """Test province validity."""
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        assert province.is_valid() is True
        province.set_valid(False)
        assert province.is_valid() is False
        assert hex1.get_province() is None  # Should be cleared on invalidation

    def test_encode(self):
        """Test encode() method."""
        province = Province()
        hex1 = Hex(coordinate1=5, coordinate2=10, color=HColor.RED)
        province.add_hex(hex1)
        province.set_id(3)
        province.set_money(100)
        province.set_city_name("TestCity")
        encoded = province.encode()
        assert encoded == "5<10<3<100<TestCity"

    def test_encode_empty_province(self):
        """Test encode() with empty province."""
        province = Province()
        assert province.encode() == ""

    def test_string_representations(self):
        """Test string and repr representations."""
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        province.set_id(5)
        province.set_money(100)
        province.set_city_name("TestCity")
        str_repr = str(province)
        assert "Province" in str_repr
        assert "5" in str_repr
        assert "100" in str_repr
        assert "TestCity" in str_repr
        repr_str = repr(province)
        assert "Province" in repr_str
        assert "id=5" in repr_str

    def test_string_invalid_province(self):
        """Test string representation of invalid province."""
        province = Province()
        province.set_valid(False)
        assert str(province) == "[Invalid province]"

    def test_get_hexes_returns_copy(self):
        """Test that get_hexes() returns a copy."""
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        hexes = province.get_hexes()
        hexes.append(Hex())  # Try to modify
        assert len(province.get_hexes()) == 1  # Original unchanged
