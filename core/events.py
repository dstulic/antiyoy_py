"""Event system for game state changes."""

from abc import ABC, abstractmethod
from typing import Optional, Protocol
from core.enums import EventType, HColor, PieceType
from core.hex import Hex
from core.core_utils import is_unit


class IEventListener(Protocol):
    """Protocol for event listeners."""

    def on_event_validated(self, event: "AbstractEvent") -> None:
        """Called when event is validated."""
        ...

    def on_event_applied(self, event: "AbstractEvent") -> None:
        """Called when event is applied."""
        ...

    def get_listen_priority(self) -> int:
        """Get listener priority (lower = higher priority)."""
        ...


class AbstractEvent(ABC):
    """Abstract base class for all game events."""

    def __init__(self):
        """Initialize event."""
        self.core_model = None
        self._quick = False
        self._reusable = False
        self.author = None

    @abstractmethod
    def get_type(self) -> EventType:
        """Get the event type."""
        pass

    @abstractmethod
    def is_valid(self) -> bool:
        """Check if event is valid."""
        pass

    @abstractmethod
    def apply_change(self) -> None:
        """Apply the event's changes to the game state."""
        pass

    @abstractmethod
    def copy_from(self, src_event: "AbstractEvent") -> None:
        """Copy data from another event."""
        pass

    @abstractmethod
    def _get_local_encoded_info(self) -> str:
        """Get local encoded information for this event."""
        pass

    def encode(self) -> str:
        """Encode event to string format."""
        key = EventKeys.convert_type_to_key(self.get_type())
        return f"{key} {self._get_local_encoded_info()}"

    def is_quick(self) -> bool:
        """Check if event is quick (not notable)."""
        return self._quick

    def set_quick(self, quick: bool) -> None:
        """Set quick flag."""
        self._quick = quick

    def is_notable(self) -> bool:
        """Check if event is notable (should be recorded in history)."""
        return not self._quick and not self._reusable

    def is_reusable(self) -> bool:
        """Check if event is reusable."""
        return self._reusable

    def set_reusable(self, reusable: bool) -> None:
        """Set reusable flag."""
        self._reusable = reusable

    def set_core_model(self, core_model) -> None:
        """Set the core model reference."""
        self.core_model = core_model

    def set_author(self, author) -> None:
        """Set the author (player entity) of this event."""
        self.author = author

    def can_be_undone(self) -> bool:
        """Check if event can be undone."""
        from core.core_utils import can_be_undone
        return can_be_undone(self.get_type())

    def reset(self) -> None:
        """Reset event to initial state."""
        if not self._reusable:
            # Should not reset non-reusable events
            pass
        self._quick = False
        self.author = None

    def __str__(self) -> str:
        """Return string representation."""
        return f"[{self.__class__.__name__}]"


class SystemAuthor:
    """Sentinel author for events triggered by game logic (death, trees, init, etc.), not a player."""

    color = None
    name = "system"


# Singleton for use as event author when no player is responsible.
SYSTEM_AUTHOR = SystemAuthor()


class EventKeys:
    """Utility class for converting between EventType and string keys."""

    TYPE_TO_KEY = {
        EventType.HEX_CHANGE_COLOR: "hcc",
        EventType.SET_MONEY: "sm",
        EventType.TURN_END: "te",
        EventType.TURN_BEGIN: "tb",
        EventType.LAP_BEGIN: "lb",
        EventType.PLAYER_TURN_STATS: "pts",
        EventType.GRAPH_CREATED: "gc",
        EventType.MATCH_STARTED: "mc",
        EventType.UNIT_MOVE: "um",
        EventType.PIECE_BUILD: "pb",
        EventType.PIECE_DELETE: "pd",
        EventType.PIECE_ADD: "pa",
        EventType.MERGE_ON_BUILD: "mob",
        EventType.MERGE: "m",
        EventType.SET_RELATION_SOFTLY: "srs",
        EventType.SEND_LETTER: "sl",
        EventType.INDICATE_UNDO_LETTER: "iul",
        EventType.DECLINE_LETTER: "dl",
        EventType.APPLY_LETTER: "al",
        EventType.GIVE_MONEY: "gm",
        EventType.SUBTRACT_MONEY: "sbm",
        EventType.SET_READY: "sr",
    }

    KEY_TO_TYPE = {v: k for k, v in TYPE_TO_KEY.items()}

    @staticmethod
    def convert_type_to_key(event_type: EventType) -> str:
        """Convert EventType to string key."""
        return EventKeys.TYPE_TO_KEY.get(event_type, "-")

    @staticmethod
    def convert_key_to_type(key: str) -> Optional[EventType]:
        """Convert string key to EventType."""
        return EventKeys.KEY_TO_TYPE.get(key)


