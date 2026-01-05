"""Province management for the game."""

from typing import Optional, List, Callable
from core.hex import Hex
from core.enums import HColor, PieceType
from core.events import IEventListener, AbstractEvent
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
        self.modified_province = hex.get_province()
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
        if not self.previous_color:
            return
        hexes = (
            self.provinces_manager.core_model.hexes
            if self.provinces_manager.core_model
            else []
        )
        for hex in hexes:
            if hex.flag:
                continue
            if hex.color != self.previous_color:
                continue
            if not hex.is_adjacent_to_hexes_of_same_color():
                continue
            cluster = PrwCluster()
            self.current_cluster = cluster
            self.wave_worker.apply(hex)
            if len(cluster.hexes) > 0:
                self.clusters.append(cluster)

    def _handle_simple_situations(self) -> None:
        """Handle simple situations (no split, single hex removal)."""
        if len(self.clusters) == 0:
            if self.modified_province:
                self.provinces_manager.remove_province(self.modified_province)
            return
        if len(self.clusters) == 1:
            # Single cluster - just update province
            cluster = self.clusters[0]
            if self.modified_province:
                # Remove hexes not in cluster
                hexes_to_remove = [
                    h
                    for h in self.modified_province.get_hexes()
                    if h not in cluster.hexes
                ]
                for h in hexes_to_remove:
                    self.modified_province.remove_hex(h)
            return
        # Multiple clusters - handle split
        self._handle_split_situation()

    def _handle_split_situation(self) -> None:
        """Handle province split into multiple clusters."""
        self._update_successor_cluster()
        self._modify_province_to_match_successor_cluster()
        self._make_provinces_for_rest_of_clusters()

    def _update_successor_cluster(self) -> None:
        """Update successor cluster (largest or contains most money)."""
        if not self.modified_province:
            self.successor_cluster = self.clusters[0] if self.clusters else None
            return
        # Find cluster with most hexes from original province
        best_cluster = None
        best_count = 0
        for cluster in self.clusters:
            count = sum(1 for h in cluster.hexes if self.modified_province.contains(h))
            if count > best_count:
                best_count = count
                best_cluster = cluster
        self.successor_cluster = best_cluster or (self.clusters[0] if self.clusters else None)

    def _modify_province_to_match_successor_cluster(self) -> None:
        """Modify province to match successor cluster."""
        if not self.modified_province or not self.successor_cluster:
            return
        # Remove hexes not in successor cluster
        hexes_to_remove = [
            h
            for h in self.modified_province.get_hexes()
            if h not in self.successor_cluster.hexes
        ]
        for h in hexes_to_remove:
            self.modified_province.remove_hex(h)

    def _make_provinces_for_rest_of_clusters(self) -> None:
        """Create new provinces for remaining clusters."""
        for cluster in self.clusters:
            if cluster == self.successor_cluster:
                continue
            if len(cluster.hexes) < 1:
                continue
            province = self.provinces_manager.add_province()
            for hex in cluster.hexes:
                province.add_hex(hex)


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
        """Handle event validated."""
        pass

    def on_event_applied(self, event: AbstractEvent) -> None:
        """Handle event applied."""
        from core.events import EventHexChangeColor

        if event.get_type() == EventType.HEX_CHANGE_COLOR:
            if isinstance(event, EventHexChangeColor):
                previous_color = None
                if event.hex:
                    # Need to track previous color - this is a simplification
                    # In full implementation, we'd track this properly
                    pass
                # Trigger reduction worker
                if event.hex and previous_color:
                    self.reduction_worker.on_hex_color_changed(event.hex, previous_color)

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
        ]
        self.index = 0

    def generate(self) -> str:
        """Generate a name."""
        name = self.names[self.index % len(self.names)]
        self.index += 1
        return name
