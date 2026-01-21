"""Visual test: Split province test."""

from tests.visual.visual_test_base import VisualTest, visual_test
from core.game_state import GameState
from save_load.decoder import GameStateDecoder
from core.enums import HColor, PieceType
from commands.types import BuildPieceCommand
from commands.executor import CommandExecutor


def _run_split_test(
    game_state: GameState,
    color1: HColor,
    color2: HColor,
    hex_x: int,
    hex_y: int,
    test_name: str
) -> GameState:
    """
    Helper function to run a province split test.
    
    Args:
        game_state: The game state to test
        color1: The color that should have 1 province initially and 2 after split
        color2: The color that will build the spearman
        hex_x: X coordinate of hex to build on
        hex_y: Y coordinate of hex to build on
        test_name: Name of the test (for error messages)
    
    Returns:
        Modified game state after the test
    """
    # Step 1: Verify that color1 player has one province
    color1_provinces = [p for p in game_state.provinces_manager.provinces if p.get_color() == color1]
    initial_count = len(color1_provinces)
    assert initial_count == 1, f"[{test_name}] Expected {color1.value} player to have 1 province initially, got {initial_count}"
    
    # Check hex initial state - should be color1 (not color2 yet)
    hex_target = game_state.get_hex(hex_x, hex_y)
    assert hex_target is not None, f"[{test_name}] Hex ({hex_x},{hex_y}) should exist"
    assert hex_target.color == color1, f"[{test_name}] Hex ({hex_x},{hex_y}) should be {color1.value} initially to test the split, got {hex_target.color.value}"
    
    # Step 2: Make it color2 player's turn
    # Find color2 entity index
    color2_entity = game_state.entities_manager.get_entity(color2)
    assert color2_entity is not None, f"[{test_name}] {color2.value} entity should exist"
    
    # Find the index of color2 entity in the entities list
    color2_index = None
    for i, entity in enumerate(game_state.entities_manager.entities):
        if entity.color == color2:
            color2_index = i
            break
    
    assert color2_index is not None, f"[{test_name}] {color2.value} entity should be in entities list"
    game_state.turns_manager.turn_index = color2_index
    
    # Verify it's now color2's turn
    current_entity = game_state.entities_manager.get_current_entity()
    assert current_entity is not None, f"[{test_name}] Current entity should exist"
    assert current_entity.color == color2, f"[{test_name}] Expected {color2.value} player's turn, got {current_entity.color.value}"
    
    # Step 3: Make color2 player build spearman on hex
    # Get color2 province for the build command
    color2_province = game_state.provinces_manager.get_province_by_color(color2)
    assert color2_province is not None, f"[{test_name}] {color2.value} province should exist"
    
    # Ensure province has enough money to build spearman (cost is typically 20)
    if color2_province.get_money() < 20:
        color2_province.set_money(20)
    
    # Create build command
    build_cmd = BuildPieceCommand(
        hex=hex_target,
        piece_type=PieceType.SPEARMAN,
        province_id=color2_province.get_id(),
        province_hex=color2_province.get_hexes()[0] if color2_province.get_hexes() else None
    )
    
    # Execute the build command
    executor = CommandExecutor(game_state)
    success, error = executor.execute(build_cmd, color2)
    
    assert success, f"[{test_name}] Build command should succeed, got error: {error}"
    
    # Step 4: Province splitting logic should have run automatically when hex color changed
    # (No action needed - the event system handles this)
    
    # Step 5: Verify that color1 player now has two provinces
    color1_provinces_after = [p for p in game_state.provinces_manager.provinces if p.get_color() == color1]
    assert len(color1_provinces_after) == 2, f"[{test_name}] Expected {color1.value} player to have 2 provinces after split, got {len(color1_provinces_after)}"
    
    # Verify hex is now color2 with spearman
    hex_after = game_state.get_hex(hex_x, hex_y)
    assert hex_after is not None, f"[{test_name}] Hex ({hex_x},{hex_y}) should still exist"
    assert hex_after.color == color2, f"[{test_name}] Hex ({hex_x},{hex_y}) should be {color2.value} after build, got {hex_after.color.value}"
    assert hex_after.piece == PieceType.SPEARMAN, f"[{test_name}] Hex ({hex_x},{hex_y}) should have spearman, got {hex_after.piece}"
    
    return game_state


@visual_test("split province test A", "Test A: red split by aqua at (2,0)")
class SplitProvinceTestA(VisualTest):
    """Test for province splitting scenarios."""
    
    def get_map_file_path(self):
        """Override to use the shared map file."""
        from pathlib import Path
        maps_dir = Path(__file__).parent.parent / 'visual' / 'maps'
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / "split_province_test.map"
    
    def setup(self) -> GameState:
        """Set up initial state from map file."""
        # Load from map file
        game_state = self.load_map()
        
        if game_state is None:
            raise ValueError("Failed to load split_province_test.map - map file is required")
        
        return game_state
    
    def run(self, game_state: GameState) -> GameState:
        """Run test A: red split by aqua at (2,0)."""
        return _run_split_test(game_state, HColor.RED, HColor.AQUA, 2, 0, "Test A")


