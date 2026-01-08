#!/usr/bin/env python3
"""Dump decoded level information for verification."""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from campaign.levels import get_level_code
from save_load.decoder import GameStateDecoder

def dump_level(level_index: int):
    """Dump decoded level information."""
    level_code = get_level_code(level_index)
    if level_code == "-":
        print(f"Level {level_index} not found or invalid")
        return
    
    decoder = GameStateDecoder()
    game_state, _ = decoder.decode(level_code)
    
    if game_state is None:
        print(f"Failed to decode level {level_index}")
        return
    
    print(f"Level {level_index} Decoded Information:")
    print("=" * 60)
    print(f"Hexes: {len(game_state.hexes)}")
    print(f"Provinces: {len(game_state.provinces_manager.provinces) if game_state.provinces_manager else 0}")
    print(f"Entities: {len(game_state.entities_manager.entities) if game_state.entities_manager else 0}")
    
    if game_state.provinces_manager:
        print("\nProvinces:")
        for province in game_state.provinces_manager.provinces:
            hexes = province.get_hexes()
            money = province.get_money()
            color = province.get_color()
            city_name = province.get_city_name()
            print(f"  - {city_name or 'Unnamed'} ({color.value}): {len(hexes)} hexes, {money} money")
    
    if game_state.entities_manager:
        print("\nEntities:")
        for entity in game_state.entities_manager.entities:
            entity_type = getattr(entity, 'type', getattr(entity, 'entity_type', 'unknown'))
            entity_type_str = entity_type.value if hasattr(entity_type, 'value') else str(entity_type)
            color = getattr(entity, 'color', None)
            color_str = color.value if color and hasattr(color, 'value') else str(color)
            name = getattr(entity, 'name', 'Unnamed')
            print(f"  - {name} ({entity_type_str}, {color_str})")
    
    if game_state.ruleset:
        print(f"\nRuleset: {game_state.ruleset.get_rules_type().value} v{game_state.ruleset.get_version_code()}")
    
    if game_state.fog_of_war_manager:
        fog_enabled = game_state.fog_of_war_manager.enabled
        print(f"Fog of War: {'Enabled' if fog_enabled else 'Disabled'}")
    
    if game_state.turns_manager:
        current_color = getattr(game_state.turns_manager, 'current_color', None)
        if not current_color:
            turn_index = getattr(game_state.turns_manager, 'turn_index', None)
            if turn_index is not None and game_state.entities_manager:
                entities = game_state.entities_manager.entities
                if entities and 0 <= turn_index < len(entities):
                    current_color = entities[turn_index].color
        turn_str = current_color.value if current_color and hasattr(current_color, 'value') else 'N/A'
        print(f"Turn: {turn_str}")
    
    print("=" * 60)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: dump_level.py <level_index>")
        sys.exit(1)
    
    try:
        level_index = int(sys.argv[1])
        dump_level(level_index)
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid level index")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
