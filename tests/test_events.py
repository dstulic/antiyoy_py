"""Unit tests for core/events.py."""

import pytest
from core.events import (
    AbstractEvent,
    EventKeys,
    EventTurnEnd,
    EventHexChangeColor,
    EventUnitMove,
    EventPieceAdd,
    EventPieceDelete,
    EventPieceBuild,
    EventSetMoney,
    EventGiveMoney,
    EventSubtractMoney,
    EventsFactory,
    EventsManager,
)
from core.enums import EventType, HColor, PieceType
from core.hex import Hex


class MockCoreModel:
    """Mock core model for testing."""

    def __init__(self):
        self.turns_manager = None
        self.provinces_manager = None
        self.hexes = []
        # Mock game_end_manager to prevent "Game has ended" errors in tests
        self.game_end_manager = MockGameEndManager()

    def get_hex_with_same_coordinates(self, hex: Hex) -> Hex | None:
        """Find hex with same coordinates."""
        for h in self.hexes:
            if h.has_same_coordinates_as(hex):
                return h
        return None


class MockGameEndManager:
    """Mock game end manager for testing."""

    def __init__(self):
        self.game_ended = False
        self.dead_players = set()

    def is_player_dead(self, color):
        """Check if player is dead."""
        return color in self.dead_players

    def can_make_turn(self):
        """Check if turn can be made."""
        return not self.game_ended


class MockTurnsManager:
    """Mock turns manager."""

    def __init__(self):
        self.turn_index = 0

    def do_switch_turn_index(self) -> None:
        """Switch turn index."""
        self.turn_index = (self.turn_index + 1) % 2


class MockProvincesManager:
    """Mock provinces manager."""

    def __init__(self):
        self.provinces = {}

    def get_province(self, province_id: int):
        """Get province by ID."""
        return self.provinces.get(province_id)
    
    def get_province_by_color(self, color):
        """Get province by color (returns first matching)."""
        for province in self.provinces.values():
            if province.get_color() == color:
                return province
        return None


class MockProvince:
    """Mock province."""

    def __init__(self, province_id: int):
        self._id = province_id
        self._money = 0

    def get_id(self) -> int:
        """Get ID."""
        return self._id

    def get_money(self) -> int:
        """Get money."""
        return self._money

    def set_money(self, money: int) -> None:
        """Set money."""
        self._money = money


class TestEventKeys:
    """Tests for EventKeys."""

    def test_convert_type_to_key(self):
        """Test converting EventType to key."""
        assert EventKeys.convert_type_to_key(EventType.TURN_END) == "te"
        assert EventKeys.convert_type_to_key(EventType.UNIT_MOVE) == "um"
        assert EventKeys.convert_type_to_key(EventType.HEX_CHANGE_COLOR) == "hcc"

    def test_convert_key_to_type(self):
        """Test converting key to EventType."""
        assert EventKeys.convert_key_to_type("te") == EventType.TURN_END
        assert EventKeys.convert_key_to_type("um") == EventType.UNIT_MOVE
        assert EventKeys.convert_key_to_type("hcc") == EventType.HEX_CHANGE_COLOR
        assert EventKeys.convert_key_to_type("invalid") is None


class TestEventTurnEnd:
    """Tests for EventTurnEnd."""

    def test_event_type(self):
        """Test event type."""
        event = EventTurnEnd()
        assert event.get_type() == EventType.TURN_END

    def test_is_valid(self):
        """Test validation."""
        event = EventTurnEnd()
        assert event.is_valid() is True

    def test_apply_change(self):
        """Test applying change."""
        event = EventTurnEnd()
        core_model = MockCoreModel()
        core_model.turns_manager = MockTurnsManager()
        event.set_core_model(core_model)
        initial_index = core_model.turns_manager.turn_index
        event.apply_change()
        assert core_model.turns_manager.turn_index != initial_index

    def test_encode(self):
        """Test encoding."""
        event = EventTurnEnd()
        event.set_current_color(HColor.RED)
        event.set_target_end_time(1000)
        encoded = event.encode()
        assert "te" in encoded
        assert "1000" in encoded
        assert "red" in encoded


