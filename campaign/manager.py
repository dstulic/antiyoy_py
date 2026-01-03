"""
Campaign Manager - handles campaign progress tracking and level unlocking.

This module manages:
- Completed level tracking
- Level unlocking logic
- Difficulty assignment
- Campaign progress persistence
"""

from typing import List, Optional, Set
from enum import Enum
import json
import os

from core.enums import Difficulty, HColor


class CciType(Enum):
    """Campaign level completion/info type."""
    COMPLETED = "completed"
    UNLOCKED = "unlocked"
    UNKNOWN = "unknown"


class CampaignManager:
    """
    Manages campaign progress and level unlocking.
    
    Uses a simple file-based storage for progress persistence.
    In a full implementation, this could use a database or cloud storage.
    """

    def __init__(self, progress_file: str = "campaign_progress.json"):
        self.progress_file = progress_file
        self.completed_levels: Set[int] = set()
        self.current_level_index: int = -1
        self._load_values()

    def _load_values(self) -> None:
        """Load campaign progress from file."""
        if not os.path.exists(self.progress_file):
            self.completed_levels = set()
            return

        try:
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                self.completed_levels = set(data.get('completed_levels', []))
                self.current_level_index = data.get('current_level_index', -1)
        except (json.JSONDecodeError, IOError):
            # If file is corrupted or can't be read, start fresh
            self.completed_levels = set()
            self.current_level_index = -1

    def _save_values(self) -> None:
        """Save campaign progress to file."""
        try:
            data = {
                'completed_levels': list(self.completed_levels),
                'current_level_index': self.current_level_index
            }
            with open(self.progress_file, 'w') as f:
                json.dump(data, f)
        except IOError:
            # If we can't save, continue without saving
            pass

    def on_level_completed(self, index: int) -> None:
        """Mark a level as completed."""
        if self.is_level_completed(index):
            return

        self.completed_levels.add(index)
        self._save_values()

    def is_level_completed(self, index: int) -> bool:
        """Check if a level is completed."""
        if index == -1:
            return True
        return index in self.completed_levels

    def are_all_levels_completed(self) -> bool:
        """Check if all levels are completed."""
        last_level_index = self.get_last_level_index()
        return len(self.completed_levels) >= last_level_index

    def get_last_level_index(self) -> int:
        """Get the index of the last level."""
        from campaign.levels import get_level_code
        # Try to find the last level by checking indices
        # In a real implementation, this would query the levels database
        # For now, we'll use a reasonable default
        max_index = 0
        for i in range(200):  # Check up to 200 levels
            try:
                level_code = get_level_code(i)
                if level_code:
                    max_index = i
            except (IndexError, KeyError):
                break
        return max_index

    def get_next_level_index(self, index: int) -> int:
        """
        Get the next uncompleted level index after the given index.
        Returns -1 if no next level exists.
        """
        last_level_index = self.get_last_level_index()
        if index >= last_level_index:
            return -1

        next_index = index + 1
        # Skip completed levels
        while next_index != index and self.is_level_completed(next_index):
            next_index += 1
            if next_index > last_level_index:
                # Wrap around to beginning
                next_index = 0

        return next_index

    def get_level_type(self, level_index: int) -> CciType:
        """
        Get the type/status of a level (completed, unlocked, or unknown).
        
        A level is unlocked if:
        - It's the start of a new difficulty section, OR
        - At least one of the previous 3 levels is completed
        """
        if self.is_level_completed(level_index):
            return CciType.COMPLETED

        # Check if it's the start of a new difficulty section
        current_difficulty = self.get_difficulty(level_index)
        previous_difficulty = self.get_difficulty(level_index - 1)
        if current_difficulty != previous_difficulty:
            return CciType.UNLOCKED

        # Check if any of the previous 3 levels are completed
        if (self.is_level_completed(level_index - 1) or
            self.is_level_completed(level_index - 2) or
            self.is_level_completed(level_index - 3)):
            return CciType.UNLOCKED

        return CciType.UNKNOWN

    def get_difficulty(self, level_index: int) -> Difficulty:
        """
        Get the difficulty for a level index.
        
        Difficulty progression:
        - Levels 0-11: Easy
        - Levels 12-23: Average
        - Levels 24-59: Hard
        - Levels 60-119: Expert
        - Levels 120+: Balancer
        """
        if level_index < 0:
            return Difficulty.EASY

        if level_index < 12:
            return Difficulty.EASY
        elif level_index < 24:
            return Difficulty.AVERAGE
        elif level_index < 60:
            return Difficulty.HARD
        elif level_index < 120:
            return Difficulty.EXPERT
        else:
            return Difficulty.BALANCER

    def get_index_of_target_unlocked_level(self) -> int:
        """Get the index of the first unlocked level."""
        last_level_index = self.get_last_level_index()
        for index in range(last_level_index):
            if self.get_level_type(index) == CciType.UNLOCKED:
                return index
        return last_level_index

    def convert_difficulty_into_color(self, difficulty: Difficulty) -> HColor:
        """Convert difficulty to a color representation."""
        if difficulty == Difficulty.TUTORIAL:
            return HColor.ICE
        elif difficulty == Difficulty.EASY:
            return HColor.YELLOW
        elif difficulty == Difficulty.AVERAGE:
            return HColor.MINT
        elif difficulty == Difficulty.HARD:
            return HColor.CYAN
        elif difficulty == Difficulty.EXPERT:
            return HColor.PURPLE
        elif difficulty == Difficulty.BALANCER:
            return HColor.ROSE
        else:
            return HColor.GRAY

    def launch_campaign_level(self, index: int) -> Optional[str]:
        """
        Get the level code for a campaign level.
        Returns the level code string, or None if the level doesn't exist.
        """
        from campaign.levels import get_level_code
        try:
            level_code = get_level_code(index)
            self.current_level_index = index
            return level_code
        except (IndexError, KeyError):
            return None

    def reset_progress(self) -> None:
        """Reset all campaign progress (for testing/debugging)."""
        self.completed_levels = set()
        self.current_level_index = -1
        self._save_values()
