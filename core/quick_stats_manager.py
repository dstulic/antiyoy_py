"""Quick Stats Manager - efficiently tracks hex quantities per color."""

from typing import Dict, TYPE_CHECKING
from core.enums import HColor

if TYPE_CHECKING:
    from core.game_state import GameState


class QuickStatsManager:
    """Manages quick statistics about the game state."""
    
    def __init__(self, game_state: "GameState"):
        """Initialize quick stats manager."""
        self.game_state = game_state
        self.map_quantities: Dict[HColor, int] = {}
    
    def update(self) -> None:
        """Update statistics."""
        self.update_quantities()
    
    def get_quantity(self, color: HColor) -> int:
        """Get quantity of hexes for a color."""
        if color not in self.map_quantities:
            return 0
        return self.map_quantities[color]
    
    def update_quantities(self) -> None:
        """Update hex quantities per color."""
        self.map_quantities.clear()
        
        # Initialize with all entity colors
        if self.game_state.entities_manager and self.game_state.entities_manager.entities:
            for entity in self.game_state.entities_manager.entities:
                self.map_quantities[entity.color] = 0
        
        # Count hexes per color from provinces
        if self.game_state.provinces_manager and self.game_state.provinces_manager.provinces:
            for province in self.game_state.provinces_manager.provinces:
                color = province.get_color()
                if color in self.map_quantities:
                    current_quantity = self.map_quantities[color]
                    self.map_quantities[color] = current_quantity + len(province.get_hexes())
