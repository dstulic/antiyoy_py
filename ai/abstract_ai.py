"""Abstract base class for AI players."""

from abc import ABC, abstractmethod
import random
from typing import Optional
from core.game_state import GameState
from core.enums import Difficulty, HColor, PieceType


class AbstractAI(ABC):
    """Abstract base class for all AI implementations."""

    def __init__(self, game_state: GameState):
        """
        Initialize AI.
        
        Args:
            game_state: The game state this AI operates on
        """
        self.game_state = game_state
        self.random = random.Random()
        self.difficulty: Optional[Difficulty] = None
        self.diplomatic_ai = self.get_diplomatic_ai()
        self.temp_list: List = []  # Temporary list for operations

    def perform(self) -> None:
        """
        Perform AI turn.
        
        This is the main entry point that:
        1. Applies the AI's decision making (apply())
        2. Handles diplomatic actions
        3. Ends the turn
        """
        self.apply()
        self._check_to_apply_diplomatic_ai()
        self._command_turn_end()

    def set_difficulty(self, difficulty: Difficulty) -> None:
        """
        Set the difficulty level.
        
        Args:
            difficulty: The difficulty level
        """
        self.difficulty = difficulty

    @abstractmethod
    def get_version_code(self) -> int:
        """
        Get the version code for this AI.
        
        Returns:
            Version code integer
        """
        pass

    @abstractmethod
    def apply(self) -> None:
        """
        Apply AI decision making.
        
        This is where the AI makes its moves, builds pieces, etc.
        """
        pass

    @abstractmethod
    def get_diplomatic_ai(self):
        """
        Get the diplomatic AI instance for this AI.
        
        Returns:
            DiplomaticAI instance
        """
        pass

    def _check_to_apply_diplomatic_ai(self) -> None:
        """Check and apply diplomatic AI if diplomacy is enabled."""
        # Placeholder - would need diplomacy manager
        # if not self.game_state.diplomacy_manager or not self.game_state.diplomacy_manager.enabled:
        #     return
        # self.diplomatic_ai.apply()
        pass

    def _command_turn_end(self) -> None:
        """Command the turn to end."""
        from commands.types import EndTurnCommand
        from commands.executor import CommandExecutor
        
        executor = CommandExecutor(self.game_state)
        command = EndTurnCommand()
        executor.execute(command, self.game_state.entities_manager.get_current_color())

    def get_events_factory(self):
        """Get the events factory."""
        return self.game_state.events_manager.factory
    
    # Helper methods for AI implementations
    def get_current_color(self):
        """Get current player color."""
        current_entity = self.game_state.entities_manager.get_current_entity()
        return current_entity.color if current_entity else None
    
    def is_ready(self, hex):
        """Check if hex unit is ready to move."""
        return hex in self.game_state.readiness_manager.ready_hexes
    
    def get_strength(self, hex_or_piece):
        """Get strength of unit."""
        from core.core_utils import get_strength
        if hasattr(hex_or_piece, 'piece'):
            return get_strength(hex_or_piece.piece)
        return get_strength(hex_or_piece)
    
    def get_ruleset(self):
        """Get ruleset."""
        return self.game_state.ruleset
    
    def get_move_zone_manager(self):
        """Get move zone manager."""
        return self.game_state.move_zone_manager
    
    def is_owned(self, province):
        """Check if province is owned by current player."""
        current_color = self.get_current_color()
        return province.get_color() == current_color if current_color else False
    
    def can_afford_unit(self, province, strength, turns_to_survive=None):
        """Check if province can afford a unit."""
        if turns_to_survive is None:
            turns_to_survive = strength + 1
        
        from core.core_utils import get_unit_by_strength
        unit_piece = get_unit_by_strength(strength)
        if not unit_piece:
            return False
        
        current_profit = self.game_state.economics_manager.calculate_province_profit(province)
        price = self.get_ruleset().get_price(province, unit_piece)
        if province.get_money() < price:
            return False
        
        consumption = self.get_ruleset().get_consumption(unit_piece)
        new_profit = current_profit - consumption
        return province.get_money() + turns_to_survive * new_profit >= 0
    
    def is_difficulty_less_than(self, difficulty):
        """Check if current difficulty is less than given difficulty."""
        if not self.difficulty:
            return True
        difficulty_order = [
            Difficulty.TUTORIAL,
            Difficulty.EASY,
            Difficulty.AVERAGE,
            Difficulty.HARD,
            Difficulty.EXPERT,
            Difficulty.BALANCER,
        ]
        # This is a simplified check - in practice, difficulty comparison is more complex
        return False  # Default to allowing all features
    
    def command_unit_build(self, province, hex, strength):
        """Command building a unit."""
        from core.core_utils import get_unit_by_strength
        from commands.types import BuildPieceCommand
        from commands.executor import CommandExecutor
        
        piece_type = get_unit_by_strength(strength)
        if not piece_type:
            return False
        
        executor = CommandExecutor(self.game_state)
        command = BuildPieceCommand(
            hex=hex,
            piece_type=piece_type,
            province_id=province.get_id()
        )
        success, _ = executor.execute(command, self.get_current_color())
        return success
    
    def command_unit_move(self, start_hex, finish_hex):
        """Command moving a unit."""
        from commands.types import MoveUnitCommand
        from commands.executor import CommandExecutor
        
        executor = CommandExecutor(self.game_state)
        command = MoveUnitCommand(
            start_hex=start_hex,
            finish_hex=finish_hex,
            color_transfer_enabled=True
        )
        success, _ = executor.execute(command, self.get_current_color())
        return success
    
    def command_piece_build(self, province, hex, piece_type):
        """Command building a non-unit piece."""
        from commands.types import BuildPieceCommand
        from commands.executor import CommandExecutor
        
        executor = CommandExecutor(self.game_state)
        command = BuildPieceCommand(
            hex=hex,
            piece_type=piece_type,
            province_id=province.get_id()
        )
        success, _ = executor.execute(command, self.get_current_color())
        return success
    
    def is_adjacent_to_enemy(self, hex):
        """Check if hex is adjacent to enemy."""
        for adj_hex in hex.adjacent_hexes:
            if adj_hex.color == HColor.GRAY:
                continue
            if adj_hex.color == hex.color:
                continue
            if adj_hex.get_province() is None:
                continue
            return True
        return False
    
    def get_defense_value(self, hex, ignored_hex=None):
        """Get defense value for hex."""
        if ignored_hex:
            # Calculate defense without considering ignored hex
            max_value = self.get_ruleset().get_defense_value(hex.piece)
            hex_province = hex.get_province()
            for adj_hex in hex.adjacent_hexes:
                if adj_hex == ignored_hex:
                    continue
                if adj_hex.color != hex.color:
                    continue
                if hex_province and adj_hex.get_province() != hex_province:
                    continue
                value = self.get_ruleset().get_defense_value(adj_hex.piece)
                if value > max_value:
                    max_value = value
            return max_value
        return self.get_ruleset().get_defense_value_hex(hex)