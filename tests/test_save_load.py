"""Unit tests for save/load system."""

import pytest
from save_load.decoder import GameStateDecoder
from save_load.encoder import GameStateEncoder
from campaign.levels import get_level_code


class TestSaveLoad:
    """Tests for save/load system."""

    def test_encode_decode_round_trip(self):
        """Test that encoding and decoding preserves game state."""
        decoder = GameStateDecoder()
        encoder = GameStateEncoder()
        
        # Get a level code
        level_code = get_level_code(1)
        assert level_code and level_code != "-"
        
        # Decode
        game_state, campaign_index = decoder.decode(level_code)
        assert game_state is not None
        assert len(game_state.hexes) > 0
        assert len(game_state.entities_manager.entities) > 0
        
        # Encode
        encoded = encoder.encode(game_state, campaign_level_index=campaign_index)
        assert encoded is not None
        assert len(encoded) > 0
        
        # Decode again
        game_state2, campaign_index2 = decoder.decode(encoded)
        assert game_state2 is not None
        assert len(game_state2.hexes) == len(game_state.hexes)
        assert len(game_state2.entities_manager.entities) == len(game_state.entities_manager.entities)
        assert len(game_state2.provinces_manager.provinces) == len(game_state.provinces_manager.provinces)
        assert campaign_index2 == campaign_index

    def test_decode_multiple_levels(self):
        """Test decoding multiple campaign levels."""
        decoder = GameStateDecoder()
        
        for level_index in [1, 2, 3, 4, 5]:
            level_code = get_level_code(level_index)
            if level_code and level_code != "-":
                game_state, campaign_index = decoder.decode(level_code)
                assert game_state is not None
                assert len(game_state.hexes) > 0

    def test_encode_campaign_level(self):
        """Test encoding with campaign level index."""
        decoder = GameStateDecoder()
        encoder = GameStateEncoder()
        
        level_code = get_level_code(1)
        game_state, _ = decoder.decode(level_code)
        
        encoded = encoder.encode(game_state, campaign_level_index=1)
        assert "#campaign:" in encoded
        assert "1" in encoded.split("#campaign:")[1].split("#")[0]
