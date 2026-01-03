"""Unit tests for core/province.py - ProvincesManager."""

import pytest
from core.province import (
    ProvincesManager,
    ProvincesBuilder,
    ProvincesReductionWorker,
    WaveWorker,
)
from core.hex import Hex
from core.enums import HColor, EventType
from core.events import EventHexChangeColor


class MockCoreModel:
    """Mock core model for testing."""

    def __init__(self):
        self.hexes: list[Hex] = []
        self.events_manager = None


class MockEventsManager:
    """Mock events manager."""

    def __init__(self):
        self.listeners = []

    def add_listener(self, listener):
        """Add listener."""
        if listener not in self.listeners:
            self.listeners.append(listener)


class TestWaveWorker:
    """Tests for WaveWorker."""

    def test_flood_fill(self):
        """Test flood-fill algorithm."""
        # Create a small grid of hexes
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex3 = Hex(coordinate1=2, coordinate2=0, color=HColor.BLUE)
        hex1.add_adjacent_hex(hex2)
        hex2.add_adjacent_hex(hex3)
        collected = []

        def condition(parent_hex, hex):
            return hex.color == HColor.RED

        def action(parent_hex, hex):
            collected.append(hex)

        worker = WaveWorker(condition, action)
        worker.apply(hex1)
        assert hex1 in collected
        assert hex2 in collected
        assert hex3 not in collected  # Different color


class TestProvincesBuilder:
    """Tests for ProvincesBuilder."""

    def test_build_provinces(self):
        """Test building provinces from hexes."""
        core_model = MockCoreModel()
        core_model.events_manager = MockEventsManager()
        manager = ProvincesManager(core_model)
        # Create connected red hexes
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex3 = Hex(coordinate1=2, coordinate2=0, color=HColor.BLUE)
        hex4 = Hex(coordinate1=3, coordinate2=0, color=HColor.BLUE)
        hex1.add_adjacent_hex(hex2)
        hex2.add_adjacent_hex(hex3)
        hex3.add_adjacent_hex(hex4)
        core_model.hexes = [hex1, hex2, hex3, hex4]
        manager.builder.grant_permission()
        manager.builder.apply()
        # Should create 2 provinces (red and blue)
        assert len(manager.provinces) == 2
        red_province = manager.get_province_by_color(HColor.RED)
        assert red_province is not None
        assert red_province.contains(hex1)
        assert red_province.contains(hex2)
        blue_province = manager.get_province_by_color(HColor.BLUE)
        assert blue_province is not None
        assert blue_province.contains(hex3)
        assert blue_province.contains(hex4)