# Event implementations

class EventTurnEnd(AbstractEvent):
    """Event for ending a turn. For replay: turn_index_after/lap_after set state after switch."""

    def __init__(self):
        """Initialize turn end event."""
        super().__init__()
        self.target_end_time: int = 0
        self.current_color: Optional[HColor] = None
        self.turn_index_after: int = -1
        self.lap_after: int = -1

    def get_type(self) -> EventType:
        """Get event type."""
        return EventType.TURN_END

    def is_valid(self) -> bool:
        """Check if event is valid."""
        return True

    def apply_change(self) -> None:
        """Apply turn end."""
        tm = self.core_model.turns_manager if self.core_model else None
        if not tm:
            return
        if self.turn_index_after >= 0 and self.lap_after >= 0:
            tm.turn_index = self.turn_index_after
            tm.lap = self.lap_after
        else:
            tm.do_switch_turn_index()

    def copy_from(self, src_event: AbstractEvent) -> None:
        """Copy from another event."""
        if isinstance(src_event, EventTurnEnd):
            self.current_color = src_event.current_color
            self.target_end_time = src_event.target_end_time
            self.turn_index_after = src_event.turn_index_after
            self.lap_after = src_event.lap_after

    def _get_local_encoded_info(self) -> str:
        """Encode: target_end_time current_color turn_index_after lap_after (for replay)."""
        time_str = str(self.target_end_time) if self.target_end_time > 0 else "-"
        color_str = self.current_color.value if self.current_color else ""
        ti = self.turn_index_after if self.turn_index_after >= 0 else "-"
        lap = self.lap_after if self.lap_after >= 0 else "-"
        return f"{time_str} {color_str} {ti} {lap}"

    def set_target_end_time(self, target_end_time: int) -> None:
        """Set target end time."""
        self.target_end_time = target_end_time

    def set_current_color(self, current_color: HColor) -> None:
        """Set current color."""
        self.current_color = current_color

    def set_turn_index_lap_after(self, turn_index: int, lap: int) -> None:
        """Set turn index and lap after this turn end (for replay)."""
        self.turn_index_after = turn_index
        self.lap_after = lap


class EventTurnBegin(AbstractEvent):
    """Marker event: whose turn it is now (for replay)."""

    def __init__(self):
        super().__init__()
        self.turn_index: int = 0
        self.lap: int = 0
        self.color: Optional[HColor] = None

    def get_type(self) -> EventType:
        return EventType.TURN_BEGIN

    def is_valid(self) -> bool:
        return True

    def apply_change(self) -> None:
        if self.core_model and self.core_model.turns_manager:
            self.core_model.turns_manager.turn_index = self.turn_index
            self.core_model.turns_manager.lap = self.lap

    def copy_from(self, src_event: AbstractEvent) -> None:
        if isinstance(src_event, EventTurnBegin):
            self.turn_index = src_event.turn_index
            self.lap = src_event.lap
            self.color = src_event.color

    def _get_local_encoded_info(self) -> str:
        ti = str(self.turn_index)
        lap = str(self.lap)
        color_str = self.color.value if self.color else ""
        return f"{ti} {lap} {color_str}"

    def set_turn_index(self, v: int) -> None:
        self.turn_index = v

    def set_lap(self, v: int) -> None:
        self.lap = v

    def set_color(self, c: HColor) -> None:
        self.color = c


class EventLapBegin(AbstractEvent):
    """Marker event: start of a new lap (for replay)."""

    def __init__(self):
        super().__init__()
        self.lap: int = 0

    def get_type(self) -> EventType:
        return EventType.LAP_BEGIN

    def is_valid(self) -> bool:
        return True

    def apply_change(self) -> None:
        if self.core_model and self.core_model.turns_manager:
            self.core_model.turns_manager.lap = self.lap

    def copy_from(self, src_event: AbstractEvent) -> None:
        if isinstance(src_event, EventLapBegin):
            self.lap = src_event.lap

    def _get_local_encoded_info(self) -> str:
        return str(self.lap)

    def set_lap(self, v: int) -> None:
        self.lap = v