@visual_test("split province test B", "Test B: red split by aqua at (2,-2)")
class SplitProvinceTestB(VisualTest):
    """Test B: red split by aqua at (2,-2)."""
    
    def get_map_file_path(self):
        """Override to use the shared map file."""
        from pathlib import Path
        maps_dir = Path(__file__).parent.parent / 'visual' / 'maps'
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / "split_province_test.map"
    
    def setup(self) -> GameState:
        """Set up initial state from map file."""
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load split_province_test.map - map file is required")
        return game_state
    
    def run(self, game_state: GameState) -> GameState:
        """Run test B: red split by aqua at (2,-2)."""
        return _run_split_test(game_state, HColor.RED, HColor.AQUA, 2, -2, "Test B")


@visual_test("split province test C", "Test C: aqua split by red at (1,-1)")
class SplitProvinceTestC(VisualTest):
    """Test C: aqua split by red at (1,-1)."""
    
    def get_map_file_path(self):
        """Override to use the shared map file."""
        from pathlib import Path
        maps_dir = Path(__file__).parent.parent / 'visual' / 'maps'
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / "split_province_test.map"
    
    def setup(self) -> GameState:
        """Set up initial state from map file."""
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load split_province_test.map - map file is required")
        return game_state
    
    def run(self, game_state: GameState) -> GameState:
        """Run test C: aqua split by red at (1,-1)."""
        return _run_split_test(game_state, HColor.AQUA, HColor.RED, 1, -1, "Test C")


@visual_test("split province test D", "Test D: aqua split by lavender at (1,-3)")
class SplitProvinceTestD(VisualTest):
    """Test D: aqua split by lavender at (1,-3)."""
    
    def get_map_file_path(self):
        """Override to use the shared map file."""
        from pathlib import Path
        maps_dir = Path(__file__).parent.parent / 'visual' / 'maps'
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / "split_province_test.map"
    
    def setup(self) -> GameState:
        """Set up initial state from map file."""
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load split_province_test.map - map file is required")
        return game_state
    
    def run(self, game_state: GameState) -> GameState:
        """Run test D: aqua split by lavender at (1,-3)."""
        return _run_split_test(game_state, HColor.AQUA, HColor.LAVENDER, 1, -3, "Test D")


@visual_test("split province test E", "Test E: lavender split by aqua at (0,0)")
class SplitProvinceTestE(VisualTest):
    """Test E: lavender split by aqua at (0,0)."""
    
    def get_map_file_path(self):
        """Override to use the shared map file."""
        from pathlib import Path
        maps_dir = Path(__file__).parent.parent / 'visual' / 'maps'
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / "split_province_test.map"
    
    def setup(self) -> GameState:
        """Set up initial state from map file."""
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load split_province_test.map - map file is required")
        return game_state
    
    def run(self, game_state: GameState) -> GameState:
        """Run test E: lavender split by aqua at (0,0)."""
        return _run_split_test(game_state, HColor.LAVENDER, HColor.AQUA, 0, 0, "Test E")


@visual_test("split province test F", "Test F: lavender split by aqua at (0,2)")
class SplitProvinceTestF(VisualTest):
    """Test F: lavender split by aqua at (0,2)."""
    
    def get_map_file_path(self):
        """Override to use the shared map file."""
        from pathlib import Path
        maps_dir = Path(__file__).parent.parent / 'visual' / 'maps'
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir / "split_province_test.map"
    
    def setup(self) -> GameState:
        """Set up initial state from map file."""
        game_state = self.load_map()
        if game_state is None:
            raise ValueError("Failed to load split_province_test.map - map file is required")
        return game_state
    
    def run(self, game_state: GameState) -> GameState:
        """Run test F: lavender split by aqua at (0,2)."""
        return _run_split_test(game_state, HColor.LAVENDER, HColor.AQUA, 0, 2, "Test F")


# Pytest-compatible test functions
def test_split_province_A():
    """Run split province test A (can be executed with pytest)."""
    test = SplitProvinceTestA("split province test A", "Test A: red split by aqua at (2,0)")
    initial, final = test.execute()
    assert initial is not None and final is not None
    print("Split province test A passed!")


def test_split_province_B():
    """Run split province test B (can be executed with pytest)."""
    test = SplitProvinceTestB("split province test B", "Test B: red split by aqua at (2,-2)")
    initial, final = test.execute()
    assert initial is not None and final is not None
    print("Split province test B passed!")


def test_split_province_C():
    """Run split province test C (can be executed with pytest)."""
    test = SplitProvinceTestC("split province test C", "Test C: aqua split by red at (1,-1)")
    initial, final = test.execute()
    assert initial is not None and final is not None
    print("Split province test C passed!")


def test_split_province_D():
    """Run split province test D (can be executed with pytest)."""
    test = SplitProvinceTestD("split province test D", "Test D: aqua split by lavender at (1,-3)")
    initial, final = test.execute()
    assert initial is not None and final is not None
    print("Split province test D passed!")


def test_split_province_E():
    """Run split province test E (can be executed with pytest)."""
    test = SplitProvinceTestE("split province test E", "Test E: lavender split by aqua at (0,0)")
    initial, final = test.execute()
    assert initial is not None and final is not None
    print("Split province test E passed!")


def test_split_province_F():
    """Run split province test F (can be executed with pytest)."""
    test = SplitProvinceTestF("split province test F", "Test F: lavender split by aqua at (0,2)")
    initial, final = test.execute()
    assert initial is not None and final is not None
    print("Split province test F passed!")
