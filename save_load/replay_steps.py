"""
Compute replay steps from stored snapshots.

Snapshots use diff-based hex storage: the first snapshot has full hex state,
subsequent snapshots store only changed hex tokens (prefixed with 'D:').
Events are only used for animation data (what piece moved where).
"""

from typing import List, Optional
from core.enums import PieceType, HColor
from core.history_manager import _hex_str_to_token_map


def _animation_from_event_encoding(event_encoding: str, prev_hexes_map: dict) -> Optional[dict]:
    """Build animation payload from an event encoding string.
    prev_hexes_map: (c1,c2) -> hex_info dict for looking up piece type at source."""
    parts = (event_encoding or "").strip().split()
    if not parts:
        return None
    key = parts[0]
    p = parts[1:]

    if key == "um" and len(p) >= 4:
        try:
            c1, c2 = int(p[0]), int(p[1])
            c3, c4 = int(p[2]), int(p[3])
            src = prev_hexes_map.get((c1, c2))
            piece_type = (src.get("piece") if src else None) or "peasant"
            return {
                "type": "unit_move",
                "piece_type": piece_type,
                "source": {"coordinate1": c1, "coordinate2": c2},
                "target": {"coordinate1": c3, "coordinate2": c4},
            }
        except (ValueError, TypeError):
            return None

    if key == "pb" and len(p) >= 3:
        try:
            c1, c2 = int(p[0]), int(p[1])
            return {
                "type": "piece_build",
                "piece_type": p[2],
                "target": {"coordinate1": c1, "coordinate2": c2},
            }
        except (ValueError, TypeError):
            return None

    return None


def _is_system_snapshot(snap) -> bool:
    """True if this snapshot was caused by a system event (no animation needed)."""
    if snap.author_name == "system":
        return True
    if snap.author_color is None and (snap.author_name is None or snap.author_name == ""):
        return True
    enc = (snap.event_encoding or "").strip()
    key = enc.split()[0] if enc else ""
    if key == "pa":
        parts = enc.split()
        if len(parts) >= 4 and parts[3].lower() in ("palm", "pine"):
            return True
    if key in ("te", "tb", "lb", "pts", "gc", "mc", "sr", "sm", "sbm", "gm", "hcc", "pd"):
        return True
    return False


# ---------------------------------------------------------------------------
# Hex token map helpers (for diff-based reconstruction)
# ---------------------------------------------------------------------------

def _apply_hex_update(running_map: dict, hex_str: str) -> dict:
    """Apply a hex string (full or D:-prefixed diff) to a running token map.
    Returns the updated map (same object for diffs, new object for full)."""
    if hex_str.startswith("D:"):
        diff_str = hex_str[2:]
        if diff_str:
            for token in diff_str.split(","):
                token = token.strip()
                if not token:
                    continue
                parts = token.split(" ")
                if len(parts) >= 2:
                    try:
                        running_map[(int(parts[0]), int(parts[1]))] = token
                    except ValueError:
                        continue
        return running_map
    return _hex_str_to_token_map(hex_str)


def _tokens_to_hex_list(running_map: dict) -> list:
    """Convert a running token map to a list of hex dicts for the frontend."""
    hexes = []
    for token in running_map.values():
        parts = token.split(" ")
        if len(parts) < 3:
            continue
        try:
            hexes.append({
                "coordinate1": int(parts[0]),
                "coordinate2": int(parts[1]),
                "color": parts[2],
                "piece": parts[3] if len(parts) > 3 else None,
                "unit_id": int(parts[4]) if len(parts) > 4 else -1,
                "is_ready": False,
            })
        except (ValueError, IndexError):
            continue
    return hexes


def _hexes_to_map(hexes_list: list) -> dict:
    """Build a (c1,c2) -> hex_info dict for animation lookup."""
    return {(h["coordinate1"], h["coordinate2"]): h for h in hexes_list}


# ---------------------------------------------------------------------------
# Snapshot field parsers
# ---------------------------------------------------------------------------

def _parse_turn(turn_str: str) -> tuple:
    parts = turn_str.split()
    return (int(parts[0]), int(parts[1])) if len(parts) >= 2 else (0, 0)


def _parse_entities(entities_str: str) -> list:
    if not entities_str:
        return []
    out = []
    for part in entities_str.split(";"):
        parts = part.strip().split(" ", 2)
        if len(parts) >= 3:
            out.append({"type": parts[0], "color": parts[1], "name": parts[2]})
    return out


def _parse_provinces(provinces_str: str) -> list:
    if not provinces_str:
        return []
    out = []
    for part in provinces_str.split(";"):
        parts = part.strip().split()
        if len(parts) >= 5:
            out.append({
                "c1": int(parts[0]), "c2": int(parts[1]),
                "id": int(parts[2]), "money": int(parts[3]), "color": parts[4],
            })
    return out


_HEX_INCOME = {
    "farm": 5, "farm0": 5, "farm1": 5, "farm2": 5,
    "palm": 0, "pine": 0,
}
_PIECE_CONSUMPTION = {
    "peasant": 2, "spearman": 6, "baron": 18, "knight": 36,
    "tower": 1, "strong_tower": 6,
}


