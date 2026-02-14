"""Visual test: One AI move per difficulty level."""

from pathlib import Path

from tests.visual.visual_test_base import VisualTest, visual_test
from core.game_state import GameState
from core.core_utils import is_unit
from core.enums import Difficulty
from ai.ai_manager import AIManager


# Shared map filename for all difficulty variants
ONE_MOVE_AI_MAP_EXPERT = "one_move_ai_expert.map"


def _set_all_ai_difficulties(game_state: GameState, difficulty: Difficulty) -> None:
    """Set ai_difficulty on all AI entities (for tests)."""
    for entity in (game_state.entities_manager.entities or []):
        if entity.is_artificial_intelligence():
            entity.set_ai_difficulty(difficulty)


@visual_test("one move ai expert easy", "Execute a single AI move (easy) on level 2")
class OneMoveAIExpertEasyTest(VisualTest):
    """One AI move with EASY difficulty."""

    def get_map_file_path(self) -> Path:
        maps_dir = Path(__file__).parent / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / ONE_MOVE_AI_MAP_EXPERT

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load one_move_ai_expert.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        _assert_ready_ai_unit_at_32(game_state)
        _print_move_zone_for_unit_at_32(game_state)
        _set_all_ai_difficulties(game_state, Difficulty.EASY)
        ai_manager = AIManager(game_state)
        ai_manager.process_ai_turn()
        return game_state


@visual_test("one move ai expert average", "Execute a single AI move (average) on level 2")
class OneMoveAIExpertAverageTest(VisualTest):
    """One AI move with AVERAGE difficulty."""

    def get_map_file_path(self) -> Path:
        maps_dir = Path(__file__).parent / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / ONE_MOVE_AI_MAP_EXPERT

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load one_move_ai_expert.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        _assert_ready_ai_unit_at_32(game_state)
        _print_move_zone_for_unit_at_32(game_state)
        _set_all_ai_difficulties(game_state, Difficulty.AVERAGE)
        ai_manager = AIManager(game_state)
        ai_manager.process_ai_turn()
        return game_state


@visual_test("one move ai expert hard", "Execute a single AI move (hard) on level 2")
class OneMoveAIExpertHardTest(VisualTest):
    """One AI move with HARD difficulty."""

    def get_map_file_path(self) -> Path:
        maps_dir = Path(__file__).parent / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / ONE_MOVE_AI_MAP_EXPERT

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load one_move_ai_expert.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        _assert_ready_ai_unit_at_32(game_state)
        _print_move_zone_for_unit_at_32(game_state)
        _set_all_ai_difficulties(game_state, Difficulty.HARD)
        ai_manager = AIManager(game_state)
        ai_manager.process_ai_turn()
        return game_state


@visual_test("one move ai expert expert", "Execute a single AI move (expert) on level 2")
class OneMoveAIExpertExpertTest(VisualTest):
    """One AI move with EXPERT difficulty."""

    def get_map_file_path(self) -> Path:
        maps_dir = Path(__file__).parent / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / ONE_MOVE_AI_MAP_EXPERT

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load one_move_ai_expert.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        _assert_ready_ai_unit_at_32(game_state)
        _print_move_zone_for_unit_at_32(game_state)
        _set_all_ai_difficulties(game_state, Difficulty.EXPERT)
        ai_manager = AIManager(game_state)
        ai_manager.process_ai_turn()
        return game_state


@visual_test("one move ai expert balancer", "Execute a single AI move (balancer) on level 2")
class OneMoveAIExpertBalancerTest(VisualTest):
    """One AI move with BALANCER difficulty."""

    def get_map_file_path(self) -> Path:
        maps_dir = Path(__file__).parent / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / ONE_MOVE_AI_MAP_EXPERT

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load one_move_ai.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        _assert_ready_ai_unit_at_32(game_state)
        _print_move_zone_for_unit_at_32(game_state)
        _set_all_ai_difficulties(game_state, Difficulty.BALANCER)
        ai_manager = AIManager(game_state)
        ai_manager.process_ai_turn()
        return game_state


