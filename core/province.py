"""Province management for the game."""

from typing import Optional, List, Callable, Dict
from core.hex import Hex
from core.enums import HColor, PieceType
from core.events import IEventListener, AbstractEvent, EventPieceAdd, EventPieceDelete
from core.enums import EventType


class Province:
    """Represents a province - a contiguous group of hexes of the same color."""

    def __init__(self):
        """Initialize an empty province."""
        self._hexes: list[Hex] = []
        self._money: int = 0
        self._city_name: str = ""
        self._id: int = -1
        self._valid: bool = True

    def reset(self) -> None:
        """Reset province to initial state."""
        self._hexes.clear()
        self._money = 0
        self._city_name = ""
        self._valid = True
        self._id = -1

    def contains(self, hex: Hex) -> bool:
        """Check if province contains a hex."""
        self._check_validity()
        return hex in self._hexes

    def contains_piece_type(self, piece_type: PieceType) -> bool:
        """Check if province contains a specific piece type."""
        self._check_validity()
        for hex in self._hexes:
            if hex.piece == piece_type:
                return True
        return False

    def get_color(self) -> Optional[HColor]:
        """Get the color of this province (all hexes must be same color)."""
        self._check_validity()
        if len(self._hexes) == 0:
            return None
        return self._hexes[0].color

    def count_pieces(self, piece_type: PieceType) -> int:
        """Count pieces of a specific type in this province."""
        self._check_validity()
        count = 0
        for hex in self._hexes:
            if hex.piece == piece_type:
                count += 1
        return count

    def can_afford(self, piece_type: PieceType, ruleset) -> bool:
        """Check if province can afford a piece type (requires ruleset for pricing)."""
        self._check_validity()
        if len(self._hexes) == 0:
            return False
        price = ruleset.get_price(self, piece_type)
        return self._money >= price

    def get_hexes(self) -> list[Hex]:
        """Get all hexes in this province."""
        self._check_validity()
        return self._hexes.copy()  # Return copy to prevent external modification

    def get_first_hex(self) -> Optional[Hex]:
        """Get the first hex in this province."""
        self._check_validity()
        if len(self._hexes) == 0:
            return None
        return self._hexes[0]

    def add_hex(self, hex: Hex) -> None:
        """Add a hex to this province."""
        self._check_validity()
        if hex not in self._hexes:
            self._hexes.append(hex)
            hex.on_added_to_province(self)

    def remove_hex(self, hex: Hex) -> None:
        """Remove a hex from this province."""
        self._check_validity()
        if hex in self._hexes:
            self._hexes.remove(hex)
            hex.on_removed_from_province(self)

    def get_money(self) -> int:
        """Get the money in this province."""
        self._check_validity()
        return self._money

    def set_money(self, money: int) -> None:
        """Set the money in this province."""
        self._check_validity()
        self._money = money

    def get_city_name(self) -> str:
        """Get the city name of this province."""
        self._check_validity()
        return self._city_name

    def set_city_name(self, city_name: str) -> None:
        """Set the city name of this province."""
        self._check_validity()
        self._city_name = city_name

    def get_id(self) -> int:
        """Get the ID of this province."""
        self._check_validity()
        if self._id == -1:
            # ID not set - this is suspicious but we'll return -1
            pass
        return self._id

    def set_id(self, id: int) -> None:
        """Set the ID of this province."""
        self._check_validity()
        self._id = id

    def is_valid(self) -> bool:
        """Check if province is valid."""
        return self._valid

    def set_valid(self, valid: bool) -> None:
        """Set validity of this province."""
        if self._valid == valid:
            return
        self._valid = valid
        if not valid:
            self._on_invalidated()

    def _on_invalidated(self) -> None:
        """Called when province is invalidated."""
        for hex in self._hexes:
            hex.on_province_invalidated(self)

    def _check_validity(self) -> None:
        """Check if province is valid before operations."""
        if not self._valid:
            # In debug mode, we might want to log this
            pass

    def encode(self) -> str:
        """Encode province to string format for save/load."""
        if len(self._hexes) == 0:
            return ""
        first_hex = self._hexes[0]
        return f"{first_hex.coordinate1}<{first_hex.coordinate2}<{self._id}<{self._money}<{self._city_name}"

    def __str__(self) -> str:
        """Return string representation."""
        if not self.is_valid():
            return "[Invalid province]"
        color_str = str(self.get_color()) if self.get_color() else "None"
        return f"[Province: {color_str}<{self._id}>, ${self._money} {self._city_name}]"

    def __repr__(self) -> str:
        """Return detailed representation."""
        return (
            f"Province(id={self._id}, color={self.get_color()}, "
            f"money={self._money}, city='{self._city_name}', "
            f"hexes={len(self._hexes)}, valid={self._valid})"
        )


