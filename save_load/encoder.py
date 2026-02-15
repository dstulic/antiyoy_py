"""Encoder for save game format."""

import base64
from typing import Optional
from save_load.format import (
    start_section,
    SECTION_TITLE,
    SECTION_CORE_INIT,
    SECTION_HEXES,
    SECTION_CORE_CURRENT_IDS,
    SECTION_PLAYER_ENTITIES,
    SECTION_PROVINCES,
    SECTION_READY,
    SECTION_RULES,
    SECTION_TURN,
    SECTION_FOG,
    SECTION_EVENTS_LIST,
    SECTION_CAMPAIGN,
    SECTION_PAUSE_NAME,
    SECTION_RNG_STATE,
    SECTION_ORIGINAL_LEVEL_CODE,
)
from core.game_state import GameState


class GameStateEncoder:
    """Encodes game state to save string format."""

    def __init__(self):
        """Initialize encoder."""
        pass

    def encode(
        self,
        game_state: GameState,
        campaign_level_index: int = -1,
        pause_name: Optional[str] = None,
    ) -> str:
        """
        Encode a game state to level code string.

        Args:
            game_state: The GameState to encode
            campaign_level_index: Campaign level index (-1 if not a campaign)
            pause_name: Optional pause name

        Returns:
            Level code string
        """
        builder = []

        # Title
        builder.append(SECTION_TITLE)

        # Core initialization
        builder.append(start_section(SECTION_CORE_INIT))
        builder.append(game_state.encode_initialization())
        
        # Hexes
        builder.append(start_section(SECTION_HEXES))
        builder.append(game_state.encode_hexes())
        
        # Core current IDs
        builder.append(start_section(SECTION_CORE_CURRENT_IDS))
        builder.append(game_state.encode_current_ids())
        
        # Player entities
        builder.append(start_section(SECTION_PLAYER_ENTITIES))
        builder.append(game_state.entities_manager.encode())
        
        # Provinces
        builder.append(start_section(SECTION_PROVINCES))
        builder.append(game_state.provinces_manager.encode())
        
        # Ready (readiness manager)
        builder.append(start_section(SECTION_READY))
        builder.append(game_state.readiness_manager.encode())
        
        # Rules
        builder.append(start_section(SECTION_RULES))
        builder.append(game_state.encode_rules())
        
        # Turn
        builder.append(start_section(SECTION_TURN))
        builder.append(game_state.turns_manager.encode())

        # Fog of war
        builder.append(start_section(SECTION_FOG))
        if game_state.fog_of_war_manager and hasattr(game_state.fog_of_war_manager, "enabled"):
            builder.append("true" if game_state.fog_of_war_manager.enabled else "false")
        else:
            builder.append("false")

        # Events list (history)
        if hasattr(game_state, 'history_manager') and game_state.history_manager:
            builder.append(start_section(SECTION_EVENTS_LIST))
            builder.append(game_state.history_manager.encode_events_list())
        else:
            builder.append(start_section(SECTION_EVENTS_LIST))
            builder.append("")  # Empty if no history manager

        # Campaign
        if campaign_level_index != -1:
            builder.append(start_section(SECTION_CAMPAIGN))
            builder.append(str(campaign_level_index))
        
        # Pause name
        if pause_name:
            builder.append(start_section(SECTION_PAUSE_NAME))
            builder.append(pause_name)
        
        # RNG state - save current random number generator state
        rng_state = game_state.get_rng_state()
        if rng_state:
            import pickle
            # Pickle the RNG state tuple to bytes
            rng_state_bytes = pickle.dumps(rng_state)
            # Encode to base64 string for safe storage in level code
            rng_state_str = base64.b64encode(rng_state_bytes).decode('ascii')
            builder.append(start_section(SECTION_RNG_STATE))
            builder.append(rng_state_str)
        else:
            # If no RNG state, store placeholder
            builder.append(start_section(SECTION_RNG_STATE))
            builder.append("-")

        # Original level code (so loaded save restores the level we started from)
        original_b64 = base64.b64encode(
            game_state._original_level_code.encode("utf-8")
        ).decode("ascii")
        builder.append(start_section(SECTION_ORIGINAL_LEVEL_CODE))
        builder.append(original_b64)
        
        # End with #
        builder.append("#")
        
        return "".join(builder)
