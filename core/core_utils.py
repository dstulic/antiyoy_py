"""Core utility functions."""

from core.enums import PieceType

_UNIT_TYPES = frozenset({
    PieceType.PEASANT,
    PieceType.SPEARMAN,
    PieceType.BARON,
    PieceType.KNIGHT,
})

_STRENGTH_MAP = {
    PieceType.PEASANT: 1,
    PieceType.SPEARMAN: 2,
    PieceType.BARON: 3,
    PieceType.KNIGHT: 4,
}

_UNIT_BY_STRENGTH = {
    1: PieceType.PEASANT,
    2: PieceType.SPEARMAN,
    3: PieceType.BARON,
    4: PieceType.KNIGHT,
}


def is_unit(piece_type: PieceType | None) -> bool:
    """Check if a piece type is a unit."""
    return piece_type in _UNIT_TYPES


def get_strength(piece_type: PieceType | None) -> int:
    """Get the strength of a unit piece type."""
    if piece_type is None:
        return -1
    return _STRENGTH_MAP.get(piece_type, -1)


def get_unit_by_strength(strength: int) -> PieceType | None:
    """Get unit piece type by strength."""
    return _UNIT_BY_STRENGTH.get(strength)


def get_merge_result(piece1: PieceType, piece2: PieceType) -> PieceType | None:
    """Get the result of merging two unit pieces."""
    strength1 = get_strength(piece1)
    if strength1 == -1:
        return None
    strength2 = get_strength(piece2)
    if strength2 == -1:
        return None
    return get_unit_by_strength(strength1 + strength2)


def can_be_undone(event_type) -> bool:
    """Check if an event type can be undone."""
    from core.enums import EventType
    undoable_types = {
        EventType.UNIT_MOVE,
        EventType.PIECE_BUILD,
        EventType.MERGE,
        EventType.MERGE_ON_BUILD,
        EventType.SEND_LETTER,
        EventType.DECLINE_LETTER,
        EventType.APPLY_LETTER,
    }
    return event_type in undoable_types
