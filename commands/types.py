"""Command type definitions."""

from dataclasses import dataclass
from typing import Optional
from core.enums import PieceType
from core.hex import Hex


@dataclass
class Command:
    """Base command class."""
    command_type: str


@dataclass
class MoveUnitCommand(Command):
    """Command to move a unit from one hex to another."""
    start_hex: Hex
    finish_hex: Hex
    color_transfer_enabled: bool = True
    
    def __init__(self, start_hex: Hex, finish_hex: Hex, color_transfer_enabled: bool = True):
        super().__init__("move_unit")
        self.start_hex = start_hex
        self.finish_hex = finish_hex
        self.color_transfer_enabled = color_transfer_enabled


@dataclass
class BuildPieceCommand(Command):
    """Command to build a piece on a hex."""
    hex: Hex
    piece_type: PieceType
    province_id: int = -1
    province_hex: Optional[Hex] = None  # For units built on gray hexes
    
    def __init__(self, hex: Hex, piece_type: PieceType, province_id: int = -1, province_hex: Optional[Hex] = None):
        super().__init__("build_piece")
        self.hex = hex
        self.piece_type = piece_type
        self.province_id = province_id
        self.province_hex = province_hex


@dataclass
class EndTurnCommand(Command):
    """Command to end the current turn."""
    
    def __init__(self):
        super().__init__("end_turn")