class EventPlayerTurnStats(AbstractEvent):
    """Cumulative money and income for a player at end of their turn (for replay/verification)."""

    def __init__(self):
        super().__init__()
        self.color: Optional[HColor] = None
        self.total_money: int = 0
        self.total_income: int = 0

    def get_type(self) -> EventType:
        return EventType.PLAYER_TURN_STATS

    def is_valid(self) -> bool:
        return True

    def apply_change(self) -> None:
        pass

    def copy_from(self, src_event: AbstractEvent) -> None:
        if isinstance(src_event, EventPlayerTurnStats):
            self.color = src_event.color
            self.total_money = src_event.total_money
            self.total_income = src_event.total_income

    def _get_local_encoded_info(self) -> str:
        color_str = self.color.value if self.color else ""
        return f"{color_str} {self.total_money} {self.total_income}"

    def set_color(self, c: HColor) -> None:
        self.color = c

    def set_total_money(self, v: int) -> None:
        self.total_money = v

    def set_total_income(self, v: int) -> None:
        self.total_income = v


class EventHexChangeColor(AbstractEvent):
    """Event for changing hex color."""

    def __init__(self):
        """Initialize hex change color event."""
        super().__init__()
        self.hex: Optional[Hex] = None
        self.color: Optional[HColor] = None

    def get_type(self) -> EventType:
        """Get event type."""
        return EventType.HEX_CHANGE_COLOR

    def is_valid(self) -> bool:
        """Check if event is valid."""
        return self.hex is not None and self.color is not None

    def apply_change(self) -> None:
        """Apply color change."""
        if self.hex:
            self.hex.set_color(self.color)

    def copy_from(self, src_event: AbstractEvent) -> None:
        """Copy from another event."""
        if isinstance(src_event, EventHexChangeColor) and self.core_model:
            # Find hex with same coordinates
            if src_event.hex:
                self.hex = self.core_model.get_hex_with_same_coordinates(src_event.hex)
            self.color = src_event.color

    def _get_local_encoded_info(self) -> str:
        """Get encoded info."""
        if self.hex and self.color:
            return f"{self.hex.coordinate1} {self.hex.coordinate2} {self.color.value}"
        return ""

    def set_hex(self, hex: Hex) -> None:
        """Set hex."""
        self.hex = hex

    def set_color(self, color: HColor) -> None:
        """Set color."""
        self.color = color


class EventUnitMove(AbstractEvent):
    """Event for moving a unit."""

    def __init__(self):
        """Initialize unit move event."""
        super().__init__()
        self.start: Optional[Hex] = None
        self.finish: Optional[Hex] = None
        self.color_transfer_enabled: bool = True

    def get_type(self) -> EventType:
        """Get event type."""
        return EventType.UNIT_MOVE

    def is_valid(self) -> bool:
        """
        Check if event is valid.
        
        This matches the original game's EventUnitMove.isValid() method.
        """
        if self.start is None or self.finish is None:
            return False
        if not self.start.has_unit():
            return False
        
        # Check if start hex has a province (required for tree cutting)
        if self.start.get_province() is None and self.finish.has_tree():
            return False
        
        # Check readiness (if not quick event)
        if not self.is_quick() and self.core_model and self.core_model.readiness_manager:
            if not self.core_model.readiness_manager.is_ready(self.start):
                return False
        
        # Check move zone for color transfer (enemy hex capture); skip for quick/replay events
        if not self.is_quick() and self.are_color_transfer_conditions_satisfied():
            if self.core_model and self.core_model.move_zone_manager:
                self.core_model.move_zone_manager.update_for_unit(self.start)
                if not self.core_model.move_zone_manager.contains(self.finish):
                    return False
        
        # Check same-color static piece movement (only trees and graves allowed)
        if self.start.color == self.finish.color and self.finish.has_static_piece():
            from core.enums import PieceType
            return self.finish.has_tree() or self.finish.piece == PieceType.GRAVE
        
        return True

    def apply_change(self) -> None:
        """Apply unit move."""
        if self.start is None or self.finish is None:
            return
        # Move piece and unit_id
        self.finish.set_piece(self.start.piece)
        self.finish.set_unit_id(self.start.unit_id)
        self.start.set_piece(None)
        self.start.set_unit_id(-1)
        # Color transfer if enabled
        if self.are_color_transfer_conditions_satisfied():
            self.finish.set_color(self.start.color)

    def are_color_transfer_conditions_satisfied(self) -> bool:
        """Check if color transfer conditions are satisfied."""
        if self.start is None or self.finish is None:
            return False
        return self.color_transfer_enabled and self.start.color != self.finish.color

    def copy_from(self, src_event: AbstractEvent) -> None:
        """Copy from another event."""
        if isinstance(src_event, EventUnitMove) and self.core_model:
            if src_event.start:
                self.start = self.core_model.get_hex_with_same_coordinates(src_event.start)
            if src_event.finish:
                self.finish = self.core_model.get_hex_with_same_coordinates(src_event.finish)
            self.color_transfer_enabled = src_event.color_transfer_enabled

    def _get_local_encoded_info(self) -> str:
        """Get encoded info."""
        if self.start and self.finish:
            ct_str = "1" if self.color_transfer_enabled else "0"
            return (
                f"{self.start.coordinate1} {self.start.coordinate2} "
                f"{self.finish.coordinate1} {self.finish.coordinate2} {ct_str}"
            )
        return ""

    def set_start(self, start: Hex) -> None:
        """Set start hex."""
        self.start = start

    def set_finish(self, finish: Hex) -> None:
        """Set finish hex."""
        self.finish = finish

    def set_color_transfer_enabled(self, enabled: bool) -> None:
        """Set color transfer enabled."""
        self.color_transfer_enabled = enabled


