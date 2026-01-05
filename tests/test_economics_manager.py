"""Unit tests for core/economics_manager.py."""

import pytest
from core.economics_manager import EconomicsManager
from core.province import Province
from core.hex import Hex
from core.enums import HColor, PieceType
from typing import Optional


class MockRuleset:
    """Mock ruleset for testing."""

    def get_hex_income(self, piece_type: Optional[PieceType]) -> int:
        """Get hex income - matches RulesetDefaultV1 logic."""
        if piece_type is None:
            return 1
        if piece_type in (PieceType.PINE, PieceType.PALM):
            return 0
        if piece_type == PieceType.FARM:
            return 5
        return 1

    def get_consumption(self, piece_type: Optional[PieceType]) -> int:
        """Get consumption - matches RulesetDefaultV1 logic."""
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


class MockGameState:
    """Mock game state for testing."""

    def __init__(self, ruleset=None):
        """Initialize mock game state."""
        self.ruleset = ruleset


class TestEconomicsManager:
    """Tests for EconomicsManager class."""

    def test_initialization(self):
        """Test EconomicsManager initialization."""
        game_state = MockGameState()
        manager = EconomicsManager(game_state)
        assert manager.game_state == game_state

    def test_calculate_province_income_empty_hex(self):
        """Test income calculation for empty hex (should be 1)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        
        income = manager.calculate_province_income(province)
        assert income == 1  # Empty hex gives 1 income

    def test_calculate_province_income_farm(self):
        """Test income calculation for farm (should be 5)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.FARM
        province.add_hex(hex1)
        
        income = manager.calculate_province_income(province)
        assert income == 5  # Farm gives 5 income

    def test_calculate_province_income_tree_palm(self):
        """Test income calculation for palm tree (should be 0)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PALM
        province.add_hex(hex1)
        
        income = manager.calculate_province_income(province)
        assert income == 0  # Trees give 0 income

    def test_calculate_province_income_tree_pine(self):
        """Test income calculation for pine tree (should be 0)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PINE
        province.add_hex(hex1)
        
        income = manager.calculate_province_income(province)
        assert income == 0  # Trees give 0 income

    def test_calculate_province_income_city(self):
        """Test income calculation for city (should be 1)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.CITY
        province.add_hex(hex1)
        
        income = manager.calculate_province_income(province)
        assert income == 1  # City gives 1 income

    def test_calculate_province_income_multiple_hexes(self):
        """Test income calculation for multiple hexes."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # Empty hex: 1 income
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        # Farm: 5 income
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex2.piece = PieceType.FARM
        province.add_hex(hex2)
        # City: 1 income
        hex3 = Hex(coordinate1=2, coordinate2=0, color=HColor.RED)
        hex3.piece = PieceType.CITY
        province.add_hex(hex3)
        # Palm: 0 income
        hex4 = Hex(coordinate1=3, coordinate2=0, color=HColor.RED)
        hex4.piece = PieceType.PALM
        province.add_hex(hex4)
        
        income = manager.calculate_province_income(province)
        assert income == 7  # 1 + 5 + 1 + 0 = 7

    def test_calculate_province_income_no_hexes(self):
        """Test income calculation for province with no hexes (should be 0)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        
        income = manager.calculate_province_income(province)
        assert income == 0

    def test_calculate_province_income_no_ruleset(self):
        """Test income calculation when ruleset is None (should be 0)."""
        game_state = MockGameState(ruleset=None)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        
        income = manager.calculate_province_income(province)
        assert income == 0

    def test_calculate_province_consumption_empty_hex(self):
        """Test consumption calculation for empty hex (should be 0)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 0  # Empty hex has no consumption

    def test_calculate_province_consumption_peasant(self):
        """Test consumption calculation for peasant (should be 2)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PEASANT
        province.add_hex(hex1)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 2  # Peasant consumes 2

    def test_calculate_province_consumption_spearman(self):
        """Test consumption calculation for spearman (should be 6)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.SPEARMAN
        province.add_hex(hex1)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 6  # Spearman consumes 6

    def test_calculate_province_consumption_baron(self):
        """Test consumption calculation for baron (should be 18)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.BARON
        province.add_hex(hex1)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 18  # Baron consumes 18

    def test_calculate_province_consumption_knight(self):
        """Test consumption calculation for knight (should be 36)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.KNIGHT
        province.add_hex(hex1)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 36  # Knight consumes 36

    def test_calculate_province_consumption_tower(self):
        """Test consumption calculation for tower (should be 1)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.TOWER
        province.add_hex(hex1)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 1  # Tower consumes 1

    def test_calculate_province_consumption_strong_tower(self):
        """Test consumption calculation for strong tower (should be 6)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.STRONG_TOWER
        province.add_hex(hex1)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 6  # Strong tower consumes 6

    def test_calculate_province_consumption_city(self):
        """Test consumption calculation for city (should be 0)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.CITY
        province.add_hex(hex1)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 0  # City has no consumption

    def test_calculate_province_consumption_farm(self):
        """Test consumption calculation for farm (should be 0)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.FARM
        province.add_hex(hex1)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 0  # Farm has no consumption

    def test_calculate_province_consumption_multiple_pieces(self):
        """Test consumption calculation for multiple pieces."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # Peasant: 2 consumption
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PEASANT
        province.add_hex(hex1)
        # Tower: 1 consumption
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex2.piece = PieceType.TOWER
        province.add_hex(hex2)
        # Empty hex: 0 consumption
        hex3 = Hex(coordinate1=2, coordinate2=0, color=HColor.RED)
        province.add_hex(hex3)
        # Knight: 36 consumption
        hex4 = Hex(coordinate1=3, coordinate2=0, color=HColor.RED)
        hex4.piece = PieceType.KNIGHT
        province.add_hex(hex4)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 39  # 2 + 1 + 0 + 36 = 39

    def test_calculate_province_consumption_no_ruleset(self):
        """Test consumption calculation when ruleset is None (should be 0)."""
        game_state = MockGameState(ruleset=None)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PEASANT
        province.add_hex(hex1)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 0

    def test_calculate_province_profit_positive(self):
        """Test profit calculation with positive profit."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 5 empty hexes: 5 income
        for i in range(5):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            province.add_hex(hex1)
        # 1 peasant: 1 income, 2 consumption
        hex2 = Hex(coordinate1=5, coordinate2=0, color=HColor.RED)
        hex2.piece = PieceType.PEASANT
        province.add_hex(hex2)
        
        profit = manager.calculate_province_profit(province)
        assert profit == 4  # (5 + 1) income - 2 consumption = 4 profit

    def test_calculate_province_profit_negative(self):
        """Test profit calculation with negative profit."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 1 empty hex: 1 income
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        # 1 knight: 1 income, 36 consumption
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex2.piece = PieceType.KNIGHT
        province.add_hex(hex2)
        
        profit = manager.calculate_province_profit(province)
        assert profit == -34  # (1 + 1) income - 36 consumption = -34 profit

    def test_calculate_province_profit_zero(self):
        """Test profit calculation with zero profit."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 1 empty hex: 1 income
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        # 1 peasant: 1 income, 2 consumption
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex2.piece = PieceType.PEASANT
        province.add_hex(hex2)
        
        profit = manager.calculate_province_profit(province)
        assert profit == 0  # (1 + 1) income - 2 consumption = 0 profit

    def test_calculate_province_profit_with_farm(self):
        """Test profit calculation with farm (high income, no consumption)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 1 farm: 5 income, 0 consumption
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.FARM
        province.add_hex(hex1)
        # 1 peasant: 1 income, 2 consumption
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex2.piece = PieceType.PEASANT
        province.add_hex(hex2)
        
        profit = manager.calculate_province_profit(province)
        assert profit == 4  # (5 + 1) income - 2 consumption = 4 profit

    def test_calculate_province_profit_with_trees(self):
        """Test profit calculation with trees (0 income, 0 consumption)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 1 empty hex: 1 income
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        province.add_hex(hex1)
        # 1 palm: 0 income, 0 consumption
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex2.piece = PieceType.PALM
        province.add_hex(hex2)
        
        profit = manager.calculate_province_profit(province)
        assert profit == 1  # (1 + 0) income - 0 consumption = 1 profit

    def test_calculate_province_profit_single_hex_city(self):
        """Test profit calculation for single hex with city (should be 1)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.CITY
        province.add_hex(hex1)
        
        profit = manager.calculate_province_profit(province)
        assert profit == 1  # 1 income (city) - 0 consumption = 1 profit

    def test_calculate_province_income_large_province(self):
        """Test income calculation for a large province with many hexes."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # Add 20 empty hexes: 20 income
        for i in range(20):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            province.add_hex(hex1)
        # Add 5 farms: 25 income
        for i in range(5):
            hex2 = Hex(coordinate1=i, coordinate2=1, color=HColor.RED)
            hex2.piece = PieceType.FARM
            province.add_hex(hex2)
        # Add 10 trees: 0 income
        for i in range(10):
            hex3 = Hex(coordinate1=i, coordinate2=2, color=HColor.RED)
            hex3.piece = PieceType.PALM if i % 2 == 0 else PieceType.PINE
            province.add_hex(hex3)
        # Add 3 cities: 3 income
        for i in range(3):
            hex4 = Hex(coordinate1=i, coordinate2=3, color=HColor.RED)
            hex4.piece = PieceType.CITY
            province.add_hex(hex4)
        
        income = manager.calculate_province_income(province)
        assert income == 48  # 20 + 25 + 0 + 3 = 48

    def test_calculate_province_consumption_all_unit_types(self):
        """Test consumption calculation with all unit types."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # Peasant: 2 consumption
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.PEASANT
        province.add_hex(hex1)
        # Spearman: 6 consumption
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex2.piece = PieceType.SPEARMAN
        province.add_hex(hex2)
        # Baron: 18 consumption
        hex3 = Hex(coordinate1=2, coordinate2=0, color=HColor.RED)
        hex3.piece = PieceType.BARON
        province.add_hex(hex3)
        # Knight: 36 consumption
        hex4 = Hex(coordinate1=3, coordinate2=0, color=HColor.RED)
        hex4.piece = PieceType.KNIGHT
        province.add_hex(hex4)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 62  # 2 + 6 + 18 + 36 = 62

    def test_calculate_province_consumption_all_tower_types(self):
        """Test consumption calculation with all tower types."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # Tower: 1 consumption
        hex1 = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        hex1.piece = PieceType.TOWER
        province.add_hex(hex1)
        # Strong tower: 6 consumption
        hex2 = Hex(coordinate1=1, coordinate2=0, color=HColor.RED)
        hex2.piece = PieceType.STRONG_TOWER
        province.add_hex(hex2)
        
        consumption = manager.calculate_province_consumption(province)
        assert consumption == 7  # 1 + 6 = 7

    def test_calculate_province_profit_mixed_units_and_towers(self):
        """Test profit calculation with mixed units and towers."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 10 empty hexes: 10 income
        for i in range(10):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            province.add_hex(hex1)
        # 2 peasants: 2 income, 4 consumption
        for i in range(2):
            hex2 = Hex(coordinate1=i, coordinate2=1, color=HColor.RED)
            hex2.piece = PieceType.PEASANT
            province.add_hex(hex2)
        # 1 spearman: 1 income, 6 consumption
        hex3 = Hex(coordinate1=0, coordinate2=2, color=HColor.RED)
        hex3.piece = PieceType.SPEARMAN
        province.add_hex(hex3)
        # 3 towers: 3 income, 3 consumption
        for i in range(3):
            hex4 = Hex(coordinate1=i, coordinate2=3, color=HColor.RED)
            hex4.piece = PieceType.TOWER
            province.add_hex(hex4)
        # 1 strong tower: 1 income, 6 consumption
        hex5 = Hex(coordinate1=0, coordinate2=4, color=HColor.RED)
        hex5.piece = PieceType.STRONG_TOWER
        province.add_hex(hex5)
        
        profit = manager.calculate_province_profit(province)
        # Income: 10 (empty) + 2 (peasants) + 1 (spearman) + 3 (towers) + 1 (strong tower) = 17
        # Consumption: 4 (peasants) + 6 (spearman) + 3 (towers) + 6 (strong tower) = 19
        assert profit == -2  # 17 - 19 = -2

    def test_calculate_province_profit_only_trees(self):
        """Test profit calculation for province with only trees (0 income, 0 consumption)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 5 palm trees: 0 income
        for i in range(5):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            hex1.piece = PieceType.PALM
            province.add_hex(hex1)
        # 5 pine trees: 0 income
        for i in range(5):
            hex2 = Hex(coordinate1=i, coordinate2=1, color=HColor.RED)
            hex2.piece = PieceType.PINE
            province.add_hex(hex2)
        
        profit = manager.calculate_province_profit(province)
        assert profit == 0  # 0 income - 0 consumption = 0

    def test_calculate_province_profit_multiple_farms(self):
        """Test profit calculation with multiple farms."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 3 farms: 15 income
        for i in range(3):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            hex1.piece = PieceType.FARM
            province.add_hex(hex1)
        # 2 empty hexes: 2 income
        for i in range(2):
            hex2 = Hex(coordinate1=i, coordinate2=1, color=HColor.RED)
            province.add_hex(hex2)
        
        profit = manager.calculate_province_profit(province)
        assert profit == 17  # (15 + 2) income - 0 consumption = 17

    def test_calculate_province_profit_break_even_scenario(self):
        """Test profit calculation at break-even point."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 18 empty hexes: 18 income
        for i in range(18):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            province.add_hex(hex1)
        # 1 knight: 1 income, 36 consumption
        hex2 = Hex(coordinate1=0, coordinate2=1, color=HColor.RED)
        hex2.piece = PieceType.KNIGHT
        province.add_hex(hex2)
        # 17 peasants: 17 income, 34 consumption
        for i in range(17):
            hex3 = Hex(coordinate1=i, coordinate2=2, color=HColor.RED)
            hex3.piece = PieceType.PEASANT
            province.add_hex(hex3)
        
        profit = manager.calculate_province_profit(province)
        # Income: 18 + 1 + 17 = 36
        # Consumption: 36 + 34 = 70
        assert profit == -34  # 36 - 70 = -34

    def test_calculate_province_profit_maximum_consumption(self):
        """Test profit calculation with maximum consumption (all knights)."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 10 knights: 10 income, 360 consumption
        for i in range(10):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            hex1.piece = PieceType.KNIGHT
            province.add_hex(hex1)
        
        profit = manager.calculate_province_profit(province)
        assert profit == -350  # 10 income - 360 consumption = -350

    def test_calculate_province_profit_high_income_low_consumption(self):
        """Test profit calculation with high income and low consumption."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 10 farms: 50 income
        for i in range(10):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            hex1.piece = PieceType.FARM
            province.add_hex(hex1)
        # 20 empty hexes: 20 income
        for i in range(20):
            hex2 = Hex(coordinate1=i, coordinate2=1, color=HColor.RED)
            province.add_hex(hex2)
        # 1 tower: 1 income, 1 consumption
        hex3 = Hex(coordinate1=0, coordinate2=2, color=HColor.RED)
        hex3.piece = PieceType.TOWER
        province.add_hex(hex3)
        
        profit = manager.calculate_province_profit(province)
        assert profit == 70  # (50 + 20 + 1) income - 1 consumption = 70

    def test_calculate_province_income_trees_reduce_income(self):
        """Test that trees reduce income compared to empty hexes."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province_with_trees = Province()
        # 10 trees: 0 income
        for i in range(10):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            hex1.piece = PieceType.PALM
            province_with_trees.add_hex(hex1)
        
        province_without_trees = Province()
        # 10 empty hexes: 10 income
        for i in range(10):
            hex2 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            province_without_trees.add_hex(hex2)
        
        income_with_trees = manager.calculate_province_income(province_with_trees)
        income_without_trees = manager.calculate_province_income(province_without_trees)
        
        assert income_with_trees == 0
        assert income_without_trees == 10
        assert income_with_trees < income_without_trees  # Trees reduce income

    def test_calculate_province_profit_complex_mixed_scenario(self):
        """Test profit calculation with a complex mix of all piece types."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 5 empty hexes: 5 income
        for i in range(5):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            province.add_hex(hex1)
        # 3 farms: 15 income
        for i in range(3):
            hex2 = Hex(coordinate1=i, coordinate2=1, color=HColor.RED)
            hex2.piece = PieceType.FARM
            province.add_hex(hex2)
        # 4 trees: 0 income
        for i in range(4):
            hex3 = Hex(coordinate1=i, coordinate2=2, color=HColor.RED)
            hex3.piece = PieceType.PALM if i % 2 == 0 else PieceType.PINE
            province.add_hex(hex3)
        # 2 cities: 2 income
        for i in range(2):
            hex4 = Hex(coordinate1=i, coordinate2=3, color=HColor.RED)
            hex4.piece = PieceType.CITY
            province.add_hex(hex4)
        # 2 peasants: 2 income, 4 consumption
        for i in range(2):
            hex5 = Hex(coordinate1=i, coordinate2=4, color=HColor.RED)
            hex5.piece = PieceType.PEASANT
            province.add_hex(hex5)
        # 1 spearman: 1 income, 6 consumption
        hex6 = Hex(coordinate1=0, coordinate2=5, color=HColor.RED)
        hex6.piece = PieceType.SPEARMAN
        province.add_hex(hex6)
        # 1 baron: 1 income, 18 consumption
        hex7 = Hex(coordinate1=1, coordinate2=5, color=HColor.RED)
        hex7.piece = PieceType.BARON
        province.add_hex(hex7)
        # 1 tower: 1 income, 1 consumption
        hex8 = Hex(coordinate1=2, coordinate2=5, color=HColor.RED)
        hex8.piece = PieceType.TOWER
        province.add_hex(hex8)
        # 1 strong tower: 1 income, 6 consumption
        hex9 = Hex(coordinate1=3, coordinate2=5, color=HColor.RED)
        hex9.piece = PieceType.STRONG_TOWER
        province.add_hex(hex9)
        
        profit = manager.calculate_province_profit(province)
        # Income: 5 (empty) + 15 (farms) + 0 (trees) + 2 (cities) + 2 (peasants) + 1 (spearman) + 1 (baron) + 1 (tower) + 1 (strong tower) = 28
        # Consumption: 4 (peasants) + 6 (spearman) + 18 (baron) + 1 (tower) + 6 (strong tower) = 35
        assert profit == -7  # 28 - 35 = -7

    def test_calculate_province_profit_balanced_army(self):
        """Test profit calculation with a balanced army composition."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 20 empty hexes: 20 income
        for i in range(20):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            province.add_hex(hex1)
        # 5 peasants: 5 income, 10 consumption
        for i in range(5):
            hex2 = Hex(coordinate1=i, coordinate2=1, color=HColor.RED)
            hex2.piece = PieceType.PEASANT
            province.add_hex(hex2)
        # 2 spearmen: 2 income, 12 consumption
        for i in range(2):
            hex3 = Hex(coordinate1=i, coordinate2=2, color=HColor.RED)
            hex3.piece = PieceType.SPEARMAN
            province.add_hex(hex3)
        # 1 baron: 1 income, 18 consumption
        hex4 = Hex(coordinate1=0, coordinate2=3, color=HColor.RED)
        hex4.piece = PieceType.BARON
        province.add_hex(hex4)
        # 3 towers: 3 income, 3 consumption
        for i in range(3):
            hex5 = Hex(coordinate1=i, coordinate2=4, color=HColor.RED)
            hex5.piece = PieceType.TOWER
            province.add_hex(hex5)
        
        profit = manager.calculate_province_profit(province)
        # Income: 20 + 5 + 2 + 1 + 3 = 31
        # Consumption: 10 + 12 + 18 + 3 = 43
        assert profit == -12  # 31 - 43 = -12

    def test_calculate_province_profit_economic_powerhouse(self):
        """Test profit calculation for an economic powerhouse province."""
        ruleset = MockRuleset()
        game_state = MockGameState(ruleset)
        manager = EconomicsManager(game_state)
        
        province = Province()
        # 15 farms: 75 income
        for i in range(15):
            hex1 = Hex(coordinate1=i, coordinate2=0, color=HColor.RED)
            hex1.piece = PieceType.FARM
            province.add_hex(hex1)
        # 30 empty hexes: 30 income
        for i in range(30):
            hex2 = Hex(coordinate1=i, coordinate2=1, color=HColor.RED)
            province.add_hex(hex2)
        # 5 cities: 5 income
        for i in range(5):
            hex3 = Hex(coordinate1=i, coordinate2=2, color=HColor.RED)
            hex3.piece = PieceType.CITY
            province.add_hex(hex3)
        # Minimal consumption: 2 towers
        for i in range(2):
            hex4 = Hex(coordinate1=i, coordinate2=3, color=HColor.RED)
            hex4.piece = PieceType.TOWER
            province.add_hex(hex4)
        
        profit = manager.calculate_province_profit(province)
        # Income: 75 + 30 + 5 + 2 = 112
        # Consumption: 2
        assert profit == 110  # 112 - 2 = 110
