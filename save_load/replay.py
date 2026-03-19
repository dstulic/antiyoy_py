"""Save game replay when game end condition is reached.

Replay filename format: {source}-{YY-MM-DD-HH-MM-SS}-{source-details}.replay
- AI playthrough: source="ai", source_details="{level}-{ai}-{total-turn-count}"
- Web game: source="web", source_details="human-{level}-{dash-separated-ai-levels}"
"""

import os
from datetime import datetime
from typing import Optional

from core.game_state import GameState
from save_load.encoder import GameStateEncoder


REPLAYS_DIR = "replays"


def _sanitize_filename_part(s: str) -> str:
    """Replace characters that are unsafe in filenames with dash."""
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in str(s))


def save_replay(
    game_state: GameState,
    source: str,
    source_details: str,
    campaign_level_index: int = -1,
    replays_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Encode the current game state and save it to replays/{source}-{timestamp}-{source_details}.replay.

    Args:
        game_state: The game state to save.
        source: "ai" or "web".
        source_details: For ai: "{level}-{ai}-{turn_count}"; for web: "human-{level}-{ai1}-{ai2}-...".
        campaign_level_index: Campaign level index for the encoder (-1 if not campaign).
        replays_dir: Directory for replay files (default: REPLAYS_DIR relative to cwd).

    Returns:
        Path to the saved file, or None on failure.
    """
    if replays_dir is None:
        replays_dir = REPLAYS_DIR
    os.makedirs(replays_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%y-%m-%d-%H-%M-%S")
    safe_details = _sanitize_filename_part(source_details)
    filename = f"{source}-{timestamp}-{safe_details}.replay"
    filepath = os.path.join(replays_dir, filename)
    try:
        encoder = GameStateEncoder()
        level_code = encoder.encode(game_state, campaign_level_index=campaign_level_index)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(level_code)
        return filepath
    except Exception:
        return None
