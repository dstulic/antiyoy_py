"""Compute end-of-game "win condition" statistics for a trained agent.

After a model first solves a level we record a snapshot of the agent's
position at the moment it wins, so different models (and the same model at
different points in the curriculum) can be compared later.  See
``tools/curriculum_train.py`` for the driver that produces the CSV.
"""

from typing import Optional, List

from core.game_state import GameState
from core.enums import HColor, PieceType
from core.core_utils import is_unit, get_strength

# CSV column order (the driver prepends model_details / level / timestamp).
WIN_STAT_FIELDS: List[str] = [
    "turns",
    "income_per_turn",
    "money_in_bank",
    "unit_strength",
    "unit_count",
    "defense_strength",
    "tower_count",
]

_TOWERS = (PieceType.TOWER, PieceType.STRONG_TOWER)


def compute_win_stats(game_state: GameState, agent_color: HColor) -> dict:
    """Snapshot the agent's economy and military from a finished game.

    - ``income_per_turn``: gross income summed over the agent's provinces
      (1/hex, +4 per farm, 0 for trees), i.e. before unit/tower upkeep.
    - ``money_in_bank``: money held across the agent's provinces.
    - ``unit_strength`` / ``unit_count``: sum of unit strengths (peasant 1 ..
      knight 4) and the number of units.
    - ``defense_strength`` / ``tower_count``: sum of tower defense values
      (tower 2, strong_tower 3) and the number of towers.
    """
    econ = game_state.economics_manager
    ruleset = game_state.ruleset

    provinces = [
        p for p in game_state.provinces_manager.provinces
        if p.get_color() == agent_color
    ]
    income = sum(econ.calculate_province_income(p) for p in provinces)
    money = sum(p.get_money() for p in provinces)

    unit_strength = unit_count = defense_strength = tower_count = 0
    for hex in game_state.hexes:
        if hex.color != agent_color:
            continue
        piece = hex.piece
        if is_unit(piece):
            unit_strength += get_strength(piece)
            unit_count += 1
        elif piece in _TOWERS:
            defense_strength += ruleset.get_defense_value(piece) if ruleset else 0
            tower_count += 1

    return {
        "income_per_turn": income,
        "money_in_bank": money,
        "unit_strength": unit_strength,
        "unit_count": unit_count,
        "defense_strength": defense_strength,
        "tower_count": tower_count,
    }


def play_until_win(
    model,
    level_index: int,
    action_space_hexes: int,
    max_turns: int = 400,
    max_attempts: int = 20,
    deterministic: bool = False,
    seed: int = 0,
    verbose: bool = False,
) -> Optional[dict]:
    """Play the level with ``model`` until the agent wins, then return the
    win stats (including ``turns``).  Returns ``None`` if no win occurs
    within ``max_attempts``.

    Uses stochastic actions by default: a greedy policy can trap itself
    repeating a non-terminating action, whereas sampling matches how the
    agent actually plays and reliably closes out winnable games.
    """
    from ml.env import AntiyoyEnv

    env = AntiyoyEnv(
        level_indices=[level_index],
        action_space_hexes=action_space_hexes,
        max_turns=max_turns,
    )
    try:
        for attempt in range(max_attempts):
            obs, info = env.reset(seed=seed + attempt)
            done = False
            while not done:
                masks = env.action_masks()
                action, _ = model.predict(
                    obs, action_masks=masks, deterministic=deterministic
                )
                obs, _reward, terminated, truncated, info = env.step(int(action))
                done = terminated or truncated
            if info.get("agent_won"):
                stats = compute_win_stats(env.game_state, env.agent_color)
                stats["turns"] = int(info.get("turn_count", 0))
                if verbose:
                    print(f"  win on attempt {attempt + 1}: {stats}", flush=True)
                return stats
            if verbose:
                print(f"  attempt {attempt + 1}/{max_attempts}: no win "
                      f"(turns={info.get('turn_count')})", flush=True)
    finally:
        try:
            env.close()
        except Exception:
            pass
    return None
