"""Pluggable reward calculators for the Gymnasium environment."""

from abc import ABC, abstractmethod

from core.game_state import GameState
from core.enums import HColor
from ml.config import MAX_CAMPAIGN_HEXES


class RewardCalculator(ABC):
    """Abstract interface for computing step rewards."""

    @abstractmethod
    def reset(self, game_state: GameState, agent_color: HColor) -> None:
        """Called on env reset to initialise any baseline tracking."""

    def sync_baseline(self, game_state: GameState, agent_color: HColor) -> None:
        """Re-baseline shaping state without emitting reward (default: no-op).

        Overridden by calculators that use per-step deltas so opponent-turn
        changes can be absorbed rather than shaped. Safe to call on any
        calculator.
        """
        return None

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
    """Sparse terminal reward with self-relative per-step shaping.

    The shaping is measured against the agent's *own previous state* (not
    against opponents), which is near potential-based: the per-step deltas
    telescope to ``final - initial`` over an episode, so total shaping is
    bounded and does not distort the optimal policy. It is low variance and
    still captures opponent pressure indirectly (losing hexes / income yields
    a negative delta).

    Three orthogonal signals:

    - **territory**: change in the *number* of own hexes, normalised by a
      **fixed** ``territory_norm`` (default = the largest campaign map, 384)
      rather than the current map's hex count. This makes one hex worth the
      same (``territory_weight / territory_norm``) on every map, so expansion
      is incentivised consistently across the curriculum instead of the
      per-hex reward shrinking on larger maps. Opponents expanding into neutral
      land does not move it — only gaining/losing your own hexes does.
    - **opponent decline**: change in the number of *opponent* hexes, sign
      flipped (shrinking the enemy is rewarded, letting them grow penalised),
      normalised by the same ``territory_norm``. Against the win condition
      (own 80% or eliminate all opponents), own-territory alone caps out well
      below 80% on maps with a large entrenched enemy, so it cannot reward the
      decisive conquest phase. With equal weights this makes taking an enemy
      hex *doubly* rewarded (your count up, theirs down = ``1:2`` vs a neutral
      grab) and gives a dense gradient toward eliminating the opponent. Off by
      default (``opponent_weight=0``) to preserve prior behaviour.
    - **economy**: change in ``income - hex_count`` = ``4*farms - trees``.
      The base ``+1`` per hex cancels (so it does not double-count territory),
      unit upkeep is excluded (so building military is not punished), and the
      per-object values are constants so the signal is map-size invariant.

    All three are self-relative per-step deltas measured against the previous
    state, so they telescope over an episode and stay near potential-based.

    Parameters
    ----------
    territory_weight : float
        Weight on the per-step *own* hex-count delta. One hex captured is worth
        ``territory_weight / territory_norm``.
    opponent_weight : float
        Weight on the per-step opponent hex-count *decline* (reward =
        ``opponent_weight * (prev_opp_hexes - opp_hexes) / territory_norm``).
        Defaults to ``0.0`` (disabled).
    income_weight : float
        Weight on the per-step economy (``4*farms - trees``) delta.
    territory_norm : float
        Fixed denominator for the territory/opponent terms so a hex is worth the
        same on any map. Defaults to ``MAX_CAMPAIGN_HEXES`` (384).
    win_reward : float
        Terminal reward when the agent wins.
    loss_penalty : float
        Terminal reward when an opponent wins.
    truncation_penalty : float
        Terminal reward when the episode ends with no winner (max turns /
        steps reached). Defaults to ``-1.0`` so stalling to truncation is no
        better than losing, removing the stall-to-truncation local minimum.
    """

    def __init__(
        self,
        territory_weight: float = 0.5,
        income_weight: float = 0.004,
        win_reward: float = 1.0,
        loss_penalty: float = -1.0,
        truncation_penalty: float = -1.0,
        opponent_weight: float = 0.0,
        territory_norm: float = float(MAX_CAMPAIGN_HEXES),
    ):
        self.territory_weight = territory_weight
        self.opponent_weight = opponent_weight
        self.income_weight = income_weight
        self.territory_norm = float(territory_norm) if territory_norm else 1.0
        self.win_reward = win_reward
        self.loss_penalty = loss_penalty
        self.truncation_penalty = truncation_penalty
        self._prev_agent_hexes: int = 0
        self._prev_opp_hexes: int = 0
        self._prev_economy: float = 0.0

    def reset(self, game_state: GameState, agent_color: HColor) -> None:
        self.sync_baseline(game_state, agent_color)

    def sync_baseline(self, game_state: GameState, agent_color: HColor) -> None:
        """Snap the shaping baseline to the current state without emitting reward.

        Used to *exclude* changes made outside the agent's own turn (an
        opponent expanding into neutral land on its turn) from the per-step
        shaping. The env computes the end-turn shaping first, advances the
        opponents, then calls this so their autonomous deltas are absorbed into
        the baseline rather than penalising/rewarding the agent for moves it did
        not make.
        """
        self._prev_agent_hexes, self._prev_opp_hexes = self._hex_counts(
            game_state, agent_color
        )
        self._prev_economy = self._economy(game_state, agent_color)

    @staticmethod
    def _hex_counts(game_state: GameState, agent_color: HColor):
        """Return ``(agent_hexes, opponent_hexes)`` over all hexes in one pass.

        A hex counts toward a player only if it belongs to a province (matching
        the engine's ownership + ``get_hex_ownership_stats``); every province
        hex that is not the agent's belongs to an opponent. Neutral/unattached
        hexes count toward neither.
        """
        agent_hexes = 0
        opp_hexes = 0
        for hex in game_state.hexes:
            if hex.get_province() is not None:
                if hex.color == agent_color:
                    agent_hexes += 1
                else:
                    opp_hexes += 1
        return agent_hexes, opp_hexes

    @staticmethod
    def _economy(game_state: GameState, agent_color: HColor) -> float:
        """Return ``income - hex_count`` for the agent (= ``4*farms - trees``).

        Only hexes that belong to a province generate income, matching the
        engine's economics; single unattached hexes are ignored.
        """
        ruleset = game_state.ruleset
        if ruleset is None:
            return 0.0
        economy = 0
        for hex in game_state.hexes:
            if hex.color == agent_color and hex.get_province() is not None:
                economy += ruleset.get_hex_income(hex.piece) - 1
        return float(economy)

    def calculate(
        self,
        game_state: GameState,
        agent_color: HColor,
        terminated: bool,
        info: dict,
    ) -> float:
        if terminated:
            winner = game_state.game_end_manager.get_winner()
            if winner is not None and winner.color == agent_color:
                return self.win_reward
            if winner is not None:
                return self.loss_penalty
            return self.truncation_penalty  # no winner => truncation

        current_agent_hexes, current_opp_hexes = self._hex_counts(
            game_state, agent_color
        )
        current_economy = self._economy(game_state, agent_color)

        reward = (
            self.territory_weight
            * (current_agent_hexes - self._prev_agent_hexes) / self.territory_norm
            + self.opponent_weight
            * (self._prev_opp_hexes - current_opp_hexes) / self.territory_norm
            + self.income_weight * (current_economy - self._prev_economy)
        )

        self._prev_agent_hexes = current_agent_hexes
        self._prev_opp_hexes = current_opp_hexes
        self._prev_economy = current_economy
        return reward
