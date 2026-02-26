"""History manager for tracking game events and recording hex snapshots for replay."""

from typing import List, Optional
from core.events import IEventListener, AbstractEvent
from core.enums import EventType, HColor


class HistoryEvent:
    """Represents a historical event with author information."""

    def __init__(self, event: AbstractEvent, author_color: Optional[HColor] = None, author_name: Optional[str] = None):
        self.event = event
        self.author_color = author_color
        self.author_name = author_name

    def encode(self) -> str:
        """Format: <event_encoding>|author:<color>:<name> or |author:system or |author:-"""
        event_encoding = self.event.encode()
        if self.author_color:
            author_str = f"{self.author_color.value}"
            if self.author_name:
                author_str += f":{self.author_name}"
            return f"{event_encoding}|author:{author_str}"
        if self.author_name:
            return f"{event_encoding}|author:{self.author_name}"
        return f"{event_encoding}|author:-"

    def __str__(self) -> str:
        author_info = "Unknown"
        if self.author_color:
            author_info = self.author_color.value
            if self.author_name:
                author_info += f" ({self.author_name})"
        elif self.author_name:
            author_info = self.author_name
        return f"{self.event.get_type().value} by {author_info}"


def _snapshot_hexes(game_state) -> str:
    """Capture full hex state: 'c1 c2 color [piece unit_id], ...'  (same format as hexes section)."""
    return game_state.encode_hexes()


def _snapshot_provinces(game_state) -> str:
    """Capture province state (id, money, color) for each province."""
    parts = []
    pm = getattr(game_state, "provinces_manager", None)
    if not pm:
        return ""
    for p in pm.provinces:
        first_hex = p.get_first_hex()
        if first_hex is None:
            continue
        parts.append(f"{first_hex.coordinate1} {first_hex.coordinate2} {p.get_id()} {p.get_money()} {p.get_color().value if p.get_color() else 'gray'}")
    return ";".join(parts)


def _snapshot_turn(game_state) -> str:
    """Capture turn_index and lap."""
    tm = getattr(game_state, "turns_manager", None)
    if not tm:
        return "0 0"
    return f"{tm.turn_index} {tm.lap}"


def _snapshot_entities(game_state) -> str:
    """Capture entity list: 'type color name;...'"""
    em = getattr(game_state, "entities_manager", None)
    if not em or not em.entities:
        return ""
    parts = []
    for e in em.entities:
        t = e.type.value if hasattr(e.type, "value") else str(e.type)
        c = e.color.value if hasattr(e.color, "value") else str(e.color)
        parts.append(f"{t} {c} {e.name}")
    return ";".join(parts)


def _hex_str_to_token_map(hex_str: str) -> dict:
    """Parse a full hex string into {(c1,c2): token_str}."""
    result = {}
    if not hex_str or hex_str == "-":
        return result
    for token in hex_str.split(","):
        token = token.strip()
        if not token:
            continue
        parts = token.split(" ")
        if len(parts) >= 2:
            try:
                result[(int(parts[0]), int(parts[1]))] = token
            except ValueError:
                continue
    return result


def _compute_hex_diff(prev_map: dict, current_hexes: str) -> tuple:
    """Compute a hex diff against the previous state.
    Returns (hex_string_for_snapshot, updated_token_map).
    First snapshot (empty prev_map) is stored as full state; subsequent ones as 'D:' prefixed diffs."""
    new_map = _hex_str_to_token_map(current_hexes)
    if not prev_map:
        return current_hexes, new_map
    changed = [token for key, token in new_map.items()
               if prev_map.get(key) != token]
    return "D:" + ",".join(changed), new_map


class ReplaySnapshot:
    """A game-state snapshot recorded at a step boundary during the live game.
    The hexes field is either a full hex string or a 'D:'-prefixed diff containing
    only the hex tokens that changed since the previous snapshot."""

    def __init__(self, hexes: str, provinces: str, turn: str,
                 event_encoding: str = "", author_color: Optional[str] = None,
                 author_name: Optional[str] = None, entities: str = ""):
        self.hexes = hexes
        self.provinces = provinces
        self.turn = turn
        self.event_encoding = event_encoding
        self.author_color = author_color
        self.author_name = author_name
        self.entities = entities

    def is_hex_diff(self) -> bool:
        return self.hexes.startswith("D:")

    def encode(self) -> str:
        ac = self.author_color or ""
        an = self.author_name or ""
        enc = self.event_encoding or ""
        ent = self.entities or ""
        return f"{self.hexes}\t{self.provinces}\t{self.turn}\t{enc}\t{ac}\t{an}\t{ent}"

    @staticmethod
    def decode(raw: str) -> Optional["ReplaySnapshot"]:
        parts = raw.split("\t")
        if len(parts) < 3:
            return None
        hexes = parts[0]
        provinces = parts[1]
        turn = parts[2]
        enc = parts[3] if len(parts) > 3 else ""
        ac = parts[4] if len(parts) > 4 and parts[4] else None
        an = parts[5] if len(parts) > 5 and parts[5] else None
        ent = parts[6] if len(parts) > 6 else ""
        return ReplaySnapshot(hexes, provinces, turn, enc, ac, an, ent)


