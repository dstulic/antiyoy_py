"""Game end condition manager."""

from typing import Optional, Set
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
        self.dead_players: Set[HColor] = set()  # Players with no provinces
        
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
        # Check for lose/win conditions after turn end and province changes
        if event.get_type() in (EventType.TURN_END, EventType.HEX_CHANGE_COLOR, EventType.UNIT_MOVE, EventType.PIECE_BUILD):
            self._update_dead_players()
            self._check_game_end()
    
    def _update_dead_players(self) -> None:
        """Update the set of dead players (players with no provinces)."""
        self.dead_players.clear()
        
        if not self.game_state.entities_manager:
            return
        
        for entity in self.game_state.entities_manager.entities:
            # Check if entity has any provinces
            province = self.game_state.provinces_manager.get_province_by_color(entity.color)
            if province is None:
                self.dead_players.add(entity.color)
    
    def is_player_dead(self, color: HColor) -> bool:
        """Check if a player is dead (has no provinces)."""
        return color in self.dead_players
    
    def _check_game_end(self) -> None:
        """Check if game has ended (all provinces are one color)."""
        if self.game_ended:
            return
        
        provinces = self.game_state.provinces_manager.provinces
        if len(provinces) == 0:
            return
        
        # Only check for game end if there are multiple players
        # Single-player scenarios shouldn't trigger game end
        if not self.game_state.entities_manager or not self.game_state.entities_manager.entities:
            return
        
        # Count distinct player colors (non-AI players)
        player_colors = set()
        for entity in self.game_state.entities_manager.entities:
            if entity.is_human() or entity.is_artificial_intelligence():
                player_colors.add(entity.color)
        
        # If there's only one player, don't check for game end
        if len(player_colors) <= 1:
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
    
    def check_player_lose(self, color: HColor) -> bool:
        """Check if a player has lost (has no provinces)."""
        return self.is_player_dead(color)
    
    def check_player_win(self, color: HColor) -> bool:
        """
        Check if a player has won.
        Win conditions:
        1. All opponents are dead (have no provinces)
        2. Player owns 80% or more of all hexes
        """
        if not self.game_state.entities_manager:
            return False
        
        # Get hex ownership statistics
        hex_stats = self.game_state.get_hex_ownership_stats(color)
        total_hexes = hex_stats['total_hexes']
        player_hexes = hex_stats['player_hexes']
        
        # Check condition 1: All opponents are dead
        all_opponents_dead = True
        for entity in self.game_state.entities_manager.entities:
            if entity.color == color:
                continue  # Skip self
            if not self.is_player_dead(entity.color):
                all_opponents_dead = False
                break
        
        if all_opponents_dead and len(self.game_state.entities_manager.entities) > 1:
            return True
        
        # Check condition 2: Player owns 80% or more of hexes
        if total_hexes > 0:
            percentage = (player_hexes / total_hexes) * 100
            if percentage >= 80.0:
                return True
        
        return False
    
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
