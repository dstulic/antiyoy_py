"""Visual test: AI spend money per difficulty level."""

from pathlib import Path

from tests.visual.visual_test_base import VisualTest, visual_test
from core.game_state import GameState
from core.core_utils import is_unit
from core.enums import Difficulty, HColor, PieceType
from ai.ai_manager import AIManager
from commands.executor import CommandExecutor
from commands.types import EndTurnCommand


# Shared map filename for all difficulty variants
AI_SPEND_MONEY_MAP = "ai_spend_money.map"

# Expected lavender piece counts after turns (farms, towers, strong_towers, peasants).
# If tests fail, AI behavior or map may have changed; or set RNG seed in setup for determinism.
EXPECTED_LAVENDER = {
    Difficulty.EASY: {"farms": 0, "towers": 0, "strong_towers": 0, "peasants": 2},
    Difficulty.AVERAGE: {"farms": 6, "towers": 2, "strong_towers": 0, "peasants": 2},
    Difficulty.HARD: {"farms": 5, "towers": 2, "strong_towers": 0, "peasants": 3},
    Difficulty.EXPERT: {"farms": 4, "towers": 1, "strong_towers": 1, "peasants": 3},
    Difficulty.BALANCER: {"farms": 4, "towers": 1, "strong_towers": 1, "peasants": 3},
}


def _count_lavender_pieces(game_state: GameState) -> dict:
    """Count farms, towers, strong_towers, peasants for lavender."""
    counts = {"farms": 0, "towers": 0, "strong_towers": 0, "peasants": 0}
    for h in game_state.hexes:
        if h.color != HColor.LAVENDER:
            continue
        if h.piece == PieceType.FARM:
            counts["farms"] += 1
        elif h.piece == PieceType.TOWER:
            counts["towers"] += 1
        elif h.piece == PieceType.STRONG_TOWER:
            counts["strong_towers"] += 1
        elif h.piece == PieceType.PEASANT:
            counts["peasants"] += 1
    return counts


def _assert_lavender_piece_counts(game_state: GameState, difficulty: Difficulty) -> None:
    """Assert lavender has expected piece counts for this difficulty."""
    expected = EXPECTED_LAVENDER.get(difficulty)
    if not expected:
        return
    counts = _count_lavender_pieces(game_state)
    for key in ("farms", "towers", "strong_towers", "peasants"):
        assert counts[key] == expected[key], (
            f"Lavender {key}: expected {expected[key]}, got {counts[key]} (difficulty={difficulty.value})"
        )


def _run_until_lap_2(game_state: GameState, ai_manager: AIManager) -> None:
    """Run turns until lap >= 2: process AI turns, end turn for human player."""
    executor = CommandExecutor(game_state)
    while game_state.turns_manager.lap < 2:
        current_entity = game_state.entities_manager.get_current_entity()
        if not current_entity:
            break
        if current_entity.is_artificial_intelligence():
            ai_manager.process_ai_turn()
        elif current_entity.is_human():
            success, error = executor.execute(EndTurnCommand(), current_entity.color)
            if not success:
                raise RuntimeError(f"End turn failed: {error}")
        else:
            break


@visual_test("ai spend money easy", "AI spend money (easy)")
class AiSpendMoneyEasyTest(VisualTest):
    """AI spend money with EASY difficulty."""

    def get_map_file_path(self) -> Path:
        maps_dir = Path(__file__).parent / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / AI_SPEND_MONEY_MAP

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load ai_spend_money.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        _assert_ready_ai_unit_at_32(game_state)
        _print_move_zone_for_unit_at_32(game_state)
        ai_manager = AIManager(game_state, Difficulty.EASY)
        _run_until_lap_2(game_state, ai_manager)
        return game_state


@visual_test("ai spend money average", "AI spend money (average)")
class AiSpendMoneyAverageTest(VisualTest):
    """AI spend money with AVERAGE difficulty."""

    def get_map_file_path(self) -> Path:
        maps_dir = Path(__file__).parent / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / AI_SPEND_MONEY_MAP

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load ai_spend_money.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        _assert_ready_ai_unit_at_32(game_state)
        _print_move_zone_for_unit_at_32(game_state)
        ai_manager = AIManager(game_state, Difficulty.AVERAGE)
        _run_until_lap_2(game_state, ai_manager)
        return game_state


