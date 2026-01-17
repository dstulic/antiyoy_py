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
        # Check if game has ended - no more turns allowed
        if hasattr(self.game_state, 'game_end_manager') and self.game_state.game_end_manager:
            if not self.game_state.game_end_manager.can_make_turn():
                return False, "Game has ended"
        
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
        
        # Check if unit is ready to move
        if not self.game_state.readiness_manager.is_ready(command.start_hex):
            return False, "Unit has already moved this turn"
        
        # Use MoveZoneManager to check if finish hex is reachable (up to 4 hexes away)
        # Ensure adjacency is built
        if not command.start_hex.adjacent_hexes:
            from save_load.decoder import _build_adjacency_graph
            _build_adjacency_graph(self.game_state)
        
        # Update move zone for the unit
        self.game_state.move_zone_manager.update_for_unit(command.start_hex)
        
        # Check if finish hex is in the move zone
        if not self.game_state.move_zone_manager.contains(command.finish_hex):
            return False, "Finish hex is not reachable (outside movement range)"
        
        # Check finish hex is empty, has enemy unit, or has friendly unit (for merging)
        if command.finish_hex.has_unit() and command.finish_hex.color == player_color:
            # Check if both hexes are in the same province (required for merging)
            if command.start_hex.get_province() != command.finish_hex.get_province():
                return False, "Cannot move to hex with friendly unit in different province"
            # Check if merge result is valid
            from core.core_utils import get_merge_result
            if get_merge_result(command.start_hex.piece, command.finish_hex.piece) is None:
                return False, "Cannot merge these units"
        
        return True, None

    def _validate_build_piece(self, command: BuildPieceCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Validate build piece command."""
        if not command.hex:
            return False, "Hex required"
        
        if not self.game_state.ruleset:
            return False, "No ruleset defined"
        
        # Get province - for units, use province from province_hex if provided (for gray hexes)
        # For static pieces, get province from the target hex
        from core.core_utils import is_unit
        province = None
        
        if is_unit(command.piece_type) and command.province_hex:
            # For units: get province from the selected province hex (allows building on gray hexes)
            province = command.province_hex.get_province()
        
        # If province not found yet, try to get it from target hex
        if not province:
            province = command.hex.get_province()
            if not province:
                province = self.game_state.provinces_manager.find_province_slowly(command.hex)
        
        if not province:
            return False, "Province not found"
        
        # Check if province belongs to current player
        if province.get_color() != player_color:
            return False, "Province does not belong to current player"
        
        # For static pieces, check that hex belongs to the province
        # For units, hex can be gray (neutral) - it will be colored when unit is built
        if not is_unit(command.piece_type):
            if command.hex.color != province.get_color():
                return False, "Hex does not belong to province"
        
        # Check if piece type is buildable
        if not self.game_state.ruleset.is_buildable(command.piece_type):
            return False, f"Piece type {command.piece_type.value} is not buildable"
        
        # Check if province can afford it
        price = self.game_state.ruleset.get_price(province, command.piece_type)
        if province.get_money() < price:
            return False, f"Not enough money. Need {price}, have {province.get_money()}"
        
        # Check if hex is empty (for static pieces) or can accept unit
        if is_unit(command.piece_type):
            # For units: use MoveZoneManager to check if hex is reachable (up to 4 hexes away)
            # This matches the Java implementation: updateMoveZoneForUnitConstruction + contains check
            from core.core_utils import get_strength
            strength = get_strength(command.piece_type)
            province_hexes = province.get_hexes()
            
            # Ensure adjacency is built
            if not province_hexes[0].adjacent_hexes:
                from save_load.decoder import _build_adjacency_graph
                _build_adjacency_graph(self.game_state)
            
            # Check if hex is reachable from any province hex using MoveZoneManager
            hex_reachable = False
            for p_hex in province_hexes:
                self.game_state.move_zone_manager.update(p_hex, limit=4, strength=strength)
                if self.game_state.move_zone_manager.contains(command.hex):
                    hex_reachable = True
                    break
            
            if not hex_reachable:
                return False, "Hex is not reachable for unit construction (outside movement range)"
            
            # For units, check if hex can accept the unit
            # MoveZoneManager already checked if enemy hexes can be captured, so if it's in the zone, it's valid
            # But we still need to check some edge cases:
            if command.hex.has_piece():
                if command.hex.piece not in (PieceType.PINE, PieceType.PALM, PieceType.GRAVE):
                    # Check if it's a mergeable unit (same color, same province)
                    if command.hex.has_unit() and command.hex.color == province.get_color():
                        # Check if merge result is valid
                        from core.core_utils import get_merge_result
                        if get_merge_result(command.piece_type, command.hex.piece) is None:
                            return False, "Cannot merge these units"
                    # For enemy units or static pieces: MoveZoneManager already validated they can be captured
                    # For friendly static pieces (city/tower): cannot build units on them (except trees/graves)
                    elif command.hex.color == province.get_color() and command.hex.has_static_piece():
                        return False, "Cannot build unit on friendly static piece (city/tower)"
        else:
            # For static pieces (towers, farms), hex must be empty
            # Exception: strong_tower can be built on tower
            if command.piece_type == PieceType.STRONG_TOWER:
                if command.hex.piece != PieceType.TOWER:
                    return False, "Strong tower can only be built on existing tower"
            else:
                if not command.hex.is_empty():
                    return False, "Hex must be empty to build this piece"
        
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
