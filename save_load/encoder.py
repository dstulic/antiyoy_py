"""Encoder for save game format."""

from typing import Optional
from save_load.format import (
    start_section,
    SECTION_TITLE,
    SECTION_CLIENT_INIT,
    SECTION_CAMERA,
    SECTION_CORE_INIT,
    SECTION_HEXES,
    SECTION_CORE_CURRENT_IDS,
    SECTION_PLAYER_ENTITIES,
    SECTION_PROVINCES,
    SECTION_READY,
    SECTION_RULES,
    SECTION_TURN,
    SECTION_DIPLOMACY,
    SECTION_MAIL_BASKET,
    SECTION_FOG,
    SECTION_STARTING_HEXES,
    SECTION_EVENTS_LIST,
    SECTION_STARTING_PROVINCES,
    SECTION_EDITOR,
    SECTION_CAMPAIGN,
    SECTION_PAUSE_NAME,
    SECTION_RNG_STATE,
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
        client_init: Optional[str] = None,
        camera: Optional[str] = None,
        campaign_level_index: int = -1,
        pause_name: Optional[str] = None,
    ) -> str:
        """
        Encode a game state to level code string.
        
        Args:
            game_state: The GameState to encode
            client_init: Optional client initialization data (e.g., "small,-1")
            camera: Optional camera position (e.g., "0.65 1.04 1.0")
            campaign_level_index: Campaign level index (-1 if not a campaign)
            pause_name: Optional pause name
            
        Returns:
            Level code string
        """
        builder = []
        
        # Title
        builder.append(SECTION_TITLE)
        
        # Client initialization
        if client_init:
            builder.append(start_section(SECTION_CLIENT_INIT))
            builder.append(client_init)
        
        # Camera position
        if camera:
            builder.append(start_section(SECTION_CAMERA))
            builder.append(camera)
        
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
        
        # Diplomacy (placeholder)
        builder.append(start_section(SECTION_DIPLOMACY))
        builder.append("off")  # Placeholder
        
        # Mail basket (placeholder)
        builder.append(start_section(SECTION_MAIL_BASKET))
        builder.append("0,")  # Placeholder
        
        # Fog of war (placeholder)
        builder.append(start_section(SECTION_FOG))
        if game_state.fog_of_war_manager and hasattr(game_state.fog_of_war_manager, "enabled"):
            builder.append("true" if game_state.fog_of_war_manager.enabled else "false")
        else:
            builder.append("false")
        
        # Starting hexes (history - placeholder)
        # builder.append(start_section(SECTION_STARTING_HEXES))
        # builder.append("")  # Would need history manager
        
        # Events list (history - placeholder)
        # builder.append(start_section(SECTION_EVENTS_LIST))
        # builder.append("")  # Would need history manager
        
        # Starting provinces (history - placeholder)
        # builder.append(start_section(SECTION_STARTING_PROVINCES))
        # builder.append("")  # Would need history manager
        
        # Editor (placeholder)
        # builder.append(start_section(SECTION_EDITOR))
        # builder.append("")  # Would need editor manager
        
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
            import base64
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
        
        # End with #
        builder.append("#")
        
        return "".join(builder)
