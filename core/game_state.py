"""Main game state class that integrates all game components."""

from typing import Optional, List
from core.hex import Hex
from core.enums import HColor, RulesType
from core.province import ProvincesManager
from core.player_entity import EntitiesManager, TurnsManager
from core.events import EventsManager, IEventListener, AbstractEvent
from core.enums import EventType
from core.ruleset import RulesetFactory, AbstractRuleset


class GameState(IEventListener):
    """Main game state class integrating all game components."""

    def __init__(self, name: str = ""):
        """Initialize game state."""
        self.name = name
        self.hexes: List[Hex] = []
        self.current_unit_id = 0

        # Initialize managers
        self.events_manager = EventsManager(self)
        self.provinces_manager = ProvincesManager(self)
        self.entities_manager = EntitiesManager(self)
        self.turns_manager = TurnsManager(self)
        self.ruleset_factory = RulesetFactory(self)
        self.ruleset: Optional[AbstractRuleset] = None

        # Initialize economics manager
        from core.economics_manager import EconomicsManager
        self.economics_manager = EconomicsManager(self)
        
        # Initialize fog of war manager
        from core.fog_of_war import FogOfWarManager
        self.fog_of_war_manager = FogOfWarManager(self)
        
        # Placeholder managers (to be implemented later)
        self.move_zone_manager = None
        self.readiness_manager = None
        self.construction_manager = None
        self.death_manager = None
        self.city_manager = None
        self.diplomacy_manager = None
        self.letters_manager = None

    def get_hex(self, coordinate1: int, coordinate2: int) -> Optional[Hex]:
        """Get hex by coordinates."""
        for hex in self.hexes:
            if hex.has_coordinates(coordinate1, coordinate2):
                return hex
        return None

    def get_hex_with_same_coordinates(self, hex: Hex) -> Optional[Hex]:
        """Get hex with same coordinates as given hex."""
        return self.get_hex(hex.coordinate1, hex.coordinate2)

    def add_hex(self, coordinate1: int, coordinate2: int, color: HColor = HColor.GRAY) -> Hex:
        """Add a hex to the game state."""
        hex = Hex(coordinate1=coordinate1, coordinate2=coordinate2, color=color)
        self.hexes.append(hex)
        return hex

    def remove_hex(self, hex: Hex) -> None:
        """Remove a hex from the game state."""
        if hex in self.hexes:
            self.hexes.remove(hex)
        # Remove from adjacent hexes
        for other_hex in self.hexes:
            if hex in other_hex.adjacent_hexes:
                other_hex.adjacent_hexes.remove(hex)

    def set_ruleset(self, rules_type: RulesType, version_code: int = 1) -> None:
        """Set the ruleset for this game."""
        self.ruleset = self.ruleset_factory.create(rules_type, version_code)

    def get_id_for_new_unit(self) -> int:
        """Get ID for a new unit."""
        unit_id = self.current_unit_id
        self.current_unit_id += 1
        return unit_id

    def on_event_validated(self, event: AbstractEvent) -> None:
        """Handle event validated."""
        pass

    def on_event_applied(self, event: AbstractEvent) -> None:
        """Handle event applied."""
        from core.events import EventPieceAdd, EventPieceBuild, EventMerge, EventMergeOnBuild

        event_type = event.get_type()
        if event_type == EventType.PIECE_ADD:
            if isinstance(event, EventPieceAdd):
                self._check_to_increase_current_unit_id(event.unit_id)
        elif event_type == EventType.PIECE_BUILD:
            if isinstance(event, EventPieceBuild):
                self._check_to_increase_current_unit_id(event.unit_id)
        elif event_type == EventType.MERGE:
            if isinstance(event, EventMerge):
                # EventMerge would have unit_id attribute
                if hasattr(event, "unit_id"):
                    self._check_to_increase_current_unit_id(event.unit_id)
        elif event_type == EventType.MERGE_ON_BUILD:
            if isinstance(event, EventMergeOnBuild):
                if hasattr(event, "unit_id"):
                    self._check_to_increase_current_unit_id(event.unit_id)

    def _check_to_increase_current_unit_id(self, unit_id: int) -> None:
        """Check and increase current unit ID if needed."""
        if unit_id < self.current_unit_id:
            return
        self.current_unit_id = unit_id + 10

    def get_listen_priority(self) -> int:
        """Get listener priority."""
        return 9

    def on_quick_event_applied(self) -> None:
        """Handle quick event applied."""
        self.provinces_manager.builder.grant_permission()
        self.provinces_manager.builder.apply()

    def is_terminal(self) -> bool:
        """Check if game is in terminal state (game over)."""
        # Basic check - can be extended
        if not self.entities_manager or not self.entities_manager.entities:
            return False
        if len(self.provinces_manager.provinces) == 0:
            return False  # No provinces yet, game not over
        # Check if only one player has provinces
        colors_with_provinces = set()
        for province in self.provinces_manager.provinces:
            color = province.get_color()
            if color and color != HColor.GRAY:
                colors_with_provinces.add(color)
        # Game ends when only one color has provinces
        return len(colors_with_provinces) == 1

    def get_winner(self) -> Optional[HColor]:
        """Get the winner color if game is over."""
        if not self.is_terminal():
            return None
        # Find the color with provinces
        for province in self.provinces_manager.provinces:
            color = province.get_color()
            if color and color != HColor.GRAY:
                return color
        return None

    def encode_hexes(self) -> str:
        """Encode all hexes to string."""
        if not self.hexes:
            return "-"
        encoded_parts = [hex.encode() for hex in self.hexes]
        return ",".join(encoded_parts)

    def encode_initialization(self) -> str:
        """Encode initialization data."""
        # Simplified - would need bounds and hex radius
        return "0.0 0.0 1.0"  # Placeholder

    def encode_current_ids(self) -> str:
        """Encode current IDs."""
        return str(self.current_unit_id)

    def encode_rules(self) -> str:
        """Encode rules."""
        if self.ruleset:
            return f"def {self.ruleset.get_version_code()}"
        return "def 1"
    
    def get_hexes_for_player(self, player_color: Optional[HColor] = None) -> List[Hex]:
        """
        Get hexes visible to a specific player, respecting fog of war.
        
        Args:
            player_color: The color of the player. If None, uses current player's color.
                         If fog of war is disabled, returns all hexes.
        
        Returns:
            List of hexes visible to the player
        """
        # If fog of war is disabled, return all hexes
        if not self.fog_of_war_manager or not self.fog_of_war_manager.enabled:
            return self.hexes.copy()
        
        # Determine target color
        target_color = player_color
        if target_color is None:
            # Use current player's color
            if self.entities_manager:
                current_entity = self.entities_manager.get_current_entity()
                if current_entity:
                    target_color = current_entity.color
                else:
                    # No current entity, return all hexes
                    return self.hexes.copy()
            else:
                # No entities manager, return all hexes
                return self.hexes.copy()
        
        # Update fog of war for this player
        # Temporarily override target color update to use the specified player
        original_target = self.fog_of_war_manager.target_color
        original_update_method = self.fog_of_war_manager._update_target_color
        
        # Override _update_target_color to use our target
        def override_update_target():
            self.fog_of_war_manager.target_color = target_color
        
        self.fog_of_war_manager._update_target_color = override_update_target
        self.fog_of_war_manager.apply_update()
        
        # Restore original method and target
        self.fog_of_war_manager._update_target_color = original_update_method
        self.fog_of_war_manager.target_color = original_target
        
        # Return visible hexes
        return self.fog_of_war_manager.currently_visible_hexes.copy()
