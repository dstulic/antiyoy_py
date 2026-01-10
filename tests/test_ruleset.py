"""Unit tests for core/ruleset.py."""

import pytest
from core.ruleset import (
    AbstractRuleset,
    RulesetDefaultV1,
    RulesetClassicV1,
    RulesetExperimentalV1,
    RulesetDuelV1,
    RulesetFactory,
)
from core.enums import RulesType, PieceType, HColor
from core.hex import Hex
from core.province import Province


class MockCoreModel:
    """Mock core model for testing."""

    def __init__(self):
        self.move_zone_manager = None
        # Mock game_end_manager to prevent "Game has ended" errors in tests
        self.game_end_manager = MockGameEndManager()


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


class TestRulesetDefaultV1:
    """Tests for RulesetDefaultV1."""

    def test_ruleset_type(self):
        """Test ruleset type."""
        core_model = MockCoreModel()
        ruleset = RulesetDefaultV1(core_model)
        assert ruleset.get_rules_type() == RulesType.DEF
        assert ruleset.get_version_code() == 1

    def test_get_hex_income(self):
        """Test get_hex_income()."""
        core_model = MockCoreModel()
        ruleset = RulesetDefaultV1(core_model)
        assert ruleset.get_hex_income(None) == 1
        assert ruleset.get_hex_income(PieceType.PINE) == 0
        assert ruleset.get_hex_income(PieceType.PALM) == 0
        assert ruleset.get_hex_income(PieceType.FARM) == 5
        assert ruleset.get_hex_income(PieceType.CITY) == 1

    def test_get_price(self):
        """Test get_price()."""
        core_model = MockCoreModel()
        ruleset = RulesetDefaultV1(core_model)
        province = Province()
        hex1 = Hex()
        province.add_hex(hex1)
        assert ruleset.get_price(province, PieceType.PEASANT) == 10
        assert ruleset.get_price(province, PieceType.SPEARMAN) == 20
        assert ruleset.get_price(province, PieceType.BARON) == 30
        assert ruleset.get_price(province, PieceType.KNIGHT) == 40
        assert ruleset.get_price(province, PieceType.TOWER) == 15
        assert ruleset.get_price(province, PieceType.STRONG_TOWER) == 35
        # Farm price increases with count
        assert ruleset.get_price(province, PieceType.FARM) == 12
        hex2 = Hex()
        hex2.set_piece(PieceType.FARM)
        province.add_hex(hex2)
        assert ruleset.get_price(province, PieceType.FARM) == 14

    def test_is_buildable(self):
        """Test is_buildable()."""
        core_model = MockCoreModel()
        ruleset = RulesetDefaultV1(core_model)
        assert ruleset.is_buildable(PieceType.PEASANT) is True
        assert ruleset.is_buildable(PieceType.CITY) is False
        assert ruleset.is_buildable(PieceType.FARM) is True

    def test_get_consumption(self):
        """Test get_consumption()."""
        core_model = MockCoreModel()
        ruleset = RulesetDefaultV1(core_model)
        assert ruleset.get_consumption(None) == 0
        assert ruleset.get_consumption(PieceType.PEASANT) == 2
        assert ruleset.get_consumption(PieceType.SPEARMAN) == 6
        assert ruleset.get_consumption(PieceType.BARON) == 18
        assert ruleset.get_consumption(PieceType.KNIGHT) == 36
        assert ruleset.get_consumption(PieceType.TOWER) == 1

    def test_get_defense_value(self):
        """Test get_defense_value()."""
        core_model = MockCoreModel()
        ruleset = RulesetDefaultV1(core_model)
        assert ruleset.get_defense_value(None) == 0
        assert ruleset.get_defense_value(PieceType.PEASANT) == 1
        assert ruleset.get_defense_value(PieceType.SPEARMAN) == 2
        assert ruleset.get_defense_value(PieceType.BARON) == 3
        assert ruleset.get_defense_value(PieceType.KNIGHT) == 4
        assert ruleset.get_defense_value(PieceType.CITY) == 1
        assert ruleset.get_defense_value(PieceType.TOWER) == 2
        assert ruleset.get_defense_value(PieceType.STRONG_TOWER) == 3

    def test_get_defense_value_hex(self):
        """Test get_defense_value_hex()."""
        core_model = MockCoreModel()
        ruleset = RulesetDefaultV1(core_model)
        hex1 = Hex(color=HColor.RED)
        hex1.set_piece(PieceType.PEASANT)
        hex2 = Hex(color=HColor.RED)
        hex2.set_piece(PieceType.TOWER)
        hex1.add_adjacent_hex(hex2)
        # Should get max from hex and adjacent
        defense = ruleset.get_defense_value_hex(hex1)
        assert defense >= 2  # At least tower defense

    def test_can_hex_be_captured(self):
        """Test can_hex_be_captured()."""
        core_model = MockCoreModel()
        ruleset = RulesetDefaultV1(core_model)
        hex1 = Hex()
        hex1.set_piece(PieceType.PEASANT)  # Defense 1
        assert ruleset.can_hex_be_captured(hex1, 2) is True  # 2 > 1
        assert ruleset.can_hex_be_captured(hex1, 1) is False  # 1 <= 1
        assert ruleset.can_hex_be_captured(hex1, 4) is True  # Knight always captures

    def test_get_tree_reward(self):
        """Test get_tree_reward()."""
        core_model = MockCoreModel()
        ruleset = RulesetDefaultV1(core_model)
        assert ruleset.get_tree_reward() == 3

    def test_is_unit_ready_on_built(self):
        """Test is_unit_ready_on_built()."""
        core_model = MockCoreModel()
        ruleset = RulesetDefaultV1(core_model)
        assert ruleset.is_unit_ready_on_built() is True


