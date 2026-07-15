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
    invalid_action_penalty : float
        Positive magnitude subtracted from the reward when a chosen action
        cannot be decoded or fails validation. Discourages spamming illegal
        actions. Defaults to ``0.0`` (off).
    time_cost : float
        Small positive magnitude subtracted from *every* ``step`` reward. Adds
        a constant per-action cost so long games and per-turn action churn are
        penalised, nudging the agent toward decisive play. Defaults to ``0.0``.
    noop_opponents : bool
        When *True*, opponents do not run their AI — each opponent turn is ended
        immediately with no moves. This is the first rung of a difficulty
        ladder (``noop -> easy -> average -> hard``): it lets the agent secure
        first wins against a passive enemy before facing an active one.
    opponent_income_tax : float
        Fraction of each opponent's *positive per-turn income* withheld before
        it is applied to their treasury (``0.0`` = off, ``1.0`` = keep nothing).
        Upkeep is untouched, so opponents run their normal AI logic but grow
        their economy more slowly (and can starve if upkeep outpaces net
        income). A continuous difficulty knob — anneal ``0.99 -> 0`` across
        resumes to hand the agent a progressively stronger enemy that plays the
        same way throughout the game. The agent's own income is exempt.
    record_replay : bool
        When *True*, keep the ``history_manager`` attached so per-event replay
        snapshots are captured and can be serialised with ``save_replay`` at
        game end. Off by default because snapshotting roughly doubles per-step
        cost; only enable it for one-off replay generation, never for training.
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
        log_progress: bool = False,
        action_space_hexes: Optional[int] = None,  # None = auto-detect from levels
        invalid_action_penalty: float = 0.0,
        time_cost: float = 0.0,
        noop_opponents: bool = False,
        opponent_income_tax: float = 0.0,
        record_replay: bool = False,
    ):
        super().__init__()

        self.level_indices = level_indices or [1]
        self.level_code = level_code
        self.requested_agent_color = agent_color
        self.opponent_difficulty = opponent_difficulty
        self.max_turns = max_turns
        self.max_steps = max_steps
        self.verbose = verbose
        self.log_progress = log_progress
        self._action_space_hexes = action_space_hexes
        self.invalid_action_penalty = invalid_action_penalty
        self.time_cost = time_cost
        self.noop_opponents = noop_opponents
        self.opponent_income_tax = opponent_income_tax
        self.record_replay = record_replay
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
        parallel envs share the same dimensions.

        If ``action_space_hexes`` was provided, it overrides the auto-detected
        max, allowing the model to play on larger maps than the training set.
        """
        if self._action_space_hexes:
            max_hexes = self._action_space_hexes
        elif self.level_code:
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

    def _log(self, msg: str) -> None:
        if self.log_progress:
            import time
            from datetime import datetime
            pid = os.getpid()
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts} pid={pid}] {msg}", flush=True)

    def reset(
        self, *, seed: Optional[int] = None, options: Optional[dict] = None
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self._log(f"reset() called, level_indices={self.level_indices}")

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

        # Apply the opponent income-tax handicap (exempting the agent) before
        # any opponent turn is processed so their very first income is taxed.
        if self.opponent_income_tax > 0.0:
            self.game_state.economics_manager.income_tax_rate = self.opponent_income_tax
            self.game_state.economics_manager.income_tax_exempt_color = self.agent_color

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

        if self.log_progress and self._step_count % 500 == 0:
            self._log(f"step {self._step_count}/{self.max_steps or '∞'}  "
                      f"turn={self._turn_count}/{self.max_turns}  "
                      f"level={self._current_level_index}")

        if self.max_steps and self._step_count >= self.max_steps:
            if self.log_progress:
                self._log(f"Episode DONE (max_steps): steps={self._step_count} turns={self._turn_count}")
            reward = self.reward_calc.calculate(
                self.game_state, self.agent_color, True, {}
            )
            obs = self.obs_encoder.encode(self.game_state, self.agent_color)
            return obs, reward - self.time_cost, True, True, self._make_info()

        terminated = False
        truncated = False

        command = self.action_mapper.action_to_command(action, self.game_state)
        if command is None:
            obs = self.obs_encoder.encode(self.game_state, self.agent_color)
            reward = -self.invalid_action_penalty - self.time_cost
            return obs, reward, False, False, self._make_info()

        if self.log_progress and isinstance(command, EndTurnCommand):
            self._log(f"EndTurn at step {self._step_count}, turn {self._turn_count} — running opponents")

        success, _err = self.executor.execute(command, self.agent_color)
        if not success:
            obs = self.obs_encoder.encode(self.game_state, self.agent_color)
            reward = -self.invalid_action_penalty - self.time_cost
            return obs, reward, False, False, self._make_info()

        # Shaping computed on the agent's *own* turn only. For an end-turn we
        # snapshot the delta before opponents move, then re-baseline afterwards
        # so the opponents' autonomous expansion is not attributed to the agent.
        shaping_reward: Optional[float] = None

        if self.game_state.game_end_manager.is_game_ended():
            terminated = True
        elif isinstance(command, EndTurnCommand):
            shaping_reward = self.reward_calc.calculate(
                self.game_state, self.agent_color, False, {}
            )
            self._turn_count += 1
            self._advance_opponents()
            # Absorb opponents' turn deltas into the baseline (no reward for them).
            self.reward_calc.sync_baseline(self.game_state, self.agent_color)
            if self.log_progress:
                self._log(f"Opponents done, turn now {self._turn_count}")
            if self.game_state.game_end_manager.is_game_ended():
                terminated = True

        if not terminated and self._turn_count >= self.max_turns:
            truncated = True
            terminated = True

        if self.log_progress and (terminated or truncated):
            self._log(f"Episode DONE: steps={self._step_count} turns={self._turn_count} "
                      f"terminated={terminated} truncated={truncated}")

        if terminated:
            # Terminal reward (win / loss / truncation) overrides shaping.
            reward = self.reward_calc.calculate(
                self.game_state, self.agent_color, True, {}
            )
        elif shaping_reward is not None:
            # End-turn step: use the pre-opponent shaping snapshot.
            reward = shaping_reward
        else:
            # Move/build within the agent's turn: shape normally.
            reward = self.reward_calc.calculate(
                self.game_state, self.agent_color, False, {}
            )

        obs = self.obs_encoder.encode(self.game_state, self.agent_color)
        info = self._make_info()

        return obs, reward - self.time_cost, terminated, truncated, info

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
        # the full game state on every event, ~50% of per-step cost. The
        # history_manager is kept when recording a replay so its snapshots can
        # be serialised at game end (much slower, so off during training/eval).
        gs.events_manager.remove_listener(gs.undo_manager)
        if not self.record_replay:
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

        if self.noop_opponents:
            self._advance_opponents_noop()
            return

        with self._suppress_stdout():
            gs.ai_manager.process_ai_turns()

    def _advance_opponents_noop(self) -> None:
        """End each opponent's turn without running its AI (passive enemy).

        Cycles through non-agent players by submitting an ``EndTurnCommand`` for
        each in turn (which still applies their turn-start income), so opponents
        accumulate money but never move, build, or expand. Bounded by an
        iteration guard so a stuck transition can't loop forever.
        """
        gs = self.game_state
        n_entities = len(gs.entities_manager.entities or []) or 1
        guard = 0
        with self._suppress_stdout():
            while guard < n_entities * 4:
                guard += 1
                if gs.game_end_manager.is_game_ended():
                    return
                current = gs.entities_manager.get_current_entity()
                if current is None or current.color == self.agent_color:
                    return
                success, _err = self.executor.execute(
                    EndTurnCommand(), current.color
                )
                if not success:
                    # Can't advance this entity's turn — bail rather than spin.
                    return

    def _make_info(self) -> dict:
        gs = self.game_state
        stats = gs.get_hex_ownership_stats(self.agent_color)
        winner = gs.game_end_manager.get_winner()
        agent_won = winner is not None and winner.color == self.agent_color
        return {
            "turn_count": self._turn_count,
            "step_count": self._step_count,
            "ownership_pct": stats["percentage"],
            "game_ended": gs.game_end_manager.is_game_ended(),
            "winner_color": winner.color.value if winner else None,
            "agent_won": agent_won,
            "is_success": agent_won,
        }
