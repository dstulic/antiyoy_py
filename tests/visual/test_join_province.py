"""Visual test: join province test."""

from pathlib import Path

from tests.visual.visual_test_base import VisualTest, visual_test
from core.game_state import GameState
from core.enums import HColor, PieceType
from commands.types import BuildPieceCommand
from commands.executor import CommandExecutor


def _run_join_test(
    game_state: GameState,
    color: HColor,
    hex_x: int,
    hex_y: int,
    test_name: str,
    city_x: int,
    city_y: int,
) -> GameState:
    """
    Helper function to run a province join test.

    Steps:
    1) Verify <color> player has two provinces.
    2) Make <color> player be the next turn.
    3) Make <color> player build peasant on hex (hex_x, hex_y).
    4) Verify that <color> player now has one province.
    5) Verify that <color> player now has one city at (city_x, city_y).

    Args:
        game_state: The game state to test
        color: The color that has two provinces and will build to join them
        hex_x: X coordinate of hex to build peasant on
        hex_y: Y coordinate of hex to build peasant on
        test_name: Name of the test (for error messages)
        city_x: X coordinate where city must be after join
        city_y: Y coordinate where city must be after join

    Returns:
        Modified game state after the test
    """
    # Step 1: Verify that color player has two provinces
    color_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == color]
    initial_count = len(color_provinces)
    assert initial_count == 2, (
        f"[{test_name}] Expected {color.value} player to have 2 provinces initially, got {initial_count}"
    )

    hex_target = game_state.get_hex(hex_x, hex_y)
    assert hex_target is not None, f"[{test_name}] Hex ({hex_x},{hex_y}) should exist"
    assert hex_target.color == HColor.GRAY, (
        f"[{test_name}] Hex ({hex_x},{hex_y}) should be grey (neutral) initially, got {hex_target.color.value}"
    )

    # Player builds on grey hex to capture it; use either province of that color (one that can build on this hex)
    color_province = game_state.provinces_manager.get_province_by_color(color)
    assert color_province is not None, f"[{test_name}] {color.value} player should have at least one province"
    province = color_province

    # Step 2: Make it color's turn
    color_entity = game_state.entities_manager.get_entity(color)
    assert color_entity is not None, f"[{test_name}] {color.value} entity should exist"

    color_index = None
    for i, entity in enumerate(game_state.entities_manager.entities):
        if entity.color == color:
            color_index = i
            break
    assert color_index is not None, f"[{test_name}] {color.value} entity should be in entities list"
    game_state.turns_manager.turn_index = color_index

    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None and current_entity.color == color, (
        f"[{test_name}] Expected {color.value} player's turn"
    )

    # Step 3: Build peasant on hex (ensure province has enough money; peasant typically costs 10)
    peasant_cost = 10
    if province.get_money() < peasant_cost:
        province.set_money(peasant_cost)

    build_cmd = BuildPieceCommand(
        hex=hex_target,
        piece_type=PieceType.PEASANT,
        province_id=province.get_id(),
        province_hex=province.get_hexes()[0] if province.get_hexes() else None
    )
    executor = CommandExecutor(game_state)
    success, error = executor.execute(build_cmd, color)
    assert success, f"[{test_name}] Build command should succeed, got error: {error}"

    # Step 4: Verify that color player now has one province
    color_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == color]
    assert len(color_provinces_after) == 1, (
        f"[{test_name}] Expected {color.value} player to have 1 province after join, got {len(color_provinces_after)}"
    )

    # Step 5: Verify that color player now has one city at (city_x, city_y)
    single_province = color_provinces_after[0]
    cities = [h for h in single_province.get_hexes() if h.piece == PieceType.CITY]
    assert len(cities) == 1, (
        f"[{test_name}] Expected {color.value} player to have 1 city after join, got {len(cities)}"
    )
    city_hex = game_state.get_hex(city_x, city_y)
    assert city_hex is not None, f"[{test_name}] Hex ({city_x},{city_y}) should exist for city verification"
    assert city_hex.piece == PieceType.CITY, (
        f"[{test_name}] Expected city at ({city_x},{city_y}) after join, got {city_hex.piece}"
    )

    return game_state


