"""Action space encoding, decoding, and masking for the Gymnasium environment.

Layout for a map with N hexes (B = 7 buildable piece types):
    Index 0           : EndTurn
    Indices 1 .. N*N  : MoveUnit  (i -> src=(i-1)//N, dst=(i-1)%N in game_state.hexes)
    Indices N*N+1 .. N*N+N*B : BuildPiece (j -> hex=(j-N*N-1)//B, piece_idx=(j-N*N-1)%B)
"""

from typing import Optional, List

import numpy as np

from core.game_state import GameState
from core.enums import HColor, PieceType
from core.hex import Hex
from core.core_utils import is_unit
from commands.types import (
    Command,
    MoveUnitCommand,
    BuildPieceCommand,
    EndTurnCommand,
)

BUILDABLE_PIECES: List[PieceType] = [
    PieceType.PEASANT,
    PieceType.SPEARMAN,
    PieceType.BARON,
    PieceType.KNIGHT,
    PieceType.TOWER,
    PieceType.STRONG_TOWER,
    PieceType.FARM,
]
NUM_BUILDABLE = len(BUILDABLE_PIECES)


class ActionMapper:
    """Maps between flat discrete action indices and game Commands."""

    def __init__(self, n_hexes: int):
        self.n_hexes = n_hexes
        self.action_space_size = 1 + n_hexes * n_hexes + n_hexes * NUM_BUILDABLE

    # ------------------------------------------------------------------
    # Index arithmetic
    # ------------------------------------------------------------------

    def _move_index(self, src_idx: int, dst_idx: int) -> int:
        return 1 + src_idx * self.n_hexes + dst_idx

    def _build_index(self, hex_idx: int, piece_idx: int) -> int:
        return 1 + self.n_hexes * self.n_hexes + hex_idx * NUM_BUILDABLE + piece_idx

    def _decode_move(self, action: int) -> tuple[int, int]:
        """Return (src_hex_idx, dst_hex_idx)."""
        offset = action - 1
        return offset // self.n_hexes, offset % self.n_hexes

    def _decode_build(self, action: int) -> tuple[int, int]:
        """Return (hex_idx, piece_list_idx)."""
        offset = action - 1 - self.n_hexes * self.n_hexes
        return offset // NUM_BUILDABLE, offset % NUM_BUILDABLE

    # ------------------------------------------------------------------
    # Action -> Command
    # ------------------------------------------------------------------

    def action_to_command(
        self, action: int, game_state: GameState
    ) -> Optional[Command]:
        """Convert an action index into a Command object, or None if invalid."""
        hexes = game_state.hexes

        if action == 0:
            return EndTurnCommand()

        move_end = 1 + self.n_hexes * self.n_hexes
        if 1 <= action < move_end:
            src_idx, dst_idx = self._decode_move(action)
            if src_idx >= len(hexes) or dst_idx >= len(hexes):
                return None
            return MoveUnitCommand(
                start_hex=hexes[src_idx],
                finish_hex=hexes[dst_idx],
                color_transfer_enabled=True,
            )

        build_end = move_end + self.n_hexes * NUM_BUILDABLE
        if move_end <= action < build_end:
            hex_idx, piece_idx = self._decode_build(action)
            if hex_idx >= len(hexes):
                return None
            target_hex = hexes[hex_idx]
            piece_type = BUILDABLE_PIECES[piece_idx]

            province, province_hex = _resolve_province_for_build(
                game_state, target_hex, piece_type
            )
            if province is None:
                return None

            return BuildPieceCommand(
                hex=target_hex,
                piece_type=piece_type,
                province_id=province.get_id(),
                province_hex=province_hex,
            )

        return None

    # ------------------------------------------------------------------
    # Action mask
    # ------------------------------------------------------------------

    def get_action_mask(
        self, game_state: GameState, agent_color: HColor
    ) -> np.ndarray:
        """Return a boolean mask (True = valid) over the full action space."""
        mask = np.zeros(self.action_space_size, dtype=bool)
        mask[0] = True  # EndTurn is always valid as a safe fallback
        hexes = game_state.hexes

        current_color = game_state.entities_manager.get_current_color()
        if current_color != agent_color:
            return mask

        if game_state.game_end_manager.is_game_ended():
            return mask

        hex_index = {id(h): i for i, h in enumerate(hexes)}

        # --- Move actions ---
        ready_hexes = game_state.readiness_manager.ready_hexes
        for src_hex in ready_hexes:
            if src_hex.color != agent_color:
                continue
            src_idx = hex_index.get(id(src_hex))
            if src_idx is None:
                continue
            game_state.move_zone_manager.update_for_unit(src_hex)
            for dst_hex in game_state.move_zone_manager.hexes:
                if dst_hex is src_hex:
                    continue
                dst_idx = hex_index.get(id(dst_hex))
                if dst_idx is None:
                    continue
                mask[self._move_index(src_idx, dst_idx)] = True

        # --- Build actions ---
        agent_provinces = [
            p
            for p in game_state.provinces_manager.provinces
            if p.get_color() == agent_color
        ]
        ruleset = game_state.ruleset
        if ruleset is None:
            return mask

        for province in agent_provinces:
            money = province.get_money()
            province_hexes = province.get_hexes()

            for piece_idx, piece_type in enumerate(BUILDABLE_PIECES):
                if not ruleset.is_buildable(piece_type):
                    continue
                price = ruleset.get_price(province, piece_type)
                if money < price:
                    continue

                if is_unit(piece_type):
                    _mask_unit_builds(
                        mask,
                        game_state,
                        province,
                        province_hexes,
                        piece_type,
                        piece_idx,
                        hex_index,
                        self,
                    )
                else:
                    _mask_static_builds(
                        mask,
                        province_hexes,
                        piece_type,
                        piece_idx,
                        hex_index,
                        self,
                        province,
                    )

        return mask


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _resolve_province_for_build(
    game_state: GameState,
    target_hex: Hex,
    piece_type: PieceType,
) -> tuple:
    """Return (province, province_hex) for a build action, or (None, None)."""
    current_color = game_state.entities_manager.get_current_color()
    if current_color is None:
        return None, None

    # Try direct province from target hex
    province = target_hex.get_province()
    if province and province.get_color() == current_color:
        return province, target_hex

    # For units on gray / enemy hexes, find adjacent province
    if is_unit(piece_type):
        for adj in target_hex.adjacent_hexes:
            p = adj.get_province()
            if p and p.get_color() == current_color:
                return p, adj

    # Fallback: slow lookup
    province = game_state.provinces_manager.find_province_slowly(target_hex)
    if province and province.get_color() == current_color:
        return province, province.get_first_hex()
    return None, None


