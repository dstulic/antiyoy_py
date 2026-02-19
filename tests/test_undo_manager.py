"""Unit tests for undo manager functionality."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType
from core.hex import Hex
from core.events import EventPieceBuild
from commands.types import BuildPieceCommand
from commands.executor import CommandExecutor
from save_load.decoder import _build_adjacency_graph


def create_simple_game_state() -> GameState:
    """Create a simple game state for testing."""
    game_state = GameState()
    game_state.set_ruleset(RulesType.DEF, version_code=1)
    
    # Create a small hex grid (3x3)
    # Red province in center
    hexes = []
    for q in range(-1, 2):
        for r in range(-1, 2):
            # Center hex is red with city, others are red empty
            if q == 0 and r == 0:
                hex = game_state.add_hex(q, r, HColor.RED)
                hex.piece = PieceType.CITY
            else:
                hex = game_state.add_hex(q, r, HColor.RED)
            hexes.append(hex)
    
    # Build adjacency graph
    _build_adjacency_graph(game_state)
    
    # Create player entity
    from core.player_entity import PlayerEntity
    player = PlayerEntity(game_state.entities_manager, EntityType.HUMAN, HColor.RED)
    player.set_name("TestPlayer")
    # Initialize entities list if needed
    if game_state.entities_manager.entities is None:
        game_state.entities_manager.entities = []
    game_state.entities_manager.entities.append(player)
    
    # Build provinces
    game_state.provinces_manager.builder.grant_permission()
    game_state.provinces_manager.builder.apply()
    
    # Set initial money for province
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            province.set_money(100)
            break
    
    return game_state


def get_red_province(game_state: GameState):
    """Get the red province from game state."""
    for province in game_state.provinces_manager.provinces:
        if province.get_color() == HColor.RED:
            return province
    return None


def get_empty_hex_in_province(game_state: GameState, province) -> Hex:
    """Get an empty hex in the province."""
    for hex in province.get_hexes():
        if hex.is_empty():
            return hex
    return None


class TestUndoManager:
    """Test undo manager functionality."""
    
    def test_undo_manager_initialized(self):
        """Test that undo manager is initialized with game state."""
        game_state = create_simple_game_state()
        assert hasattr(game_state, 'undo_manager')
        assert game_state.undo_manager is not None
        assert game_state.undo_manager.game_state == game_state
    
    def test_undo_farm_build(self):
        """Test undoing a farm build."""
        game_state = create_simple_game_state()
        province = get_red_province(game_state)
        initial_money = province.get_money()
        
        # Find an empty hex adjacent to city (for farm placement)
        city_hex = None
        for hex in province.get_hexes():
            if hex.piece == PieceType.CITY:
                city_hex = hex
                break
        
        # Find adjacent empty hex
        build_hex = None
        for adj_hex in city_hex.adjacent_hexes:
            if adj_hex.color == HColor.RED and adj_hex.is_empty():
                build_hex = adj_hex
                break
        
        assert build_hex is not None, "No valid hex for farm placement"
        
        # Build farm
        command = BuildPieceCommand(hex=build_hex, piece_type=PieceType.FARM)
        executor = CommandExecutor(game_state)
        current_entity = game_state.entities_manager.get_current_entity()
        success, error = executor.execute(command, current_entity.color)
        
        assert success, f"Build failed: {error}"
        assert build_hex.piece == PieceType.FARM
        assert province.get_money() < initial_money
        
        # Store state after build
        money_after_build = province.get_money()
        
        # Undo
        assert game_state.undo_manager.can_undo()
        undo_success = game_state.undo_manager.undo()
        assert undo_success, "Undo failed"
        
        # Re-find province after undo (provinces might have been rebuilt)
        province_after_undo = get_red_province(game_state)
        assert province_after_undo is not None, "Province not found after undo"
        
        # Verify state restored
        assert build_hex.piece is None, f"Hex should be empty but has {build_hex.piece}"
        assert province_after_undo.get_money() == initial_money, \
            f"Money not restored: expected {initial_money}, got {province_after_undo.get_money()}"
    
    def test_undo_tower_build(self):
        """Test undoing a tower build."""
        game_state = create_simple_game_state()
        province = get_red_province(game_state)
        initial_money = province.get_money()
        
        # Find empty hex
        build_hex = get_empty_hex_in_province(game_state, province)
        assert build_hex is not None
        
        # Build tower
        command = BuildPieceCommand(hex=build_hex, piece_type=PieceType.TOWER)
        executor = CommandExecutor(game_state)
        current_entity = game_state.entities_manager.get_current_entity()
        success, error = executor.execute(command, current_entity.color)
        
        assert success, f"Build failed: {error}"
        assert build_hex.piece == PieceType.TOWER
        assert province.get_money() < initial_money
        
        # Undo
        assert game_state.undo_manager.can_undo()
        undo_success = game_state.undo_manager.undo()
        assert undo_success, "Undo failed"
        
        # Re-find province after undo (provinces might have been rebuilt)
        province_after_undo = get_red_province(game_state)
        assert province_after_undo is not None, "Province not found after undo"
        
        # Verify state restored
        assert build_hex.piece is None, f"Hex should be empty but has {build_hex.piece}"
        assert province_after_undo.get_money() == initial_money, \
            f"Money not restored: expected {initial_money}, got {province_after_undo.get_money()}"
    
    def test_undo_strong_tower_build(self):
        """Test undoing a strong tower build."""
        game_state = create_simple_game_state()
        province = get_red_province(game_state)
        initial_money = province.get_money()
        
        # First build a tower
        build_hex = get_empty_hex_in_province(game_state, province)
        assert build_hex is not None
        
        command = BuildPieceCommand(hex=build_hex, piece_type=PieceType.TOWER)
        executor = CommandExecutor(game_state)
        current_entity = game_state.entities_manager.get_current_entity()
        success, error = executor.execute(command, current_entity.color)
        assert success
        
        money_after_tower = province.get_money()
        
        # Build strong tower on tower
        command = BuildPieceCommand(hex=build_hex, piece_type=PieceType.STRONG_TOWER)
        success, error = executor.execute(command, current_entity.color)
        
        assert success, f"Build failed: {error}"
        assert build_hex.piece == PieceType.STRONG_TOWER
        assert province.get_money() < money_after_tower
        
        # Undo strong tower (should restore to tower)
        assert game_state.undo_manager.can_undo()
        undo_success = game_state.undo_manager.undo()
        assert undo_success, "Undo failed"
        
        # Re-find province after undo
        province_after_undo = get_red_province(game_state)
        assert province_after_undo is not None, "Province not found after undo"
        
        # Verify state restored to tower
        assert build_hex.piece == PieceType.TOWER, f"Expected tower, got {build_hex.piece}"
        assert province_after_undo.get_money() == money_after_tower, \
            f"Money not restored: expected {money_after_tower}, got {province_after_undo.get_money()}"
    
    def test_undo_peasant_build(self):
        """Test undoing a peasant (unit) build."""
        game_state = create_simple_game_state()
        province = get_red_province(game_state)
        initial_money = province.get_money()
        
        # Find hex adjacent to province for unit placement
        province_hex = province.get_hexes()[0]
        build_hex = None
        for adj_hex in province_hex.adjacent_hexes:
            if adj_hex.is_empty() or adj_hex.piece in (PieceType.PINE, PieceType.PALM, PieceType.GRAVE):
                build_hex = adj_hex
                break
        
        # If no adjacent empty hex, create one
        if build_hex is None:
            build_hex = game_state.add_hex(2, 0, HColor.GRAY)
            _build_adjacency_graph(game_state)
            # Rebuild provinces to include new hex in adjacency
            game_state.provinces_manager.builder.grant_permission()
            game_state.provinces_manager.builder.apply()
        
        # Build peasant
        command = BuildPieceCommand(
            hex=build_hex,
            piece_type=PieceType.PEASANT,
            province_hex=province_hex
        )
        executor = CommandExecutor(game_state)
        current_entity = game_state.entities_manager.get_current_entity()
        success, error = executor.execute(command, current_entity.color)
        
        assert success, f"Build failed: {error}"
        assert build_hex.piece == PieceType.PEASANT
        assert province.get_money() < initial_money
        
        # Undo
        assert game_state.undo_manager.can_undo()
        undo_success = game_state.undo_manager.undo()
        assert undo_success, "Undo failed"
        
        # Re-find province after undo
        province_after_undo = get_red_province(game_state)
        assert province_after_undo is not None, "Province not found after undo"
        
        # Verify state restored
        # Note: Unit on gray hex might change hex color, so we check piece is gone
        # The hex might still be colored if it was merged into province
        # For a gray hex, the piece should be removed
        if build_hex.color == HColor.GRAY:
            assert build_hex.piece is None
        # Money should be restored
        assert province_after_undo.get_money() == initial_money, \
            f"Money not restored: expected {initial_money}, got {province_after_undo.get_money()}"
    
    def test_undo_spearman_build(self):
        """Test undoing a spearman build."""
        game_state = create_simple_game_state()
        province = get_red_province(game_state)
        initial_money = province.get_money()
        
        # Find hex adjacent to province
        province_hex = province.get_hexes()[0]
        build_hex = None
        for adj_hex in province_hex.adjacent_hexes:
            if adj_hex.is_empty():
                build_hex = adj_hex
                break
        
        if build_hex is None:
            build_hex = game_state.add_hex(2, 0, HColor.GRAY)
            _build_adjacency_graph(game_state)
            game_state.provinces_manager.builder.grant_permission()
            game_state.provinces_manager.builder.apply()
        
        # Build spearman
        command = BuildPieceCommand(
            hex=build_hex,
            piece_type=PieceType.SPEARMAN,
            province_hex=province_hex
        )
        executor = CommandExecutor(game_state)
        current_entity = game_state.entities_manager.get_current_entity()
        success, error = executor.execute(command, current_entity.color)
        
        assert success, f"Build failed: {error}"
        assert build_hex.piece == PieceType.SPEARMAN
        
        # Undo
        assert game_state.undo_manager.can_undo()
        undo_success = game_state.undo_manager.undo()
        assert undo_success
        
        # Re-find province after undo
        province_after_undo = get_red_province(game_state)
        assert province_after_undo is not None, "Province not found after undo"
        
        # Verify money restored
        assert province_after_undo.get_money() == initial_money, \
            f"Money not restored: expected {initial_money}, got {province_after_undo.get_money()}"
    
    def test_undo_baron_build(self):
        """Test undoing a baron build."""
        game_state = create_simple_game_state()
        province = get_red_province(game_state)
        initial_money = province.get_money()
        
        # Find hex adjacent to province
        province_hex = province.get_hexes()[0]
        build_hex = None
        for adj_hex in province_hex.adjacent_hexes:
            if adj_hex.is_empty():
                build_hex = adj_hex
                break
        
        if build_hex is None:
            build_hex = game_state.add_hex(2, 0, HColor.GRAY)
            _build_adjacency_graph(game_state)
            game_state.provinces_manager.builder.grant_permission()
            game_state.provinces_manager.builder.apply()
        
        # Build baron
        command = BuildPieceCommand(
            hex=build_hex,
            piece_type=PieceType.BARON,
            province_hex=province_hex
        )
        executor = CommandExecutor(game_state)
        current_entity = game_state.entities_manager.get_current_entity()
        success, error = executor.execute(command, current_entity.color)
        
        assert success, f"Build failed: {error}"
        assert build_hex.piece == PieceType.BARON
        
        # Undo
        assert game_state.undo_manager.can_undo()
        undo_success = game_state.undo_manager.undo()
        assert undo_success
        
        # Re-find province after undo
        province_after_undo = get_red_province(game_state)
        assert province_after_undo is not None, "Province not found after undo"
        
        # Verify money restored
        assert province_after_undo.get_money() == initial_money, \
            f"Money not restored: expected {initial_money}, got {province_after_undo.get_money()}"
    
    def test_undo_knight_build(self):
        """Test undoing a knight build."""
        game_state = create_simple_game_state()
        province = get_red_province(game_state)
        initial_money = province.get_money()
        
        # Find hex adjacent to province
        province_hex = province.get_hexes()[0]
        build_hex = None
        for adj_hex in province_hex.adjacent_hexes:
            if adj_hex.is_empty():
                build_hex = adj_hex
                break
        
        if build_hex is None:
            build_hex = game_state.add_hex(2, 0, HColor.GRAY)
            _build_adjacency_graph(game_state)
            game_state.provinces_manager.builder.grant_permission()
            game_state.provinces_manager.builder.apply()
        
        # Build knight
        command = BuildPieceCommand(
            hex=build_hex,
            piece_type=PieceType.KNIGHT,
            province_hex=province_hex
        )
        executor = CommandExecutor(game_state)
        current_entity = game_state.entities_manager.get_current_entity()
        success, error = executor.execute(command, current_entity.color)
        
        assert success, f"Build failed: {error}"
        assert build_hex.piece == PieceType.KNIGHT
        
        # Undo
        assert game_state.undo_manager.can_undo()
        undo_success = game_state.undo_manager.undo()
        assert undo_success
        
        # Re-find province after undo
        province_after_undo = get_red_province(game_state)
        assert province_after_undo is not None, "Province not found after undo"
        
        # Verify money restored
        assert province_after_undo.get_money() == initial_money, \
            f"Money not restored: expected {initial_money}, got {province_after_undo.get_money()}"
    
    def test_multiple_undos(self):
        """Test multiple consecutive undos."""
        game_state = create_simple_game_state()
        province = get_red_province(game_state)
        initial_money = province.get_money()
        
        executor = CommandExecutor(game_state)
        current_entity = game_state.entities_manager.get_current_entity()
        
        # Build multiple pieces
        builds = []
        
        # Build farm
        city_hex = None
        for hex in province.get_hexes():
            if hex.piece == PieceType.CITY:
                city_hex = hex
                break
        
        for adj_hex in city_hex.adjacent_hexes:
            if adj_hex.color == HColor.RED and adj_hex.is_empty():
                command = BuildPieceCommand(hex=adj_hex, piece_type=PieceType.FARM)
                success, _ = executor.execute(command, current_entity.color)
                if success:
                    builds.append(adj_hex)
                    break
        
        # Build tower
        build_hex = get_empty_hex_in_province(game_state, province)
        if build_hex:
            command = BuildPieceCommand(hex=build_hex, piece_type=PieceType.TOWER)
            success, _ = executor.execute(command, current_entity.color)
            if success:
                builds.append(build_hex)
        
        # Verify builds happened
        assert len(builds) >= 1
        
        # Undo all builds
        for i in range(len(builds)):
            assert game_state.undo_manager.can_undo()
            undo_success = game_state.undo_manager.undo()
            assert undo_success
        
        # Re-find province after undo
        province_after_undo = get_red_province(game_state)
        assert province_after_undo is not None, "Province not found after undo"
        
        # Verify all pieces are gone and money is restored
        for build_hex in builds:
            assert build_hex.piece is None
        
        assert province_after_undo.get_money() == initial_money, \
            f"Money not restored: expected {initial_money}, got {province_after_undo.get_money()}"
    
    def test_undo_cleared_on_turn_end(self):
        """Test that undo list is cleared when turn ends."""
        game_state = create_simple_game_state()
        province = get_red_province(game_state)
        
        # Build something
        build_hex = get_empty_hex_in_province(game_state, province)
        if build_hex:
            command = BuildPieceCommand(hex=build_hex, piece_type=PieceType.TOWER)
            executor = CommandExecutor(game_state)
            current_entity = game_state.entities_manager.get_current_entity()
            executor.execute(command, current_entity.color)
        
        # Verify undo is available
        assert game_state.undo_manager.can_undo()
        
        # End turn
        from core.events import EventTurnEnd, SYSTEM_AUTHOR
        event = EventTurnEnd()
        event.set_core_model(game_state)
        game_state.events_manager.apply_event(event, author=SYSTEM_AUTHOR)
        
        # Verify undo list is cleared
        assert not game_state.undo_manager.can_undo()
        assert len(game_state.undo_manager.items) == 0
    
    def test_undo_restores_province_money(self):
        """Test that undo correctly restores province money."""
        game_state = create_simple_game_state()
        province = get_red_province(game_state)
        initial_money = province.get_money()
        
        # Build expensive piece
        build_hex = get_empty_hex_in_province(game_state, province)
        if build_hex:
            command = BuildPieceCommand(hex=build_hex, piece_type=PieceType.KNIGHT)
            executor = CommandExecutor(game_state)
            current_entity = game_state.entities_manager.get_current_entity()
            success, error = executor.execute(command, current_entity.color)
            
            if success:
                money_after_build = province.get_money()
                assert money_after_build < initial_money
                
                # Undo
                assert game_state.undo_manager.can_undo()
                undo_success = game_state.undo_manager.undo()
                assert undo_success, "Undo failed"
                
                # Re-find province after undo
                province_after_undo = get_red_province(game_state)
                assert province_after_undo is not None, "Province not found after undo"
                
                # Verify money restored
                assert province_after_undo.get_money() == initial_money, \
                    f"Money not restored: expected {initial_money}, got {province_after_undo.get_money()}"


if __name__ == '__main__':
    # Simple test runner
    test = TestUndoManager()
    test.test_undo_manager_initialized()
    print("✓ test_undo_manager_initialized passed")
    
    test.test_undo_farm_build()
    print("✓ test_undo_farm_build passed")
    
    test.test_undo_tower_build()
    print("✓ test_undo_tower_build passed")
    
    test.test_undo_strong_tower_build()
    print("✓ test_undo_strong_tower_build passed")
    
    test.test_undo_peasant_build()
    print("✓ test_undo_peasant_build passed")
    
    test.test_undo_spearman_build()
    print("✓ test_undo_spearman_build passed")
    
    test.test_undo_baron_build()
    print("✓ test_undo_baron_build passed")
    
    test.test_undo_knight_build()
    print("✓ test_undo_knight_build passed")
    
    test.test_multiple_undos()
    print("✓ test_multiple_undos passed")
    
    test.test_undo_cleared_on_turn_end()
    print("✓ test_undo_cleared_on_turn_end passed")
    
    test.test_undo_restores_province_money()
    print("✓ test_undo_restores_province_money passed")
    
    print("\nAll tests passed!")
