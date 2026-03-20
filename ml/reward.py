"""Pluggable reward calculators for the Gymnasium environment."""

from abc import ABC, abstractmethod

from core.game_state import GameState
from core.enums import HColor


class RewardCalculator(ABC):
    """Abstract interface for computing step rewards."""

    @abstractmethod
    def reset(self, game_state: GameState, agent_color: HColor) -> None:
        """Called on env reset to initialise any baseline tracking."""

    @abstractmethod
    def calculate(
        self,
        game_state: GameState,
        agent_color: HColor,
        terminated: bool,
        info: dict,
    ) -> float:
        """Return the scalar reward after a step."""


class DefaultRewardCalculator(RewardCalculator):
    """Sparse terminal reward +/- 1, with optional per-step shaping.

    Parameters
    ----------
    shaping_weight : float
        Weight applied to the per-step ownership-delta shaping signal.
        Set to 0.0 for purely sparse reward.
    """

    def __init__(self, shaping_weight: float = 0.1):
        self.shaping_weight = shaping_weight
        self._prev_ownership_pct: float = 0.0

    def reset(self, game_state: GameState, agent_color: HColor) -> None:
        stats = game_state.get_hex_ownership_stats(agent_color)
        self._prev_ownership_pct = stats["percentage"]

    def calculate(
        self,
        game_state: GameState,
        agent_color: HColor,
        terminated: bool,
        info: dict,
    ) -> float:
        reward = 0.0

        if terminated:
            winner = game_state.game_end_manager.get_winner()
            if winner is not None and winner.color == agent_color:
                reward += 1.0
            elif winner is not None:
                reward -= 1.0
            else:
                reward -= 0.5  # truncated / indeterminate
            return reward

        # Per-step shaping: delta in ownership percentage (scaled)
        if self.shaping_weight > 0.0:
            stats = game_state.get_hex_ownership_stats(agent_color)
            current_pct = stats["percentage"]
            delta = current_pct - self._prev_ownership_pct
            reward += self.shaping_weight * (delta / 100.0)
            self._prev_ownership_pct = current_pct

        return reward
