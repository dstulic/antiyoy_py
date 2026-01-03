"""Unit tests for save_load/format.py."""

import pytest
from save_load.format import (
    get_section,
    has_section,
    extract_all_sections,
    is_valid_level_code,
    start_section,
    SECTION_TITLE,
    SECTION_HEXES,
    SECTION_PLAYER_ENTITIES,
    SECTION_CORE_INIT,
)


class TestSaveFormat:
    """Tests for save format utilities."""

    def test_get_section(self):
        """Test get_section() function."""
        level_code = (
            "onliyoy_level_code#client_init:small,-1#hexes:0 0 gray,1 0 red"
            "#player_entities:human>red>Player1#rules:def 1"
        )
        
        assert get_section(level_code, "hexes") == "0 0 gray,1 0 red"
        assert get_section(level_code, "player_entities") == "human>red>Player1"
        assert get_section(level_code, "rules") == "def 1"
        assert get_section(level_code, "client_init") == "small,-1"
        assert get_section(level_code, "nonexistent") is None

    def test_get_section_last_section(self):
        """Test get_section() for the last section."""
        level_code = "onliyoy_level_code#hexes:0 0 gray#rules:def 1"
        assert get_section(level_code, "rules") == "def 1"

    def test_get_section_empty(self):
        """Test get_section() with empty section."""
        level_code = "onliyoy_level_code#hexes:#rules:def 1"
        assert get_section(level_code, "hexes") == ""

    def test_has_section(self):
        """Test has_section() function."""
        level_code = (
            "onliyoy_level_code#hexes:0 0 gray#player_entities:human>red>Player1"
        )
        
        assert has_section(level_code, SECTION_TITLE) is True
        assert has_section(level_code, "hexes") is True
        assert has_section(level_code, "player_entities") is True
        assert has_section(level_code, "nonexistent") is False

    def test_extract_all_sections(self):
        """Test extract_all_sections() function."""
        level_code = (
            "onliyoy_level_code#client_init:small,-1#hexes:0 0 gray"
            "#player_entities:human>red>Player1#rules:def 1"
        )
        
        sections = extract_all_sections(level_code)
        
        assert SECTION_TITLE in sections
        assert sections["client_init"] == "small,-1"
        assert sections["hexes"] == "0 0 gray"
        assert sections["player_entities"] == "human>red>Player1"
        assert sections["rules"] == "def 1"

    def test_is_valid_level_code(self):
        """Test is_valid_level_code() function."""
        valid_code = (
            "onliyoy_level_code#core_init:546.0 873.6 29.4"
            "#hexes:0 0 gray#player_entities:human>red>Player1"
        )
        assert is_valid_level_code(valid_code) is True
        
        invalid_code = "not_a_level_code"
        assert is_valid_level_code(invalid_code) is False
        
        invalid_code2 = "onliyoy_level_code#hexes:0 0 gray"
        assert is_valid_level_code(invalid_code2) is False  # Missing required sections
        
        invalid_code3 = ""
        assert is_valid_level_code(invalid_code3) is False

    def test_start_section(self):
        """Test start_section() function."""
        assert start_section("hexes") == "#hexes:"
        assert start_section("player_entities") == "#player_entities:"
