"""
Fog of War Manager - handles visibility calculation and fog filtering.

This module implements the fog of war system that determines which hexes
are visible to each player based on light radius from pieces and provinces.
"""

from typing import TYPE_CHECKING, List, Optional, Set
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from core.game_state import GameState
    from core.hex import Hex
    from core.province import Province
    from core.player_entity import PlayerEntity
    from core.events import AbstractEvent, IEventListener
    from core.enums import HColor, PieceType, RelationType


class CmWaveWorker(ABC):
    """
    Abstract wave worker for flood-fill algorithms.
    Uses hex.flag to track visited hexes.
    """

    def __init__(self):
        self.propagation_list: List["Hex"] = []
        self.start_hex: Optional["Hex"] = None

    def apply(self, start_hex: "Hex") -> None:
        """
        Apply wave propagation from start_hex.
        Important: hex.flag should be prepared externally before calling this.
        """
        self.start_hex = start_hex
        self.propagation_list.clear()
        self._add_to_propagation_list(None, start_hex)

        while self.propagation_list:
            hex = self.propagation_list[0]
            self.propagation_list.remove(hex)
            self._propagate(hex)

    def _propagate(self, hex: "Hex") -> None:
        """Propagate to adjacent hexes."""
        for adjacent_hex in hex.adjacent_hexes:
            if adjacent_hex.flag:
                continue
            if not self.condition(hex, adjacent_hex):
                continue
            self._add_to_propagation_list(hex, adjacent_hex)

    @abstractmethod
    def condition(self, parent_hex: Optional["Hex"], hex: "Hex") -> bool:
        """Check if hex should be included in the wave."""
        pass

    @abstractmethod
    def action(self, parent_hex: Optional["Hex"], hex: "Hex") -> None:
        """Action to perform when hex is added to the wave."""
        pass

    def _add_to_propagation_list(self, parent_hex: Optional["Hex"], hex: "Hex") -> None:
        """Add hex to propagation list and mark it."""
        hex.flag = True
        self.propagation_list.append(hex)
        self.action(parent_hex, hex)


class DirectionsManager:
    """Manages hex directions and adjacent coordinate calculations."""

    def __init__(self, game_state: "GameState"):
        self.game_state = game_state
        self.adj_coordinate1: int = 0
        self.adj_coordinate2: int = 0
        self.angles: List[float] = []
        self._init_angles()

    def _init_angles(self) -> None:
        """Initialize direction angles."""
        import math
        self.angles = []
        a = math.pi / 2
        da = math.pi / 3
        for _ in range(6):
            self.angles.append(a)
            a -= da
            if a < 0:
                a += 2 * math.pi

    def get_angle(self, direction: int) -> float:
        """Get angle for a given direction."""
        if 0 <= direction < len(self.angles):
            return self.angles[direction]
        return 0.0

    def get_adjacent_hex(self, hex: "Hex", direction: int) -> Optional["Hex"]:
        """
        Get adjacent hex in the given direction.
        Note: This method is not fast and should not be used frequently.
        """
        self._update_adjacent_coordinates(hex, direction)
        return self.game_state.get_hex(self.adj_coordinate1, self.adj_coordinate2)

    def _update_adjacent_coordinates(self, hex: "Hex", direction: int) -> None:
        """Update adjacent coordinates based on direction."""
        self.adj_coordinate1 = hex.coordinate1
        self.adj_coordinate2 = hex.coordinate2

        # Adjacent offsets in axial coordinates
        offsets = [
            (1, 0),   # direction 0
            (0, 1),   # direction 1
            (-1, 1),  # direction 2
            (-1, 0),  # direction 3
            (0, -1),  # direction 4
            (1, -1),  # direction 5
        ]

        if 0 <= direction < len(offsets):
            offset = offsets[direction]
            self.adj_coordinate1 += offset[0]
            self.adj_coordinate2 += offset[1]

    def get_adj_coordinate1(self) -> int:
        """Get adjacent coordinate 1."""
        return self.adj_coordinate1

    def get_adj_coordinate2(self) -> int:
        """Get adjacent coordinate 2."""
        return self.adj_coordinate2