class WaveWorker:
    """Flood-fill worker for province detection."""

    def __init__(
        self,
        condition: Callable[[Hex, Hex], bool],
        action: Callable[[Hex, Hex], None],
    ):
        """Initialize wave worker with condition and action callbacks."""
        self.condition = condition
        self.action = action
        self.propagation_list: List[Hex] = []
        self.start_hex: Optional[Hex] = None

    def apply(self, start_hex: Hex) -> None:
        """Apply flood-fill algorithm starting from start_hex."""
        self.start_hex = start_hex
        self.propagation_list.clear()
        self._add_to_propagation_list(None, start_hex)
        while len(self.propagation_list) > 0:
            hex = self.propagation_list.pop(0)
            self._propagate(hex)

    def _propagate(self, hex: Hex) -> None:
        """Propagate from a hex to adjacent hexes."""
        for adjacent_hex in hex.adjacent_hexes:
            if adjacent_hex.flag:
                continue
            if not self.condition(hex, adjacent_hex):
                continue
            self._add_to_propagation_list(hex, adjacent_hex)

    def _add_to_propagation_list(self, parent_hex: Optional[Hex], hex: Hex) -> None:
        """Add hex to propagation list."""
        hex.flag = True
        self.propagation_list.append(hex)
        self.action(parent_hex, hex)


class ProvincesBuilder:
    """Builder for creating provinces using flood-fill algorithm."""

    def __init__(self, provinces_manager: "ProvincesManager"):
        """Initialize provinces builder."""
        self.provinces_manager = provinces_manager
        self.cumulative_list: List[Hex] = []
        self.permission_granted = False
        self._init_wave_worker()

    def _init_wave_worker(self) -> None:
        """Initialize wave worker for flood-fill."""
        self.wave_worker = WaveWorker(
            condition=lambda parent_hex, hex: parent_hex.color == hex.color,
            action=lambda parent_hex, hex: self.cumulative_list.append(hex),
        )

    def apply(self) -> None:
        """Build all provinces from hexes."""
        self._check_permission()
        self._clear()
        self._prepare_flags()
        hexes = self.provinces_manager.core_model.hexes if self.provinces_manager.core_model else []
        for hex in hexes:
            if hex.flag:
                continue
            if not hex.is_colored():
                continue
            # Skip gray (neutral) hexes that aren't part of a province
            if hex.color == HColor.GRAY and not hex.is_adjacent_to_hexes_of_same_color():
                continue
            # For non-gray hexes, always create a province (even if single-hex)
            # The wave worker will handle both multi-hex and single-hex provinces
            self._build_province(hex)

    def _check_permission(self) -> None:
        """Check if permission is granted."""
        if not self.permission_granted:
            # Should not call apply without permission
            pass
        self.permission_granted = False

    def _build_province(self, start_hex: Hex) -> None:
        """Build a province starting from start_hex."""
        self.cumulative_list.clear()
        self.wave_worker.apply(start_hex)
        self._turn_cumulative_list_into_province()

    def _turn_cumulative_list_into_province(self) -> None:
        """Convert cumulative list into a province."""
        if len(self.cumulative_list) == 0:
            return
        province = self.provinces_manager.add_province()
        for hex in self.cumulative_list:
            province.add_hex(hex)

    def _prepare_flags(self) -> None:
        """Prepare flags for all hexes."""
        hexes = self.provinces_manager.core_model.hexes if self.provinces_manager.core_model else []
        for hex in hexes:
            hex.flag = False

    def _clear(self) -> None:
        """Clear all provinces."""
        self.provinces_manager.clear_provinces()

    def grant_permission(self) -> None:
        """Grant permission to build provinces."""
        self.permission_granted = True


class PrwCluster:
    """Cluster of hexes for province reduction."""

    def __init__(self):
        """Initialize cluster."""
        self.hexes: List[Hex] = []
    
    def has_city(self) -> bool:
        """Check if cluster has a city."""
        from core.enums import PieceType
        return any(hex.piece == PieceType.CITY for hex in self.hexes)
    
    def count_farms(self) -> int:
        """Count farms in cluster."""
        from core.enums import PieceType
        return sum(1 for hex in self.hexes if hex.piece == PieceType.FARM)


