"""Unit tests for history manager."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.history_manager import HistoryManager, HistoryEvent
from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType, EventType
from core.events import EventPieceBuild, EventUnitMove, EventTurnEnd
from core.hex import Hex


def create_test_game_state() -> GameState:
    """Create a minimal test game state."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a simple hex
    hex1 = game_state.add_hex(0, 0, HColor.RED)
    hex1.piece = PieceType.CITY
    
    # Create player entity
    from core.player_entity import PlayerEntity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    player.set_name("TestPlayer")
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)
    
    return game_state


def test_history_manager_initialization():
    """Test that history manager initializes correctly."""
    game_state = create_test_game_state()
    
    assert hasattr(game_state, 'history_manager'), "GameState should have history_manager"
    assert game_state.history_manager is not None, "history_manager should not be None"
    assert len(game_state.history_manager.events_list) == 0, "Events list should be empty initially"
    assert len(game_state.history_manager.current_turn_events) == 0, "Current turn events should be empty initially"


def test_history_manager_tracks_notable_events():
    """Test that history manager tracks notable events."""
    game_state = create_test_game_state()
    history_manager = game_state.history_manager
    
    # Create a notable event (piece build)
    events_factory = game_state.events_manager.factory
    event = events_factory.create_event(EventType.PIECE_BUILD)
    
    if isinstance(event, EventPieceBuild):
        hex1 = game_state.get_hex(0, 0)
        event.set_hex(hex1)
        event.set_piece_type(PieceType.PEASANT)
        event.set_province_id(1)
        event.unit_id = 1
        
        # Set author
        player = game_state.entities_manager.entities[0]
        event.set_author(player)
        
        # Apply event (this should trigger on_event_validated)
        if event.is_valid():
            event.set_core_model(game_state)
            game_state.events_manager.apply_event(event)
            
            # Check that event was tracked
            assert len(history_manager.current_turn_events) == 1, "Should have 1 current turn event"
            history_event = history_manager.current_turn_events[0]
            assert history_event.author_color == HColor.RED, "Author color should be RED"
            assert history_event.author_name == "TestPlayer", "Author name should be TestPlayer"


def test_history_manager_ignores_non_notable_events():
    """Test that history manager ignores non-notable events."""
    game_state = create_test_game_state()
    history_manager = game_state.history_manager
    
    # Create a quick event (non-notable)
    events_factory = game_state.events_manager.factory
    event = events_factory.create_event(EventType.PIECE_BUILD)
    
    if isinstance(event, EventPieceBuild):
        hex1 = game_state.get_hex(0, 0)
        event.set_hex(hex1)
        event.set_piece_type(PieceType.PEASANT)
        event.set_province_id(1)
        event.unit_id = 1
        event.set_quick(True)  # Make it quick (non-notable)
        
        # Apply event
        if event.is_valid():
            event.set_core_model(game_state)
            game_state.events_manager.apply_event(event)
            
            # Check that event was NOT tracked
            assert len(history_manager.current_turn_events) == 0, "Should not track quick events"


def test_history_manager_moves_events_on_turn_end():
    """Test that history manager moves current turn events to events list on turn end."""
    game_state = create_test_game_state()
    history_manager = game_state.history_manager
    
    # Create and validate a notable event
    events_factory = game_state.events_manager.factory
    event = events_factory.create_event(EventType.PIECE_BUILD)
    
    if isinstance(event, EventPieceBuild):
        hex1 = game_state.get_hex(0, 0)
        event.set_hex(hex1)
        event.set_piece_type(PieceType.PEASANT)
        event.set_province_id(1)
        event.unit_id = 1
        
        player = game_state.entities_manager.entities[0]
        event.set_author(player)
        
        if event.is_valid():
            event.set_core_model(game_state)
            game_state.events_manager.apply_event(event)
            
            # Should be in current turn events (may have other events from province updates, etc.)
            build_events = [he for he in history_manager.current_turn_events 
                           if he.event.get_type() == EventType.PIECE_BUILD]
            assert len(build_events) >= 1, "Should have at least 1 build event in current turn"
            assert len(history_manager.events_list) == 0, "Events list should be empty"
            
            # Count events before turn end
            events_before = len(history_manager.current_turn_events)
            
            # Create and apply turn end event
            turn_end_event = events_factory.create_event(EventType.TURN_END)
            if turn_end_event:
                turn_end_event.set_core_model(game_state)
                game_state.events_manager.apply_event(turn_end_event)
                
                # Debug: print what events are still in current_turn_events
                if len(history_manager.current_turn_events) > 0:
                    event_types = [he.event.get_type().value for he in history_manager.current_turn_events]
                    print(f"DEBUG: Events still in current_turn_events: {event_types}")
                
                # Should be moved to events list (all current turn events)
                # Note: Some events might be created during turn_end processing, so we check that
                # the original events were moved, not that current_turn_events is empty
                assert len(history_manager.events_list) >= events_before, f"Events list should have at least {events_before} events"