def _mask_unit_builds(
    mask: np.ndarray,
    game_state: GameState,
    province,
    province_hexes: list,
    piece_type: PieceType,
    piece_idx: int,
    hex_index: dict,
    mapper: ActionMapper,
) -> None:
    """Enable mask entries for valid unit build locations."""
    from core.core_utils import get_strength, get_merge_result

    strength = get_strength(piece_type)
    reachable: set = set()

    for p_hex in province_hexes:
        game_state.move_zone_manager.update(p_hex, limit=4, strength=strength)
        for h in game_state.move_zone_manager.hexes:
            reachable.add(id(h))

    agent_color = province.get_color()
    for h in game_state.hexes:
        if id(h) not in reachable:
            continue
        h_idx = hex_index.get(id(h))
        if h_idx is None:
            continue

        if h.has_piece():
            if h.piece in (PieceType.PINE, PieceType.PALM, PieceType.GRAVE):
                mask[mapper._build_index(h_idx, piece_idx)] = True
            elif h.has_unit() and h.color == agent_color:
                if get_merge_result(piece_type, h.piece) is not None:
                    mask[mapper._build_index(h_idx, piece_idx)] = True
            # Friendly static pieces (city/tower/farm) can't have units built on them
            # Enemy pieces are handled by move zone (captured on placement)
            elif h.color != agent_color:
                mask[mapper._build_index(h_idx, piece_idx)] = True
        else:
            mask[mapper._build_index(h_idx, piece_idx)] = True


def _is_adjacent_to_farm_or_city(hex_obj, province) -> bool:
    """True if *hex_obj* has at least one adjacent hex in *province* with a CITY or FARM."""
    for adj in hex_obj.adjacent_hexes:
        if adj.get_province() is not province:
            continue
        if adj.piece in (PieceType.CITY, PieceType.FARM):
            return True
    return False


def _mask_static_builds(
    mask: np.ndarray,
    province_hexes: list,
    piece_type: PieceType,
    piece_idx: int,
    hex_index: dict,
    mapper: ActionMapper,
    province=None,
) -> None:
    """Enable mask entries for valid static piece build locations."""
    for h in province_hexes:
        h_idx = hex_index.get(id(h))
        if h_idx is None:
            continue

        if piece_type == PieceType.STRONG_TOWER:
            if h.is_empty() or h.piece == PieceType.TOWER:
                mask[mapper._build_index(h_idx, piece_idx)] = True
        elif piece_type == PieceType.FARM:
            if h.is_empty() and _is_adjacent_to_farm_or_city(h, province):
                mask[mapper._build_index(h_idx, piece_idx)] = True
        else:
            if h.is_empty():
                mask[mapper._build_index(h_idx, piece_idx)] = True
