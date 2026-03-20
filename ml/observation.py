"""Pluggable observation encoders for converting game state to model input."""

from abc import ABC, abstractmethod
from typing import List

import numpy as np
import gymnasium

from core.game_state import GameState
from core.enums import HColor
from core.province import Province


class ObservationEncoder(ABC):
    """Abstract interface for encoding game state into observations."""

    @abstractmethod
    def get_observation_space(self) -> gymnasium.spaces.Space:
        """Return the gymnasium observation space this encoder produces."""

    @abstractmethod
    def encode(self, game_state: GameState, agent_color: HColor) -> np.ndarray:
        """Encode the current game state into a numpy array from the agent's perspective."""


# Feature sizes for FlatObservationEncoder
_GLOBAL_FEATURES = 4
_AGENT_FEATURES = 5
_MAX_OPPONENTS = 5
_OPPONENT_FEATURES = 3
_MAX_PROVINCES = 8
_PROVINCE_FEATURES = 6


def _compute_flat_obs_size() -> int:
    return (
        _GLOBAL_FEATURES
        + _AGENT_FEATURES
        + _MAX_OPPONENTS * _OPPONENT_FEATURES
        + _MAX_PROVINCES * _PROVINCE_FEATURES  # agent provinces
        + _MAX_PROVINCES * _PROVINCE_FEATURES  # enemy provinces
    )


FLAT_OBS_SIZE = _compute_flat_obs_size()


class FlatObservationEncoder(ObservationEncoder):
    """Encodes game state as a fixed-size flat feature vector (~120 floats).

    Feature layout (all values normalised to roughly [-1, 1] or [0, 1]):
        Global (4):  ownership_pct, turn_number, lap, num_players_alive
        Agent  (5):  total_money, total_income, num_provinces, num_hexes, num_units
        Per-opponent (5*3=15): hex_count, province_count, alive
        Agent provinces top-8 (8*6=48): money, income, profit, hex_count, unit_count, frontline_count
        Enemy provinces top-8 (8*6=48): same
    """

    def get_observation_space(self) -> gymnasium.spaces.Space:
        return gymnasium.spaces.Box(
            low=-np.inf, high=np.inf, shape=(FLAT_OBS_SIZE,), dtype=np.float32
        )

    def encode(self, game_state: GameState, agent_color: HColor) -> np.ndarray:
        obs = np.zeros(FLAT_OBS_SIZE, dtype=np.float32)
        idx = 0

        entities = game_state.entities_manager.entities or []
        total_hexes = len(game_state.hexes) or 1

        # --- Global features ---
        stats = game_state.get_hex_ownership_stats(agent_color)
        obs[idx] = stats["percentage"] / 100.0
        idx += 1
        obs[idx] = min(game_state.turns_manager.turn_index / max(len(entities), 1), 1.0)
        idx += 1
        obs[idx] = min(game_state.turns_manager.lap / 200.0, 1.0)
        idx += 1
        alive_count = sum(
            1
            for e in entities
            if not game_state.game_end_manager.is_player_dead(e.color)
        )
        obs[idx] = alive_count / max(len(entities), 1)
        idx += 1

        # --- Agent summary ---
        agent_provinces = [
            p
            for p in game_state.provinces_manager.provinces
            if p.get_color() == agent_color
        ]
        agent_hexes = [h for h in game_state.hexes if h.color == agent_color]
        agent_units = [h for h in agent_hexes if h.has_unit()]
        total_money = sum(p.get_money() for p in agent_provinces)
        total_income = sum(
            game_state.economics_manager.calculate_province_income(p)
            for p in agent_provinces
        )

        obs[idx] = total_money / 100.0
        idx += 1
        obs[idx] = total_income / 50.0
        idx += 1
        obs[idx] = len(agent_provinces) / 10.0
        idx += 1
        obs[idx] = len(agent_hexes) / total_hexes
        idx += 1
        obs[idx] = len(agent_units) / max(total_hexes, 1)
        idx += 1

        # --- Per-opponent features ---
        opponents = [e for e in entities if e.color != agent_color]
        for i in range(_MAX_OPPONENTS):
            if i < len(opponents):
                opp = opponents[i]
                opp_stats = game_state.get_hex_ownership_stats(opp.color)
                obs[idx] = opp_stats["player_hexes"] / total_hexes
                idx += 1
                opp_provinces = [
                    p
                    for p in game_state.provinces_manager.provinces
                    if p.get_color() == opp.color
                ]
                obs[idx] = len(opp_provinces) / 10.0
                idx += 1
                obs[idx] = 0.0 if game_state.game_end_manager.is_player_dead(opp.color) else 1.0
                idx += 1
            else:
                idx += _OPPONENT_FEATURES

        # --- Agent provinces (top 8 by hex count) ---
        idx = _encode_provinces(
            obs, idx, agent_provinces, game_state, agent_color, total_hexes
        )

        # --- Enemy provinces (top 8 by hex count) ---
        enemy_provinces = [
            p
            for p in game_state.provinces_manager.provinces
            if p.get_color() != agent_color and p.get_color() != HColor.GRAY
        ]
        idx = _encode_provinces(
            obs, idx, enemy_provinces, game_state, agent_color, total_hexes
        )

        return obs


def _count_frontline_hexes(province: Province, owner_color: HColor) -> int:
    """Count hexes in the province that are adjacent to a differently-coloured hex."""
    count = 0
    for h in province.get_hexes():
        for adj in h.adjacent_hexes:
            if adj.color != owner_color:
                count += 1
                break
    return count


def _encode_provinces(
    obs: np.ndarray,
    idx: int,
    provinces: List[Province],
    game_state: GameState,
    agent_color: HColor,
    total_hexes: int,
) -> int:
    """Encode up to _MAX_PROVINCES provinces into *obs* starting at *idx*."""
    sorted_provs = sorted(provinces, key=lambda p: len(p.get_hexes()), reverse=True)
    for i in range(_MAX_PROVINCES):
        if i < len(sorted_provs):
            p = sorted_provs[i]
            hexes = p.get_hexes()
            p_color = p.get_color() or HColor.GRAY
            obs[idx] = p.get_money() / 100.0
            idx += 1
            obs[idx] = game_state.economics_manager.calculate_province_income(p) / 50.0
            idx += 1
            obs[idx] = game_state.economics_manager.calculate_province_profit(p) / 50.0
            idx += 1
            obs[idx] = len(hexes) / total_hexes
            idx += 1
            obs[idx] = sum(1 for h in hexes if h.has_unit()) / max(len(hexes), 1)
            idx += 1
            obs[idx] = _count_frontline_hexes(p, p_color) / max(len(hexes), 1)
            idx += 1
        else:
            idx += _PROVINCE_FEATURES
    return idx
