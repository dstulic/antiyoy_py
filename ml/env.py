"""Gymnasium environment wrapping the Antiyoy game engine."""

import os
import sys
from typing import Optional, List

import numpy as np
import gymnasium
from gymnasium import spaces

from core.game_state import GameState
from core.enums import HColor, EventType, Difficulty
from commands.executor import CommandExecutor
from commands.types import EndTurnCommand
from ml.observation import ObservationEncoder, FlatObservationEncoder
from ml.action_space import ActionMapper
from ml.reward import RewardCalculator, DefaultRewardCalculator


class AntiyoyEnv(gymnasium.Env):
    """Multi-step Gymnasium environment for Antiyoy.

    Each call to ``step(action)`` executes one atomic action (move a unit,
    build a piece, or end the turn).  When the agent ends its turn the
    environment advances all AI opponents before returning the next
    observation.

    Parameters
    ----------
    level_indices : list[int] | None
        Campaign level indices to sample from on ``reset()``.  If *None*,
        defaults to ``[1]``.
    level_code : str | None
        Explicit level code string.  Takes precedence over *level_indices*.
    agent_color : HColor | None
        The colour the ML agent controls.  Defaults to the first human
        entity found in the level.
    opponent_difficulty : Difficulty | None
        Difficulty assigned to all AI opponents.  When *None* (the
        default), the campaign-appropriate difficulty for the current
        level is used automatically via ``CampaignManager.get_difficulty``.
    max_turns : int
        Maximum number of full turn-cycles (laps) before truncation.
    max_steps : int | None
        Hard cap on ``step()`` calls per episode.  When set, the episode
        is truncated after this many steps regardless of turn count.
        Useful for bounding eval time with untrained policies.
    observation_encoder : ObservationEncoder | None
        Pluggable encoder; defaults to ``FlatObservationEncoder``.
    reward_calculator : RewardCalculator | None
        Pluggable reward; defaults to ``DefaultRewardCalculator``.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        level_indices: Optional[List[int]] = None,
        level_code: Optional[str] = None,
        agent_color: Optional[HColor] = None,
        opponent_difficulty: Optional[Difficulty] = None,
        max_turns: int = 500,
        max_steps: Optional[int] = None,
        observation_encoder: Optional[ObservationEncoder] = None,
        reward_calculator: Optional[RewardCalculator] = None,
        verbose: bool = False,
    ):
        super().__init__()

        self.level_indices = level_indices or [1]
        self.level_code = level_code
        self.requested_agent_color = agent_color
        self.opponent_difficulty = opponent_difficulty
        self.max_turns = max_turns
        self.max_steps = max_steps
        self.verbose = verbose
        self._current_level_index: Optional[int] = None

        self.obs_encoder = observation_encoder or FlatObservationEncoder()
        self.reward_calc = reward_calculator or DefaultRewardCalculator()

        # Will be set on first reset()
        self.game_state: Optional[GameState] = None
        self.executor: Optional[CommandExecutor] = None
        self.action_mapper: Optional[ActionMapper] = None
        self.agent_color: Optional[HColor] = None
        self._turn_count = 0
        self._step_count = 0

        # Bootstrap a throwaway game to determine N and build spaces
        self._bootstrap_spaces()

    # ------------------------------------------------------------------
    # Space construction
    # ------------------------------------------------------------------

    def _bootstrap_spaces(self) -> None:
        """Decode all configured levels to find the max hex count, then
        define fixed-size observation and action spaces so that all
        parallel envs share the same dimensions."""
        if self.level_code:
            gs = self._decode_level_code(self.level_code)
            max_hexes = len(gs.hexes)
        else:
            max_hexes = 0
            for idx in self.level_indices:
                gs = self._decode_level(idx)
                max_hexes = max(max_hexes, len(gs.hexes))

        self._max_n_hexes = max_hexes
        self.action_mapper = ActionMapper(max_hexes)
        self.observation_space = self.obs_encoder.get_observation_space()
        self.action_space = spaces.Discrete(self.action_mapper.action_space_size)

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(
        self, *, seed: Optional[int] = None, options: Optional[dict] = None
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)

        # Pick a level
        if self.level_code:
            self._current_level_index = None
            self.game_state = self._decode_level_code(self.level_code)
        else:
            idx = int(self.np_random.choice(self.level_indices))
            self._current_level_index = idx
            self.game_state = self._decode_level(idx)

        self._init_game()
        self.executor = CommandExecutor(self.game_state)

        # Resolve agent colour
        self.agent_color = self.requested_agent_color
        if self.agent_color is None:
            for e in self.game_state.entities_manager.entities or []:
                if e.is_human():
                    self.agent_color = e.color
                    break
        assert self.agent_color is not None, "No agent colour resolved"

        # If the agent isn't first to move, run AI turns until it is
        self._advance_opponents()

        self.reward_calc.reset(self.game_state, self.agent_color)
        self._turn_count = 0
        self._step_count = 0

        obs = self.obs_encoder.encode(self.game_state, self.agent_color)
        info = self._make_info()
        return obs, info

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict]:
        assert self.game_state is not None
        self._step_count += 1

        terminated = False
        truncated = False

        command = self.action_mapper.action_to_command(action, self.game_state)
        if command is None:
            # Invalid action decode -> treat as no-op, small penalty
            obs = self.obs_encoder.encode(self.game_state, self.agent_color)
            return obs, -0.01, False, False, self._make_info()

        success, _err = self.executor.execute(command, self.agent_color)
        if not success:
            obs = self.obs_encoder.encode(self.game_state, self.agent_color)
            return obs, -0.01, False, False, self._make_info()

        # Check game end after every action
        if self.game_state.game_end_manager.is_game_ended():
            terminated = True
        elif isinstance(command, EndTurnCommand):
            self._turn_count += 1
            self._advance_opponents()
            if self.game_state.game_end_manager.is_game_ended():
                terminated = True

        if not terminated and self._turn_count >= self.max_turns:
            truncated = True
            terminated = True

        if not terminated and self.max_steps and self._step_count >= self.max_steps:
            truncated = True
            terminated = True

        reward = self.reward_calc.calculate(
            self.game_state, self.agent_color, terminated, {}
        )
        obs = self.obs_encoder.encode(self.game_state, self.agent_color)
        info = self._make_info()

        return obs, reward, terminated, truncated, info

    def action_masks(self) -> np.ndarray:
        """Return action mask for sb3-contrib ``MaskablePPO`` / ``MaskableA2C``."""
        if self.game_state is None or self.agent_color is None:
            mask = np.zeros(self.action_space.n, dtype=bool)
            mask[0] = True  # EndTurn fallback so mask is never all-zeros
            return mask
        return self.action_mapper.get_action_mask(self.game_state, self.agent_color)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _decode_level(self, level_index: Optional[int]) -> GameState:
        from campaign.levels import get_level_code

        idx = level_index if level_index is not None else self.level_indices[0]
        code = get_level_code(idx)
        assert code and code != "-", f"No level code for index {idx}"
        return self._decode_level_code(code)

    @staticmethod
    def _decode_level_code(code: str) -> GameState:
        from save_load.decoder import GameStateDecoder

        decoder = GameStateDecoder()
        result = decoder.decode(code)
        if isinstance(result, tuple):
            gs, _ = result
        else:
            gs = result
        assert gs is not None, "Failed to decode game state"
        return gs

    def _resolve_difficulty(self) -> Difficulty:
        """Return the effective opponent difficulty for the current episode."""
        if self.opponent_difficulty is not None:
            return self.opponent_difficulty
        if self._current_level_index is not None:
            from campaign.manager import CampaignManager
            return CampaignManager().get_difficulty(self._current_level_index)
        return Difficulty.EASY

    def _init_game(self) -> None:
        """Mirror the init pattern from ``tools/ai_playthrough._init_game``."""
        gs = self.game_state
        from core.events import SYSTEM_AUTHOR

        # Disable history/undo tracking -- pure observers that serialise
        # the full game state on every event, ~50% of per-step cost.
        gs.events_manager.remove_listener(gs.undo_manager)
        gs.events_manager.remove_listener(gs.history_manager)

        # Starting money
        for province in gs.provinces_manager.provinces:
            if province.get_money() == 0:
                event = gs.events_manager.factory.create_event(
                    EventType.SET_MONEY, author=SYSTEM_AUTHOR
                )
                if event:
                    event.province_id = province.get_id()
                    event.money = 10
                    gs.events_manager.apply_event(event)

        if gs.fog_of_war_manager and gs.fog_of_war_manager.enabled:
            gs.fog_of_war_manager.apply_update()

        difficulty = self._resolve_difficulty()
        for entity in gs.entities_manager.entities or []:
            if entity.is_artificial_intelligence():
                entity.set_ai_difficulty(difficulty)

    def _suppress_stdout(self):
        """Context manager that silences stdout when verbose is False."""
        import contextlib
        if self.verbose:
            return contextlib.nullcontext()
        return contextlib.redirect_stdout(open(os.devnull, "w"))

    def _advance_opponents(self) -> None:
        """Run AI turns until it is the agent's turn or the game ends."""
        gs = self.game_state
        if gs.game_end_manager.is_game_ended():
            return

        current = gs.entities_manager.get_current_entity()
        if current and current.color == self.agent_color:
            return

        with self._suppress_stdout():
            gs.ai_manager.process_ai_turns()

    def _make_info(self) -> dict:
        gs = self.game_state
        stats = gs.get_hex_ownership_stats(self.agent_color)
        winner = gs.game_end_manager.get_winner()
        return {
            "turn_count": self._turn_count,
            "step_count": self._step_count,
            "ownership_pct": stats["percentage"],
            "game_ended": gs.game_end_manager.is_game_ended(),
            "winner_color": winner.color.value if winner else None,
            "agent_won": winner is not None and winner.color == self.agent_color,
        }
