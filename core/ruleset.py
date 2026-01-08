"""Game ruleset system."""

from abc import ABC, abstractmethod
from typing import Optional
from core.enums import RulesType, PieceType
from core.hex import Hex
from core.province import Province
from core.core_utils import is_unit, get_strength


class AbstractRuleset(ABC):
    """Abstract base class for game rulesets."""

    def __init__(self, core_model):
        """Initialize ruleset."""
        self.core_model = core_model

    @abstractmethod
    def get_rules_type(self) -> RulesType:
        """Get the ruleset type."""
        pass

    @abstractmethod
    def get_version_code(self) -> int:
        """Get the version code."""
        pass

    @abstractmethod
    def get_hex_income(self, piece_type: Optional[PieceType]) -> int:
        """Get income from a hex with given piece type."""
        pass

    @abstractmethod
    def get_price(self, province: Province, piece_type: PieceType) -> int:
        """Get price for building a piece type in a province."""
        pass

    @abstractmethod
    def is_buildable(self, piece_type: PieceType) -> bool:
        """Check if a piece type can be built."""
        pass

    @abstractmethod
    def get_consumption(self, piece_type: Optional[PieceType]) -> int:
        """Get consumption (upkeep) for a piece type."""
        pass

    @abstractmethod
    def get_defense_value(self, piece_type: Optional[PieceType]) -> int:
        """Get defense value for a piece type."""
        pass

    @abstractmethod
    def get_defense_value_hex(self, hex: Hex) -> int:
        """Get defense value for a hex (including adjacent support)."""
        pass

    @abstractmethod
    def can_hex_be_captured(self, hex: Hex, attacker_strength: int) -> bool:
        """Check if a hex can be captured by attacker strength."""
        pass

    @abstractmethod
    def get_tree_reward(self) -> int:
        """Get reward for cutting down a tree."""
        pass

    @abstractmethod
    def update_move_zone_for_unit_construction(
        self, province: Province, strength: int
    ) -> None:
        """Update move zone for unit construction."""
        pass

    @abstractmethod
    def is_unit_ready_on_built(self) -> bool:
        """Check if units are ready immediately after being built."""
        pass


class RulesetDefaultV1(AbstractRuleset):
    """Default ruleset version 1."""

    def get_rules_type(self) -> RulesType:
        """Get ruleset type."""
        return RulesType.DEF

    def get_version_code(self) -> int:
        """Get version code."""
        return 1

    def get_hex_income(self, piece_type: Optional[PieceType]) -> int:
        """Get hex income."""
        if piece_type is None:
            return 1
        if piece_type in (PieceType.PINE, PieceType.PALM):
            return 0
        if piece_type == PieceType.FARM:
            return 5
        return 1

    def get_price(self, province: Province, piece_type: PieceType) -> int:
        """Get price for piece type."""
        price_map = {
            PieceType.PEASANT: 10,
            PieceType.SPEARMAN: 20,
            PieceType.BARON: 30,
            PieceType.KNIGHT: 40,
            PieceType.TOWER: 15,
            PieceType.STRONG_TOWER: 35,
        }
        if piece_type in price_map:
            return price_map[piece_type]
        if piece_type == PieceType.FARM:
            return 12 + 2 * province.count_pieces(PieceType.FARM)
        return 0

    def is_buildable(self, piece_type: PieceType) -> bool:
        """Check if buildable."""
        buildable = {
            PieceType.PEASANT,
            PieceType.SPEARMAN,
            PieceType.BARON,
            PieceType.KNIGHT,
            PieceType.FARM,
            PieceType.TOWER,
            PieceType.STRONG_TOWER,
        }
        return piece_type in buildable

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

    def get_defense_value(self, piece_type: Optional[PieceType]) -> int:
        """Get defense value."""
        if piece_type is None:
            return 0
        if is_unit(piece_type):
            return get_strength(piece_type)
        defense_map = {
            PieceType.CITY: 1,
            PieceType.TOWER: 2,
            PieceType.STRONG_TOWER: 3,
        }
        return defense_map.get(piece_type, 0)

    def get_defense_value_hex(self, hex: Hex) -> int:
        """Get defense value for hex."""
        max_value = self.get_defense_value(hex.piece)
        hex_province = hex.get_province()
        for adjacent_hex in hex.adjacent_hexes:
            if adjacent_hex.color != hex.color:
                continue
            # Only consider adjacent hexes in the same province
            if hex_province is not None:
                adjacent_province = adjacent_hex.get_province()
                if adjacent_province != hex_province:
                    continue
            value = self.get_defense_value(adjacent_hex.piece)
            if value > max_value:
                max_value = value
        return max_value

    def can_hex_be_captured(self, hex: Hex, attacker_strength: int) -> bool:
        """Check if hex can be captured."""
        defense = self.get_defense_value_hex(hex)
        return attacker_strength > defense or attacker_strength == 4

    def get_tree_reward(self) -> int:
        """Get tree reward."""
        return 3

    def update_move_zone_for_unit_construction(
        self, province: Province, strength: int
    ) -> None:
        """Update move zone."""
        # This would require MoveZoneManager - placeholder for now
        if self.core_model and hasattr(self.core_model, "move_zone_manager"):
            first_hex = province.get_first_hex()
            if first_hex and self.core_model.move_zone_manager:
                self.core_model.move_zone_manager.update(first_hex, 999, strength)

    def is_unit_ready_on_built(self) -> bool:
        """Check if unit ready on built."""
        return True