class TestEventHexChangeColor:
    """Tests for EventHexChangeColor."""

    def test_event_type(self):
        """Test event type."""
        event = EventHexChangeColor()
        assert event.get_type() == EventType.HEX_CHANGE_COLOR

    def test_is_valid(self):
        """Test validation."""
        event = EventHexChangeColor()
        assert event.is_valid() is False  # No hex/color set
        hex = Hex(coordinate1=0, coordinate2=0, color=HColor.GRAY)
        event.set_hex(hex)
        event.set_color(HColor.RED)
        assert event.is_valid() is True

    def test_apply_change(self):
        """Test applying change."""
        hex = Hex(coordinate1=0, coordinate2=0, color=HColor.GRAY)
        event = EventHexChangeColor()
        event.set_hex(hex)
        event.set_color(HColor.RED)
        event.apply_change()
        assert hex.get_color() == HColor.RED


class TestEventUnitMove:
    """Tests for EventUnitMove."""

    def test_event_type(self):
        """Test event type."""
        event = EventUnitMove()
        assert event.get_type() == EventType.UNIT_MOVE

    def test_is_valid(self):
        """Test validation."""
        event = EventUnitMove()
        assert event.is_valid() is False  # No hexes set
        start = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        start.set_piece(PieceType.PEASANT)
        start.set_unit_id(1)
        finish = Hex(coordinate1=1, coordinate2=0, color=HColor.BLUE)
        event.set_start(start)
        event.set_finish(finish)
        assert event.is_valid() is True

    def test_apply_change(self):
        """Test applying change."""
        start = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        start.set_piece(PieceType.PEASANT)
        start.set_unit_id(1)
        finish = Hex(coordinate1=1, coordinate2=0, color=HColor.BLUE)
        event = EventUnitMove()
        event.set_start(start)
        event.set_finish(finish)
        event.apply_change()
        assert finish.piece == PieceType.PEASANT
        assert finish.unit_id == 1
        assert start.piece is None
        assert start.unit_id == -1

    def test_color_transfer(self):
        """Test color transfer."""
        start = Hex(coordinate1=0, coordinate2=0, color=HColor.RED)
        finish = Hex(coordinate1=1, coordinate2=0, color=HColor.BLUE)
        event = EventUnitMove()
        event.set_start(start)
        event.set_finish(finish)
        event.set_color_transfer_enabled(True)
        assert event.are_color_transfer_conditions_satisfied() is True
        event.set_color_transfer_enabled(False)
        assert event.are_color_transfer_conditions_satisfied() is False


class TestEventPieceAdd:
    """Tests for EventPieceAdd."""

    def test_event_type(self):
        """Test event type."""
        event = EventPieceAdd()
        assert event.get_type() == EventType.PIECE_ADD

    def test_is_valid(self):
        """Test validation."""
        event = EventPieceAdd()
        assert event.is_valid() is False
        hex = Hex()
        event.set_hex(hex)
        event.set_piece_type(PieceType.CITY)
        assert event.is_valid() is True
        hex.set_piece(PieceType.TOWER)
        assert event.is_valid() is False  # Hex already has piece

    def test_apply_change(self):
        """Test applying change."""
        hex = Hex()
        event = EventPieceAdd()
        event.set_hex(hex)
        event.set_piece_type(PieceType.CITY)
        event.apply_change()
        assert hex.piece == PieceType.CITY


class TestEventPieceDelete:
    """Tests for EventPieceDelete."""

    def test_event_type(self):
        """Test event type."""
        event = EventPieceDelete()
        assert event.get_type() == EventType.PIECE_DELETE

    def test_is_valid(self):
        """Test validation."""
        event = EventPieceDelete()
        assert event.is_valid() is False
        hex = Hex()
        hex.set_piece(PieceType.CITY)
        event.set_hex(hex)
        assert event.is_valid() is True

    def test_apply_change(self):
        """Test applying change."""
        hex = Hex()
        hex.set_piece(PieceType.CITY)
        event = EventPieceDelete()
        event.set_hex(hex)
        event.apply_change()
        assert hex.piece is None


