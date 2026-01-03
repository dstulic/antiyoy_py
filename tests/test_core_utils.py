"""Unit tests for core/core_utils.py."""

import pytest
from core.core_utils import is_unit, get_strength, get_unit_by_strength, get_merge_result
from core.enums import PieceType


class TestCoreUtils:
    """Tests for core utility functions."""

    def test_is_unit(self):
        """Test is_unit() function."""
        assert is_unit(PieceType.PEASANT) is True
        assert is_unit(PieceType.SPEARMAN) is True
        assert is_unit(PieceType.BARON) is True
        assert is_unit(PieceType.KNIGHT) is True
        assert is_unit(PieceType.CITY) is False
        assert is_unit(PieceType.TOWER) is False
        assert is_unit(None) is False

    def test_get_strength(self):
        """Test get_strength() function."""
        assert get_strength(PieceType.PEASANT) == 1
        assert get_strength(PieceType.SPEARMAN) == 2
        assert get_strength(PieceType.BARON) == 3
        assert get_strength(PieceType.KNIGHT) == 4
        assert get_strength(PieceType.CITY) == -1
        assert get_strength(None) == -1

    def test_get_unit_by_strength(self):
        """Test get_unit_by_strength() function."""
        assert get_unit_by_strength(1) == PieceType.PEASANT
        assert get_unit_by_strength(2) == PieceType.SPEARMAN
        assert get_unit_by_strength(3) == PieceType.BARON
        assert get_unit_by_strength(4) == PieceType.KNIGHT
        assert get_unit_by_strength(0) is None
        assert get_unit_by_strength(5) is None

    def test_get_merge_result(self):
        """Test get_merge_result() function."""
        # Peasant (1) + Peasant (1) = Spearman (2)
        assert get_merge_result(PieceType.PEASANT, PieceType.PEASANT) == PieceType.SPEARMAN
        # Peasant (1) + Spearman (2) = Baron (3)
        assert get_merge_result(PieceType.PEASANT, PieceType.SPEARMAN) == PieceType.BARON
        # Spearman (2) + Spearman (2) = Knight (4)
        assert get_merge_result(PieceType.SPEARMAN, PieceType.SPEARMAN) == PieceType.KNIGHT
        # Baron (3) + Knight (4) = None (7 > 4)
        assert get_merge_result(PieceType.BARON, PieceType.KNIGHT) is None
        # Non-unit pieces
        assert get_merge_result(PieceType.CITY, PieceType.TOWER) is None
