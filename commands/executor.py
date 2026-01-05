"""Command executor for executing validated commands."""

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
from commands.validator import CommandValidator
from core.game_state import GameState
from core.enums import HColor, EventType, RelationType
from core.events import EventType as EvtType


class CommandExecutor:
    """Executes validated commands."""

    def __init__(self, game_state: GameState):
        """
        Initialize executor.
        
        Args:
            game_state: The game state to execute commands on
        """
        self.game_state = game_state
        self.validator = CommandValidator(game_state)

    def execute(self, command: Command, player_color: HColor) -> tuple[bool, Optional[str]]:
        """
        Execute a command.
        
        Args:
            command: The command to execute
            player_color: The color of the player submitting the command
            
        Returns:
            Tuple of (success, error_message)
        """
        # Validate first
        is_valid, error = self.validator.validate(command, player_color)
        if not is_valid:
            return False, error
        
        # Execute based on command type
        try:
            if isinstance(command, MoveUnitCommand):
                return self._execute_move_unit(command)
            elif isinstance(command, BuildPieceCommand):
                return self._execute_build_piece(command)
            elif isinstance(command, EndTurnCommand):
                return self._execute_end_turn()
            elif isinstance(command, SetRelationCommand):
                return self._execute_set_relation(command, player_color)
            elif isinstance(command, SendLetterCommand):
                return self._execute_send_letter(command, player_color)
            elif isinstance(command, ApplyLetterCommand):
                return self._execute_apply_letter(command, player_color)
            elif isinstance(command, DeclineLetterCommand):
                return self._execute_decline_letter(command, player_color)
            elif isinstance(command, GiveMoneyCommand):
                return self._execute_give_money(command, player_color)
            else:
                return False, f"Unknown command type: {command.command_type}"
        except Exception as e:
            return False, f"Error executing command: {str(e)}"

    def _execute_move_unit(self, command: MoveUnitCommand) -> tuple[bool, Optional[str]]:
        """Execute move unit command."""
        events_factory = self.game_state.events_manager.factory
        event = events_factory.create_event(EventType.UNIT_MOVE)
        
        if event:
            from core.events import EventUnitMove
            if isinstance(event, EventUnitMove):
                event.set_start(command.start_hex)
                event.set_finish(command.finish_hex)
                event.color_transfer_enabled = command.color_transfer_enabled
                self.game_state.events_manager.apply_event(event)
                return True, None
        
        return False, "Failed to create move event"

    def _execute_build_piece(self, command: BuildPieceCommand) -> tuple[bool, Optional[str]]:
        """Execute build piece command."""
        from core.core_utils import is_unit
        
        # Get province - for units, use province from province_hex if provided (for gray hexes)
        # For static pieces, get province from the target hex
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
        
        # Get current entity for author
        current_entity = self.game_state.entities_manager.get_current_entity()
        if not current_entity:
            return False, "No current player"
        
        # Create build event
        events_factory = self.game_state.events_manager.factory
        event = events_factory.create_event(EventType.PIECE_BUILD)
        if not event:
            return False, "Failed to create build event"
        
        from core.events import EventPieceBuild
        if isinstance(event, EventPieceBuild):
            event.set_hex(command.hex)
            event.set_piece_type(command.piece_type)
            event.set_province_id(province.get_id())
            
            # For units, generate a new unit ID
            if is_unit(command.piece_type):
                event.set_unit_id(self.game_state.get_id_for_new_unit())
            else:
                event.unit_id = -1
            
            # Set author
            event.set_author(current_entity)
            
            # Validate event
            if not event.is_valid():
                return False, "Build event is not valid"
            
            # Apply event
            try:
                self.game_state.events_manager.apply_event(event)
                
                # Update fog of war if enabled
                if (self.game_state.fog_of_war_manager and 
                    self.game_state.fog_of_war_manager.enabled):
                    self.game_state.fog_of_war_manager.apply_update()
                
                return True, None
            except Exception as e:
                return False, f"Failed to apply build event: {str(e)}"
        
        return False, "Unexpected event type"

    def _execute_end_turn(self) -> tuple[bool, Optional[str]]:
        """Execute end turn command."""
        events_factory = self.game_state.events_manager.factory
        event = events_factory.create_event(EventType.TURN_END)
        
        if event:
            self.game_state.events_manager.apply_event(event)
            return True, None
        
        return False, "Failed to create turn end event"

    def _execute_set_relation(self, command: SetRelationCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Execute set relation command."""
        # Placeholder - would need diplomacy manager
        return True, None

    def _execute_send_letter(self, command: SendLetterCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Execute send letter command."""
        # Placeholder - would need letters manager
        return True, None

    def _execute_apply_letter(self, command: ApplyLetterCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Execute apply letter command."""
        # Placeholder - would need letters manager
        return True, None

    def _execute_decline_letter(self, command: DeclineLetterCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Execute decline letter command."""
        # Placeholder - would need letters manager
        return True, None

    def _execute_give_money(self, command: GiveMoneyCommand, player_color: HColor) -> tuple[bool, Optional[str]]:
        """Execute give money command."""
        # Placeholder - would need diplomacy manager
        return True, None