class ProvincesReductionWorker:
    """Worker for handling province splitting when hex colors change."""

    def __init__(self, provinces_manager: "ProvincesManager"):
        """Initialize reduction worker."""
        self.provinces_manager = provinces_manager
        self.clusters: List[PrwCluster] = []
        self.modified_province: Optional[Province] = None
        self.modified_hex: Optional[Hex] = None
        self.previous_color: Optional[HColor] = None
        self.current_cluster: Optional[PrwCluster] = None
        self.successor_cluster: Optional[PrwCluster] = None
        self._init_wave_worker()

    def _init_wave_worker(self) -> None:
        """Initialize wave worker for cluster detection."""
        self.wave_worker = WaveWorker(
            condition=lambda parent_hex, hex: hex.color == self.previous_color,
            action=lambda parent_hex, hex: self.current_cluster.hexes.append(hex)
            if self.current_cluster
            else None,
        )

    def on_hex_color_changed(self, hex: Hex, previous_color: HColor) -> None:
        """Handle hex color change."""
        if previous_color == HColor.GRAY:
            return
        self.modified_hex = hex
        self.previous_color = previous_color
        # Get province that contains this hex
        # The hex color may have already changed, so we can't rely on hex.get_province()
        # Instead, search through all provinces to find one that contains this hex
        # Note: We check if the hex is in the province, not the province's current color,
        # because the province's color might have changed when the hex color changed
        self.modified_province = None
        if self.provinces_manager.core_model:
            for province in self.provinces_manager.provinces:
                if hex in province.get_hexes():
                    self.modified_province = province
                    break
        self._reset_flags()
        self._update_clusters()
        self._handle_simple_situations()

    def _reset_flags(self) -> None:
        """Reset flags for all hexes."""
        hexes = (
            self.provinces_manager.core_model.hexes
            if self.provinces_manager.core_model
            else []
        )
        for h in hexes:
            if h.color == self.previous_color:
                h.flag = False

    def _update_clusters(self) -> None:
        """Update clusters after color change."""
        self.clusters.clear()
        if not self.previous_color or not self.modified_hex:
            return
        # Only look at adjacent hexes to the modified hex (matching Java implementation)
        for adjacent_hex in self.modified_hex.adjacent_hexes:
            if adjacent_hex.flag:
                continue
            if adjacent_hex.color != self.previous_color:
                continue
            self._add_cluster(adjacent_hex)

    def _handle_simple_situations(self) -> None:
        """Handle simple situations (no split, single hex removal)."""
        if len(self.clusters) == 0:
            if self.modified_province:
                self.provinces_manager.remove_province(self.modified_province)
            return
        if len(self.clusters) == 1:
            # Single cluster - remove single hex
            self._remove_single_hex()
            return
        # Multiple clusters - handle split
        self._handle_split_situation()
    
    def _remove_single_hex(self) -> None:
        """Remove single hex from province."""
        if not self.modified_province or not self.modified_hex:
            return
        self.modified_province.remove_hex(self.modified_hex)
        if len(self.modified_province.get_hexes()) < 2:
            self.provinces_manager.remove_province(self.modified_province)
    
    def _add_cluster(self, hex: Hex) -> None:
        """Add a cluster starting from hex."""
        cluster = PrwCluster()
        self.current_cluster = cluster
        self.wave_worker.apply(hex)
        if len(cluster.hexes) > 0:
            self.clusters.append(cluster)

    def _handle_split_situation(self) -> None:
        """Handle province split into multiple clusters."""
        self._update_successor_cluster()
        self._modify_province_to_match_successor_cluster()
        self._make_provinces_for_rest_of_clusters()

    def _update_successor_cluster(self) -> None:
        """Update successor cluster (city > farms > biggest)."""
        # Priority 1: Cluster with city
        self.successor_cluster = self._get_cluster_with_city()
        if self.successor_cluster is not None:
            return
        # Priority 2: Cluster with most farms
        self.successor_cluster = self._get_cluster_with_most_farms()
        if self.successor_cluster is not None:
            return
        # Priority 3: Biggest cluster
        self.successor_cluster = self._get_biggest_cluster()
    
    def _get_cluster_with_city(self) -> Optional[PrwCluster]:
        """Get cluster with a city."""
        for cluster in self.clusters:
            if cluster.has_city():
                return cluster
        return None
    
    def _get_cluster_with_most_farms(self) -> Optional[PrwCluster]:
        """Get cluster with most farms."""
        best_cluster = None
        max_farms = -1
        for cluster in self.clusters:
            farms = cluster.count_farms()
            if best_cluster is None or farms > max_farms:
                best_cluster = cluster
                max_farms = farms
        return best_cluster if max_farms > 0 else None
    
    def _get_biggest_cluster(self) -> Optional[PrwCluster]:
        """Get biggest cluster."""
        biggest_cluster = None
        for cluster in self.clusters:
            if biggest_cluster is None or len(cluster.hexes) > len(biggest_cluster.hexes):
                biggest_cluster = cluster
        return biggest_cluster

    def _modify_province_to_match_successor_cluster(self) -> None:
        """
        Modify province to match successor cluster.
        
        This matches the original game's modifyProvinceToMatchSuccessorCluster() method.
        Removes hexes not in the successor cluster, then removes the province if it has
        less than 2 hexes (unless it has a city, which allows single-hex provinces).
        """
        if not self.modified_province or not self.successor_cluster:
            return
        # Mark hexes in successor cluster
        for hex in self.modified_province.get_hexes():
            hex.flag = False
        for hex in self.successor_cluster.hexes:
            hex.flag = True
        # Remove hexes not in successor cluster (iterate backwards to avoid index issues)
        hexes_to_remove = [
            h
            for h in self.modified_province.get_hexes()
            if not h.flag
        ]
        for h in hexes_to_remove:
            self.modified_province.remove_hex(h)
        # Remove province if it has less than 2 hexes
        # Exception: keep single-hex provinces if they have a city
        remaining_hexes = self.modified_province.get_hexes()
        if len(remaining_hexes) < 2:
            # Check if the province has a city (allows single-hex provinces)
            has_city = any(hex.piece == PieceType.CITY for hex in remaining_hexes)
            if not has_city:
                self.provinces_manager.remove_province(self.modified_province)

    def _make_provinces_for_rest_of_clusters(self) -> None:
        """Create new provinces for remaining clusters."""
        for cluster in self.clusters:
            if cluster == self.successor_cluster:
                continue
            # Only create provinces for clusters with at least 2 hexes (matching Java)
            if len(cluster.hexes) < 2:
                continue
            province = self.provinces_manager.add_province()
            for hex in cluster.hexes:
                province.add_hex(hex)
            
            # If the new province doesn't have a city, add one
            # This matches the original game's CityManager logic
            if not cluster.has_city():
                self._add_city_to_province(province)
    
    def _add_city_to_province(self, province: Province) -> None:
        """
        Add a city to a province that doesn't have one.
        
        This matches the original game's CityManager.doFixProvince() method.
        Priority: empty hex > hex without tower > any hex
        """
        if not province or not self.provinces_manager.core_model:
            return
        
        # Pick a hex for the city (matching original game's pickHexForCity logic)
        hex_for_city = self._pick_hex_for_city(province)
        if not hex_for_city:
            return
        
        # Delete existing piece if any (matching original game)
        if hex_for_city.has_piece():
            delete_event = self.provinces_manager.core_model.events_manager.factory.create_event(EventType.PIECE_DELETE)
            from core.events import EventPieceDelete
            if isinstance(delete_event, EventPieceDelete):
                delete_event.set_hex(hex_for_city)
                self.provinces_manager.core_model.events_manager.apply_event(delete_event)
        
        # Add city
        add_event = self.provinces_manager.core_model.events_manager.factory.create_event(EventType.PIECE_ADD)
        if isinstance(add_event, EventPieceAdd):
            add_event.set_hex(hex_for_city)
            add_event.set_piece_type(PieceType.CITY)
            self.provinces_manager.core_model.events_manager.apply_event(add_event)
    
    def _pick_hex_for_city(self, province: Province) -> Optional[Hex]:
        """
        Pick a hex for placing a city in a province using deterministic algorithm.
        
        Strategy: Find the hex that is furthest from any enemy hexes (by walking distance).
        Uses BFS to calculate shortest path distances.
        
        Tie-breaking (applied in order):
        1. Closest to geometrical center of the map
        2. Closest to geometrical center of the province
        3. More west (lower coordinate1)
        4. More north (higher coordinate2)
        """
        if not province:
            return None
        
        hexes = province.get_hexes()
        if not hexes:
            return None
        
        province_color = province.get_color()
        if not province_color:
            return None
        
        # Get access to all hexes to find enemies
        if not self.provinces_manager.core_model:
            return None
        
        all_hexes = self.provinces_manager.core_model.hexes
        
        # Find all enemy hexes (any hex not of the province's color)
        enemy_hexes = [h for h in all_hexes if h.color != province_color and h.color != HColor.GRAY]
        
        # If no enemies, fall back to center of province
        if not enemy_hexes:
            return self._pick_hex_by_province_center(hexes)
        
        # Calculate minimum distance to any enemy for each province hex
        hex_distances = {}
        for hex in hexes:
            min_distance = self._calculate_min_distance_to_enemies(hex, enemy_hexes)
            hex_distances[hex] = min_distance
        
        # Find maximum minimum distance
        max_min_distance = max(hex_distances.values())
        
        # Get all hexes with maximum minimum distance
        candidates = [h for h, dist in hex_distances.items() if dist == max_min_distance]
        
        # Apply tie-breaking
        return self._break_tie_for_city_placement(candidates, province)
    
    def _calculate_min_distance_to_enemies(self, start_hex: Hex, enemy_hexes: List[Hex]) -> int:
        """
        Calculate the minimum walking distance from start_hex to any enemy hex.
        Uses BFS to find shortest path.
        """
        if not enemy_hexes:
            return float('inf')
        
        # Use BFS to find shortest path to any enemy
        from collections import deque
        
        # Reset flags for BFS
        visited = set()
        queue = deque([(start_hex, 0)])
        visited.add((start_hex.coordinate1, start_hex.coordinate2))
        
        while queue:
            current_hex, distance = queue.popleft()
            
            # Check if we reached an enemy hex
            if current_hex in enemy_hexes:
                return distance
            
            # Explore adjacent hexes
            for adjacent in current_hex.adjacent_hexes:
                coord_key = (adjacent.coordinate1, adjacent.coordinate2)
                if coord_key not in visited:
                    visited.add(coord_key)
                    queue.append((adjacent, distance + 1))
        
        # No path found (shouldn't happen in a connected map, but handle gracefully)
        return 0
    
    def _break_tie_for_city_placement(self, candidates: List[Hex], province: Province) -> Hex:
        """
        Break ties when multiple hexes have the same maximum distance from enemies.
        Applies multiple deterministic criteria in order:
        1. Closest to geometrical center of the map
        2. Closest to geometrical center of the province
        3. More west (lower coordinate1)
        4. More north (higher coordinate2)
        """
        if len(candidates) == 1:
            return candidates[0]
        
        # Tie-breaker 1: Closest to geometrical center of the map
        if not self.provinces_manager.core_model:
            # Fallback if we can't access all hexes
            return self._break_tie_by_province_center_and_direction(candidates, province)
        
        all_hexes = self.provinces_manager.core_model.hexes
        if not all_hexes:
            return self._break_tie_by_province_center_and_direction(candidates, province)
        
        # Calculate map center (geometrical center of all hexes)
        map_center_q = sum(h.coordinate1 for h in all_hexes) / len(all_hexes)
        map_center_r = sum(h.coordinate2 for h in all_hexes) / len(all_hexes)
        
        def distance_to_map_center(hex: Hex) -> float:
            dq = hex.coordinate1 - map_center_q
            dr = hex.coordinate2 - map_center_r
            return (dq * dq + dr * dr + (dq + dr) * (dq + dr)) ** 0.5
        
        candidates.sort(key=distance_to_map_center)
        min_map_dist = distance_to_map_center(candidates[0])
        
        # Get all hexes with same minimum distance to map center
        closest_to_map_center = []
        for h in candidates:
            if abs(distance_to_map_center(h) - min_map_dist) < 0.0001:  # Float comparison
                closest_to_map_center.append(h)
            else:
                break
        
        if len(closest_to_map_center) == 1:
            return closest_to_map_center[0]
        candidates = closest_to_map_center
        
        # Tie-breaker 2: Closest to geometrical center of the province
        return self._break_tie_by_province_center_and_direction(candidates, province)
    
    def _break_tie_by_province_center_and_direction(self, candidates: List[Hex], province: Province) -> Hex:
        """
        Apply remaining tie-breakers: province center, west, north.
        """
        if len(candidates) == 1:
            return candidates[0]
        
        province_hexes = province.get_hexes()
        province_center_q = sum(h.coordinate1 for h in province_hexes) / len(province_hexes)
        province_center_r = sum(h.coordinate2 for h in province_hexes) / len(province_hexes)
        
        def distance_to_province_center(hex: Hex) -> float:
            dq = hex.coordinate1 - province_center_q
            dr = hex.coordinate2 - province_center_r
            return (dq * dq + dr * dr + (dq + dr) * (dq + dr)) ** 0.5
        
        candidates.sort(key=distance_to_province_center)
        min_province_dist = distance_to_province_center(candidates[0])
        
        # Get all hexes with same minimum distance to province center
        closest_to_province_center = []
        for h in candidates:
            if abs(distance_to_province_center(h) - min_province_dist) < 0.0001:  # Float comparison
                closest_to_province_center.append(h)
            else:
                break
        
        if len(closest_to_province_center) == 1:
            return closest_to_province_center[0]
        candidates = closest_to_province_center
        
        # Tie-breaker 3: More west (lower coordinate1)
        min_coordinate1 = min(h.coordinate1 for h in candidates)
        west_candidates = [h for h in candidates if h.coordinate1 == min_coordinate1]
        
        if len(west_candidates) == 1:
            return west_candidates[0]
        candidates = west_candidates
        
        # Tie-breaker 4: More north (higher coordinate2)
        max_coordinate2 = max(h.coordinate2 for h in candidates)
        north_candidates = [h for h in candidates if h.coordinate2 == max_coordinate2]
        
        # At this point, if there are still multiple candidates, just return the first one
        # (should be very rare)
        return north_candidates[0] if north_candidates else candidates[0]
    
    def _pick_hex_by_province_center(self, hexes: List[Hex]) -> Hex:
        """
        Fallback: Pick hex closest to province center when no enemies exist.
        """
        if not hexes:
            return None
        
        center_q = sum(h.coordinate1 for h in hexes) / len(hexes)
        center_r = sum(h.coordinate2 for h in hexes) / len(hexes)
        
        def distance_to_center(hex: Hex) -> float:
            dq = hex.coordinate1 - center_q
            dr = hex.coordinate2 - center_r
            return (dq * dq + dr * dr + (dq + dr) * (dq + dr)) ** 0.5
        
        return min(hexes, key=distance_to_center)


