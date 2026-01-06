"""Undo manager for game state."""

from typing import Optional, List
from core.events import IEventListener, AbstractEvent
from save_load.encoder import GameStateEncoder
from save_load.decoder import GameStateDecoder


class UndoItem:
    """Represents a single undo item (snapshot of game state)."""
    
    def __init__(self, level_code: str, event: AbstractEvent):
        """Initialize undo item."""
        self.level_code = level_code
        self.event = event
        self.hook_hex_coords = None  # Store selected province hex for restoration
    
    def reset(self):
        """Reset undo item."""
        self.level_code = ""
        self.event = None
        self.hook_hex_coords = None


class UndoManager(IEventListener):
    """Manages undo functionality for game state."""
    
    def __init__(self, game_state):
        """Initialize undo manager."""
        self.game_state = game_state
        self.items: List[UndoItem] = []
        self.encoder = GameStateEncoder()
        self.decoder = GameStateDecoder()
        
        # Register as event listener
        game_state.events_manager.add_listener(self)
    
    def get_listen_priority(self) -> int:
        """Get listener priority (lower = higher priority)."""
        return 5
    
    def on_event_validated(self, event: AbstractEvent) -> None:
        """Called when event is validated - store snapshot before applying."""
        # Only store snapshots for notable, undoable events
        if not event.is_notable():
            return
        if not event.can_be_undone():
            return
        
        # Don't store snapshots for turn_end events (they clear the undo list)
        if event.get_type().value == "turn_end":
            return
        
        # Store snapshot of current game state
        try:
            level_code = self.encoder.encode(self.game_state)
            
            # Store selected province hex if available
            hook_hex_coords = None
            # Note: We don't have a selected province system yet, so this is a placeholder
            
            undo_item = UndoItem(level_code, event)
            undo_item.hook_hex_coords = hook_hex_coords
            self.items.append(undo_item)
        except Exception as e:
            print(f"Error creating undo snapshot: {e}")
    
    def on_event_applied(self, event: AbstractEvent) -> None:
        """Called when event is applied."""
        # Clear undo list on turn_end
        if event.get_type().value == "turn_end":
            self.items.clear()
    
    def can_undo(self) -> bool:
        """Check if undo is possible."""
        return len(self.items) > 0
    
    def undo(self) -> bool:
        """
        Undo the last action.
        
        Returns:
            True if undo was successful, False otherwise.
        """
        if not self.can_undo():
            return False
        
        # Get last undo item
        undo_item = self.items.pop()
        
        # Decode the previous game state
        try:
            # Decode the level code to restore game state
            restored_state, _ = self.decoder.decode(undo_item.level_code)
            
            if restored_state is None:
                print("Error: Failed to decode undo snapshot")
                return False
            
            # Copy the restored state into the current game state
            # We need to copy all the important data
            self._restore_game_state(restored_state)
            
            # Notify game state that undo was applied
            if hasattr(self.game_state, "on_undo_applied"):
                self.game_state.on_undo_applied(undo_item)
            
            return True
        except Exception as e:
            print(f"Error during undo: {e}")
            return False
    
    def _restore_game_state(self, restored_state) -> None:
        """Restore game state from a restored state."""
        # Create a coordinate map for quick lookup
        current_hex_map = {}
        for hex in self.game_state.hexes:
            current_hex_map[(hex.coordinate1, hex.coordinate2)] = hex
        
        # Copy hex data (color, piece, unit_id) from restored state to current state
        # This preserves the hex objects and their adjacency relationships
        for restored_hex in restored_state.hexes:
            coord_key = (restored_hex.coordinate1, restored_hex.coordinate2)
            if coord_key in current_hex_map:
                current_hex = current_hex_map[coord_key]
                # Copy data from restored hex
                current_hex.copy_from(restored_hex)
        
        # Copy current unit ID
        self.game_state.current_unit_id = restored_state.current_unit_id
        
        # Restore provinces
        # First, rebuild provinces from hex colors
        self.game_state.provinces_manager.builder.grant_permission()
        self.game_state.provinces_manager.builder.apply()
        
        # Then restore province data (money, city names, IDs)
        # We need to match provinces by their hexes
        for restored_province in restored_state.provinces_manager.provinces:
            # Find matching province in current state
            if not restored_province.get_hexes():
                continue
            
            # Use first hex to find matching province
            first_hex = restored_province.get_hexes()[0]
            current_hex = self.game_state.get_hex(first_hex.coordinate1, first_hex.coordinate2)
            if current_hex:
                current_province = current_hex.get_province()
                if current_province:
                    # Restore province data
                    current_province.set_money(restored_province.get_money())
                    current_province.set_city_name(restored_province.get_city_name())
                    # Note: Province IDs are managed internally, so we don't restore them
        
        # Restore entities
        # Note: Entities have references to entities_manager, but we'll update those
        self.game_state.entities_manager.entities = []
        for restored_entity in restored_state.entities_manager.entities:
            # Create new entity with same data but linked to current entities_manager
            from core.player_entity import PlayerEntity
            from core.enums import EntityType
            new_entity = PlayerEntity(
                self.game_state.entities_manager,
                restored_entity.type,
                restored_entity.color
            )
            new_entity.set_name(restored_entity.name)
            # Copy relations if any (for now, skip as relations are complex)
            self.game_state.entities_manager.entities.append(new_entity)
        
        # Restore turn index if it exists
        if hasattr(restored_state.entities_manager, 'current_index'):
            if hasattr(self.game_state.entities_manager, 'current_index'):
                self.game_state.entities_manager.current_index = restored_state.entities_manager.current_index
        
        # Restore turn info
        self.game_state.turns_manager.turn_index = restored_state.turns_manager.turn_index
        self.game_state.turns_manager.lap = restored_state.turns_manager.lap
        
        # Restore fog of war state
        if hasattr(restored_state, 'fog_of_war_manager') and restored_state.fog_of_war_manager:
            if hasattr(self.game_state, 'fog_of_war_manager') and self.game_state.fog_of_war_manager:
                self.game_state.fog_of_war_manager.enabled = restored_state.fog_of_war_manager.enabled
                # Recalculate fog of war visibility
                if self.game_state.fog_of_war_manager.enabled:
                    self.game_state.fog_of_war_manager.apply_update()
