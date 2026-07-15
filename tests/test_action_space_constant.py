"""Verify MAX_CAMPAIGN_HEXES in ml/config.py covers all campaign levels."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from save_load.decoder import GameStateDecoder
from campaign.levels import LEVEL_CODES
from ml.config import MAX_CAMPAIGN_HEXES


class TestActionSpaceConstant:

    def test_max_campaign_hexes_covers_all_levels(self):
        decoder = GameStateDecoder()
        for idx, code in LEVEL_CODES.items():
            if not code or code == "-":
                continue
            result = decoder.decode(code)
            gs = result[0] if isinstance(result, tuple) else result
            assert gs is not None, f"Failed to decode level {idx}"
            n_hexes = len(gs.hexes)
            assert n_hexes <= MAX_CAMPAIGN_HEXES, (
                f"Level {idx} has {n_hexes} hexes, exceeding "
                f"MAX_CAMPAIGN_HEXES={MAX_CAMPAIGN_HEXES}"
            )

    def test_max_campaign_hexes_is_tight(self):
        """Ensure the constant equals the actual max, not an inflated value."""
        decoder = GameStateDecoder()
        actual_max = 0
        for idx, code in LEVEL_CODES.items():
            if not code or code == "-":
                continue
            result = decoder.decode(code)
            gs = result[0] if isinstance(result, tuple) else result
            if gs:
                actual_max = max(actual_max, len(gs.hexes))
        assert actual_max == MAX_CAMPAIGN_HEXES, (
            f"MAX_CAMPAIGN_HEXES={MAX_CAMPAIGN_HEXES} but actual max is "
            f"{actual_max}. Update the constant."
        )
