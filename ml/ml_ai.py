"""ML AI player that uses a trained model for inference."""

import math
from typing import Optional

from ai.abstract_ai import AbstractAI
from core.game_state import GameState
from commands.executor import CommandExecutor
from commands.types import EndTurnCommand
from ml.observation import FlatObservationEncoder
from ml.action_space import ActionMapper, NUM_BUILDABLE


def _n_hexes_from_action_space(action_space_n: int) -> int:
    """Recover the hex count N used during training from the model's action
    space size: ``action_space_n = 1 + N*N + N*NUM_BUILDABLE``."""
    discriminant = NUM_BUILDABLE ** 2 + 4 * (action_space_n - 1)
    return int((-NUM_BUILDABLE + math.isqrt(discriminant)) // 2)


class MlAI(AbstractAI):
    """AI player that loads a trained SB3 model and uses it to play.

    Sits inside the existing ``AbstractAI`` hierarchy so it can be wired
    into ``AIManager`` just like the balancer AI.

    Parameters
    ----------
    game_state : GameState
        The shared game state object.
    model_path : str
        Path to a saved sb3-contrib ``MaskablePPO`` (or compatible) model
        file (without the ``.zip`` extension that SB3 appends).
    """

    def __init__(self, game_state: GameState, model_path: str):
        super().__init__(game_state)
        self._model_path = model_path
        self._model = None  # lazy-loaded
        self._obs_encoder = FlatObservationEncoder()
        self._action_mapper: Optional[ActionMapper] = None

    def _ensure_model(self) -> None:
        """Lazy-load the model and build an ActionMapper whose N matches
        the action space the model was trained with."""
        if self._model is not None:
            return
        from sb3_contrib import MaskablePPO
        self._model = MaskablePPO.load(self._model_path)
        n = _n_hexes_from_action_space(self._model.action_space.n)
        self._action_mapper = ActionMapper(n)

    def get_version_code(self) -> int:
        return 1

    def apply(self) -> None:
        """Run the model in a loop until it chooses EndTurn."""
        self._ensure_model()
        color = self.get_current_color()
        if color is None:
            return

        executor = CommandExecutor(self.game_state)

        n_hexes = len(self.game_state.hexes)
        max_actions = n_hexes * 4  # safety cap per turn
        for _ in range(max_actions):
            obs = self._obs_encoder.encode(self.game_state, color)
            mask = self._action_mapper.get_action_mask(self.game_state, color)

            if not mask.any():
                break

            action, _ = self._model.predict(obs, action_masks=mask, deterministic=True)
            command = self._action_mapper.action_to_command(int(action), self.game_state)

            if command is None:
                break
            if isinstance(command, EndTurnCommand):
                break

            success, _ = executor.execute(command, color)
            if not success:
                break