def _assert_ready_ai_unit_at_32(game_state: GameState) -> None:
    """Assert there is a ready AI unit at (-3, 2) (shared pre-AI checks)."""
    hex_at_32 = game_state.get_hex(-3, 2)
    assert hex_at_32 is not None, "Expected a hex at (-3, 2)"
    assert hex_at_32.piece is not None and is_unit(hex_at_32.piece), (
        f"Expected a unit at (-3, 2), got piece={hex_at_32.piece}"
    )
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, "Expected a current entity (AI's turn)"
    assert hex_at_32.color == current_entity.color, (
        f"Unit at (-3, 2) should belong to current player ({current_entity.color}), got {hex_at_32.color}"
    )
    assert game_state.readiness_manager is not None, "Readiness manager required to check unit ready state"
    game_state.readiness_manager.update()
    assert game_state.readiness_manager.is_ready(hex_at_32), (
        "Unit at (-3, 2) should not have been moved yet (must be ready to move)"
    )


def _print_move_zone_for_unit_at_32(game_state: GameState) -> None:
    """Update move zone for the AI unit at (-3, 2) and print its hexes."""
    hex_at_32 = game_state.get_hex(-3, 2)
    if hex_at_32 is None or not hex_at_32.has_unit():
        return
    game_state.move_zone_manager.update_for_unit(hex_at_32)
    zone = game_state.move_zone_manager.hexes
    coords = [(h.coordinate1, h.coordinate2) for h in zone]
    print(f"Move zone for AI unit at (-3, 2): {len(zone)} hexes -> {sorted(coords)}")


def _run_one_move_ai_for_difficulty(difficulty: Difficulty) -> tuple:
    """Run one move AI test for a given difficulty; returns (initial, final) states."""
    _classes = {
        Difficulty.EASY: OneMoveAIExpertEasyTest,
        Difficulty.AVERAGE: OneMoveAIExpertAverageTest,
        Difficulty.HARD: OneMoveAIExpertHardTest,
        Difficulty.EXPERT: OneMoveAIExpertExpertTest,
        Difficulty.BALANCER: OneMoveAIExpertBalancerTest,
    }
    test = _classes[difficulty](f"one move ai {difficulty.value}", f"One AI move ({difficulty.value})")
    return test.execute()


def test_one_move_ai_expert_easy():
    """Run one move AI test with EASY difficulty."""
    initial, final = _run_one_move_ai_for_difficulty(Difficulty.EASY)
    _assert_ai_made_move(initial, final)


def test_one_move_ai_expert_average():
    """Run one move AI test with AVERAGE difficulty."""
    initial, final = _run_one_move_ai_for_difficulty(Difficulty.AVERAGE)
    _assert_ai_made_move(initial, final)


def test_one_move_ai_expert_hard():
    """Run one move AI test with HARD difficulty."""
    initial, final = _run_one_move_ai_for_difficulty(Difficulty.HARD)
    _assert_ai_made_move(initial, final)


def test_one_move_ai_expert_expert():
    """Run one move AI test with EXPERT difficulty."""
    initial, final = _run_one_move_ai_for_difficulty(Difficulty.EXPERT)
    _assert_ai_made_move(initial, final)


def test_one_move_ai_expert_balancer():
    """Run one move AI test with BALANCER difficulty."""
    initial, final = _run_one_move_ai_for_difficulty(Difficulty.BALANCER)
    _assert_ai_made_move(initial, final)


def _assert_ai_made_move(initial: GameState, final: GameState) -> None:
    """Shared assertions that the AI generated events."""
    assert initial is not None
    assert final is not None
    assert len(initial.hexes) > 0
    assert len(final.hexes) > 0
    initial_events = (
        initial.history_manager.get_total_event_count()
        if hasattr(initial, "history_manager") and initial.history_manager
        else 0
    )
    final_events = (
        final.history_manager.get_total_event_count()
        if hasattr(final, "history_manager") and final.history_manager
        else 0
    )
    assert final_events >= initial_events, "AI should have generated some events"