class EventPieceAdd(AbstractEvent):
    """Event for adding a piece."""

    def __init__(self):
        """Initialize piece add event."""
        super().__init__()
        self.hex: Optional[Hex] = None
        self.piece_type: Optional[PieceType] = None
        self.unit_id: int = -1

    def get_type(self) -> EventType:
        """Get event type."""
        return EventType.PIECE_ADD

    def is_valid(self) -> bool:
        """Check if event is valid."""
        if self.hex is None or self.piece_type is None:
            return False
        if self.hex.has_piece():
            return False
        if is_unit(self.piece_type) and self.unit_id == -1:
            return False
        return True

    def apply_change(self) -> None:
        """Apply piece add."""
        if self.hex:
            self.hex.set_piece(self.piece_type)
            if is_unit(self.piece_type):
                self.hex.set_unit_id(self.unit_id)

    def copy_from(self, src_event: AbstractEvent) -> None:
        """Copy from another event."""
        if isinstance(src_event, EventPieceAdd) and self.core_model:
            if src_event.hex:
                self.hex = self.core_model.get_hex_with_same_coordinates(src_event.hex)
            self.piece_type = src_event.piece_type
            self.unit_id = src_event.unit_id

    def _get_local_encoded_info(self) -> str:
        """Get encoded info."""
        if self.hex and self.piece_type:
            return f"{self.hex.coordinate1} {self.hex.coordinate2} {self.piece_type.value} {self.unit_id}"
        return ""

    def set_hex(self, hex: Hex) -> None:
        """Set hex."""
        self.hex = hex

    def set_piece_type(self, piece_type: PieceType) -> None:
        """Set piece type."""
        self.piece_type = piece_type

    def set_unit_id(self, unit_id: int) -> None:
        """Set unit ID."""
        self.unit_id = unit_id


class EventPieceDelete(AbstractEvent):
    """Event for deleting a piece."""

    def __init__(self):
        """Initialize piece delete event."""
        super().__init__()
        self.hex: Optional[Hex] = None

    def get_type(self) -> EventType:
        """Get event type."""
        return EventType.PIECE_DELETE

    def is_valid(self) -> bool:
        """Check if event is valid."""
        return self.hex is not None and self.hex.has_piece()

    def apply_change(self) -> None:
        """Apply piece delete."""
        if self.hex:
            self.hex.set_piece(None)
            self.hex.set_unit_id(-1)

    def copy_from(self, src_event: AbstractEvent) -> None:
        """Copy from another event."""
        if isinstance(src_event, EventPieceDelete) and self.core_model:
            if src_event.hex:
                self.hex = self.core_model.get_hex_with_same_coordinates(src_event.hex)

    def _get_local_encoded_info(self) -> str:
        """Get encoded info."""
        if self.hex:
            return f"{self.hex.coordinate1} {self.hex.coordinate2}"
        return ""

    def set_hex(self, hex: Hex) -> None:
        """Set hex."""
        self.hex = hex


