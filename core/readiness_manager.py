"""Readiness manager to track which units can move this turn."""

from core.events import AbstractEvent, EventType, IEventListener
from core.enums import HColor


class ReadinessManager(IEventListener):
    """Manages which units are ready to move (haven't moved this turn)."""
    
    def __init__(self, game_state):
        """Initialize readiness manager."""
        self.game_state = game_state
        self.ready_hexes = []  # List of hexes with units that can move
        if game_state.events_manager:
            game_state.events_manager.add_listener(self)
    
    def update(self) -> None:
        """Update list of ready units (units owned by current entity that haven't moved)."""
        self.ready_hexes.clear()
        
        current_entity = self.game_state.entities_manager.get_current_entity()
        if not current_entity:
            return
        
        current_color = current_entity.color
        
        # Add all units owned by current entity
        for province in self.game_state.provinces_manager.provinces:
            if province.get_color() != current_color:
                continue
            for hex in province.get_hexes():
                if hex.has_unit():
                    self.ready_hexes.append(hex)
    
    def is_ready(self, hex) -> bool:
        """Check if a hex's unit is ready to move."""
        return hex in self.ready_hexes
    
    def set_ready(self, hex, value: bool) -> None:
        """Set whether a hex's unit is ready to move."""
        if value and hex not in self.ready_hexes:
            self.ready_hexes.append(hex)
        elif not value and hex in self.ready_hexes:
            self.ready_hexes.remove(hex)
    
    def on_unit_moved(self, start_hex) -> None:
        """Called when a unit moves - mark it as not ready."""
        if start_hex in self.ready_hexes:
            self.ready_hexes.remove(start_hex)
    
    def on_event_validated(self, event: AbstractEvent) -> None:
        """Handle event validated."""
        pass
    
    def on_event_applied(self, event: AbstractEvent) -> None:
        """Handle event applied."""
        event_type = event.get_type()
        
        if event_type == EventType.TURN_END:
            # Update ready units for new turn
            self.update()
        elif event_type == EventType.UNIT_MOVE:
            # Mark start hex as not ready when unit moves
            from core.events import EventUnitMove
            if isinstance(event, EventUnitMove) and event.start:
                self.on_unit_moved(event.start)
        elif event_type == EventType.MERGE:
            # Mark start hex as not ready when unit merges (moves)
            from core.events import EventMerge
            if isinstance(event, EventMerge) and event.start:
                self.on_unit_moved(event.start)
        # Note: PIECE_BUILD readiness is handled in EventPieceBuild.apply_change()
        # to check if hex was in province before building
        elif event_type == EventType.PIECE_DELETE:
            # Remove hex from ready list if unit is deleted
            from core.events import EventPieceDelete
            if isinstance(event, EventPieceDelete) and event.hex:
                if event.hex in self.ready_hexes:
                    self.ready_hexes.remove(event.hex)
    
    def get_listen_priority(self) -> int:
        """Get listener priority."""
        return 8
    
    def encode(self) -> str:
        """Encode readiness state."""
        if len(self.ready_hexes) == 0:
            return "-"
        
        parts = []
        for hex in self.ready_hexes:
            parts.append(f"{hex.coordinate1} {hex.coordinate2}")
        return ",".join(parts)
    
    def decode(self, source: str) -> None:
        """Decode readiness state."""
        self.ready_hexes.clear()
        if source == "-" or not source:
            return
        
        for token in source.split(","):
            parts = token.strip().split()
            if len(parts) < 2:
                continue
            try:
                c1 = int(parts[0])
                c2 = int(parts[1])
                hex = self.game_state.get_hex(c1, c2)
                if hex:
                    self.ready_hexes.append(hex)
            except (ValueError, IndexError):
                continue
