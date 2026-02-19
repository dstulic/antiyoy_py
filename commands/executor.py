"""Command executor for executing validated commands."""

from typing import Optional
from commands.types import (
    Command,
    MoveUnitCommand,
    BuildPieceCommand,
    EndTurnCommand,
)
from commands.validator import CommandValidator
from core.game_state import GameState
from core.enums import HColor, EventType
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
            else:
                return False, f"Unknown command type: {command.command_type}"
        except Exception as e:
            return False, f"Error executing command: {str(e)}"

    def _execute_move_unit(self, command: MoveUnitCommand) -> tuple[bool, Optional[str]]:
        """Execute move unit command."""
        from core.core_utils import get_merge_result
        
        # Check if this is a merge (moving a unit onto another unit of same color in same province)
        if (command.finish_hex.has_unit() and 
            command.start_hex.color == command.finish_hex.color and
            command.start_hex.get_province() == command.finish_hex.get_province()):
            # Check if merge result is valid
            merge_result = get_merge_result(command.start_hex.piece, command.finish_hex.piece)
            if merge_result is not None:
                current_entity = self.game_state.entities_manager.get_current_entity()
                if not current_entity:
                    return False, "No current player"
                events_factory = self.game_state.events_manager.factory
                event = events_factory.create_event(EventType.MERGE, author=current_entity)
                if not event:
                    return False, "Failed to create merge event"
                
                from core.events import EventMerge
                if isinstance(event, EventMerge):
                    event.set_start(command.start_hex)
                    event.set_finish(command.finish_hex)
                    event.set_unit_id(self.game_state.get_id_for_new_unit())
                    
                    # Validate event
                    if not event.is_valid():
                        return False, "Merge event is not valid"
                    
                    # Apply event
                    try:
                        self.game_state.events_manager.apply_event(event)
                        
                        # Update fog of war if enabled
                        if (self.game_state.fog_of_war_manager and 
                            self.game_state.fog_of_war_manager.enabled):
                            self.game_state.fog_of_war_manager.apply_update()
                        
                        return True, None
                    except Exception as e:
                        return False, f"Failed to apply merge event: {str(e)}"
        
        # Regular move event
        current_entity = self.game_state.entities_manager.get_current_entity()
        if not current_entity:
            return False, "No current player"
        events_factory = self.game_state.events_manager.factory
        event = events_factory.create_event(EventType.UNIT_MOVE, author=current_entity)
        
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
        from core.core_utils import is_unit, get_merge_result
        
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
        
        # Check if this is a merge on build (building a unit on an existing unit of same color)
        if is_unit(command.piece_type) and command.hex.has_unit() and command.hex.color == province.get_color():
            # Check if merge result is valid
            merge_result = get_merge_result(command.piece_type, command.hex.piece)
            if merge_result is not None:
                events_factory = self.game_state.events_manager.factory
                event = events_factory.create_event(EventType.MERGE_ON_BUILD, author=current_entity)
                if not event:
                    return False, "Failed to create merge on build event"
                
                from core.events import EventMergeOnBuild
                if isinstance(event, EventMergeOnBuild):
                    event.set_hex(command.hex)
                    event.set_piece_type(command.piece_type)
                    event.set_province_id(province.get_id())
                    event.set_unit_id(self.game_state.get_id_for_new_unit())
                    
                    # Validate event
                    if not event.is_valid():
                        return False, "Merge on build event is not valid"
                    
                    # Apply event
                    try:
                        self.game_state.events_manager.apply_event(event)
                        
                        # Update fog of war if enabled
                        if (self.game_state.fog_of_war_manager and 
                            self.game_state.fog_of_war_manager.enabled):
                            self.game_state.fog_of_war_manager.apply_update()
                        
                        return True, None
                    except Exception as e:
                        return False, f"Failed to apply merge on build event: {str(e)}"
        
        # Regular build event
        events_factory = self.game_state.events_manager.factory
        event = events_factory.create_event(EventType.PIECE_BUILD, author=current_entity)
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