class TestProvincesManager:
    """Tests for ProvincesManager."""

    def test_provinces_manager_initialization(self):
        """Test provinces manager initialization."""
        core_model = MockCoreModel()
        core_model.events_manager = MockEventsManager()
        manager = ProvincesManager(core_model)
        assert len(manager.provinces) == 0
        assert manager.current_id == 0

    def test_add_province(self):
        """Test adding province."""
        core_model = MockCoreModel()
        manager = ProvincesManager(core_model)
        province = manager.add_province()
        assert province.get_id() == 0
        assert len(manager.provinces) == 1
        province2 = manager.add_province()
        assert province2.get_id() == 1

    def test_remove_province(self):
        """Test removing province."""
        core_model = MockCoreModel()
        manager = ProvincesManager(core_model)
        province = manager.add_province()
        hex1 = Hex()
        province.add_hex(hex1)
        manager.remove_province(province)
        assert len(manager.provinces) == 0
        assert hex1.get_province() is None

    def test_get_province(self):
        """Test getting province by ID."""
        core_model = MockCoreModel()
        manager = ProvincesManager(core_model)
        province = manager.add_province()
        assert manager.get_province(province.get_id()) == province
        assert manager.get_province(999) is None

    def test_get_province_by_color(self):
        """Test getting province by color."""
        core_model = MockCoreModel()
        manager = ProvincesManager(core_model)
        province = manager.add_province()
        hex1 = Hex(color=HColor.RED)
        province.add_hex(hex1)
        assert manager.get_province_by_color(HColor.RED) == province
        assert manager.get_province_by_color(HColor.BLUE) is None

    def test_get_largest_province(self):
        """Test getting largest province."""
        core_model = MockCoreModel()
        manager = ProvincesManager(core_model)
        province1 = manager.add_province()
        hex1 = Hex(color=HColor.RED)
        hex2 = Hex(color=HColor.RED)
        province1.add_hex(hex1)
        province1.add_hex(hex2)
        province2 = manager.add_province()
        hex3 = Hex(color=HColor.RED)
        province2.add_hex(hex3)
        largest = manager.get_largest_province(HColor.RED)
        assert largest == province1

    def test_get_richest_province(self):
        """Test getting richest province."""
        core_model = MockCoreModel()
        manager = ProvincesManager(core_model)
        province1 = manager.add_province()
        province1.set_money(100)
        hex1 = Hex(color=HColor.RED)
        province1.add_hex(hex1)
        province2 = manager.add_province()
        province2.set_money(50)
        hex2 = Hex(color=HColor.RED)
        province2.add_hex(hex2)
        richest = manager.get_richest_province(HColor.RED)
        assert richest == province1

    def test_get_sum_money(self):
        """Test getting sum money."""
        core_model = MockCoreModel()
        manager = ProvincesManager(core_model)
        province1 = manager.add_province()
        province1.set_money(100)
        hex1 = Hex(color=HColor.RED)
        province1.add_hex(hex1)
        province2 = manager.add_province()
        province2.set_money(50)
        hex2 = Hex(color=HColor.RED)
        province2.add_hex(hex2)
        assert manager.get_sum_money(HColor.RED) == 150

    def test_find_province_slowly(self):
        """Test finding province slowly."""
        core_model = MockCoreModel()
        manager = ProvincesManager(core_model)
        province = manager.add_province()
        hex1 = Hex()
        province.add_hex(hex1)
        assert manager.find_province_slowly(hex1) == province
        hex2 = Hex()
        assert manager.find_province_slowly(hex2) is None

    def test_encode(self):
        """Test encoding."""
        core_model = MockCoreModel()
        manager = ProvincesManager(core_model)
        province = manager.add_province()
        hex1 = Hex(coordinate1=5, coordinate2=10, color=HColor.RED)
        province.add_hex(hex1)
        province.set_money(100)
        province.set_city_name("TestCity")
        encoded = manager.encode()
        assert "5<10<0<100<TestCity" in encoded
        assert "1>" in encoded  # current_id

    def test_clear_provinces(self):
        """Test clearing provinces."""
        core_model = MockCoreModel()
        manager = ProvincesManager(core_model)
        province1 = manager.add_province()
        province2 = manager.add_province()
        manager.clear_provinces()
        assert len(manager.provinces) == 0


class TestProvincesReductionWorker:
    """Tests for ProvincesReductionWorker."""

    def test_on_hex_color_changed_no_split(self):
        """Test hex color change without split."""
        core_model = MockCoreModel()
        core_model.events_manager = MockEventsManager()
        manager = ProvincesManager(core_model)
        # Create a province with connected hexes
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex3 = Hex(coordinate1=2, coordinate2=0, color=HColor.RED)
        hex1.add_adjacent_hex(hex2)
        hex2.add_adjacent_hex(hex3)
        core_model.hexes = [hex1, hex2, hex3]
        manager.builder.grant_permission()
        manager.builder.apply()
        province = manager.get_province_by_color(HColor.RED)
        assert province is not None
        assert len(province.get_hexes()) == 3
        # Change one hex color - should split province
        previous_color = hex1.color
        hex1.set_color(HColor.BLUE)
        manager.reduction_worker.on_hex_color_changed(hex1, previous_color)
        # Province should still exist with remaining red hexes
        red_province = manager.get_province_by_color(HColor.RED)
        assert red_province is not None
        assert red_province.contains(hex2)
        assert red_province.contains(hex3)
