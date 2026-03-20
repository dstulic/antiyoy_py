"""Tests for the ml package: observation encoder, action mapper, reward, and env."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from core.game_state import GameState
from core.enums import (
    HColor, PieceType, RulesType, EntityType, Difficulty, EventType,
)
from core.player_entity import PlayerEntity
from save_load.decoder import GameStateDecoder, _build_adjacency_graph
from campaign.levels import get_level_code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_level(index: int = 0) -> GameState:
    code = get_level_code(index)
    decoder = GameStateDecoder()
    result = decoder.decode(code)
    gs = result[0] if isinstance(result, tuple) else result
    assert gs is not None
    # Give provinces starting money
    from core.events import SYSTEM_AUTHOR
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
    for entity in (gs.entities_manager.entities or []):
        if entity.is_artificial_intelligence():
            entity.set_ai_difficulty(Difficulty.EASY)
    return gs


def _find_human_color(gs: GameState) -> HColor:
    for e in (gs.entities_manager.entities or []):
        if e.is_human():
            return e.color
    raise ValueError("No human entity found")


def _small_game_state() -> GameState:
    """Create a minimal game state with two players for fast tests."""
    gs = GameState()
    gs.set_ruleset(RulesType.DEF, version_code=1)

    h0 = gs.add_hex(0, 0, HColor.RED)
    h0.piece = PieceType.CITY
    gs.add_hex(1, 0, HColor.RED)
    gs.add_hex(-1, 0, HColor.RED)

    h3 = gs.add_hex(3, 0, HColor.BLUE)
    h3.piece = PieceType.CITY
    gs.add_hex(4, 0, HColor.BLUE)
    gs.add_hex(2, 0, HColor.GRAY)

    _build_adjacency_graph(gs)

    red = PlayerEntity(gs.entities_manager, EntityType.HUMAN, HColor.RED)
    blue = PlayerEntity(gs.entities_manager, EntityType.AI_BALANCER, HColor.BLUE)
    blue.set_ai_difficulty(Difficulty.EASY)
    gs.entities_manager.initialize([red, blue])

    gs.provinces_manager.builder.grant_permission()
    gs.provinces_manager.builder.apply()
    for p in gs.provinces_manager.provinces:
        p.set_money(50)

    gs.readiness_manager.update()
    return gs


# ---------------------------------------------------------------------------
# ObservationEncoder
# ---------------------------------------------------------------------------

class TestFlatObservationEncoder:
    def test_shape(self):
        from ml.observation import FlatObservationEncoder, FLAT_OBS_SIZE

        gs = _small_game_state()
        enc = FlatObservationEncoder()
        obs = enc.encode(gs, HColor.RED)

        assert obs.shape == (FLAT_OBS_SIZE,)
        assert obs.dtype == np.float32

    def test_not_all_zeros(self):
        from ml.observation import FlatObservationEncoder

        gs = _small_game_state()
        enc = FlatObservationEncoder()
        obs = enc.encode(gs, HColor.RED)
        assert np.any(obs != 0), "Observation should not be all zeros"

    def test_observation_space(self):
        from ml.observation import FlatObservationEncoder, FLAT_OBS_SIZE

        enc = FlatObservationEncoder()
        space = enc.get_observation_space()
        assert space.shape == (FLAT_OBS_SIZE,)

    def test_campaign_level(self):
        from ml.observation import FlatObservationEncoder, FLAT_OBS_SIZE

        gs = _decode_level(0)
        color = _find_human_color(gs)
        enc = FlatObservationEncoder()
        obs = enc.encode(gs, color)
        assert obs.shape == (FLAT_OBS_SIZE,)
        assert np.isfinite(obs).all(), "No NaN/Inf in observation"


# ---------------------------------------------------------------------------
# ActionMapper
# ---------------------------------------------------------------------------

class TestActionMapper:
    def test_space_size(self):
        from ml.action_space import ActionMapper, NUM_BUILDABLE

        mapper = ActionMapper(n_hexes=10)
        expected = 1 + 10 * 10 + 10 * NUM_BUILDABLE
        assert mapper.action_space_size == expected

    def test_end_turn_decode(self):
        from ml.action_space import ActionMapper

        gs = _small_game_state()
        mapper = ActionMapper(len(gs.hexes))
        cmd = mapper.action_to_command(0, gs)
        from commands.types import EndTurnCommand
        assert isinstance(cmd, EndTurnCommand)

    def test_move_roundtrip(self):
        from ml.action_space import ActionMapper

        mapper = ActionMapper(n_hexes=20)
        idx = mapper._move_index(3, 7)
        src, dst = mapper._decode_move(idx)
        assert src == 3
        assert dst == 7

    def test_build_roundtrip(self):
        from ml.action_space import ActionMapper

        mapper = ActionMapper(n_hexes=20)
        idx = mapper._build_index(5, 2)
        hex_i, piece_i = mapper._decode_build(idx)
        assert hex_i == 5
        assert piece_i == 2

    def test_mask_has_end_turn(self):
        from ml.action_space import ActionMapper

        gs = _small_game_state()
        mapper = ActionMapper(len(gs.hexes))
        mask = mapper.get_action_mask(gs, HColor.RED)
        assert mask[0] is np.bool_(True), "EndTurn should always be valid"

    def test_mask_not_our_turn(self):
        from ml.action_space import ActionMapper

        gs = _small_game_state()
        mapper = ActionMapper(len(gs.hexes))
        mask = mapper.get_action_mask(gs, HColor.BLUE)
        assert not mask.any(), "No valid actions when it's not our turn"

    def test_mask_campaign_level(self):
        from ml.action_space import ActionMapper

        gs = _decode_level(0)
        color = _find_human_color(gs)
        # Advance to human turn
        gs.ai_manager.process_ai_turns()
        mapper = ActionMapper(len(gs.hexes))
        mask = mapper.get_action_mask(gs, color)
        assert mask[0], "EndTurn should be valid"
        assert mask.sum() > 1, "Should have more actions than just EndTurn"


# ---------------------------------------------------------------------------
# RewardCalculator
# ---------------------------------------------------------------------------

class TestDefaultRewardCalculator:
    def test_reset_and_step(self):
        from ml.reward import DefaultRewardCalculator

        gs = _small_game_state()
        calc = DefaultRewardCalculator(shaping_weight=0.0)
        calc.reset(gs, HColor.RED)

        reward = calc.calculate(gs, HColor.RED, terminated=False, info={})
        assert reward == 0.0, "No shaping -> zero non-terminal reward"

    def test_terminal_win(self):
        from ml.reward import DefaultRewardCalculator

        gs = _small_game_state()
        # Fake a win
        gs.game_end_manager.game_ended = True
        gs.game_end_manager.winner_color = HColor.RED

        calc = DefaultRewardCalculator()
        calc.reset(gs, HColor.RED)
        reward = calc.calculate(gs, HColor.RED, terminated=True, info={})
        assert reward == 1.0

    def test_terminal_loss(self):
        from ml.reward import DefaultRewardCalculator

        gs = _small_game_state()
        gs.game_end_manager.game_ended = True
        gs.game_end_manager.winner_color = HColor.BLUE

        calc = DefaultRewardCalculator()
        calc.reset(gs, HColor.RED)
        reward = calc.calculate(gs, HColor.RED, terminated=True, info={})
        assert reward == -1.0


# ---------------------------------------------------------------------------
# AntiyoyEnv
# ---------------------------------------------------------------------------

class TestAntiyoyEnv:
    def test_reset_returns_obs_and_info(self):
        from ml.env import AntiyoyEnv

        env = AntiyoyEnv(level_indices=[0], opponent_difficulty=Difficulty.EASY)
        obs, info = env.reset(seed=42)
        assert obs.ndim == 1
        assert "turn_count" in info
        assert "ownership_pct" in info

    def test_step_end_turn(self):
        from ml.env import AntiyoyEnv

        env = AntiyoyEnv(level_indices=[0], opponent_difficulty=Difficulty.EASY)
        env.reset(seed=42)
        # Action 0 = EndTurn
        obs, reward, terminated, truncated, info = env.step(0)
        assert obs.ndim == 1
        assert isinstance(reward, float)

    def test_action_masks_shape(self):
        from ml.env import AntiyoyEnv

        env = AntiyoyEnv(level_indices=[0], opponent_difficulty=Difficulty.EASY)
        env.reset(seed=42)
        mask = env.action_masks()
        assert mask.shape == (env.action_space.n,)
        assert mask.dtype == bool
        assert mask[0], "EndTurn should be valid"

    def test_random_rollout(self):
        """Run a short rollout choosing random valid actions."""
        from ml.env import AntiyoyEnv

        env = AntiyoyEnv(
            level_indices=[0],
            opponent_difficulty=Difficulty.EASY,
            max_turns=10,
        )
        obs, info = env.reset(seed=123)
        done = False
        steps = 0
        while not done and steps < 200:
            mask = env.action_masks()
            valid = np.where(mask)[0]
            if len(valid) == 0:
                break
            action = env.np_random.choice(valid)
            obs, reward, terminated, truncated, info = env.step(int(action))
            done = terminated or truncated
            steps += 1
        assert steps > 0, "Should have taken at least one step"

    def test_multiple_levels(self):
        from ml.env import AntiyoyEnv

        env = AntiyoyEnv(level_indices=[0, 1], opponent_difficulty=Difficulty.EASY)
        for _ in range(3):
            obs, info = env.reset()
            assert obs.ndim == 1


# ---------------------------------------------------------------------------
# EntityType.AI_ML registration
# ---------------------------------------------------------------------------

class TestAiMlRegistration:
    def test_entity_type_exists(self):
        assert EntityType.AI_ML.value == "ai_ml"

    def test_is_ai(self):
        assert EntityType.AI_ML.is_ai()

    def test_ai_manager_returns_none_without_model(self):
        gs = _small_game_state()
        # AI_ML entity but no model file -> _get_ml_ai will be created
        # but it won't have a model loaded. Just verify the dispatch path.
        entity = PlayerEntity(gs.entities_manager, EntityType.AI_ML, HColor.GREEN)
        ai = gs.ai_manager.get_ai_for_entity(entity)
        assert ai is not None, "AIManager should return an MlAI instance"