class RulesetClassicV1(AbstractRuleset):
    """Classic ruleset version 1."""

    def get_rules_type(self) -> RulesType:
        """Get ruleset type."""
        return RulesType.CLASSIC

    def get_version_code(self) -> int:
        """Get version code."""
        return 1

    def get_hex_income(self, piece_type: Optional[PieceType]) -> int:
        """Get hex income."""
        if piece_type is None:
            return 1
        if piece_type in (PieceType.PINE, PieceType.PALM):
            return 0
        if piece_type == PieceType.FARM:
            return 4
        return 1

    def get_price(self, province: Province, piece_type: PieceType) -> int:
        """Get price."""
        price_map = {
            PieceType.PEASANT: 10,
            PieceType.SPEARMAN: 20,
            PieceType.BARON: 30,
            PieceType.KNIGHT: 40,
            PieceType.TOWER: 15,
            PieceType.STRONG_TOWER: 35,
        }
        if piece_type in price_map:
            return price_map[piece_type]
        if piece_type == PieceType.FARM:
            return 10 + 2 * province.count_pieces(PieceType.FARM)
        return 0

    def is_buildable(self, piece_type: PieceType) -> bool:
        """Check if buildable."""
        buildable = {
            PieceType.PEASANT,
            PieceType.SPEARMAN,
            PieceType.BARON,
            PieceType.KNIGHT,
            PieceType.FARM,
            PieceType.TOWER,
            PieceType.STRONG_TOWER,
        }
        return piece_type in buildable

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

    def get_defense_value(self, piece_type: Optional[PieceType]) -> int:
        """Get defense value."""
        if piece_type is None:
            return 0
        if is_unit(piece_type):
            return get_strength(piece_type)
        defense_map = {
            PieceType.CITY: 1,
            PieceType.TOWER: 2,
            PieceType.STRONG_TOWER: 3,
        }
        return defense_map.get(piece_type, 0)

    def get_defense_value_hex(self, hex: Hex) -> int:
        """Get defense value for hex."""
        max_value = self.get_defense_value(hex.piece)
        hex_province = hex.get_province()
        for adjacent_hex in hex.adjacent_hexes:
            if adjacent_hex.color != hex.color:
                continue
            # Only consider adjacent hexes in the same province
            if hex_province is not None:
                adjacent_province = adjacent_hex.get_province()
                if adjacent_province != hex_province:
                    continue
            value = self.get_defense_value(adjacent_hex.piece)
            if value > max_value:
                max_value = value
        return max_value

    def can_hex_be_captured(self, hex: Hex, attacker_strength: int) -> bool:
        """Check if hex can be captured."""
        defense = self.get_defense_value_hex(hex)
        return attacker_strength > defense or attacker_strength == 4

    def get_tree_reward(self) -> int:
        """Get tree reward."""
        return 2

    def update_move_zone_for_unit_construction(
        self, province: Province, strength: int
    ) -> None:
        """Update move zone."""
        if self.core_model and hasattr(self.core_model, "move_zone_manager"):
            first_hex = province.get_first_hex()
            if first_hex and self.core_model.move_zone_manager:
                self.core_model.move_zone_manager.update(first_hex, 999, strength)

    def is_unit_ready_on_built(self) -> bool:
        """Check if unit ready on built."""
        return False  # Classic: units not ready immediately


