"""History manager for tracking game events."""

from typing import List, Optional
from core.events import IEventListener, AbstractEvent
from core.enums import EventType, HColor


class HistoryEvent:
    """Represents a historical event with author information."""
    
    def __init__(self, event: AbstractEvent, author_color: Optional[HColor] = None, author_name: Optional[str] = None):
        """
        Initialize history event.
        
        Args:
            event: The event that occurred
            author_color: Color of the player who performed the event
            author_name: Name of the player who performed the event
        """
        self.event = event
        self.author_color = author_color
        self.author_name = author_name
    
    def encode(self) -> str:
        """
        Encode history event to string format.

        Format: <event_encoding>|author:<color>:<name> or |author:system or |author:-
        """
        event_encoding = self.event.encode()
        if self.author_color:
            author_str = f"{self.author_color.value}"
            if self.author_name:
                author_str += f":{self.author_name}"
            return f"{event_encoding}|author:{author_str}"
        if self.author_name:
            return f"{event_encoding}|author:{self.author_name}"
        return f"{event_encoding}|author:-"
    
    def __str__(self) -> str:
        """Return string representation."""
        author_info = "Unknown"
        if self.author_color:
            author_info = self.author_color.value
            if self.author_name:
                author_info += f" ({self.author_name})"
        elif self.author_name:
            author_info = self.author_name
        return f"{self.event.get_type().value} by {author_info}"


class HistoryManager(IEventListener):
    """Manages game event history."""
    
    def __init__(self, game_state):
        """
        Initialize history manager.
        
        Args:
            game_state: The game state
        """
        self.game_state = game_state
        self.events_list: List[HistoryEvent] = []
        self.current_turn_events: List[HistoryEvent] = []
        
        # Register as event listener
        if game_state and game_state.events_manager:
            game_state.events_manager.add_listener(self)
    
    def get_listen_priority(self) -> int:
        """Get listener priority (lower = higher priority)."""
        return 5
    
    def on_event_validated(self, event: AbstractEvent) -> None:
        """Called when event is validated - track notable events."""
        # Don't track turn_end events themselves (they're just markers for turn boundaries)
        if event.get_type() == EventType.TURN_END:
            return
        
        # Only track notable events
        if not event.is_notable():
            return
        
        # Get author information (player entity has .color/.name; SystemAuthor has .name only)
        author_color = getattr(event.author, "color", None) if event.author is not None else None
        author_name = getattr(event.author, "name", None) if event.author is not None else None

        # Create history event
        history_event = HistoryEvent(event, author_color, author_name)
        self.current_turn_events.append(history_event)
    
    def on_event_applied(self, event: AbstractEvent) -> None:
        """Called when event is applied."""
        if event.get_type() == EventType.TURN_END:
            self._on_turn_end_event_applied()
        elif event.get_type() == EventType.GRAPH_CREATED:
            self._on_graph_created()
        elif event.get_type() == EventType.MATCH_STARTED:
            self._on_match_started()
    
    def _on_turn_end_event_applied(self) -> None:
        """Handle turn end - move current turn events to events list."""
        self.events_list.extend(self.current_turn_events)
        self.current_turn_events.clear()
    
    def _on_graph_created(self) -> None:
        """Handle graph created - clear all history."""
        self.clear_all()
    
    def _on_match_started(self) -> None:
        """Handle match started."""
        pass
    
    def clear_all(self) -> None:
        """Clear all history."""
        self.current_turn_events.clear()
        self.clear_events_list()
    
    def clear_events_list(self) -> None:
        """Clear the events list."""
        self.events_list.clear()
    
    def get_events_list_copy(self) -> List[HistoryEvent]:
        """Get a copy of the events list."""
        return self.events_list.copy()
    
    def get_current_turn_events_copy(self) -> List[HistoryEvent]:
        """Get a copy of the current turn events."""
        return self.current_turn_events.copy()
    
    def encode_events_list(self) -> str:
        """
        Encode all events (completed turns + current turn) to string format.
        
        Returns:
            Comma-separated string of encoded events
        """
        encoded_parts = []
        
        # Add completed turn events
        for history_event in self.events_list:
            encoded_parts.append(history_event.encode())
        
        # Add current turn events
        for history_event in self.current_turn_events:
            encoded_parts.append(history_event.encode())
        
        return ",".join(encoded_parts)
    
    def get_all_events(self) -> List[HistoryEvent]:
        """Get all events (completed turns + current turn)."""
        return self.events_list + self.current_turn_events
    
    def get_events_since_index(self, start_index: int) -> List[HistoryEvent]:
        """
        Get events since a specific index in the events_list.
        
        Args:
            start_index: The index in events_list to start from (0 = from beginning)
            
        Returns:
            List of events since the specified index (includes current turn events)
        """
        if start_index < 0:
            start_index = 0
        if start_index >= len(self.events_list):
            # If start_index is beyond events_list, only return current turn events
            return self.current_turn_events.copy()
        # Return events from start_index onwards + current turn events
        return self.events_list[start_index:] + self.current_turn_events.copy()
    
    def get_total_event_count(self) -> int:
        """
        Get total number of events (completed turns only, not including current turn).
        
        Returns:
            Number of events in events_list
        """
        return len(self.events_list)