class EventPieceBuild(AbstractEvent):
    """Event for building a piece."""

    def __init__(self):
        """Initialize piece build event."""
        super().__init__()
        self.hex: Optional[Hex] = None
        self.piece_type: Optional[PieceType] = None
        self.unit_id: int = -1
        self.province_id: int = -1

    def get_type(self) -> EventType:
        """Get event type."""
        return EventType.PIECE_BUILD

    def is_valid(self) -> bool:
        """Check if event is valid."""
        # Basic validation - full validation requires ruleset
        if self.hex is None or self.piece_type is None:
            return False
        if is_unit(self.piece_type) and self.unit_id == -1:
            return False
        return True

    def apply_change(self) -> None:
        """Apply piece build."""
        if not self.core_model or not self.hex or not self.piece_type:
            return
        
        # Get province
        province = None
        if self.province_id != -1 and self.core_model.provinces_manager:
            province = self.core_model.provinces_manager.get_province(self.province_id)
        
        if not province:
            return
        
        # Calculate price before applying changes (price may change after)
        price = 0
        if self.core_model.ruleset:
            price = self.core_model.ruleset.get_price(province, self.piece_type)
        
        # Check if hex was empty and in province before building (for readiness)
        was_empty = self.hex.is_empty()
        was_in_province = self.hex.color == province.get_color()
        
        # Handle tree reward (if cutting down a tree)
        if self.hex.has_tree() and self.hex.color == province.get_color():
            if self.core_model.ruleset:
                reward = self.core_model.ruleset.get_tree_reward()
                province.set_money(province.get_money() + reward)
        
        # Set piece on hex and claim hex for province (so replay matches saved state)
        self.hex.set_piece(self.piece_type)
        self.hex.set_color(province.get_color())
        
        # For units, set unit ID
        if is_unit(self.piece_type):
            self.hex.set_unit_id(self.unit_id)
            
            # Set readiness: unit is ready only if built on empty hex within province
            # If built on gray hex (outside province), it counts as a move and is not ready
            ready = False
            if was_empty and was_in_province:
                if self.core_model.ruleset and self.core_model.ruleset.is_unit_ready_on_built():
                    ready = True
            
            if self.core_model.readiness_manager:
                self.core_model.readiness_manager.set_ready(self.hex, ready)
        
        # Deduct money from province
        province.set_money(province.get_money() - price)

    def copy_from(self, src_event: AbstractEvent) -> None:
        """Copy from another event."""
        if isinstance(src_event, EventPieceBuild) and self.core_model:
            if src_event.hex:
                self.hex = self.core_model.get_hex_with_same_coordinates(src_event.hex)
            self.piece_type = src_event.piece_type
            self.unit_id = src_event.unit_id
            self.province_id = src_event.province_id

    def _get_local_encoded_info(self) -> str:
        """Get encoded info."""
        if self.hex and self.piece_type:
            return (
                f"{self.hex.coordinate1} {self.hex.coordinate2} "
                f"{self.piece_type.value} {self.unit_id} {self.province_id}"
            )
        return ""

    def set_hex(self, hex: Hex) -> None:
        """Set hex."""
        self.hex = hex

    def set_piece_type(self, piece_type: PieceType) -> None:
        """Set piece type."""
        self.piece_type = piece_type

    def set_unit_id(self, unit_id: int) -> None:
        """Set unit ID."""
        self.unit_id = unit_id

    def set_province_id(self, province_id: int) -> None:
        """Set province ID."""
        self.province_id = province_id


class EventSetMoney(AbstractEvent):
    """Event for setting province money."""

    def __init__(self):
        """Initialize set money event."""
        super().__init__()
        self.province_id: int = -1
        self.money: int = 0

    def get_type(self) -> EventType:
        """Get event type."""
        return EventType.SET_MONEY

    def is_valid(self) -> bool:
        """Check if event is valid."""
        return self.province_id != -1

    def apply_change(self) -> None:
        """Apply money change."""
        if self.core_model and self.core_model.provinces_manager:
            province = self.core_model.provinces_manager.get_province(self.province_id)
            if province:
                province.set_money(self.money)

    def copy_from(self, src_event: AbstractEvent) -> None:
        """Copy from another event."""
        if isinstance(src_event, EventSetMoney):
            self.province_id = src_event.province_id
            self.money = src_event.money

    def _get_local_encoded_info(self) -> str:
        """Get encoded info."""
        return f"{self.province_id} {self.money}"

    def set_province_id(self, province_id: int) -> None:
        """Set province ID."""
        self.province_id = province_id

    def set_money(self, money: int) -> None:
        """Set money."""
        self.money = money


# Placeholder events for remaining types
# These can be fully implemented later as needed

class EventGraphCreated(AbstractEvent):
    """Event for graph creation."""

    def get_type(self) -> EventType:
        return EventType.GRAPH_CREATED

    def is_valid(self) -> bool:
        return True

    def apply_change(self) -> None:
        pass

    def copy_from(self, src_event: AbstractEvent) -> None:
        pass

    def _get_local_encoded_info(self) -> str:
        return ""


class EventMatchStarted(AbstractEvent):
    """Event for match start."""

    def get_type(self) -> EventType:
        return EventType.MATCH_STARTED

    def is_valid(self) -> bool:
        return True

    def apply_change(self) -> None:
        pass

    def copy_from(self, src_event: AbstractEvent) -> None:
        pass

    def _get_local_encoded_info(self) -> str:
        return ""


