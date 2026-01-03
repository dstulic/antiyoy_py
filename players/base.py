"""Base player interface."""

from abc import ABC, abstractmethod
from typing import Optional, Any, List
from core.game_state import GameState
from core.enums import HColor
from visibility.state_view import StateView


class BasePlayer(ABC):
    """Abstract base class for all player types."""

    def __init__(self, game_state: GameState, color: HColor):
        """
        Initialize player.
        
        Args:
            game_state: The game state this player is part of
            color: The color this player controls
        """
        self.game_state = game_state
        self.color = color
        self._player_entity = None
        self._update_player_entity()

    def _update_player_entity(self) -> None:
        """Update reference to player entity."""
        if self.game_state and self.game_state.entities_manager:
            self._player_entity = self.game_state.entities_manager.get_entity(self.color)

    def get_state_view(self) -> StateView:
        """
        Get player-specific game state view.
        
        This should return a filtered view of the game state that respects
        fog of war and only shows information visible to this player.
        
        Returns:
            StateView object with player-specific information
        """
        from visibility.state_view import StateView
        return StateView(self.game_state, self.color)

    @abstractmethod
    def submit_action(self, action: Any) -> bool:
        """
        Submit an action to be executed.
        
        Args:
            action: The action/command to execute
            
        Returns:
            True if action was successfully submitted, False otherwise
        """
        pass

    def is_turn_active(self) -> bool:
        """
        Check if it's currently this player's turn.
        
        Returns:
            True if it's this player's turn, False otherwise
        """
        if not self.game_state or not self.game_state.turns_manager:
            return False
        current_color = self.game_state.entities_manager.get_current_color()
        return current_color == self.color

    def get_player_entity(self):
        """Get the player entity for this player."""
        return self._player_entity

    def get_color(self) -> HColor:
        """Get the color this player controls."""
        return self.color

    def get_game_state(self) -> GameState:
        """Get the game state."""
        return self.game_state