class RulesetExperimentalV1(AbstractRuleset):
    """Experimental ruleset version 1."""

    def get_rules_type(self) -> RulesType:
        """Get ruleset type."""
        return RulesType.EXPERIMENTAL

    def get_version_code(self) -> int:
        """Get version code."""
        return 1

    def get_hex_income(self, piece_type: Optional[PieceType]) -> int:
        """Get hex income."""
        return RulesetDefaultV1.get_hex_income(self, piece_type)

    def get_price(self, province: Province, piece_type: PieceType) -> int:
        """Get price."""
        return RulesetDefaultV1.get_price(self, province, piece_type)

    def is_buildable(self, piece_type: PieceType) -> bool:
        """Check if buildable."""
        buildable = {
            PieceType.PEASANT,
            PieceType.SPEARMAN,
            PieceType.BARON,
            PieceType.KNIGHT,
            PieceType.FARM,
            PieceType.TOWER,
            PieceType.STRONG_TOWER,
        }
        return piece_type in buildable

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

    def get_defense_value(self, piece_type: Optional[PieceType]) -> int:
        """Get defense value."""
        if piece_type is None:
            return 0
        if is_unit(piece_type):
            return get_strength(piece_type)
        defense_map = {
            PieceType.CITY: 1,
            PieceType.TOWER: 2,
            PieceType.STRONG_TOWER: 3,
        }
        return defense_map.get(piece_type, 0)

    def get_defense_value_hex(self, hex: Hex) -> int:
        """Get defense value for hex."""
        max_value = self.get_defense_value(hex.piece)
        hex_province = hex.get_province()
        for adjacent_hex in hex.adjacent_hexes:
            if adjacent_hex.color != hex.color:
                continue
            # Only consider adjacent hexes in the same province
            if hex_province is not None:
                adjacent_province = adjacent_hex.get_province()
                if adjacent_province != hex_province:
                    continue
            value = self.get_defense_value(adjacent_hex.piece)
            if value > max_value:
                max_value = value
        return max_value

    def can_hex_be_captured(self, hex: Hex, attacker_strength: int) -> bool:
        """Check if hex can be captured."""
        defense = self.get_defense_value_hex(hex)
        return attacker_strength > defense or attacker_strength == 4

    def get_tree_reward(self) -> int:
        """Get tree reward."""
        return RulesetDefaultV1.get_tree_reward(self)

    def update_move_zone_for_unit_construction(
        self, province: Province, strength: int
    ) -> None:
        """Update move zone."""
        if self.core_model and hasattr(self.core_model, "move_zone_manager"):
            first_hex = province.get_first_hex()
            if first_hex and self.core_model.move_zone_manager:
                self.core_model.move_zone_manager.update(first_hex, 999, strength)

    def is_unit_ready_on_built(self) -> bool:
        """Check if unit ready on built."""
        return RulesetDefaultV1.is_unit_ready_on_built(self)