class EventMerge(AbstractEvent):
    """Event for merging units (when moving a unit onto another unit)."""

    def __init__(self):
        super().__init__()
        self.start: Optional[Hex] = None
        self.finish: Optional[Hex] = None
        self.unit_id: int = -1

    def get_type(self) -> EventType:
        return EventType.MERGE

    def is_valid(self) -> bool:
        """Check if merge event is valid."""
        if self.start is None or self.finish is None:
            return False
        if self.unit_id == -1:
            return False
        if not self.start.has_unit():
            return False
        if not self.finish.has_unit():
            return False
        if self.start.color != self.finish.color:
            return False
        # Check if both hexes are in the same province
        if self.start.get_province() != self.finish.get_province():
            return False
        # Check if merge result is valid
        from core.core_utils import get_merge_result
        if get_merge_result(self.start.piece, self.finish.piece) is None:
            return False
        return True

    def apply_change(self) -> None:
        """Apply unit merge."""
        if not self.core_model or not self.start or not self.finish:
            return
        
        from core.core_utils import get_merge_result
        merge_result = get_merge_result(self.start.piece, self.finish.piece)
        if merge_result is None:
            return
        
        # Merge: remove unit from start hex, merge into finish hex
        self.start.set_piece(None)
        self.start.set_unit_id(-1)
        self.finish.set_piece(merge_result)
        self.finish.set_unit_id(self.unit_id)
        # TODO: Handle readiness manager when implemented

    def copy_from(self, src_event: AbstractEvent) -> None:
        """Copy from another event."""
        if isinstance(src_event, EventMerge) and self.core_model:
            if src_event.start:
                self.start = self.core_model.get_hex_with_same_coordinates(src_event.start)
            if src_event.finish:
                self.finish = self.core_model.get_hex_with_same_coordinates(src_event.finish)
            self.unit_id = src_event.unit_id

    def _get_local_encoded_info(self) -> str:
        """Get encoded info."""
        if self.start and self.finish:
            return (
                f"{self.start.coordinate1} {self.start.coordinate2} "
                f"{self.finish.coordinate1} {self.finish.coordinate2} {self.unit_id}"
            )
        return ""

    def set_start(self, start: Hex) -> None:
        """Set start hex."""
        self.start = start

    def set_finish(self, finish: Hex) -> None:
        """Set finish hex."""
        self.finish = finish

    def set_unit_id(self, unit_id: int) -> None:
        """Set unit ID."""
        self.unit_id = unit_id


class EventMergeOnBuild(AbstractEvent):
    """Event for merging units when building a new unit on an existing unit."""

    def __init__(self):
        super().__init__()
        self.hex: Optional[Hex] = None
        self.piece_type: Optional[PieceType] = None
        self.unit_id: int = -1
        self.province_id: int = -1

    def get_type(self) -> EventType:
        return EventType.MERGE_ON_BUILD

    def is_valid(self) -> bool:
        """Check if merge on build event is valid."""
        if self.hex is None or self.piece_type is None:
            return False
        if self.unit_id == -1:
            return False
        if self.province_id == -1:
            return False
        
        from core.core_utils import is_unit
        if not is_unit(self.piece_type):
            return False
        
        if not self.core_model or not self.core_model.ruleset:
            return False
        
        if not self.core_model.ruleset.is_buildable(self.piece_type):
            return False
        
        # Get province
        province = None
        if self.core_model.provinces_manager:
            province = self.core_model.provinces_manager.get_province(self.province_id)
        
        if not province:
            return False
        
        # Check if province can afford it
        if not self.core_model.ruleset:
            return False
        price = self.core_model.ruleset.get_price(province, self.piece_type)
        if province.get_money() < price:
            return False
        
        # Check if hex has a unit to merge with
        if not self.hex.has_unit():
            return False
        
        # Check if hex color matches province color (peaceful merge)
        if self.hex.color != province.get_color():
            return False
        
        # Check if merge result is valid
        from core.core_utils import get_merge_result
        if get_merge_result(self.piece_type, self.hex.piece) is None:
            return False
        
        return True

    def apply_change(self) -> None:
        """Apply merge on build."""
        if not self.core_model or not self.hex or not self.piece_type:
            return
        
        # Get province
        province = None
        if self.province_id != -1 and self.core_model.provinces_manager:
            province = self.core_model.provinces_manager.get_province(self.province_id)
        
        if not province:
            return
        
        # Calculate price
        price = 0
        if self.core_model.ruleset:
            price = self.core_model.ruleset.get_price(province, self.piece_type)
        
        # Merge the units
        from core.core_utils import get_merge_result
        merge_result = get_merge_result(self.piece_type, self.hex.piece)
        if merge_result is None:
            return
        
        self.hex.set_piece(merge_result)
        self.hex.set_unit_id(self.unit_id)
        
        # Deduct money from province
        province.set_money(province.get_money() - price)
        
        # TODO: Handle readiness manager when implemented

    def copy_from(self, src_event: AbstractEvent) -> None:
        """Copy from another event."""
        if isinstance(src_event, EventMergeOnBuild) and self.core_model:
            if src_event.hex:
                self.hex = self.core_model.get_hex_with_same_coordinates(src_event.hex)
            self.piece_type = src_event.piece_type
            self.unit_id = src_event.unit_id
            self.province_id = src_event.province_id

    def _get_local_encoded_info(self) -> str:
        """Get encoded info."""
        if self.hex and self.piece_type:
            return (
                f"{self.hex.coordinate1} {self.hex.coordinate2} "
                f"{self.piece_type.value} {self.unit_id} {self.province_id}"
            )
        return ""

    def set_hex(self, hex: Hex) -> None:
        """Set hex."""
        self.hex = hex

    def set_piece_type(self, piece_type: PieceType) -> None:
        """Set piece type."""
        self.piece_type = piece_type

    def set_unit_id(self, unit_id: int) -> None:
        """Set unit ID."""
        self.unit_id = unit_id

    def set_province_id(self, province_id: int) -> None:
        """Set province ID."""
        self.province_id = province_id


