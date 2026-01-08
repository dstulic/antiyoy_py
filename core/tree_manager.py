"""
Tree Manager - handles tree spawning, grave processing, and lonely city conversion.
"""

from typing import TYPE_CHECKING
import random
from core.events import IEventListener, AbstractEvent, EventType, EventPieceDelete, EventPieceAdd, EventSubtractMoney
from core.enums import PieceType, HColor
from core.rng_utils import get_deterministic_seed

if TYPE_CHECKING:
    from core.game_state import GameState
    from core.hex import Hex
    from core.province import Province


class TreeManager(IEventListener):
    """
    Manages tree spawning, grave processing, and lonely city conversion.
    
    Responsibilities:
    - Convert graves to trees at turn end (for current entity)
    - Spawn new trees (tree breeding) on first entity's turn
    - Convert lonely cities to trees
    - Handle money subtraction when spawning trees (burial cost)
    """

    def __init__(self, game_state: "GameState"):
        """Initialize tree manager."""
        self.game_state = game_state
        self.temp_hex_list: list["Hex"] = []  # For tree breeding
        
        # Initialize RNG with deterministic seed from original level code
        seed = 0  # Default fallback
        if game_state and hasattr(game_state, '_original_level_code') and game_state._original_level_code:
            seed = get_deterministic_seed(game_state._original_level_code)
        
        self.random = random.Random(seed)
        
        # If RNG state is already set (from save/load), restore it
        if game_state and hasattr(game_state, '_rng_state') and game_state._rng_state:
            self.random.setstate(game_state._rng_state)
        
        # Register as event listener
        if game_state and game_state.events_manager:
            game_state.events_manager.add_listener(self)

    def on_event_validated(self, event: AbstractEvent) -> None:
        """Called when event is validated."""
        pass

    def on_event_applied(self, event: AbstractEvent) -> None:
        """Called when event is applied."""
        if event.get_type() == EventType.TURN_END:
            self._on_turn_end_event_applied()

    def get_listen_priority(self) -> int:
        """Get listener priority (lower = higher priority)."""
        return 7  # Same as original Java implementation (between DeathManager=6 and EconomicsManager=8)

    def _on_turn_end_event_applied(self) -> None:
        """Handle turn end event - process graves, spawn trees, process lonely cities."""
        # Note: spawnBreed() is only called on first entity's turn (turn_index == 0)
        self._spawn_breed()
        
        self._process_graves()
        self._process_lonely_cities()

    def _process_graves(self) -> None:
        """
        Process graves owned by current entity - convert them to trees.
        
        This matches the original game's processGraves() method.
        Note: This is called after turn end, so it processes graves for the
        entity whose turn it is NOW (after the turn switch).
        
        Graves are converted to trees, and if the province has money > 0,
        1 money is subtracted (burial cost).
        """
        current_entity = self.game_state.entities_manager.get_current_entity()
        if not current_entity:
            return
        
        current_color = current_entity.color
        
        for hex in self.game_state.hexes:
            # Only process graves owned by current entity (after turn switch)
            if hex.color != current_color:
                continue
            
            # Only process graves
            if hex.piece != PieceType.GRAVE:
                continue
            
            # Convert grave to tree
            self._turn_into_tree(hex)

    def _process_lonely_cities(self) -> None:
        """
        Process lonely cities - convert cities not in any province to trees.
        
        This matches the original game's processLonelyCities() method.
        A lonely city is a city that:
        - Is not gray (has a color)
        - Is not in any province (get_province() returns None)
        - Is a city piece
        
        Note: Unlike process_graves(), this processes ALL lonely cities
        regardless of which entity owns them (except gray hexes).
        """
        for hex in self.game_state.hexes:
            # Skip gray hexes
            if hex.color == HColor.GRAY:
                continue
            
            # Skip hexes that are in a province
            if hex.get_province() is not None:
                continue
            
            # Only process cities
            if hex.piece != PieceType.CITY:
                continue
            
            # Convert lonely city to tree
            self._turn_into_tree(hex)

    def _turn_into_tree(self, hex: "Hex") -> None:
        """
        Convert a hex (with any piece) into a tree.
        
        This matches the original game's turnIntoTree() method.
        First deletes any existing piece, then spawns a tree.
        """
        # Delete existing piece if any
        if hex.has_piece():
            delete_event = self.game_state.events_manager.factory.create_event(EventType.PIECE_DELETE)
            if isinstance(delete_event, EventPieceDelete):
                delete_event.set_hex(hex)
                self.game_state.events_manager.apply_event(delete_event)
        
        # Spawn tree with possible money subtraction
        self._do_spawn_tree_with_possible_money_subtraction(hex)

    def _do_spawn_tree_with_possible_money_subtraction(self, hex: "Hex") -> None:
        """
        Spawn a tree and check if money should be subtracted.
        
        This matches the original game's doSpawnTreeWithPossibleMoneySubtraction() method.
        """
        self._do_spawn_tree(hex)
        self._check_for_money_subtraction(hex)

    def _check_for_money_subtraction(self, hex: "Hex") -> None:
        """
        Check if money should be subtracted when spawning a tree.
        
        Money is subtracted only if:
        - The hex belongs to the first entity (entities[0])
        - The hex is in a province
        - The province has money > 0
        
        This matches the original game's checkForMoneySubtraction() method.
        """
        entities = self.game_state.entities_manager.entities
        if not entities or len(entities) == 0:
            return
        
        # Only subtract money for first entity
        if hex.color != entities[0].color:
            return
        
        province = hex.get_province()
        if not province:
            return
        
        # Important: don't subtract if province has 0 or negative money
        if province.get_money() <= 0:
            return
        
        # Subtract 1 money (burial cost)
        subtract_event = self.game_state.events_manager.factory.create_event(EventType.SUBTRACT_MONEY)
        if isinstance(subtract_event, EventSubtractMoney):
            subtract_event.province_id = province.get_id()
            subtract_event.amount = 1
            self.game_state.events_manager.apply_event(subtract_event)

    def _do_spawn_tree(self, hex: "Hex") -> None:
        """
        Spawn a tree on a hex.
        
        - If hex has 6 adjacent hexes → spawn pine
        - Otherwise → spawn palm
        
        This matches the original game's doSpawnTree() method.
        """
        # Determine tree type based on number of adjacent hexes
        if len(hex.adjacent_hexes) == 6:
            piece_type = PieceType.PINE
        else:
            piece_type = PieceType.PALM
        
        # Add tree piece
        add_event = self.game_state.events_manager.factory.create_event(EventType.PIECE_ADD)
        if isinstance(add_event, EventPieceAdd):
            add_event.set_hex(hex)
            add_event.set_piece_type(piece_type)
            self.game_state.events_manager.apply_event(add_event)

    def _spawn_breed(self) -> None:
        """
        Spawn new trees through tree breeding (propagation).
        
        This matches the original game's spawnBreed() method.
        Only runs on first entity's turn (turn_index == 0).
        Trees propagate to adjacent empty hexes with 33% probability.
        """
        # Only run on first entity's turn
        if not self.game_state.turns_manager:
            return
        if self.game_state.turns_manager.turn_index != 0:
            return
        
        self._reset_flags()
        self._update_temp_hex_list_by_trees()
        self._propagate_temp_list_for_trees()
        self._spawn_trees_on_flagged_hexes()

    def _reset_flags(self) -> None:
        """Reset all hex flags."""
        for hex in self.game_state.hexes:
            hex.flag = False

    def _update_temp_hex_list_by_trees(self) -> None:
        """Collect all existing trees into temp list."""
        self.temp_hex_list.clear()
        for hex in self.game_state.hexes:
            if hex.has_tree():
                self.temp_hex_list.append(hex)

    def _propagate_temp_list_for_trees(self) -> None:
        """Propagate trees from temp list to adjacent hexes."""
        for hex in self.temp_hex_list:
            if hex.piece == PieceType.PALM:
                self._propagate_palm(hex)
            elif hex.piece == PieceType.PINE:
                self._propagate_pine(hex)

    def _propagate_pine(self, hex: "Hex") -> None:
        """
        Propagate pine tree to adjacent empty hexes.
        
        Pine trees only propagate to adjacent empty hexes if that hex
        has at least 2 adjacent trees.
        
        This matches the original game's propagatePine() method.
        """
        for adjacent_hex in hex.adjacent_hexes:
            # Skip hexes that already have pieces
            if adjacent_hex.has_piece():
                continue
            
            # Only propagate if adjacent hex has at least 2 adjacent trees
            if self._count_adjacent_trees(adjacent_hex) < 2:
                continue
            
            # Flag this hex for tree spawning
            adjacent_hex.flag = True

    def _propagate_palm(self, hex: "Hex") -> None:
        """
        Propagate palm tree to adjacent empty hexes.
        
        Palm trees propagate to adjacent empty hexes unless that hex
        has 6 adjacent hexes (fully surrounded).
        
        This matches the original game's propagatePalm() method.
        """
        for adjacent_hex in hex.adjacent_hexes:
            # Skip hexes that already have pieces
            if adjacent_hex.has_piece():
                continue
            
            # Skip hexes with 6 adjacent hexes (fully surrounded)
            if len(adjacent_hex.adjacent_hexes) == 6:
                continue
            
            # Flag this hex for tree spawning
            adjacent_hex.flag = True

    def _count_adjacent_trees(self, hex: "Hex") -> int:
        """
        Count trees adjacent to a hex.
        
        This matches the original game's countAdjacentTrees() method.
        """
        count = 0
        for adjacent_hex in hex.adjacent_hexes:
            if adjacent_hex.has_tree():
                count += 1
        return count

    def _spawn_trees_on_flagged_hexes(self) -> None:
        """
        Spawn trees on flagged hexes with 33% probability.
        
        This matches the original game's spawnTreesOnFlaggedHexes() method.
        Each flagged hex has a 33% chance of spawning a tree.
        """
        for hex in self.game_state.hexes:
            if not hex.flag:
                continue
            
            # 33% chance to spawn tree (random.nextFloat() > 0.33f means skip)
            if self.random.random() > 0.33:
                continue
            
            # Spawn tree with possible money subtraction
            self._do_spawn_tree_with_possible_money_subtraction(hex)