class RulesetDuelV1(AbstractRuleset):
    """Duel ruleset version 1."""

    def get_rules_type(self) -> RulesType:
        """Get ruleset type."""
        return RulesType.DUEL

    def get_version_code(self) -> int:
        """Get version code."""
        return 1

    def get_hex_income(self, piece_type: Optional[PieceType]) -> int:
        """Get hex income."""
        return RulesetDefaultV1.get_hex_income(self, piece_type)

    def get_price(self, province: Province, piece_type: PieceType) -> int:
        """Get price."""
        return RulesetDefaultV1.get_price(self, province, piece_type)

    def is_buildable(self, piece_type: PieceType) -> bool:
        """Check if buildable."""
        buildable = {
            PieceType.PEASANT,
            PieceType.SPEARMAN,
            PieceType.BARON,
            PieceType.KNIGHT,
            PieceType.FARM,
            PieceType.TOWER,
            PieceType.STRONG_TOWER,
        }
        return piece_type in buildable

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

    def get_defense_value(self, piece_type: Optional[PieceType]) -> int:
        """Get defense value."""
        if piece_type is None:
            return 0
        if is_unit(piece_type):
            return get_strength(piece_type)
        defense_map = {
            PieceType.CITY: 1,
            PieceType.TOWER: 2,
            PieceType.STRONG_TOWER: 3,
        }
        return defense_map.get(piece_type, 0)

    def get_defense_value_hex(self, hex: Hex) -> int:
        """Get defense value for hex."""
        max_value = self.get_defense_value(hex.piece)
        hex_province = hex.get_province()
        for adjacent_hex in hex.adjacent_hexes:
            if adjacent_hex.color != hex.color:
                continue
            # Only consider adjacent hexes in the same province
            if hex_province is not None:
                adjacent_province = adjacent_hex.get_province()
                if adjacent_province != hex_province:
                    continue
            value = self.get_defense_value(adjacent_hex.piece)
            if value > max_value:
                max_value = value
        return max_value

    def can_hex_be_captured(self, hex: Hex, attacker_strength: int) -> bool:
        """Check if hex can be captured."""
        defense = self.get_defense_value_hex(hex)
        return attacker_strength > defense or attacker_strength == 4

    def get_tree_reward(self) -> int:
        """Get tree reward."""
        return RulesetDefaultV1.get_tree_reward(self)

    def update_move_zone_for_unit_construction(
        self, province: Province, strength: int
    ) -> None:
        """Update move zone."""
        if self.core_model and hasattr(self.core_model, "move_zone_manager"):
            first_hex = province.get_first_hex()
            if first_hex and self.core_model.move_zone_manager:
                self.core_model.move_zone_manager.update(first_hex, 999, strength)

    def is_unit_ready_on_built(self) -> bool:
        """Check if unit ready on built."""
        return RulesetDefaultV1.is_unit_ready_on_built(self)


class RulesetFactory:
    """Factory for creating rulesets."""

    def __init__(self, core_model):
        """Initialize factory."""
        self.core_model = core_model

    def create(self, rules_type: RulesType, version_code: int = 1) -> Optional[AbstractRuleset]:
        """Create a ruleset."""
        if rules_type == RulesType.DEF:
            return self._create_ruleset_default(version_code)
        elif rules_type == RulesType.CLASSIC:
            return self._create_ruleset_classic(version_code)
        elif rules_type == RulesType.EXPERIMENTAL:
            return self._create_ruleset_experimental(version_code)
        elif rules_type == RulesType.DUEL:
            return self._create_ruleset_duel(version_code)
        return None

    def _create_ruleset_default(self, version_code: int) -> Optional[AbstractRuleset]:
        """Create default ruleset."""
        if version_code == 1:
            return RulesetDefaultV1(self.core_model)
        return None

    def _create_ruleset_classic(self, version_code: int) -> Optional[AbstractRuleset]:
        """Create classic ruleset."""
        if version_code == 1:
            return RulesetClassicV1(self.core_model)
        return None

    def _create_ruleset_experimental(self, version_code: int) -> Optional[AbstractRuleset]:
        """Create experimental ruleset."""
        if version_code == 1:
            return RulesetExperimentalV1(self.core_model)
        return None

    def _create_ruleset_duel(self, version_code: int) -> Optional[AbstractRuleset]:
        """Create duel ruleset."""
        if version_code == 1:
            return RulesetDuelV1(self.core_model)
        return None
