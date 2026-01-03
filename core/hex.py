"""Hex representation for the game board."""

from typing import Optional
from core.enums import HColor, PieceType
from core.core_utils import is_unit


class Hex:
    """Represents a single hexagonal tile on the game board."""

    def __init__(
        self,
        coordinate1: int = 0,
        coordinate2: int = 0,
        color: HColor = HColor.GRAY,
    ):
        """Initialize a hex with coordinates and color."""
        self.coordinate1 = coordinate1
        self.coordinate2 = coordinate2
        self.color = color
        self.piece: Optional[PieceType] = None
        self.unit_id: int = -1
        self.adjacent_hexes: list["Hex"] = []
        self._province = None  # Will be set by ProvinceManager
        self.flag = False  # For algorithms
        self.lg_flag = False  # For algorithms
        self.counter = 0  # For algorithms
        self.fog = False
        self.farm_diversity_index = self._calculate_farm_diversity_index()

    def _calculate_farm_diversity_index(self) -> int:
        """Calculate farm diversity index based on coordinates."""
        return (99999 + 101 * self.coordinate1 * self.coordinate2 + 7 * self.coordinate2) % 3

    def copy_from(self, src: "Hex") -> None:
        """Copy piece, unit_id, and color from another hex."""
        self.piece = src.piece
        self.unit_id = src.unit_id
        self.color = src.color

    def is_linked_to(self, hex: "Hex") -> bool:
        """Check if this hex is linked to another hex."""
        return hex in self.adjacent_hexes

    def is_adjacent_to_hexes_of_same_color(self) -> bool:
        """Check if this hex is adjacent to any hexes of the same color."""
        for adjacent_hex in self.adjacent_hexes:
            if self.color == adjacent_hex.color:
                return True
        return False

    def add_adjacent_hex(self, hex: "Hex") -> None:
        """Add an adjacent hex (bidirectional)."""
        if hex not in self.adjacent_hexes:
            self.adjacent_hexes.append(hex)
        if self not in hex.adjacent_hexes:
            hex.adjacent_hexes.append(self)

    def on_added_to_province(self, province) -> None:
        """Called when hex is added to a province."""
        self._province = province

    def on_removed_from_province(self, province) -> None:
        """Called when hex is removed from a province."""
        if self._province != province:
            return  # Removed from one of previous provinces
        if self._province is None:
            # Suspicious - should not happen
            pass
        self._province = None

    def on_province_invalidated(self, province) -> None:
        """Called when a province is invalidated."""
        if self._province != province:
            return  # One of previous owners invalidated
        if self._province is None:
            # Suspicious - should not happen
            pass
        self._province = None

    def has_piece(self) -> bool:
        """Check if hex has a piece."""
        return self.piece is not None

    def is_empty(self) -> bool:
        """Check if hex is empty (no piece)."""
        return self.piece is None

    def has_unit(self) -> bool:
        """Check if hex has a unit piece."""
        return self.has_piece() and is_unit(self.piece)

    def has_tree(self) -> bool:
        """Check if hex has a tree (palm or pine)."""
        return self.piece in (PieceType.PINE, PieceType.PALM)

    def has_tower(self) -> bool:
        """Check if hex has a tower (tower or strong_tower)."""
        return self.piece in (PieceType.TOWER, PieceType.STRONG_TOWER)

    def has_static_piece(self) -> bool:
        """Check if hex has a static (non-unit) piece."""
        return self.has_piece() and not is_unit(self.piece)

    def has_same_coordinates_as(self, hex: "Hex") -> bool:
        """Check if this hex has the same coordinates as another hex."""
        return self.coordinate1 == hex.coordinate1 and self.coordinate2 == hex.coordinate2

    def set_piece(self, piece_type: Optional[PieceType]) -> None:
        """Set the piece type on this hex."""
        self.piece = piece_type

    def set_unit_id(self, unit_id: int) -> None:
        """Set the unit ID on this hex."""
        self.unit_id = unit_id

    def has_coordinates(self, c1: int, c2: int) -> bool:
        """Check if hex has specific coordinates."""
        return self.coordinate1 == c1 and self.coordinate2 == c2

    def set_color(self, h_color: HColor) -> None:
        """Set the color of this hex."""
        if self.color != h_color:
            self.color = h_color

    def get_color(self) -> HColor:
        """Get the color of this hex."""
        return self.color

    def get_province(self):
        """Get the province this hex belongs to."""
        return self._province

    def is_colored(self) -> bool:
        """Check if hex is colored (not gray/neutral)."""
        return self.color != HColor.GRAY

    def is_neutral(self) -> bool:
        """Check if hex is neutral (gray)."""
        return self.color == HColor.GRAY

    def encode(self) -> str:
        """Encode hex to string format for save/load."""
        necessary_part = f"{self.coordinate1} {self.coordinate2} {self.color.value}"
        piece_part = ""
        if self.piece is not None:
            piece_part = f" {self.piece.value} {self.unit_id}"
        return necessary_part + piece_part

    def __str__(self) -> str:
        """Return string representation."""
        return f"[{self.encode()}]"

    def __repr__(self) -> str:
        """Return detailed representation."""
        return (
            f"Hex(c1={self.coordinate1}, c2={self.coordinate2}, "
            f"color={self.color.value}, piece={self.piece}, unit_id={self.unit_id})"
        )
