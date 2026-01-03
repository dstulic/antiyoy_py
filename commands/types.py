"""Command type definitions."""

from dataclasses import dataclass
from typing import Optional
from core.enums import PieceType, RelationType
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
    
    def __init__(self, hex: Hex, piece_type: PieceType, province_id: int = -1):
        super().__init__("build_piece")
        self.hex = hex
        self.piece_type = piece_type
        self.province_id = province_id


@dataclass
class EndTurnCommand(Command):
    """Command to end the current turn."""
    
    def __init__(self):
        super().__init__("end_turn")


@dataclass
class SetRelationCommand(Command):
    """Command to set diplomatic relation."""
    target_color: str  # HColor value as string
    relation_type: RelationType
    
    def __init__(self, target_color: str, relation_type: RelationType):
        super().__init__("set_relation")
        self.target_color = target_color
        self.relation_type = relation_type


@dataclass
class SendLetterCommand(Command):
    """Command to send a diplomatic letter."""
    target_color: str  # HColor value as string
    letter_type: str
    
    def __init__(self, target_color: str, letter_type: str):
        super().__init__("send_letter")
        self.target_color = target_color
        self.letter_type = letter_type


@dataclass
class ApplyLetterCommand(Command):
    """Command to apply a received letter."""
    letter_id: int
    
    def __init__(self, letter_id: int):
        super().__init__("apply_letter")
        self.letter_id = letter_id


@dataclass
class DeclineLetterCommand(Command):
    """Command to decline a received letter."""
    letter_id: int
    
    def __init__(self, letter_id: int):
        super().__init__("decline_letter")
        self.letter_id = letter_id


@dataclass
class GiveMoneyCommand(Command):
    """Command to give money to another player."""
    target_color: str  # HColor value as string
    amount: int
    
    def __init__(self, target_color: str, amount: int):
        super().__init__("give_money")
        self.target_color = target_color
        self.amount = amount