class TestRulesetClassicV1:
    """Tests for RulesetClassicV1."""

    def test_ruleset_type(self):
        """Test ruleset type."""
        core_model = MockCoreModel()
        ruleset = RulesetClassicV1(core_model)
        assert ruleset.get_rules_type() == RulesType.CLASSIC

    def test_get_hex_income(self):
        """Test get_hex_income()."""
        core_model = MockCoreModel()
        ruleset = RulesetClassicV1(core_model)
        assert ruleset.get_hex_income(PieceType.FARM) == 4  # Different from default

    def test_get_tree_reward(self):
        """Test get_tree_reward()."""
        core_model = MockCoreModel()
        ruleset = RulesetClassicV1(core_model)
        assert ruleset.get_tree_reward() == 2  # Different from default

    def test_is_unit_ready_on_built(self):
        """Test is_unit_ready_on_built()."""
        core_model = MockCoreModel()
        ruleset = RulesetClassicV1(core_model)
        assert ruleset.is_unit_ready_on_built() is False  # Classic difference


class TestRulesetFactory:
    """Tests for RulesetFactory."""

    def test_create_default(self):
        """Test creating default ruleset."""
        core_model = MockCoreModel()
        factory = RulesetFactory(core_model)
        ruleset = factory.create(RulesType.DEF, 1)
        assert isinstance(ruleset, RulesetDefaultV1)

    def test_create_classic(self):
        """Test creating classic ruleset."""
        core_model = MockCoreModel()
        factory = RulesetFactory(core_model)
        ruleset = factory.create(RulesType.CLASSIC, 1)
        assert isinstance(ruleset, RulesetClassicV1)

    def test_create_experimental(self):
        """Test creating experimental ruleset."""
        core_model = MockCoreModel()
        factory = RulesetFactory(core_model)
        ruleset = factory.create(RulesType.EXPERIMENTAL, 1)
        assert isinstance(ruleset, RulesetExperimentalV1)

    def test_create_duel(self):
        """Test creating duel ruleset."""
        core_model = MockCoreModel()
        factory = RulesetFactory(core_model)
        ruleset = factory.create(RulesType.DUEL, 1)
        assert isinstance(ruleset, RulesetDuelV1)

    def test_create_invalid_version(self):
        """Test creating with invalid version."""
        core_model = MockCoreModel()
        factory = RulesetFactory(core_model)
        ruleset = factory.create(RulesType.DEF, 999)
        assert ruleset is None