class EventSetRelationSoftly(AbstractEvent):
    """Event for setting diplomatic relation."""

    def __init__(self):
        super().__init__()
        self.color1: Optional[HColor] = None
        self.color2: Optional[HColor] = None
        self.relation = None

    def get_type(self) -> EventType:
        return EventType.SET_RELATION_SOFTLY

    def is_valid(self) -> bool:
        return self.color1 is not None and self.color2 is not None

    def apply_change(self) -> None:
        pass  # TODO: Implement relation setting

    def copy_from(self, src_event: AbstractEvent) -> None:
        pass

    def _get_local_encoded_info(self) -> str:
        return ""


class EventSendLetter(AbstractEvent):
    """Event for sending diplomatic letter."""

    def get_type(self) -> EventType:
        return EventType.SEND_LETTER

    def is_valid(self) -> bool:
        return True

    def apply_change(self) -> None:
        pass

    def copy_from(self, src_event: AbstractEvent) -> None:
        pass

    def _get_local_encoded_info(self) -> str:
        return ""


class EventIndicateUndoLetter(AbstractEvent):
    """Event for indicating undo letter."""

    def get_type(self) -> EventType:
        return EventType.INDICATE_UNDO_LETTER

    def is_valid(self) -> bool:
        return True

    def apply_change(self) -> None:
        pass

    def copy_from(self, src_event: AbstractEvent) -> None:
        pass

    def _get_local_encoded_info(self) -> str:
        return ""


class EventDeclineLetter(AbstractEvent):
    """Event for declining letter."""

    def get_type(self) -> EventType:
        return EventType.DECLINE_LETTER

    def is_valid(self) -> bool:
        return True

    def apply_change(self) -> None:
        pass

    def copy_from(self, src_event: AbstractEvent) -> None:
        pass

    def _get_local_encoded_info(self) -> str:
        return ""


class EventApplyLetter(AbstractEvent):
    """Event for applying letter."""

    def get_type(self) -> EventType:
        return EventType.APPLY_LETTER

    def is_valid(self) -> bool:
        return True

    def apply_change(self) -> None:
        pass

    def copy_from(self, src_event: AbstractEvent) -> None:
        pass

    def _get_local_encoded_info(self) -> str:
        return ""


class EventGiveMoney(AbstractEvent):
    """Event for giving money."""

    def __init__(self):
        super().__init__()
        self.province_id: int = -1
        self.amount: int = 0

    def get_type(self) -> EventType:
        return EventType.GIVE_MONEY

    def is_valid(self) -> bool:
        return self.province_id != -1

    def apply_change(self) -> None:
        if self.core_model and self.core_model.provinces_manager:
            province = self.core_model.provinces_manager.get_province(self.province_id)
            if province:
                province.set_money(province.get_money() + self.amount)

    def copy_from(self, src_event: AbstractEvent) -> None:
        if isinstance(src_event, EventGiveMoney):
            self.province_id = src_event.province_id
            self.amount = src_event.amount

    def _get_local_encoded_info(self) -> str:
        return f"{self.province_id} {self.amount}"


