"""Move zone manager for calculating valid movement hexes for units."""

from typing import TYPE_CHECKING, List, Optional
from core.hex import Hex
from core.enums import HColor
from core.core_utils import get_strength

if TYPE_CHECKING:
    from core.game_state import GameState
    from core.province import WaveWorker


class MoveZoneManager:
    """Manages movement zones for units using wave propagation."""

    def __init__(self, game_state: "GameState"):
        """Initialize move zone manager."""
        self.game_state = game_state
        self.hexes: List[Hex] = []
        self._limit: int = 4  # Maximum movement distance
        self._strength: int = 0
        self._start_hex: Optional[Hex] = None
        self._start_entity = None
        self._wave_worker: Optional["WaveWorker"] = None
        self._init_wave_worker()

    def _init_wave_worker(self) -> None:
        """Initialize wave worker for movement zone calculation."""
        from core.province import WaveWorker

        def condition(parent_hex: Optional[Hex], hex: Hex) -> bool:
            """Check if hex can be reached from parent hex."""
            if self._start_hex is None:
                return False
            
            # For the start hex (parent_hex is None), always allow it
            if parent_hex is None:
                return True
            
            # Parent hex must have same color as start hex
            if parent_hex.color != self._start_hex.color:
                return False
            
            # Parent hex's counter must be > 0 (movement remaining)
            if not hasattr(parent_hex, 'counter') or parent_hex.counter <= 0:
                return False
            
            # Check if hex can be captured (if different color)
            if hex.color != self._start_hex.color:
                if self.game_state.ruleset:
                    if not self.game_state.ruleset.can_hex_be_captured(hex, self._strength):
                        return False
                # Check diplomacy (if diplomacy manager exists)
                if self._start_entity and hasattr(self.game_state, 'diplomacy_manager') and self.game_state.diplomacy_manager:
                    if not self.game_state.diplomacy_manager.is_attack_allowed(
                        self._start_entity, hex
                    ):
                        return False
            
            return True

        def action(parent_hex: Optional[Hex], hex: Hex) -> None:
            """Action when hex is added to movement zone."""
            if parent_hex is not None:
                # Set counter to parent's counter - 1
                hex.counter = parent_hex.counter - 1
                # Safety check: counter should never be negative
                if hex.counter < 0:
                    hex.counter = 0
                # Safety check: if counter is 0, we've reached the limit, don't add this hex
                # This prevents hexes beyond the limit from being added
                if hex.counter == 0:
                    return
            else:
                # Start hex gets the limit
                hex.counter = self._limit
            
            # Only add hex if we haven't exceeded the limit
            self.hexes.append(hex)

        self._wave_worker = WaveWorker(condition, action)

    def update_for_unit(self, start_hex: Hex) -> None:
        """Update movement zone for a unit starting from start_hex."""
        if not start_hex.has_unit():
            return
        
        strength = get_strength(start_hex.piece)
        self.update(start_hex, self._limit, strength)

    def update(self, start_hex: Hex, limit: int, strength: int) -> None:
        """Update movement zone with given parameters."""
        self._limit = limit
        self._strength = strength
        self._start_hex = start_hex
        
        # Get start entity
        if self.game_state.entities_manager:
            self._start_entity = self.game_state.entities_manager.get_entity(start_hex.color)
        
        self.clear()
        
        if self._start_entity is None:
            return
        
        # Reset flags and counters for all hexes (important: counters must be reset!)
        for hex in self.game_state.hexes:
            hex.flag = False
            hex.counter = 0  # Reset counter to prevent propagation beyond limit
        
        # Apply wave worker
        if self._wave_worker:
            self._wave_worker.apply(start_hex)
        
        # Final safety check: filter out any hexes beyond the limit
        # This catches any edge cases where hexes might have been added incorrectly
        filtered_hexes = []
        for hex in self.hexes:
            if hex == start_hex:
                filtered_hexes.append(hex)
                continue
            distance = self._calculate_hex_distance(start_hex, hex)
            if distance <= limit:
                filtered_hexes.append(hex)
            # If distance > limit, this is a bug - log it but don't add the hex
            elif distance > limit:
                # This should never happen, but if it does, we filter it out
                pass
        self.hexes = filtered_hexes

    def clear(self) -> None:
        """Clear movement zone."""
        self.hexes.clear()
    
    def _calculate_hex_distance(self, hex1: Hex, hex2: Hex) -> int:
        """Calculate distance between two hexes using axial coordinates."""
        dq = hex2.coordinate1 - hex1.coordinate1
        dr = hex2.coordinate2 - hex1.coordinate2
        return (abs(dq) + abs(dq + dr) + abs(dr)) // 2

    def contains(self, hex: Hex) -> bool:
        """Check if hex is in movement zone."""
        return hex in self.hexes