def _map_path() -> Path:
    maps_dir = Path(__file__).parent / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    return maps_dir / "join_province_test.map"


@visual_test("join province test A", "Test A: lavender builds peasant at (0,1)")
class JoinProvinceTestA(VisualTest):
    """Test A: lavender player has two provinces; build peasant at (0,1) to join; expect one province, one city."""

    def get_map_file_path(self):
        return _map_path()

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load join_province_test.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        return _run_join_test(game_state, HColor.LAVENDER, 0, 1, "Test A", city_x=-3, city_y=1)


@visual_test("join province test B", "Test B: aqua builds peasant at (1,-2)")
class JoinProvinceTestB(VisualTest):
    """Test B: aqua player has two provinces; build peasant at (1,-2) to join; expect one province, one city."""

    def get_map_file_path(self):
        return _map_path()

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load join_province_test.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        return _run_join_test(game_state, HColor.AQUA, 1, -2, "Test B", city_x=-4, city_y=-5)


@visual_test("join province test C", "Test C: red builds peasant at (2,-1)")
class JoinProvinceTestC(VisualTest):
    """Test C: red player has two provinces; build peasant at (2,-1) to join; expect one province, one city."""

    def get_map_file_path(self):
        return _map_path()

    def setup(self) -> GameState:
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load join_province_test.map - map file is required")
        return game_state

    def run(self, game_state: GameState) -> GameState:
        return _run_join_test(game_state, HColor.RED, 2, -1, "Test C", city_x=6, city_y=0)


# Pytest-compatible test functions
def test_join_province_A():
    """Run join province test A (lavender, (0,1)); city at (-3,1)."""
    test = JoinProvinceTestA("join province test A", "Test A: lavender builds peasant at (0,1)")
    initial, final = test.execute()
    assert initial is not None and final is not None
    color_provinces = [p for p in final.provinces_manager.provinces if p.get_color() == HColor.LAVENDER]
    assert len(color_provinces) == 1
    cities = [h for h in color_provinces[0].get_hexes() if h.piece == PieceType.CITY]
    assert len(cities) == 1
    city_hex = final.get_hex(-3, 1)
    assert city_hex is not None and city_hex.piece == PieceType.CITY
    print("join province test A passed!")


def test_join_province_B():
    """Run join province test B (aqua, (1,-2)); city at (-4,-5)."""
    test = JoinProvinceTestB("join province test B", "Test B: aqua builds peasant at (1,-2)")
    initial, final = test.execute()
    assert initial is not None and final is not None
    color_provinces = [p for p in final.provinces_manager.provinces if p.get_color() == HColor.AQUA]
    assert len(color_provinces) == 1
    cities = [h for h in color_provinces[0].get_hexes() if h.piece == PieceType.CITY]
    assert len(cities) == 1
    city_hex = final.get_hex(-4, -5)
    assert city_hex is not None and city_hex.piece == PieceType.CITY
    print("join province test B passed!")


def test_join_province_C():
    """Run join province test C (red, (2,-1)); city at (6,0)."""
    test = JoinProvinceTestC("join province test C", "Test C: red builds peasant at (2,-1)")
    initial, final = test.execute()
    assert initial is not None and final is not None
    color_provinces = [p for p in final.provinces_manager.provinces if p.get_color() == HColor.RED]
    assert len(color_provinces) == 1
    cities = [h for h in color_provinces[0].get_hexes() if h.piece == PieceType.CITY]
    assert len(cities) == 1
    city_hex = final.get_hex(6, 0)
    assert city_hex is not None and city_hex.piece == PieceType.CITY
    print("join province test C passed!")