class ProvincesManager(IEventListener):
    """Manages all provinces in the game."""

    def __init__(self, core_model):
        """Initialize provinces manager."""
        self.core_model = core_model
        if core_model and core_model.events_manager:
            core_model.events_manager.add_listener(self)
        self.provinces: List[Province] = []
        self.builder = ProvincesBuilder(self)
        self.reduction_worker = ProvincesReductionWorker(self)
        self.current_id = 0
        self._name_generator = SimpleNameGenerator()
        self._previous_color: Optional[HColor] = None
        self._temp_unit_move_event: Optional[AbstractEvent] = None

    def add_province(self) -> Province:
        """Add a new province."""
        province = Province()
        province.set_id(self.current_id)
        self.current_id += 1
        province.set_city_name(self._name_generator.generate())
        self.provinces.append(province)
        return province

    def clear_provinces(self) -> None:
        """Clear all provinces."""
        while len(self.provinces) > 0:
            self.remove_province(self.provinces[0])

    def remove_province(self, province: Province) -> None:
        """Remove a province."""
        province.set_valid(False)
        if province in self.provinces:
            self.provinces.remove(province)

    def get_province(self, province_id: int) -> Optional[Province]:
        """Get province by ID."""
        for province in self.provinces:
            if province.get_id() == province_id:
                return province
        return None

    def get_province_by_color(self, color: HColor) -> Optional[Province]:
        """Get province by color (returns first matching)."""
        for province in self.provinces:
            if province.get_color() == color:
                return province
        return None

    def get_largest_province(self, color: HColor) -> Optional[Province]:
        """Get largest province of a color."""
        best_province = None
        for province in self.provinces:
            if province.get_color() != color:
                continue
            if best_province is None or len(province.get_hexes()) > len(
                best_province.get_hexes()
            ):
                best_province = province
        return best_province

    def get_richest_province(self, color: HColor) -> Optional[Province]:
        """Get richest province of a color."""
        best_province = None
        for province in self.provinces:
            if province.get_color() != color:
                continue
            if best_province is None or province.get_money() > best_province.get_money():
                best_province = province
        return best_province

    def get_sum_money(self, color: HColor) -> int:
        """Get sum of money for all provinces of a color."""
        total = 0
        for province in self.provinces:
            if province.get_color() == color:
                total += province.get_money()
        return total

    def find_province_slowly(self, hex: Hex) -> Optional[Province]:
        """Find province containing a hex (slow search)."""
        for province in self.provinces:
            if province.contains(hex):
                return province
        return None

    def on_event_validated(self, event: AbstractEvent) -> None:
        """Handle event validated (before application)."""
        from core.events import EventPieceBuild, EventUnitMove, EventHexChangeColor
        from core.core_utils import is_unit
        
        # Track previous color for events that change hex color
        if event.get_type() == EventType.PIECE_BUILD:
            if isinstance(event, EventPieceBuild) and event.hex:
                if is_unit(event.piece_type):
                    # Store previous color before it changes
                    self._previous_color = event.hex.color
                else:
                    self._previous_color = None
        elif event.get_type() == EventType.UNIT_MOVE:
            # Track previous color for unit moves that change hex color
            if isinstance(event, EventUnitMove) and event.finish:
                if event.are_color_transfer_conditions_satisfied():
                    # Store the event and previous color for later use
                    self._temp_unit_move_event = event
                    self._previous_color = event.finish.color
                else:
                    self._temp_unit_move_event = None
                    self._previous_color = None
        elif event.get_type() == EventType.HEX_CHANGE_COLOR:
            # Track previous color for hex color change events
            if isinstance(event, EventHexChangeColor) and event.hex:
                # Store previous color before it changes
                # If _previous_color was already set (e.g., by test), keep it
                # Otherwise, use the hex's current color
                if self._previous_color is None:
                    self._previous_color = event.hex.color
        else:
            self._previous_color = None
            self._temp_unit_move_event = None

    def on_event_applied(self, event: AbstractEvent) -> None:
        """Handle event applied."""
        from core.events import EventHexChangeColor, EventPieceBuild, EventUnitMove
        from core.core_utils import is_unit
        from core.enums import HColor

        if event.get_type() == EventType.HEX_CHANGE_COLOR:
            if isinstance(event, EventHexChangeColor):
                previous_color = getattr(self, '_previous_color', None)
                # Use the new color from the event, not the hex's current color
                # (the hex color has already been changed by apply_change())
                new_color = event.color if event.color else (event.hex.color if event.hex else None)
                if event.hex and previous_color is not None and previous_color != new_color:
                    # Hex color changed - need to update provinces
                    # First handle reduction (if hex was part of a province)
                    if previous_color != HColor.GRAY:
                        self.reduction_worker.on_hex_color_changed(event.hex, previous_color)
                    # Then handle enlargement (add hex to adjacent province of new color)
                    if new_color != HColor.GRAY:
                        self._enlarge_province_for_hex(event.hex)
                    # After province changes, ensure all provinces have cities
                    # This matches the original game's CityManager.onHexColorChanged() logic
                    if previous_color != HColor.GRAY:
                        self._fix_provinces_without_cities()
        elif event.get_type() == EventType.UNIT_MOVE:
            # Handle unit moves that change hex color (color transfer)
            if isinstance(event, EventUnitMove) and event.finish:
                # Check if this is the temp event we stored (color transfer occurred)
                if (hasattr(self, '_temp_unit_move_event') and 
                    self._temp_unit_move_event is not None and
                    self._temp_unit_move_event == event):
                    # Color transfer occurred - update provinces
                    previous_color = getattr(self, '_previous_color', None)
                    if previous_color is not None and previous_color != event.finish.color:
                        # Hex color changed - need to update provinces
                        # First handle reduction (if hex was part of a province)
                        if previous_color != HColor.GRAY:
                            self.reduction_worker.on_hex_color_changed(event.finish, previous_color)
                        # Then handle enlargement (add hex to adjacent province of new color)
                        if event.finish.color != HColor.GRAY:
                            self._enlarge_province_for_hex(event.finish)
                        # After province changes, ensure all provinces have cities
                        if previous_color != HColor.GRAY:
                            self._fix_provinces_without_cities()
                    # Clear temp event
                    self._temp_unit_move_event = None
                # Also handle the case where color transfer happened but we didn't track it
                # (fallback: check if finish hex color changed)
                elif event.are_color_transfer_conditions_satisfied():
                    # Color transfer occurred - check if hex color actually changed
                    # This is a fallback in case the temp event tracking didn't work
                    if event.finish.color != HColor.GRAY:
                        # Try to find adjacent province and add hex to it
                        self._enlarge_province_for_hex(event.finish)
        elif event.get_type() == EventType.PIECE_BUILD:
            # Handle unit builds that change hex color (e.g., building on gray hex)
            if isinstance(event, EventPieceBuild) and event.hex:
                if is_unit(event.piece_type):
                    previous_color = getattr(self, '_previous_color', None)
                    if previous_color is not None and previous_color != event.hex.color:
                        # Hex color changed - need to update provinces
                        # First handle reduction (if hex was part of a province)
                        if previous_color != HColor.GRAY:
                            self.reduction_worker.on_hex_color_changed(event.hex, previous_color)
                        # Then handle enlargement (add hex to adjacent province of new color)
                        if event.hex.color != HColor.GRAY:
                            self._enlarge_province_for_hex(event.hex)

    def _enlarge_province_for_hex(self, hex: Hex) -> None:
        """
        Enlarge province to include hex (when hex color changes to match adjacent province).
        
        This matches the original game's ProvincesEnlargementWorker.onHexColorChanged() method.
        Only processes hexes that are adjacent to hexes of the same color.
        Also adds "previously lonely hexes" (adjacent hexes of same color not in any province).
        """
        # Skip gray hexes (matching original game)
        if hex.color == HColor.GRAY:
            return
        
        # Only process hexes that are adjacent to hexes of the same color
        # This matches the original game's check: if (!hex.isAdjacentToHexesOfSameColor()) return;
        if not hex.is_adjacent_to_hexes_of_same_color():
            return
        
        # Update lists: find adjacent provinces and previously lonely hexes
        # This matches the original game's updateLists() method
        adjacent_provinces = []
        previously_lonely_hexes = []
        for adj_hex in hex.adjacent_hexes:
            if adj_hex.color != hex.color:
                continue
            province = adj_hex.get_province()
            if province and province.get_color() == hex.color:
                if province not in adjacent_provinces:
                    adjacent_provinces.append(province)
            else:
                # Adjacent hex of same color but not in any province (previously lonely)
                previously_lonely_hexes.append(adj_hex)
        
        # Determine target province and add the modified hex
        target_province = None
        if len(adjacent_provinces) == 0:
            # No adjacent province found - create new province for this hex
            # Also add previously lonely hexes to the new province
            if hex.color != HColor.GRAY:
                target_province = self.add_province()
                target_province.add_hex(hex)
                # Add previously lonely hexes (matching original game's makeTargetProvinceFromScratch)
                for lonely_hex in previously_lonely_hexes:
                    target_province.add_hex(lonely_hex)
        elif len(adjacent_provinces) == 1:
            # Single adjacent province - add hex to it
            target_province = adjacent_provinces[0]
            target_province.add_hex(hex)
            # Add previously lonely hexes (matching original game's pourInPreviouslyLonelyHexes)
            for lonely_hex in previously_lonely_hexes:
                if lonely_hex.get_province() is None:
                    target_province.add_hex(lonely_hex)
        else:
            # Multiple adjacent provinces - merge into largest and add hex
            largest_province = max(adjacent_provinces, key=lambda p: len(p.get_hexes()))
            target_province = largest_province
            largest_province.add_hex(hex)
            
            # Before merging, track which province each city belongs to
            # This is needed to update the city name after removing excessive cities
            city_to_province_map = {}
            for province in adjacent_provinces:
                for h in province.get_hexes():
                    if h.piece == PieceType.CITY:
                        city_to_province_map[h] = province
            
            # Merge other provinces into largest
            for province in adjacent_provinces:
                if province == largest_province:
                    continue
                # Transfer hexes and money
                for h in province.get_hexes():
                    largest_province.add_hex(h)
                largest_province.set_money(largest_province.get_money() + province.get_money())
                self.remove_province(province)
            
            # After merging, ensure only one city remains in the merged province
            # This matches the original game's checkToRemoveExcessiveCities() logic
            # Also update the city name to match the province whose city is kept
            self._remove_excessive_cities(largest_province, city_to_province_map)
            
            # Add previously lonely hexes (matching original game's pourInPreviouslyLonelyHexes)
            for lonely_hex in previously_lonely_hexes:
                if lonely_hex.get_province() is None:
                    target_province.add_hex(lonely_hex)

    def _fix_provinces_without_cities(self) -> None:
        """
        Ensure all provinces have at least one city.
        
        This matches the original game's CityManager.doFixProvincesWithoutCities() method.
        Called after hex color changes to ensure provinces that lost their city get a new one.
        """
        for province in self.provinces:
            # Check if province has a city
            has_city = any(hex.piece == PieceType.CITY for hex in province.get_hexes())
            if not has_city:
                # Province doesn't have a city - add one
                self.reduction_worker._add_city_to_province(province)

    def _remove_excessive_cities(self, province: Province, city_to_province_map: Optional[Dict[Hex, Province]] = None) -> None:
        """
        Remove excessive cities from a province, keeping only one.

        The city to keep is chosen by (in order):
        1) Furthest from enemy territory (same BFS walking distance as in split city placement)
        2) Most adjacent friendly farms
        3) More east (higher coordinate1)
        4) More north (higher coordinate2)

        Args:
            province: The province to process
            city_to_province_map: Optional map of city hex -> original province (before merging)
                                 Used to update the province's city name to match the kept city's original province
        """
        if not province or not self.core_model:
            return

        # Find all cities in the province
        city_hexes = []
        for hex in province.get_hexes():
            if hex.piece == PieceType.CITY:
                city_hexes.append(hex)

        if len(city_hexes) < 2:
            return

        # Choose which city to keep using the new criteria
        city_to_keep = self._find_city_to_keep_when_merging(province, city_hexes)
        if city_to_keep is None:
            city_to_keep = city_hexes[0]

        # Remove all cities except the one we keep
        for city_hex in city_hexes:
            if city_hex is city_to_keep:
                continue
            delete_event = self.core_model.events_manager.factory.create_event(EventType.PIECE_DELETE)
            from core.events import EventPieceDelete
            if isinstance(delete_event, EventPieceDelete):
                delete_event.set_hex(city_hex)
                self.core_model.events_manager.apply_event(delete_event)

        # Update the province's city name to match the kept city's original province (if we have that info)
        if city_to_province_map and city_to_keep in city_to_province_map:
            original_province = city_to_province_map[city_to_keep]
            province.set_city_name(original_province.get_city_name())

    def _find_city_to_keep_when_merging(self, province: Province, city_hexes: List[Hex]) -> Optional[Hex]:
        """
        Choose which city to keep when multiple provinces are merged into one.

        Criteria (in order):
        1) Furthest from enemy territory (BFS walking distance, same as split city placement)
        2) Most adjacent friendly farms
        3) More east (higher coordinate1)
        4) More north (higher coordinate2)
        """
        if not city_hexes:
            return None
        if len(city_hexes) == 1:
            return city_hexes[0]

        province_color = province.get_color()
        all_hexes = self.core_model.hexes if self.core_model else []
        enemy_hexes = [h for h in all_hexes if h.color != province_color and h.color != HColor.GRAY]

        # 1) Furthest from enemy territory (max of min walking distance to any enemy)
        max_dist = -1
        candidates = []
        for h in city_hexes:
            d = self.reduction_worker._calculate_min_distance_to_enemies(h, enemy_hexes)
            if d > max_dist:
                max_dist = d
                candidates = [h]
            elif d == max_dist:
                candidates.append(h)

        if len(candidates) == 1:
            return candidates[0]

        # 2) Most adjacent farms
        max_farms = -1
        candidates2 = []
        for h in candidates:
            n = self._count_adjacent_friendly_farms(h)
            if n > max_farms:
                max_farms = n
                candidates2 = [h]
            elif n == max_farms:
                candidates2.append(h)
        candidates = candidates2

        if len(candidates) == 1:
            return candidates[0]

        # 3) More east (higher coordinate1)
        max_c1 = max(h.coordinate1 for h in candidates)
        candidates = [h for h in candidates if h.coordinate1 == max_c1]

        if len(candidates) == 1:
            return candidates[0]

        # 4) More north (higher coordinate2)
        max_c2 = max(h.coordinate2 for h in candidates)
        candidates = [h for h in candidates if h.coordinate2 == max_c2]

        return candidates[0] if candidates else None

    def _count_adjacent_friendly_farms(self, hex: Hex) -> int:
        """
        Count the number of adjacent friendly farms.
        
        This matches the original game's getNumberOfAdjacentFriendlyFarms() method.
        """
        count = 0
        for adj_hex in hex.adjacent_hexes:
            # Check if adjacent hex is same color (friendly)
            if adj_hex.color != hex.color:
                continue
            # Check if it's a farm
            if adj_hex.piece == PieceType.FARM:
                count += 1
        return count

    def get_listen_priority(self) -> int:
        """Get listener priority."""
        return 7

    def encode(self) -> str:
        """Encode provinces manager to string."""
        if not self.provinces:
            return "0>"
        encoded_parts = [province.encode() for province in self.provinces]
        return f"{self.current_id}>" + ",".join(encoded_parts)

    def decode(self, source: str) -> None:
        """Decode provinces manager from string."""
        self.clear_provinces()
        if not source or source == "-":
            return
        parts = source.split(">", 1)
        if len(parts) >= 1:
            try:
                self.current_id = int(parts[0])
            except ValueError:
                self.current_id = 0
        if len(parts) < 2 or not parts[1]:
            return
        for token in parts[1].split(","):
            if not token.strip():
                continue
            province_parts = token.split("<")
            if len(parts) < 5:
                continue
            try:
                c1 = int(province_parts[0])
                c2 = int(province_parts[1])
                province_id = int(province_parts[2])
                money = int(province_parts[3])
                city_name = province_parts[4] if len(province_parts) > 4 else ""
                # Find hexes for this province - would need core_model access
                # This is a simplified decode
            except (ValueError, IndexError):
                continue


class SimpleNameGenerator:
    """Simple name generator for provinces."""

    def __init__(self):
        """Initialize name generator."""
        self.names = [
            "Resse",
            "Naclo",
            "Esyemo",
            "Kakamo",
            "Amako",
            "Kamak",
            "Akako",
            "Kakko",
            "Kama",
            "Kakako",
            "TheArmor",
            "DigitalBlood",
            "GrizzlyBreaker",
            "AcidSnake",
            "BlisteredOutlaws",
            "InvaderPenguin",
            "WarioRaptor",
            "SuperboyFallout",
            "FastClawDraw",
            "SystemSnap",
            "RedReaperSlice",
            "CoolCobra",
            "CutthroatRattler",
            "BruisedKnuckles",
            "HurricaneMachine",
            "WarlockAdmiral",
            "Damin",
            "Cytos",
            "Inkronos",
            "Grumblemoor",
        ]
        self.index = 0

    def generate(self) -> str:
        """Generate a name."""
        name = self.names[self.index % len(self.names)]
        self.index += 1
        return name
