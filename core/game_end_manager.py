"""Game end condition manager."""

from typing import Optional
from core.events import IEventListener, AbstractEvent, EventType
from core.enums import HColor
from core.player_entity import PlayerEntity


class GameEndManager(IEventListener):
    """Manages game end conditions."""
    
    def __init__(self, game_state):
        """Initialize game end manager."""
        self.game_state = game_state
        self.game_ended = False
        self.winner_color: Optional[HColor] = None
        
        # Register as event listener
        if game_state.events_manager:
            game_state.events_manager.add_listener(self)
    
    def get_listen_priority(self) -> int:
        """Get listener priority (lower = higher priority)."""
        return 10  # Run after most other managers
    
    def on_event_validated(self, event: AbstractEvent) -> None:
        """Called when event is validated."""
        pass
    
    def on_event_applied(self, event: AbstractEvent) -> None:
        """Called when event is applied."""
        # Check for game end after turn end
        if event.get_type() == EventType.TURN_END:
            self._check_game_end()
    
    def _check_game_end(self) -> None:
        """Check if game has ended (all provinces are one color)."""
        if self.game_ended:
            return
        
        provinces = self.game_state.provinces_manager.provinces
        if len(provinces) == 0:
            return
        
        # Check if all provinces are the same color
        first_color = provinces[0].get_color()
        for province in provinces:
            if province.get_color() != first_color:
                # Game hasn't ended - multiple colors still exist
                return
        
        # All provinces are the same color - game has ended
        self.game_ended = True
        self.winner_color = first_color
    
    def get_winner(self) -> Optional[PlayerEntity]:
        """Get the winner entity, or None if game hasn't ended."""
        if not self.game_ended or not self.winner_color:
            return None
        
        if not self.game_state.entities_manager:
            return None
        
        return self.game_state.entities_manager.get_entity(self.winner_color)
    
    def is_game_ended(self) -> bool:
        """Check if game has ended."""
        return self.game_ended
    
    def can_make_turn(self) -> bool:
        """Check if a turn can be made (game hasn't ended)."""
        return not self.game_ended