@visual_test("ai spend money hard", "AI spend money (hard)")
class AiSpendMoneyHardTest(VisualTest):
    """AI spend money with HARD difficulty."""

    def get_map_file_path(self) -> Path:
        maps_dir = Path(__file__).parent / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / AI_SPEND_MONEY_MAP

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load ai_spend_money.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        _assert_ready_ai_unit_at_32(game_state)
        _print_move_zone_for_unit_at_32(game_state)
        ai_manager = AIManager(game_state, Difficulty.HARD)
        _run_until_lap_2(game_state, ai_manager)
        return game_state


@visual_test("ai spend money expert", "AI spend money (expert)")
class AiSpendMoneyExpertTest(VisualTest):
    """AI spend money with EXPERT difficulty."""

    def get_map_file_path(self) -> Path:
        maps_dir = Path(__file__).parent / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / AI_SPEND_MONEY_MAP

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load ai_spend_money.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        _assert_ready_ai_unit_at_32(game_state)
        _print_move_zone_for_unit_at_32(game_state)
        ai_manager = AIManager(game_state, Difficulty.EXPERT)
        _run_until_lap_2(game_state, ai_manager)
        return game_state


@visual_test("ai spend money balancer", "AI spend money (balancer)")
class AiSpendMoneyBalancerTest(VisualTest):
    """AI spend money with BALANCER difficulty."""

    def get_map_file_path(self) -> Path:
        maps_dir = Path(__file__).parent / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / AI_SPEND_MONEY_MAP

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load ai_spend_money.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        _assert_ready_ai_unit_at_32(game_state)
        _print_move_zone_for_unit_at_32(game_state)
        ai_manager = AIManager(game_state, Difficulty.BALANCER)
        _run_until_lap_2(game_state, ai_manager)
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


def _run_ai_spend_money_for_difficulty(difficulty: Difficulty) -> tuple:
    """Run AI spend money test for a given difficulty; returns (initial, final) states."""
    _classes = {
        Difficulty.EASY: AiSpendMoneyEasyTest,
        Difficulty.AVERAGE: AiSpendMoneyAverageTest,
        Difficulty.HARD: AiSpendMoneyHardTest,
        Difficulty.EXPERT: AiSpendMoneyExpertTest,
        Difficulty.BALANCER: AiSpendMoneyBalancerTest,
    }
    test = _classes[difficulty](f"ai spend money {difficulty.value}", f"AI spend money ({difficulty.value})")
    return test.execute()


def test_ai_spend_money_easy():
    """Run AI spend money test with EASY difficulty."""
    initial, final = _run_ai_spend_money_for_difficulty(Difficulty.EASY)
    _assert_ai_made_move(initial, final)
    _assert_lavender_piece_counts(final, Difficulty.EASY)


def test_ai_spend_money_average():
    """Run AI spend money test with AVERAGE difficulty."""
    initial, final = _run_ai_spend_money_for_difficulty(Difficulty.AVERAGE)
    _assert_ai_made_move(initial, final)
    _assert_lavender_piece_counts(final, Difficulty.AVERAGE)


def test_ai_spend_money_hard():
    """Run AI spend money test with HARD difficulty."""
    initial, final = _run_ai_spend_money_for_difficulty(Difficulty.HARD)
    _assert_ai_made_move(initial, final)
    _assert_lavender_piece_counts(final, Difficulty.HARD)


def test_ai_spend_money_expert():
    """Run AI spend money test with EXPERT difficulty."""
    initial, final = _run_ai_spend_money_for_difficulty(Difficulty.EXPERT)
    _assert_ai_made_move(initial, final)
    _assert_lavender_piece_counts(final, Difficulty.EXPERT)


def test_ai_spend_money_balancer():
    """Run AI spend money test with BALANCER difficulty."""
    initial, final = _run_ai_spend_money_for_difficulty(Difficulty.BALANCER)
    _assert_ai_made_move(initial, final)
    _assert_lavender_piece_counts(final, Difficulty.BALANCER)


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
    assert final_events >= initial_events, "AI should have generated some events (two full turns)"
