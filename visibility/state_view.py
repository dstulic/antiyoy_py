"""Player-specific game state view."""

from typing import List, Optional
from core.game_state import GameState
from core.hex import Hex
from core.province import Province
from core.enums import HColor
from core.player_entity import PlayerEntity


class StateView:
    """Player-specific view of the game state."""

    def __init__(self, game_state: GameState, player_color: HColor):
        """
        Initialize state view.
        
        Args:
            game_state: The full game state
            player_color: The color of the player this view is for
        """
        self.game_state = game_state
        self.player_color = player_color
        self._visible_hexes: List[Hex] = []
        self._visible_provinces: List[Province] = []
        self._player_entity: Optional[PlayerEntity] = None
        self._enemy_entities: List[PlayerEntity] = []
        self._update_view()

    def _update_view(self) -> None:
        """Update the view based on current game state."""
        # For now, show all hexes (fog-of-war will be added later)
        self._visible_hexes = list(self.game_state.hexes)
        
        # Get player entity
        if self.game_state.entities_manager:
            self._player_entity = self.game_state.entities_manager.get_entity(self.player_color)
            
            # Get enemy entities
            self._enemy_entities = [
                entity
                for entity in self.game_state.entities_manager.entities
                if entity.color != self.player_color
            ]
        
        # Get visible provinces (all for now)
        self._visible_provinces = list(self.game_state.provinces_manager.provinces)

    def get_visible_hexes(self) -> List[Hex]:
        """Get hexes visible to this player."""
        return self._visible_hexes.copy()

    def get_visible_provinces(self) -> List[Province]:
        """Get provinces visible to this player."""
        return self._visible_provinces.copy()

    def get_player_provinces(self) -> List[Province]:
        """Get provinces owned by this player."""
        return [
            province
            for province in self._visible_provinces
            if province.get_color() == self.player_color
        ]

    def get_enemy_provinces(self) -> List[Province]:
        """Get provinces owned by enemies."""
        return [
            province
            for province in self._visible_provinces
            if province.get_color() != self.player_color and province.get_color() != HColor.GRAY
        ]

    def get_player_entity(self) -> Optional[PlayerEntity]:
        """Get the player entity."""
        return self._player_entity

    def get_enemy_entities(self) -> List[PlayerEntity]:
        """Get enemy entities."""
        return self._enemy_entities.copy()

    def get_current_turn_color(self) -> Optional[HColor]:
        """Get the color of the player whose turn it is."""
        if self.game_state.entities_manager:
            return self.game_state.entities_manager.get_current_color()
        return None

    def is_my_turn(self) -> bool:
        """Check if it's this player's turn."""
        current_color = self.get_current_turn_color()
        return current_color == self.player_color

    def get_player_hexes(self) -> List[Hex]:
        """Get hexes owned by this player."""
        return [
            hex
            for hex in self._visible_hexes
            if hex.color == self.player_color
        ]

    def get_enemy_hexes(self) -> List[Hex]:
        """Get hexes owned by enemies."""
        return [
            hex
            for hex in self._visible_hexes
            if hex.color != self.player_color and hex.color != HColor.GRAY
        ]

    def get_player_units(self) -> List[Hex]:
        """Get hexes with units owned by this player."""
        return [
            hex
            for hex in self.get_player_hexes()
            if hex.has_unit()
        ]

    def get_enemy_units(self) -> List[Hex]:
        """Get hexes with units owned by enemies."""
        return [
            hex
            for hex in self.get_enemy_hexes()
            if hex.has_unit()
        ]

    def get_total_money(self) -> int:
        """Get total money across all player provinces."""
        provinces = self.get_player_provinces()
        return sum(province.get_money() for province in provinces)