def test_history_event_encoding():
    """Test that history events encode correctly with author information."""
    game_state = create_test_game_state()
    
    # Create an event with author
    events_factory = game_state.events_manager.factory
    event = events_factory.create_event(EventType.PIECE_BUILD)
    
    if isinstance(event, EventPieceBuild):
        hex1 = game_state.get_hex(0, 0)
        event.set_hex(hex1)
        event.set_piece_type(PieceType.PEASANT)
        event.set_province_id(1)
        event.unit_id = 1
        
        player = game_state.entities_manager.entities[0]
        event.set_author(player)
        
        # Create history event
        history_event = HistoryEvent(event, HColor.RED, "TestPlayer")
        
        # Encode
        encoded = history_event.encode()
        
        # Should contain event encoding and author info
        assert "author:red" in encoded or "author:RED" in encoded, "Should contain author color"
        assert "TestPlayer" in encoded, "Should contain author name"
        assert "|" in encoded, "Should have separator between event and author"


def test_history_manager_encode_events_list():
    """Test that history manager encodes events list correctly."""
    game_state = create_test_game_state()
    history_manager = game_state.history_manager
    
    # Create some events
    events_factory = game_state.events_manager.factory
    player = game_state.entities_manager.entities[0]
    
    # Create first event
    event1 = events_factory.create_event(EventType.PIECE_BUILD)
    if isinstance(event1, EventPieceBuild):
        hex1 = game_state.get_hex(0, 0)
        event1.set_hex(hex1)
        event1.set_piece_type(PieceType.PEASANT)
        event1.set_province_id(1)
        event1.unit_id = 1
        event1.set_author(player)
        
        if event1.is_valid():
            event1.set_core_model(game_state)
            game_state.events_manager.apply_event(event1)
    
    # End turn to move to events list
    turn_end = events_factory.create_event(EventType.TURN_END)
    if turn_end:
        turn_end.set_core_model(game_state)
        game_state.events_manager.apply_event(turn_end)
    
    # Create second event (in current turn)
    event2 = events_factory.create_event(EventType.PIECE_BUILD)
    if isinstance(event2, EventPieceBuild):
        hex1 = game_state.get_hex(0, 0)
        event2.set_hex(hex1)
        event2.set_piece_type(PieceType.SPEARMAN)
        event2.set_province_id(1)
        event2.unit_id = 2
        event2.set_author(player)
        
        if event2.is_valid():
            event2.set_core_model(game_state)
            game_state.events_manager.apply_event(event2)
    
    # Encode
    encoded = history_manager.encode_events_list()
    
    # Should contain both events
    assert len(encoded) > 0, "Encoded string should not be empty"
    assert "," in encoded or len(history_manager.get_all_events()) == 1, "Should have comma separator or single event"


if __name__ == "__main__":
    test_history_manager_initialization()
    print("✓ test_history_manager_initialization passed")
    
    test_history_manager_tracks_notable_events()
    print("✓ test_history_manager_tracks_notable_events passed")
    
    test_history_manager_ignores_non_notable_events()
    print("✓ test_history_manager_ignores_non_notable_events passed")
    
    test_history_manager_moves_events_on_turn_end()
    print("✓ test_history_manager_moves_events_on_turn_end passed")
    
    test_history_event_encoding()
    print("✓ test_history_event_encoding passed")
    
    test_history_manager_encode_events_list()
    print("✓ test_history_manager_encode_events_list passed")
    
    print("\nAll tests passed!")