class FogOfWarManager:
    """
    Manages fog of war visibility calculation.
    
    Determines which hexes are visible to the current player based on:
    - Light radius from pieces (units, towers, cities)
    - Province ownership
    - Diplomatic relations (allies can see each other's provinces)
    """

    def __init__(self, game_state: "GameState"):
        self.game_state = game_state
        self.enabled: bool = False
        self.currently_visible_hexes: List["Hex"] = []
        self.target_color: Optional["HColor"] = None
        self.wave_light: Optional[CmWaveWorker] = None
        self.directions_manager: DirectionsManager = DirectionsManager(game_state)
        self._init_waves()
        # Register as event listener
        if hasattr(game_state, 'events_manager'):
            game_state.events_manager.add_listener(self)

    def _init_waves(self) -> None:
        """Initialize wave worker for light propagation."""

        class LightWaveWorker(CmWaveWorker):
            def condition(self, parent_hex: Optional["Hex"], hex: "Hex") -> bool:
                if parent_hex is None:
                    return True
                # Use counter to track remaining light radius
                if not hasattr(hex, 'counter'):
                    hex.counter = 0
                return parent_hex.counter > 0

            def action(self, parent_hex: Optional["Hex"], hex: "Hex") -> None:
                hex.fog = False
                if parent_hex is not None and hasattr(parent_hex, 'counter'):
                    if not hasattr(hex, 'counter'):
                        hex.counter = 0
                    hex.counter = parent_hex.counter - 1

        self.wave_light = LightWaveWorker()

    def on_event_validated(self, event: "AbstractEvent") -> None:
        """Called when an event is validated (before application)."""
        pass

    def on_event_applied(self, event: "AbstractEvent") -> None:
        """Called when an event is applied."""
        if not self.enabled:
            return
        self.apply_update()

    def on_undo_applied(self) -> None:
        """Called when an undo is applied."""
        if not self.enabled:
            return
        self.apply_update()

    def apply_update(self) -> None:
        """Update fog of war visibility."""
        self.currently_visible_hexes.clear()
        if not self.game_state.entities_manager or not self.game_state.entities_manager.entities:
            return

        self._update_target_color()
        if self.target_color is None:
            return

        self._reset_fog()
        self._apply_provinces()
        self._update_list()

    def _update_list(self) -> None:
        """Update the list of currently visible hexes."""
        self.currently_visible_hexes.clear()
        for hex in self.game_state.hexes:
            if not hasattr(hex, 'fog') or not hex.fog:
                self.currently_visible_hexes.append(hex)

    def _apply_provinces(self) -> None:
        """Apply light from provinces that should be visible."""
        # Prepare hexes once before processing all provinces
        self._prepare_hexes()
        
        for province in self.game_state.provinces_manager.provinces:
            if not self._should_province_be_light_upped(province):
                continue
            self._apply_province(province)

    def _should_province_be_light_upped(self, province: "Province") -> bool:
        """Check if a province should be lit up (visible)."""
        if province.get_color() == self.target_color:
            return True

        # Check diplomatic relations if diplomacy is enabled
        # For now, we'll skip diplomacy check as it's not yet implemented
        # In the future, check if province owner is friend/alliance with target
        return False

    def _apply_province(self, province: "Province") -> None:
        """Apply light from all hexes in a province."""
        for hex in province.get_hexes():
            # Prepare hexes before each wave propagation (reset flags)
            self._prepare_hexes()
            # Set counter to light radius for the starting hex
            hex.counter = self._get_light_radius(hex)
            # Clear fog on the starting hex
            hex.fog = False
            if self.wave_light:
                self.wave_light.apply(hex)

    def _get_light_radius(self, hex: "Hex") -> int:
        """Get light radius for a hex based on its piece type."""
        if hex.is_empty():
            return 1

        from core.enums import PieceType
        piece = hex.piece

        if piece == PieceType.PEASANT:
            return 2
        elif piece == PieceType.SPEARMAN:
            return 2
        elif piece == PieceType.BARON:
            return 2
        elif piece == PieceType.KNIGHT:
            return 2
        elif piece == PieceType.TOWER:
            return 3
        elif piece == PieceType.CITY:
            return 4
        elif piece == PieceType.STRONG_TOWER:
            return 5
        else:
            return 1

    def _reset_fog(self) -> None:
        """Reset fog on all hexes."""
        for hex in self.game_state.hexes:
            hex.fog = True

    def _prepare_hexes(self) -> None:
        """Prepare hex flags for wave propagation."""
        for hex in self.game_state.hexes:
            hex.flag = False

    def _update_target_color(self) -> None:
        """Update the target color (player whose view we're calculating)."""
        human_colors = self._count_human_colors()
        if human_colors == 0:
            self.target_color = None
        elif human_colors == 1:
            self.target_color = self._get_alive_human().color
        else:
            # Multiple human players - use current player's color
            current_entity = self.game_state.entities_manager.get_current_entity()
            if current_entity:
                self.target_color = current_entity.color
            else:
                self.target_color = None

    def _count_human_colors(self) -> int:
        """Count the number of alive human players."""
        count = 0
        for entity in self.game_state.entities_manager.entities:
            if self._is_alive_human(entity):
                count += 1
        return count

    def _get_alive_human(self) -> Optional["PlayerEntity"]:
        """Get the first alive human player."""
        for entity in self.game_state.entities_manager.entities:
            if self._is_alive_human(entity):
                return entity
        return None

    def _is_alive_human(self, entity: "PlayerEntity") -> bool:
        """Check if entity is a human player with at least one province."""
        if not entity.is_human():
            return False
        # Check if entity has at least one province
        province = self.game_state.provinces_manager.get_province(entity.color)
        return province is not None

    def is_visible(self) -> bool:
        """Check if fog of war is active and visible."""
        return self.enabled and self.target_color is not None

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable fog of war."""
        self.enabled = enabled
        if enabled:
            self.apply_update()

    def get_listen_priority(self) -> int:
        """Get event listener priority."""
        return 2
