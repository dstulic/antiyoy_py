"""Save format parser and utilities."""

import re
from typing import Optional, Dict


# Section name constants
SECTION_TITLE = "onliyoy_level_code"
SECTION_CLIENT_INIT = "client_init"
SECTION_CAMERA = "camera"
SECTION_CORE_INIT = "core_init"
SECTION_HEXES = "hexes"
SECTION_CORE_CURRENT_IDS = "core_current_ids"
SECTION_PLAYER_ENTITIES = "player_entities"
SECTION_PROVINCES = "provinces"
SECTION_READY = "ready"
SECTION_RULES = "rules"
SECTION_TURN = "turn"
SECTION_DIPLOMACY = "diplomacy"
SECTION_MAIL_BASKET = "mail_basket"
SECTION_FOG = "fog"
SECTION_STARTING_HEXES = "starting_hexes"
SECTION_EVENTS_LIST = "events_list"
SECTION_STARTING_PROVINCES = "starting_provinces"
SECTION_EDITOR = "editor"
SECTION_CAMPAIGN = "campaign"
SECTION_PAUSE_NAME = "pause_name"
SECTION_RNG_STATE = "rng_state"


def get_section(level_code: str, section_name: str) -> Optional[str]:
    """
    Extract a section from the level code.
    
    Args:
        level_code: The full level code string
        section_name: Name of the section to extract
        
    Returns:
        The section data (content after the colon), or None if not found
    """
    if not level_code or not section_name:
        return None
    
    # Special case for title section (no colon)
    if section_name == SECTION_TITLE:
        if level_code.startswith(SECTION_TITLE):
            # Find where the title ends (first #)
            hash_index = level_code.find("#", len(SECTION_TITLE))
            if hash_index == -1:
                return ""  # Title is the only content
            return ""  # Title has no data, just presence matters
    
    # Find the section marker: #section_name:
    section_marker = f"#{section_name}:"
    section_index = level_code.find(section_marker)
    if section_index == -1:
        return None
    
    # Find the colon after the section name
    colon_index = section_index + len(section_marker) - 1
    if colon_index >= len(level_code):
        return None
    
    # Find the next # (or end of string)
    hash_index = level_code.find("#", colon_index + 1)
    if hash_index == -1:
        # Last section, return everything after colon
        return level_code[colon_index + 1:]
    
    # Extract content between colon and next #
    # Allow empty sections (hash_index - colon_index == 1 means empty)
    if hash_index - colon_index < 1:
        return None
    
    return level_code[colon_index + 1:hash_index]


def has_section(level_code: str, section_name: str) -> bool:
    """
    Check if a section exists in the level code.
    
    Args:
        level_code: The full level code string
        section_name: Name of the section to check
        
    Returns:
        True if section exists, False otherwise
    """
    if section_name == SECTION_TITLE:
        return level_code.startswith(SECTION_TITLE)
    return f"#{section_name}:" in level_code


def extract_all_sections(level_code: str) -> Dict[str, str]:
    """
    Extract all sections from a level code.
    
    Args:
        level_code: The full level code string
        
    Returns:
        Dictionary mapping section names to their data
    """
    sections = {}
    
    # Check for title
    if level_code.startswith(SECTION_TITLE):
        sections[SECTION_TITLE] = ""
    
    # Find all sections using regex
    # Pattern: #section_name:data
    pattern = r"#([^#:]+):([^#]*)"
    matches = re.finditer(pattern, level_code)
    
    for match in matches:
        section_name = match.group(1)
        section_data = match.group(2)
        sections[section_name] = section_data
    
    return sections


def is_valid_level_code(level_code: str) -> bool:
    """
    Validate that a level code has the required structure.
    
    Args:
        level_code: The level code string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not level_code or len(level_code) < 3:
        return False
    
    if not level_code.startswith(SECTION_TITLE):
        return False
    
    # Check for required core sections
    required_sections = [
        SECTION_CORE_INIT,
        SECTION_HEXES,
        SECTION_PLAYER_ENTITIES,
    ]
    
    for section in required_sections:
        if not has_section(level_code, section):
            return False
    
    return True


def start_section(name: str) -> str:
    """
    Create a section header string.
    
    Args:
        name: Section name
        
    Returns:
        Section header string: "#name:"
    """
    return f"#{name}:"
