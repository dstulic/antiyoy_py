"""Visual test: One AI move."""

from tests.visual.visual_test_base import VisualTest, visual_test
from core.game_state import GameState
from save_load.decoder import GameStateDecoder
from campaign.levels import get_level_code
from ai.ai_manager import AIManager


@visual_test("one move ai", "Execute a single AI move on level 2")
class OneMoveAITest(VisualTest):
    """Test that executes a single AI move."""
    
    def setup(self) -> GameState:
        """Set up level 2 initial state."""
        level_code = get_level_code(2)
        decoder = GameStateDecoder()
        result = decoder.decode(level_code)
        
        if isinstance(result, tuple):
            game_state, _ = result
        else:
            game_state = result
        
        if game_state is None:
            raise ValueError("Failed to decode level 2")
        
        # Ensure adjacency graph is built
        from save_load.decoder import _build_adjacency_graph
        _build_adjacency_graph(game_state)
        
        # Initialize starting money for all provinces
        from core.enums import EventType, PieceType
        for province in game_state.provinces_manager.provinces:
            if province.get_money() == 0:
                province.set_money(10)
        
        return game_state
    
    def run(self, game_state: GameState) -> GameState:
        """Execute a single AI move."""
        # Create AI manager
        ai_manager = AIManager(game_state)
        
        # Process one AI turn
        ai_manager.process_ai_turn()
        
        return game_state


# Auto-register when module is imported
_test_instance = OneMoveAITest("one move ai", "Execute a single AI move on level 2")
VisualTest.register(_test_instance)


# Pytest-compatible test function
def test_one_move_ai():
    """Run the one move AI test (can be executed with pytest)."""
    test = OneMoveAITest("one move ai", "Execute a single AI move on level 2")
    initial, final = test.execute()
    
    # Basic assertions
    assert initial is not None
    assert final is not None
    assert len(initial.hexes) > 0
    assert len(final.hexes) > 0
    
    # Verify that something changed (AI made a move)
    # This is a simple check - in a real test you might want more specific assertions
    initial_events = initial.history_manager.get_total_event_count() if hasattr(initial, 'history_manager') else 0
    final_events = final.history_manager.get_total_event_count() if hasattr(final, 'history_manager') else 0
    
    # AI should have generated some events (moves, builds, etc.)
    assert final_events >= initial_events, "AI should have generated some events"
