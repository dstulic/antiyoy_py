"""Unit tests for campaign/levels.py."""

import pytest
from campaign.levels import get_level_code, LEVEL_CODES


class TestCampaignLevels:
    """Tests for campaign levels."""

    def test_get_level_code(self):
        """Test get_level_code() function."""
        # Level 0 should return "-"
        assert get_level_code(0) == "-"
        # Level 1 should return a level code
        level1 = get_level_code(1)
        assert level1 != "-"
        assert "onliyoy_level_code" in level1
        # Invalid level should return "-"
        assert get_level_code(999) == "-"

    def test_level_codes_exist(self):
        """Test that level codes exist."""
        assert 0 in LEVEL_CODES
        assert 1 in LEVEL_CODES
        # Check a few more
        assert 10 in LEVEL_CODES
        assert 50 in LEVEL_CODES
        assert 100 in LEVEL_CODES

    def test_level_code_format(self):
        """Test that level codes have correct format."""
        level1 = get_level_code(1)
        # Should start with onliyoy_level_code
        assert level1.startswith("onliyoy_level_code")
        # Should contain key sections
        assert "#hexes:" in level1
        assert "#player_entities:" in level1
        assert "#provinces:" in level1