class EventSubtractMoney(AbstractEvent):
    """Event for subtracting money."""

    def __init__(self):
        super().__init__()
        self.province_id: int = -1
        self.amount: int = 0

    def get_type(self) -> EventType:
        return EventType.SUBTRACT_MONEY

    def is_valid(self) -> bool:
        return self.province_id != -1

    def apply_change(self) -> None:
        if self.core_model and self.core_model.provinces_manager:
            province = self.core_model.provinces_manager.get_province(self.province_id)
            if province:
                province.set_money(max(0, province.get_money() - self.amount))

    def copy_from(self, src_event: AbstractEvent) -> None:
        if isinstance(src_event, EventSubtractMoney):
            self.province_id = src_event.province_id
            self.amount = src_event.amount

    def _get_local_encoded_info(self) -> str:
        return f"{self.province_id} {self.amount}"


class EventSetReady(AbstractEvent):
    """Event for setting ready state."""

    def get_type(self) -> EventType:
        return EventType.SET_READY

    def is_valid(self) -> bool:
        return True

    def apply_change(self) -> None:
        pass

    def copy_from(self, src_event: AbstractEvent) -> None:
        pass

    def _get_local_encoded_info(self) -> str:
        return ""


class EventsFactory:
    """Factory for creating events."""

    def __init__(self, events_manager: "EventsManager"):
        """Initialize factory."""
        self.events_manager = events_manager

    def create_event(self, event_type: EventType, author=SYSTEM_AUTHOR) -> Optional[AbstractEvent]:
        """Create an event of the specified type. author is required (default SYSTEM_AUTHOR)."""
        event_map = {
            EventType.PIECE_ADD: EventPieceAdd,
            EventType.UNIT_MOVE: EventUnitMove,
            EventType.PIECE_DELETE: EventPieceDelete,
            EventType.TURN_END: EventTurnEnd,
            EventType.TURN_BEGIN: EventTurnBegin,
            EventType.LAP_BEGIN: EventLapBegin,
            EventType.PLAYER_TURN_STATS: EventPlayerTurnStats,
            EventType.HEX_CHANGE_COLOR: EventHexChangeColor,
            EventType.SET_MONEY: EventSetMoney,
            EventType.PIECE_BUILD: EventPieceBuild,
            EventType.GRAPH_CREATED: EventGraphCreated,
            EventType.MATCH_STARTED: EventMatchStarted,
            EventType.MERGE: EventMerge,
            EventType.MERGE_ON_BUILD: EventMergeOnBuild,
            EventType.SET_RELATION_SOFTLY: EventSetRelationSoftly,
            EventType.SEND_LETTER: EventSendLetter,
            EventType.INDICATE_UNDO_LETTER: EventIndicateUndoLetter,
            EventType.DECLINE_LETTER: EventDeclineLetter,
            EventType.APPLY_LETTER: EventApplyLetter,
            EventType.GIVE_MONEY: EventGiveMoney,
            EventType.SUBTRACT_MONEY: EventSubtractMoney,
            EventType.SET_READY: EventSetReady,
        }
        event_class = event_map.get(event_type)
        if event_class:
            event = event_class()
            event.set_core_model(self.events_manager.core_model)
            event.set_author(author)
            return event
        return None


class EventsManager:
    """Manages game events."""

    def __init__(self, core_model):
        """Initialize events manager."""
        self.core_model = core_model
        self.factory = EventsFactory(self)
        self.event_listeners: list[IEventListener] = []
        self.automatic_utilization = True

    def add_listener(self, listener: IEventListener) -> None:
        """Add an event listener."""
        if listener not in self.event_listeners:
            self.event_listeners.append(listener)
            # Sort by priority
            self.event_listeners.sort(key=lambda l: l.get_listen_priority())

    def remove_listener(self, listener: IEventListener) -> None:
        """Remove an event listener."""
        if listener in self.event_listeners:
            self.event_listeners.remove(listener)

    def apply_event(self, event: AbstractEvent, author=None) -> None:
        """Apply an event. If author is passed, set it on the event. If event.author is still None, set SYSTEM_AUTHOR."""
        if not event.is_valid():
            return
        if author is not None:
            event.set_author(author)
        if author is None and event.author is None:
            assert False, "Event author is not set and no author was passed"
        # if event.author is None:
        #     event.set_author(SYSTEM_AUTHOR)
        # Notify listeners of validation
        for listener in self.event_listeners:
            listener.on_event_validated(event)
        # Apply the change
        event.apply_change()
        # Notify listeners of application
        for listener in self.event_listeners:
            listener.on_event_applied(event)

    def apply_multiple_events(self, events: list[AbstractEvent]) -> None:
        """Apply multiple events."""
        for event in events:
            self.apply_event(event)
        # Check for quick events
        if any(event.is_quick() for event in events):
            if hasattr(self.core_model, "on_quick_event_applied"):
                self.core_model.on_quick_event_applied()
