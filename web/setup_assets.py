"""
Setup script to copy game assets for web interface.
"""

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_SOURCE = PROJECT_ROOT.parent / "antiyoy_hd" / "assets" / "game" / "atlas"
ASSETS_DEST = Path(__file__).parent / "static" / "assets" / "original_game_assets" / "atlas"

def setup_assets():
    """Set up game assets for web interface by copying from original source."""
    if not ASSETS_SOURCE.exists():
        print(f"Warning: Assets source not found at {ASSETS_SOURCE}")
        print("Assets will not be available in the web interface.")
        return False
    
    # Create destination directory
    ASSETS_DEST.mkdir(parents=True, exist_ok=True)
    
    # Check if assets already exist
    if list(ASSETS_DEST.glob("*.png")):
        print(f"Assets already exist at {ASSETS_DEST}")
    else:
        # Copy assets directly to web static folder
        print(f"Copying assets from {ASSETS_SOURCE} to {ASSETS_DEST}...")
        try:
            shutil.copytree(ASSETS_SOURCE, ASSETS_DEST, dirs_exist_ok=True)
            print(f"✓ Copied assets to {ASSETS_DEST}")
        except Exception as e:
            print(f"Error copying assets: {e}")
            return False
    
    print("✓ Assets setup complete!")
    return True

if __name__ == '__main__':
    setup_assets()
