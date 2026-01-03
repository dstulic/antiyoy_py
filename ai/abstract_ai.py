"""Abstract base class for AI players."""

from abc import ABC, abstractmethod
import random
from typing import Optional
from core.game_state import GameState
from core.enums import Difficulty


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