class HistoryManager(IEventListener):
    """Manages game event history and records replay snapshots."""

    def __init__(self, game_state):
        self.game_state = game_state
        self.events_list: List[HistoryEvent] = []
        self.current_turn_events: List[HistoryEvent] = []
        self.replay_snapshots: List[ReplaySnapshot] = []
        self._prev_hex_map: dict = {}

        if game_state and game_state.events_manager:
            game_state.events_manager.add_listener(self)

    def get_listen_priority(self) -> int:
        return 5

    def on_event_validated(self, event: AbstractEvent) -> None:
        """Track notable events and record a snapshot for each."""
        if event.get_type() == EventType.TURN_END:
            return
        if not event.is_notable():
            return

        author_color = getattr(event.author, "color", None) if event.author is not None else None
        author_name = getattr(event.author, "name", None) if event.author is not None else None

        history_event = HistoryEvent(event, author_color, author_name)
        self.current_turn_events.append(history_event)

    def on_event_applied(self, event: AbstractEvent) -> None:
        if event.get_type() == EventType.TURN_END:
            self._record_snapshot_for_event(event)
            self._on_turn_end_event_applied()
        elif event.get_type() == EventType.GRAPH_CREATED:
            self._on_graph_created()
        elif event.get_type() == EventType.MATCH_STARTED:
            self._on_match_started()
        elif event.is_notable() and event.get_type() != EventType.TURN_END:
            self._record_snapshot_for_event(event)

    def _record_snapshot_for_event(self, event: AbstractEvent) -> None:
        """Capture hex/province/turn state right after this event was applied.
        Hexes are stored as a diff against the previous snapshot to save memory."""
        gs = self.game_state
        if gs is None:
            return
        full_hexes = _snapshot_hexes(gs)
        hex_str, self._prev_hex_map = _compute_hex_diff(self._prev_hex_map, full_hexes)
        provinces = _snapshot_provinces(gs)
        turn = _snapshot_turn(gs)
        entities = _snapshot_entities(gs)

        enc = event.encode() if hasattr(event, "encode") else ""
        ac_obj = getattr(event, "author", None)
        ac = getattr(ac_obj, "color", None)
        ac_str = ac.value if ac and hasattr(ac, "value") else None
        an = getattr(ac_obj, "name", None) if ac_obj else None

        snap = ReplaySnapshot(hex_str, provinces, turn, enc, ac_str, an, entities)
        self.replay_snapshots.append(snap)

    def _on_turn_end_event_applied(self) -> None:
        self.events_list.extend(self.current_turn_events)
        self.current_turn_events.clear()

    def _on_graph_created(self) -> None:
        self.clear_all()

    def _on_match_started(self) -> None:
        pass

    def clear_all(self) -> None:
        self.current_turn_events.clear()
        self.clear_events_list()
        self.replay_snapshots.clear()
        self._prev_hex_map = {}

    def clear_events_list(self) -> None:
        self.events_list.clear()

    # --- encoding for save file ---

    def encode_events_list(self) -> str:
        """Comma-separated encoded events (completed + current turn)."""
        parts = []
        for he in self.events_list:
            parts.append(he.encode())
        for he in self.current_turn_events:
            parts.append(he.encode())
        return ",".join(parts)

    def encode_snapshots(self) -> str:
        """Newline-separated encoded snapshots."""
        return "\n".join(snap.encode() for snap in self.replay_snapshots)

    # --- queries ---

    def get_events_list_copy(self) -> List[HistoryEvent]:
        return self.events_list.copy()

    def get_current_turn_events_copy(self) -> List[HistoryEvent]:
        return self.current_turn_events.copy()

    def get_all_events(self) -> List[HistoryEvent]:
        return self.events_list + self.current_turn_events

    def get_events_since_index(self, start_index: int) -> List[HistoryEvent]:
        if start_index < 0:
            start_index = 0
        if start_index >= len(self.events_list):
            return self.current_turn_events.copy()
        return self.events_list[start_index:] + self.current_turn_events.copy()

    def get_total_event_count(self) -> int:
        return len(self.events_list)