class TestEventSetMoney:
    """Tests for EventSetMoney."""

    def test_event_type(self):
        """Test event type."""
        event = EventSetMoney()
        assert event.get_type() == EventType.SET_MONEY

    def test_apply_change(self):
        """Test applying change."""
        core_model = MockCoreModel()
        provinces_manager = MockProvincesManager()
        province = MockProvince(1)
        province.set_money(50)
        provinces_manager.provinces[1] = province
        core_model.provinces_manager = provinces_manager
        event = EventSetMoney()
        event.set_core_model(core_model)
        event.set_province_id(1)
        event.set_money(100)
        event.apply_change()
        assert province.get_money() == 100


class TestEventGiveMoney:
    """Tests for EventGiveMoney."""

    def test_apply_change(self):
        """Test applying change."""
        core_model = MockCoreModel()
        provinces_manager = MockProvincesManager()
        province = MockProvince(1)
        province.set_money(50)
        provinces_manager.provinces[1] = province
        core_model.provinces_manager = provinces_manager
        event = EventGiveMoney()
        event.set_core_model(core_model)
        event.province_id = 1
        event.amount = 25
        event.apply_change()
        assert province.get_money() == 75


class TestEventSubtractMoney:
    """Tests for EventSubtractMoney."""

    def test_apply_change(self):
        """Test applying change."""
        core_model = MockCoreModel()
        provinces_manager = MockProvincesManager()
        province = MockProvince(1)
        province.set_money(50)
        provinces_manager.provinces[1] = province
        core_model.provinces_manager = provinces_manager
        event = EventSubtractMoney()
        event.set_core_model(core_model)
        event.province_id = 1
        event.amount = 20
        event.apply_change()
        assert province.get_money() == 30

    def test_apply_change_negative(self):
        """Test that money doesn't go negative."""
        core_model = MockCoreModel()
        provinces_manager = MockProvincesManager()
        province = MockProvince(1)
        province.set_money(10)
        provinces_manager.provinces[1] = province
        core_model.provinces_manager = provinces_manager
        event = EventSubtractMoney()
        event.set_core_model(core_model)
        event.province_id = 1
        event.amount = 20
        event.apply_change()
        assert province.get_money() == 0


class TestEventsFactory:
    """Tests for EventsFactory."""

    def test_create_event(self):
        """Test creating events."""
        core_model = MockCoreModel()
        events_manager = EventsManager(core_model)
        factory = events_manager.factory
        event = factory.create_event(EventType.TURN_END)
        assert isinstance(event, EventTurnEnd)
        assert event.core_model == core_model
        event = factory.create_event(EventType.UNIT_MOVE)
        assert isinstance(event, EventUnitMove)


class TestEventsManager:
    """Tests for EventsManager."""

    def test_add_listener(self):
        """Test adding listener."""
        core_model = MockCoreModel()
        manager = EventsManager(core_model)
        listener = MockListener()
        manager.add_listener(listener)
        assert listener in manager.event_listeners

    def test_apply_event(self):
        """Test applying event."""
        core_model = MockCoreModel()
        manager = EventsManager(core_model)
        listener = MockListener()
        manager.add_listener(listener)
        from core.events import SYSTEM_AUTHOR
        event = EventTurnEnd()
        event.set_core_model(core_model)
        manager.apply_event(event, author=SYSTEM_AUTHOR)
        assert listener.validated_count == 1
        assert listener.applied_count == 1

    def test_apply_invalid_event(self):
        """Test that invalid events are not applied."""
        core_model = MockCoreModel()
        manager = EventsManager(core_model)
        listener = MockListener()
        manager.add_listener(listener)
        event = EventHexChangeColor()  # Invalid - no hex/color
        event.set_core_model(core_model)
        manager.apply_event(event)
        assert listener.validated_count == 0
        assert listener.applied_count == 0


class MockListener:
    """Mock event listener."""

    def __init__(self):
        self.validated_count = 0
        self.applied_count = 0

    def on_event_validated(self, event: AbstractEvent) -> None:
        """Handle event validated."""
        self.validated_count += 1

    def on_event_applied(self, event: AbstractEvent) -> None:
        """Handle event applied."""
        self.applied_count += 1

    def get_listen_priority(self) -> int:
        """Get priority."""
        return 0
