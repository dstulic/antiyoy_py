"""Command validator for checking command validity."""

from typing import Optional
from commands.types import (
    Command,
    MoveUnitCommand,
    BuildPieceCommand,
    EndTurnCommand,
    SetRelationCommand,
    SendLetterCommand,
    ApplyLetterCommand,
    DeclineLetterCommand,
    GiveMoneyCommand,
)
from core.game_state import GameState
from core.enums import HColor, PieceType
from core.core_utils import is_unit


class CommandValidator:
    """Validates commands before execution."""

    def __init__(self, game_state: GameState):
        """
        Initialize validator.
        
        Args:
            game_state: The game state to validate against
        """
        self.game_state = game_state

    def validate(self, command: Command, player_color: HColor) -> tuple[bool, Optional[str]]:
        """
        Validate a command.
        
        Args:
            command: The command to validate
            player_color: The color of the player submitting the command
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if it's the player's turn (except for end_turn which can be checked separately)
        if command.command_type != "end_turn":
            if not self._is_player_turn(player_color):
                return False, "Not your turn"
        
        # Validate based on command type
        if isinstance(command, MoveUnitCommand):
            return self._validate_move_unit(command, player_color)
        elif isinstance(command, BuildPieceCommand):
            return self._validate_build_piece(command, player_color)
        elif isinstance(command, EndTurnCommand):
            return self._validate_end_turn(player_color)
        elif isinstance(command, SetRelationCommand):
            return self._validate_set_relation(command, player_color)
        elif isinstance(command, SendLetterCommand):
            return self._validate_send_letter(command, player_color)
        elif isinstance(command, ApplyLetterCommand):
            return self._validate_apply_letter(command, player_color)
        elif isinstance(command, DeclineLetterCommand):
            return self._validate_decline_letter(command, player_color)
        elif isinstance(command, GiveMoneyCommand):
            return self._validate_give_money(command, player_color)
        else:
            return False, f"Unknown command type: {command.command_type}"

    def _is_player_turn(self, player_color: HColor) -> bool:
        """Check if it's the player's turn."""
        if not self.game_state or not self.game_state.entities_manager:
            return False
        current_color = self.game_state.entities_manager.get_current_color()
        return current_color == player_color

    def _validate_move_unit(self, command: MoveUnitCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Validate move unit command."""
        if not command.start_hex or not command.finish_hex:
            return False, "Start and finish hexes required"
        
        # Check start hex has a unit
        if not command.start_hex.has_unit():
            return False, "Start hex does not have a unit"
        
        # Check unit belongs to player
        if command.start_hex.color != player_color:
            return False, "Unit does not belong to player"
        
        # Check finish hex is adjacent
        if not command.start_hex.is_linked_to(command.finish_hex):
            return False, "Finish hex is not adjacent to start hex"
        
        # Check finish hex is empty or has enemy unit
        if command.finish_hex.has_unit() and command.finish_hex.color == player_color:
            return False, "Cannot move to hex with friendly unit"
        
        return True, None

    def _validate_build_piece(self, command: BuildPieceCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Validate build piece command."""
        if not command.hex:
            return False, "Hex required"
        
        # Check hex belongs to player
        if command.hex.color != player_color:
            return False, "Hex does not belong to player"
        
        # Check hex is empty
        if command.hex.has_piece():
            return False, "Hex already has a piece"
        
        # Check ruleset allows building
        if not self.game_state.ruleset:
            return False, "No ruleset defined"
        
        # Check if piece can be built on this hex
        if not self.game_state.ruleset.is_buildable(command.hex, command.piece_type):
            return False, f"Cannot build {command.piece_type.value} on this hex"
        
        # Check if player has enough money
        province = self.game_state.provinces_manager.find_province_slowly(command.hex)
        if not province:
            return False, "Hex is not in a province"
        
        price = self.game_state.ruleset.get_price(command.piece_type)
        if province.get_money() < price:
            return False, f"Not enough money (need {price}, have {province.get_money()})"
        
        return True, None

    def _validate_end_turn(self, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Validate end turn command."""
        if not self._is_player_turn(player_color):
            return False, "Not your turn"
        return True, None

    def _validate_set_relation(self, command: SetRelationCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Validate set relation command."""
        # Placeholder - would need diplomacy manager
        return True, None

    def _validate_send_letter(self, command: SendLetterCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Validate send letter command."""
        # Placeholder - would need letters manager
        return True, None

    def _validate_apply_letter(self, command: ApplyLetterCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Validate apply letter command."""
        # Placeholder - would need letters manager
        return True, None

    def _validate_decline_letter(self, command: DeclineLetterCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Validate decline letter command."""
        # Placeholder - would need letters manager
        return True, None

    def _validate_give_money(self, command: GiveMoneyCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Validate give money command."""
        # Placeholder - would need diplomacy manager
        return True, None
