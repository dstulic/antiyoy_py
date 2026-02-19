"""
Death Manager - handles unit death when provinces go bankrupt or units become isolated.
"""

from typing import TYPE_CHECKING
from core.events import IEventListener, AbstractEvent, EventType, EventPieceDelete, EventPieceAdd, SYSTEM_AUTHOR
from core.enums import PieceType
from core.core_utils import is_unit

if TYPE_CHECKING:
    from core.game_state import GameState
    from core.hex import Hex
    from core.province import Province


class DeathManager(IEventListener):
    """
    Manages unit death when provinces go bankrupt or units become isolated.
    
    Responsibilities:
    - Kill all units in provinces with negative money (reset money to 0)
    - Kill lonely units (units not in any province)
    - Handle aggressive events that might create lonely units
    """

    def __init__(self, game_state: "GameState"):
        """Initialize death manager."""
        self.game_state = game_state
        self.aggressive_event_validated: bool = False
        # Register as event listener
        if game_state and game_state.events_manager:
            game_state.events_manager.add_listener(self)

    def on_event_validated(self, event: AbstractEvent) -> None:
        """Called when event is validated."""
        event_type = event.get_type()
        
        if event_type == EventType.UNIT_MOVE:
            # Check if this is an aggressive move (color transfer)
            from core.events import EventUnitMove
            if isinstance(event, EventUnitMove):
                if event.are_color_transfer_conditions_satisfied():
                    self.aggressive_event_validated = True
        
        elif event_type == EventType.PIECE_BUILD:
            # Check if this is an aggressive build (unit built on enemy hex)
            from core.events import EventPieceBuild
            if isinstance(event, EventPieceBuild):
                if is_unit(event.piece_type):
                    province = self.game_state.provinces_manager.get_province(event.province_id)
                    if province and province.get_color() != event.hex.color and not event.hex.is_neutral():
                        self.aggressive_event_validated = True
        
        elif event_type == EventType.APPLY_LETTER:
            # Letters can also create lonely units
            self.aggressive_event_validated = True

    def on_event_applied(self, event: AbstractEvent) -> None:
        """Called when event is applied."""
        event_type = event.get_type()
        
        if event_type == EventType.TURN_END:
            self._on_turn_end_event_applied()
        else:
            # For other events, check if we need to kill lonely units
            if self.aggressive_event_validated:
                self.aggressive_event_validated = False
                self._kill_lonely_units()

    def get_listen_priority(self) -> int:
        """
        Get listener priority (lower = higher priority).
        
        Note: DeathManager must run AFTER EconomicsManager to check for negative
        money after profits are applied. EconomicsManager has priority 8, so
        DeathManager needs a higher priority number (runs later).
        """
        return 9  # Run after EconomicsManager (8) to check negative money after profit application

    def _on_turn_end_event_applied(self) -> None:
        """Handle turn end event - check for bankrupt provinces and lonely units."""
        self._check_to_reset_money_by_killing_units()
        self._kill_lonely_units()

    def _check_to_reset_money_by_killing_units(self) -> None:
        """
        Check provinces owned by the current entity for negative money.
        If found, reset money to 0 and kill all units in that province.
        
        This matches the original game's checkToResetMoneyByKillingUnits() method,
        which uses province.isOwnedByCurrentEntity() to check the CURRENT entity
        (after the turn switch).
        
        Note: This is called after turn end, so the turn has already switched.
        Economics applies profit to the current entity's provinces, which can make
        money negative. DeathManager then checks the current entity's provinces
        and resets negative money to 0 while killing units.
        """
        # Get the current entity (after turn switch)
        # This matches the original game's isOwnedByCurrentEntity() logic
        current_entity = self.game_state.entities_manager.get_current_entity()
        if not current_entity:
            return
        
        current_color = current_entity.color
        
        for province in self.game_state.provinces_manager.provinces:
            # Only check provinces owned by the current entity (after turn switch)
            if province.get_color() != current_color:
                continue
            
            # If province has negative money, reset to 0 and kill units
            if province.get_money() < 0:
                province.set_money(0)
                self._kill_units(province)

    def _kill_units(self, province: "Province") -> None:
        """Kill all units in a province (convert them to graves)."""
        for hex in province.get_hexes():
            if hex.has_unit():
                self._spawn_grave(hex)

    def _kill_lonely_units(self) -> None:
        """
        Kill units that are not in any province (lonely units).
        These can occur after aggressive moves or builds.
        
        Note: We should NOT kill units that are adjacent to hexes of the same color,
        as they might be in the process of being added to a province by ProvincesManager.
        This matches the original game's logic where ProvincesEnlargementWorker only
        processes hexes that are adjacent to hexes of the same color.
        """
        for hex in self.game_state.hexes:
            # Skip neutral hexes
            if hex.is_neutral():
                continue
            
            # Skip hexes that are in a province
            if hex.get_province() is not None:
                continue
            
            # Skip empty hexes
            if hex.is_empty():
                continue
            
            # Only kill units
            if not hex.has_unit():
                continue
            
            # Don't kill units that are adjacent to hexes of the same color
            # These might be in the process of being added to a province
            # This matches the original game's ProvincesEnlargementWorker logic
            if hex.is_adjacent_to_hexes_of_same_color():
                continue
            
            # This is a lonely unit - kill it
            self._spawn_grave(hex)

    def _spawn_grave(self, hex: "Hex") -> None:
        """
        Convert a unit to a grave by deleting the piece and adding a grave.
        
        This matches the original game's spawnGrave() method.
        """
        # Delete the piece
        delete_event = self.game_state.events_manager.factory.create_event(EventType.PIECE_DELETE, author=SYSTEM_AUTHOR)
        if isinstance(delete_event, EventPieceDelete):
            delete_event.set_hex(hex)
            self.game_state.events_manager.apply_event(delete_event)
        
        # Add grave
        add_event = self.game_state.events_manager.factory.create_event(EventType.PIECE_ADD, author=SYSTEM_AUTHOR)
        if isinstance(add_event, EventPieceAdd):
            add_event.set_hex(hex)
            add_event.set_piece_type(PieceType.GRAVE)
            self.game_state.events_manager.apply_event(add_event)
