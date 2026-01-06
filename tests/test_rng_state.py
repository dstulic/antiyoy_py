"""Unit tests for RNG state save/load functionality."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from save_load.decoder import GameStateDecoder
from save_load.encoder import GameStateEncoder
from campaign.levels import get_level_code
from core.rng_utils import get_deterministic_seed


class TestRNGState:
    """Tests for RNG state management."""

    def test_deterministic_seed_from_level_code(self):
        """Test that the same level code always produces the same seed."""
        level_code = get_level_code(1)
        
        seed1 = get_deterministic_seed(level_code)
        seed2 = get_deterministic_seed(level_code)
        
        assert seed1 == seed2, "Same level code should produce same seed"
        assert seed1 > 0, "Seed should be positive"
        assert isinstance(seed1, int), "Seed should be an integer"

    def test_different_level_codes_produce_different_seeds(self):
        """Test that different level codes produce different seeds."""
        level_code1 = get_level_code(1)
        level_code2 = get_level_code(2)
        
        if level_code1 and level_code2:
            seed1 = get_deterministic_seed(level_code1)
            seed2 = get_deterministic_seed(level_code2)
            
            assert seed1 != seed2, "Different level codes should produce different seeds"

    def test_empty_level_code_produces_zero_seed(self):
        """Test that empty level code produces zero seed."""
        seed = get_deterministic_seed("")
        assert seed == 0, "Empty level code should produce zero seed"

    def test_original_level_code_stored_on_decode(self):
        """Test that original level code is stored when decoding."""
        decoder = GameStateDecoder()
        level_code = get_level_code(1)
        
        if not level_code or level_code == "-":
            return  # Skip if level doesn't exist
        
        game_state, _ = decoder.decode(level_code)
        
        assert hasattr(game_state, '_original_level_code'), "GameState should have _original_level_code attribute"
        assert game_state._original_level_code == level_code, "Original level code should be stored correctly"

    def test_tree_manager_rng_initialized_with_deterministic_seed(self):
        """Test that TreeManager RNG is initialized with deterministic seed."""
        decoder = GameStateDecoder()
        level_code = get_level_code(1)
        
        if not level_code or level_code == "-":
            return  # Skip if level doesn't exist
        
        game_state, _ = decoder.decode(level_code)
        
        assert hasattr(game_state.tree_manager, 'random'), "TreeManager should have random attribute"
        
        # Get first random value
        r1 = game_state.tree_manager.random.random()
        
        # Decode again - should produce same first random value
        game_state2, _ = decoder.decode(level_code)
        r2 = game_state2.tree_manager.random.random()
        
        assert r1 == r2, "Same level code should produce same first random value"

    def test_deterministic_random_sequence_for_same_level(self):
        """Test that same level code produces identical random sequences."""
        decoder = GameStateDecoder()
        level_code = get_level_code(1)
        
        if not level_code or level_code == "-":
            return  # Skip if level doesn't exist
        
        # First decode
        game_state1, _ = decoder.decode(level_code)
        values1 = [game_state1.tree_manager.random.random() for _ in range(5)]
        
        # Second decode
        game_state2, _ = decoder.decode(level_code)
        values2 = [game_state2.tree_manager.random.random() for _ in range(5)]
        
        assert values1 == values2, "Same level code should produce identical random sequences"

    def test_rng_state_saved_and_restored(self):
        """Test that RNG state is saved and restored correctly."""
        decoder = GameStateDecoder()
        encoder = GameStateEncoder()
        level_code = get_level_code(1)
        
        if not level_code or level_code == "-":
            return  # Skip if level doesn't exist
        
        # Decode and generate some random numbers
        game_state, _ = decoder.decode(level_code)
        initial_values = [game_state.tree_manager.random.random() for _ in range(3)]
        
        # Get RNG state
        rng_state = game_state.get_rng_state()
        assert rng_state is not None, "RNG state should be available"
        
        # Save game
        saved_code = encoder.encode(game_state, campaign_level_index=1)
        assert len(saved_code) > 0, "Saved code should not be empty"
        
        # Load game
        game_state2, _ = decoder.decode(saved_code)
        
        # Verify RNG state was restored
        restored_rng_state = game_state2.get_rng_state()
        assert restored_rng_state is not None, "RNG state should be restored"
        
        # Generate next random values - should continue from where we left off
        next_values = [game_state2.tree_manager.random.random() for _ in range(3)]
        
        # Values should be different (RNG continued)
        assert next_values != initial_values, "RNG should continue from saved state"

    def test_rng_state_continues_after_save_load(self):
        """Test that RNG continues correctly after save/load cycle."""
        decoder = GameStateDecoder()
        encoder = GameStateEncoder()
        level_code = get_level_code(1)
        
        if not level_code or level_code == "-":
            return  # Skip if level doesn't exist
        
        # Decode and generate random numbers
        game_state1, _ = decoder.decode(level_code)
        values_before_save = [game_state1.tree_manager.random.random() for _ in range(5)]
        
        # Save
        saved_code = encoder.encode(game_state1, campaign_level_index=1)
        
        # Continue generating in original state
        values_after_save_original = [game_state1.tree_manager.random.random() for _ in range(3)]
        
        # Load and continue generating
        game_state2, _ = decoder.decode(saved_code)
        values_after_load = [game_state2.tree_manager.random.random() for _ in range(3)]
        
        # Values after load should match values after save in original
        assert values_after_load == values_after_save_original, "RNG should continue correctly after load"

    def test_fresh_level_has_no_rng_state(self):
        """Test that fresh level (not saved) has no RNG state initially."""
        decoder = GameStateDecoder()
        level_code = get_level_code(1)
        
        if not level_code or level_code == "-":
            return  # Skip if level doesn't exist
        
        game_state, _ = decoder.decode(level_code)
        
        # Fresh level should not have RNG state stored (it's generated from seed)
        # But get_rng_state() should still return the current state
        rng_state = game_state.get_rng_state()
        assert rng_state is not None, "get_rng_state() should return current state even for fresh levels"

    def test_rng_state_encoded_in_saved_game(self):
        """Test that RNG state is encoded in saved game level code."""
        decoder = GameStateDecoder()
        encoder = GameStateEncoder()
        level_code = get_level_code(1)
        
        if not level_code or level_code == "-":
            return  # Skip if level doesn't exist
        
        # Decode and generate some random numbers
        game_state, _ = decoder.decode(level_code)
        game_state.tree_manager.random.random()  # Advance RNG
        
        # Save game
        saved_code = encoder.encode(game_state, campaign_level_index=1)
        
        # Check that RNG state section exists in saved code
        assert "#rng_state:" in saved_code, "Saved code should contain rng_state section"
        
        # RNG state should not be "-" (placeholder)
        rng_section_start = saved_code.find("#rng_state:") + len("#rng_state:")
        rng_section_end = saved_code.find("#", rng_section_start)
        if rng_section_end == -1:
            rng_section_end = len(saved_code)
        rng_state_data = saved_code[rng_section_start:rng_section_end]
        
        assert rng_state_data != "-", "RNG state should be encoded, not placeholder"

    def test_multiple_save_load_cycles(self):
        """Test that RNG state is preserved across multiple save/load cycles."""
        decoder = GameStateDecoder()
        encoder = GameStateEncoder()
        level_code = get_level_code(1)
        
        if not level_code or level_code == "-":
            return  # Skip if level doesn't exist
        
        # Initial decode
        game_state, _ = decoder.decode(level_code)
        initial_value = game_state.tree_manager.random.random()
        
        # First save/load cycle
        saved_code1 = encoder.encode(game_state, campaign_level_index=1)
        game_state1, _ = decoder.decode(saved_code1)
        value1 = game_state1.tree_manager.random.random()
        
        # Second save/load cycle
        saved_code2 = encoder.encode(game_state1, campaign_level_index=1)
        game_state2, _ = decoder.decode(saved_code2)
        value2 = game_state2.tree_manager.random.random()
        
        # All values should be different (RNG advancing)
        assert initial_value != value1, "RNG should advance after first save/load"
        assert value1 != value2, "RNG should advance after second save/load"
        
        # Verify RNG state is preserved
        rng_state1 = game_state1.get_rng_state()
        rng_state2 = game_state2.get_rng_state()
        assert rng_state1 is not None and rng_state2 is not None, "RNG states should be available"

    def test_rng_state_with_different_levels(self):
        """Test that different levels have independent RNG states."""
        decoder = GameStateDecoder()
        level_code1 = get_level_code(1)
        level_code2 = get_level_code(2)
        
        if not level_code1 or level_code1 == "-" or not level_code2 or level_code2 == "-":
            return  # Skip if levels don't exist
        
        # Check that level codes are actually different
        if level_code1 == level_code2:
            return  # Skip if level codes are the same
        
        # Decode both levels
        game_state1, _ = decoder.decode(level_code1)
        game_state2, _ = decoder.decode(level_code2)
        
        # Generate random values from both
        values1 = [game_state1.tree_manager.random.random() for _ in range(3)]
        values2 = [game_state2.tree_manager.random.random() for _ in range(3)]
        
        # Values should be different (different seeds)
        assert values1 != values2, "Different levels should produce different random sequences"