def _build_entity_stats(hexes_list: list, entities: list, provinces: list) -> list:
    if not entities:
        return []
    total_hexes = len(hexes_list)
    color_income = {}
    color_hexcount = {}
    for h in hexes_list:
        c = h.get("color")
        if c is None or c == "gray":
            continue
        color_hexcount[c] = color_hexcount.get(c, 0) + 1
        piece = h.get("piece")
        inc = _HEX_INCOME.get(piece, 1) if piece is None or piece not in ("palm", "pine") else 0
        if piece is None:
            inc = 1
        else:
            inc = _HEX_INCOME.get(piece, 1)
        cons = _PIECE_CONSUMPTION.get(piece, 0) if piece else 0
        color_income[c] = color_income.get(c, 0) + inc - cons
    stats = []
    for e in entities:
        color = e["color"]
        n_hexes = color_hexcount.get(color, 0)
        pct = round(100.0 * n_hexes / total_hexes, 1) if total_hexes > 0 else 0.0
        money = sum(p["money"] for p in provinces if p["color"] == color)
        stats.append({
            "type": e["type"], "color": color, "name": e["name"],
            "hex_pct": pct, "money": money, "income": color_income.get(color, 0),
        })
    return stats


def _build_state(hexes_list: list, provinces_str: str, turn_str: str, entities_str: str) -> dict:
    """Build a full state dict from a resolved hex list and raw snapshot strings."""
    ti, lap = _parse_turn(turn_str)
    entities = _parse_entities(entities_str)
    provinces = _parse_provinces(provinces_str)
    entity_stats = _build_entity_stats(hexes_list, entities, provinces)
    return {
        "hexes": hexes_list,
        "turn_index": ti,
        "lap": lap,
        "entities": [{"type": e["type"], "color": e["color"], "name": e["name"]} for e in entities],
        "entity_stats": entity_stats,
    }


def compute_replay_steps(
    initial_level_code: str,
    final_level_code: str,
    state_to_json,
    decoder,
    encoder,
) -> List[dict]:
    """Build replay steps from stored snapshots in the replay file.
    Snapshots may use diff-based hex encoding; this function reconstructs
    full hex state incrementally via a running token map."""
    result_final = decoder.decode(final_level_code)
    final_gs = (result_final[0] if isinstance(result_final, tuple) else result_final)
    if final_gs is None:
        return []

    snapshots = []
    hm = getattr(final_gs, "history_manager", None)
    if hm:
        snapshots = hm.replay_snapshots

    if not snapshots:
        result_init = decoder.decode(initial_level_code)
        init_gs = (result_init[0] if isinstance(result_init, tuple) else result_init)
        steps = []
        if init_gs:
            steps.append({
                "state": state_to_json(init_gs),
                "animation": None, "turn_index": 0, "lap": 0,
            })
        steps.append({
            "state": state_to_json(final_gs),
            "animation": None,
            "turn_index": getattr(final_gs.turns_manager, "turn_index", 0),
            "lap": getattr(final_gs.turns_manager, "lap", 0),
        })
        return steps

    result_init = decoder.decode(initial_level_code)
    init_gs = (result_init[0] if isinstance(result_init, tuple) else result_init)

    steps: List[dict] = []

    # Running hex token map — incrementally updated from diffs
    running_hex_map: dict = {}

    # Step 0: initial state
    if init_gs:
        running_hex_map = _hex_str_to_token_map(init_gs.encode_hexes())
        init_hexes = _tokens_to_hex_list(running_hex_map)
        ti = getattr(init_gs.turns_manager, "turn_index", 0) if init_gs.turns_manager else 0
        lap = getattr(init_gs.turns_manager, "lap", 0) if init_gs.turns_manager else 0
        entities = _parse_entities(snapshots[0].entities) if snapshots else []
        provinces = _parse_provinces(snapshots[0].provinces if snapshots else "")
        entity_stats = _build_entity_stats(init_hexes, entities, provinces)
        steps.append({
            "state": {
                "hexes": init_hexes, "turn_index": ti, "lap": lap,
                "entities": [{"type": e["type"], "color": e["color"], "name": e["name"]} for e in entities],
                "entity_stats": entity_stats,
            },
            "animation": None, "turn_index": ti, "lap": lap,
        })
        prev_anim_map = _hexes_to_map(init_hexes)
    else:
        prev_anim_map = {}

    i = 0
    while i < len(snapshots):
        snap = snapshots[i]
        if _is_system_snapshot(snap):
            running_hex_map = _apply_hex_update(running_hex_map, snap.hexes)
            while i + 1 < len(snapshots) and _is_system_snapshot(snapshots[i + 1]):
                i += 1
                running_hex_map = _apply_hex_update(running_hex_map, snapshots[i].hexes)
            last_sys = snapshots[i]
            hexes_list = _tokens_to_hex_list(running_hex_map)
            state = _build_state(hexes_list, last_sys.provinces, last_sys.turn, last_sys.entities)
            steps.append({
                "state": state, "animation": None,
                "turn_index": state["turn_index"], "lap": state["lap"],
            })
            prev_anim_map = _hexes_to_map(hexes_list)
        else:
            animation = _animation_from_event_encoding(snap.event_encoding, prev_anim_map)
            running_hex_map = _apply_hex_update(running_hex_map, snap.hexes)
            hexes_list = _tokens_to_hex_list(running_hex_map)
            state = _build_state(hexes_list, snap.provinces, snap.turn, snap.entities)
            steps.append({
                "state": state, "animation": animation,
                "turn_index": state["turn_index"], "lap": state["lap"],
            })
            prev_anim_map = _hexes_to_map(hexes_list)
        i += 1

    return steps
