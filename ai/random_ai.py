"""Random AI implementation."""

from typing import List, Optional
from ai.abstract_ai import AbstractAI
from core.game_state import GameState
from core.province import Province
from core.hex import Hex
from core.enums import PieceType
from core.core_utils import is_unit


class AiRandom(AbstractAI):
    """Random AI that makes random moves."""

    def __init__(self, game_state: GameState):
        """Initialize random AI."""
        super().__init__(game_state)
        self.temp_hex_list: List[Hex] = []

    def get_version_code(self) -> int:
        """Get version code."""
        return 1

    def apply(self) -> None:
        """Apply random AI decision making."""
        provinces = self.game_state.provinces_manager.provinces
        current_color = self.game_state.entities_manager.get_current_color()
        
        # Process provinces in reverse order
        for i in range(len(provinces) - 1, -1, -1):
            if i >= len(provinces):
                continue  # Can happen if list changes
            province = provinces[i]
            if not province.is_valid():
                continue
            if province.get_color() != current_color:
                continue
            self._apply_province(province)

    def _apply_province(self, province: Province) -> None:
        """Apply AI to a province."""
        self._move_units_randomly(province)
        self._build_peasants_randomly(province)

    def _build_peasants_randomly(self, province: Province) -> None:
        """Build peasants randomly."""
        if province.get_money() < 15:
            return
        if self.random.random() > 0.33:
            return
        empty_hex = self._get_empty_hex(province)
        if empty_hex is None:
            return
        self._command_unit_build(province, empty_hex, 1)

    def _get_empty_hex(self, province: Province) -> Optional[Hex]:
        """Get an empty hex from province."""
        if not self._has_empty_hexes(province):
            return None
        hexes = province.get_hexes()
        # Check in reverse order
        for i in range(len(hexes) - 1, -1, -1):
            hex = hexes[i]
            if hex.is_empty():
                return hex
        return None

    def _has_empty_hexes(self, province: Province) -> bool:
        """Check if province has empty hexes."""
        hexes = province.get_hexes()
        for hex in hexes:
            if hex.is_empty():
                return True
        return False

    def _move_units_randomly(self, province: Province) -> None:
        """Move units randomly."""
        hexes = province.get_hexes()
        units = [hex for hex in hexes if hex.has_unit()]
        
        for unit_hex in units:
            if self.random.random() > 0.5:
                continue  # 50% chance to move
            adjacent_hexes = [
                adj for adj in unit_hex.adjacent_hexes
                if adj.color == province.get_color() or adj.color.is_neutral()
            ]
            if not adjacent_hexes:
                continue
            target_hex = self.random.choice(adjacent_hexes)
            self._command_unit_move(unit_hex, target_hex)

    def _command_unit_build(self, province: Province, hex: Hex, strength: int) -> None:
        """Command building a unit."""
        from commands.types import BuildPieceCommand
        from commands.executor import CommandExecutor
        from core.core_utils import get_unit_by_strength
        
        piece_type = get_unit_by_strength(strength)
        if piece_type is None:
            return
        
        executor = CommandExecutor(self.game_state)
        command = BuildPieceCommand(hex, piece_type, province.get_id())
        executor.execute(command, self.game_state.entities_manager.get_current_color())

    def _command_unit_move(self, start: Hex, finish: Hex) -> None:
        """Command moving a unit."""
        from commands.types import MoveUnitCommand
        from commands.executor import CommandExecutor
        
        executor = CommandExecutor(self.game_state)
        command = MoveUnitCommand(start, finish, color_transfer_enabled=True)
        executor.execute(command, self.game_state.entities_manager.get_current_color())
