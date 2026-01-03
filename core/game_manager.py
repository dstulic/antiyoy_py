"""
Game Manager - handles the main game loop, turn advancement, and victory conditions.

This module manages the overall game flow, including:
- Turn progression
- Victory condition checking
- Game state transitions
- Match results
"""

from typing import TYPE_CHECKING, Optional, List, Dict, Any
from enum import Enum

if TYPE_CHECKING:
    from core.game_state import GameState
    from core.player_entity import PlayerEntity
    from core.enums import HColor, EntityType


class GameMode(Enum):
    """Game mode types."""
    CAMPAIGN = "campaign"
    SKIRMISH = "skirmish"
    MULTIPLAYER = "multiplayer"
    EDITOR = "editor"
    REPLAY = "replay"
    TUTORIAL = "tutorial"


class MatchResults:
    """Results of a completed match."""

    def __init__(self):
        self.winner_color: Optional["HColor"] = None
        self.entity_type: Optional["EntityType"] = None
        self.turns_made: int = 0
        self.level_size: Optional[str] = None
        self.rules_type: Optional[str] = None
        self.game_mode: Optional[GameMode] = None
        self.statistics_data: Dict[str, Any] = {}


class FinishMatchManager:
    """
    Manages match completion and victory condition checking.
    
    A match is won when all provinces belong to a single player.
    """

    def __init__(self, game_state: "GameState"):
        self.game_state = game_state

    def get_match_results(self) -> Optional[MatchResults]:
        """
        Get match results if the game is finished.
        Returns None if the game is not finished.
        """
        winner = self.get_winner()
        if winner is None:
            return None

        match_results = MatchResults()
        match_results.winner_color = winner.color
        match_results.entity_type = winner.type
        return match_results

    def get_winner(self) -> Optional["PlayerEntity"]:
        """
        Get the winner of the match.
        Returns None if there is no winner yet.
        """
        provinces = self.game_state.provinces_manager.provinces
        if len(provinces) == 0:
            return None

        if not self._does_contain_only_provinces_of_one_color(provinces):
            return None

        first_province_color = provinces[0].get_color()
        return self.game_state.entities_manager.get_entity(first_province_color)

    def _does_contain_only_provinces_of_one_color(self, provinces: List) -> bool:
        """Check if all provinces belong to the same color."""
        if len(provinces) == 0:
            return False

        first_province_color = provinces[0].get_color()
        for province in provinces:
            if province.get_color() != first_province_color:
                return False
        return True


class GameManager:
    """
    Main game manager that orchestrates the game loop and state transitions.
    
    Responsibilities:
    - Managing turn progression
    - Checking victory conditions
    - Coordinating player actions
    - Handling game state transitions
    """

    def __init__(self, game_state: "GameState", game_mode: GameMode = GameMode.SKIRMISH):
        self.game_state = game_state
        self.game_mode = game_mode
        self.finish_match_manager = FinishMatchManager(game_state)
        self.is_paused: bool = False
        self.is_finished: bool = False
        self.match_results: Optional[MatchResults] = None

    def update(self) -> None:
        """
        Update the game state (called each frame/tick).
        This handles turn progression, victory checking, etc.
        """
        if self.is_paused or self.is_finished:
            return

        # Check for victory condition
        self._check_victory_condition()

    def _check_victory_condition(self) -> None:
        """Check if the game has ended and a winner has been determined."""
        if self.is_finished:
            return

        match_results = self.finish_match_manager.get_match_results()
        if match_results is None:
            return

        # Game is finished
        self.is_finished = True
        self.match_results = match_results
        self._on_match_ended()

    def _on_match_ended(self) -> None:
        """Called when the match ends."""
        if self.match_results is None:
            return

        # Update match results with additional information
        self.match_results.game_mode = self.game_mode
        if self.game_state.ruleset:
            self.match_results.rules_type = str(self.game_state.ruleset.get_rules_type())

        # Calculate turns made
        if self.game_state.turns_manager:
            self.match_results.turns_made = self.game_state.turns_manager.lap
            # Add 1 if current turn is after winner's turn
            winner_turn_index = self._get_winner_turn_index()
            if winner_turn_index >= 0:
                if self.game_state.turns_manager.turn_index > winner_turn_index:
                    self.match_results.turns_made += 1

    def _get_winner_turn_index(self) -> int:
        """Get the turn index of the winner."""
        if not self.match_results or not self.match_results.winner_color:
            return -1

        entities = self.game_state.entities_manager.entities
        for i, entity in enumerate(entities):
            if entity.color == self.match_results.winner_color:
                return i
        return -1

    def end_turn(self) -> bool:
        """
        End the current player's turn.
        Returns True if the turn was successfully ended.
        """
        if self.is_paused or self.is_finished:
            return False

        from commands.types import EndTurnCommand
        from commands.executor import CommandExecutor

        current_color = self.game_state.entities_manager.get_current_color()
        if current_color is None:
            return False

        command = EndTurnCommand(current_color)
        executor = CommandExecutor(self.game_state)
        return executor.execute(command)

    def pause(self) -> None:
        """Pause the game."""
        self.is_paused = True

    def resume(self) -> None:
        """Resume the game."""
        self.is_paused = False

    def is_game_finished(self) -> bool:
        """Check if the game is finished."""
        return self.is_finished

    def get_match_results(self) -> Optional[MatchResults]:
        """Get match results if the game is finished."""
        return self.match_results

    def get_winner(self) -> Optional["PlayerEntity"]:
        """Get the winner of the match."""
        return self.finish_match_manager.get_winner()

    def can_advance_turn(self) -> bool:
        """Check if the game can advance to the next turn."""
        return not self.is_paused and not self.is_finished
