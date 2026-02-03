"""Decoder for save game format."""

from typing import Optional
from save_load.format import (
    get_section,
    has_section,
    SECTION_HEXES,
    SECTION_CORE_CURRENT_IDS,
    SECTION_PLAYER_ENTITIES,
    SECTION_PROVINCES,
    SECTION_RULES,
    SECTION_TURN,
    SECTION_DIPLOMACY,
    SECTION_MAIL_BASKET,
    SECTION_FOG,
    SECTION_CORE_INIT,
    SECTION_RNG_STATE,
    SECTION_EVENTS_LIST,
)
from core.game_state import GameState
from core.enums import HColor, PieceType, RulesType, EntityType
from core.events import EventsFactory, AbstractEvent


def _build_adjacency_graph(game_state: GameState) -> None:
    """
    Build adjacency relationships between hexes.
    
    In axial hex coordinates, adjacent hexes are at offsets:
    (1,0), (0,1), (-1,1), (-1,0), (0,-1), (1,-1)
    """
    # Create a coordinate map for quick lookup
    coord_map = {}
    for hex in game_state.hexes:
        coord_map[(hex.coordinate1, hex.coordinate2)] = hex
    
    # Adjacent offsets in axial coordinates
    offsets = [
        (1, 0),
        (0, 1),
        (-1, 1),
        (-1, 0),
        (0, -1),
        (1, -1),
    ]
    
    # Connect adjacent hexes
    for hex in game_state.hexes:
        for offset in offsets:
            adj_coord = (hex.coordinate1 + offset[0], hex.coordinate2 + offset[1])
            if adj_coord in coord_map:
                adj_hex = coord_map[adj_coord]
                hex.add_adjacent_hex(adj_hex)


class GameStateDecoder:
    """Decodes game state from save string format."""

    def __init__(self):
        """Initialize decoder."""
        pass

    def decode(self, level_code: str) -> tuple[Optional[GameState], int]:
        """
        Decode a game state from level code string.
        
        Args:
            level_code: The level code string to decode
            
        Returns:
            Tuple of (GameState object, campaign_level_index), or (None, -1) if decoding fails.
            campaign_level_index is -1 if not a campaign level.
        """
        if not level_code or len(level_code) < 3:
            return None, -1
        
        # Create new game state
        game_state = GameState()
        campaign_level_index = -1
        
        try:
            # Store original level code for deterministic seed generation
            game_state._original_level_code = level_code
            
            # Decode campaign level index first
            campaign_level_index = self._decode_campaign_level_index(level_code)
            
            # Decode in order
            self._decode_core_init(game_state, level_code)
            self._decode_hexes(game_state, level_code)
            self._decode_core_current_ids(game_state, level_code)
            self._decode_player_entities(game_state, level_code)
            self._decode_provinces(game_state, level_code)
            self._decode_ready(game_state, level_code)
            self._decode_rules(game_state, level_code)
            self._decode_turn(game_state, level_code)
            # Optional sections
            self._decode_mail_basket(game_state, level_code)
            self._decode_fog(game_state, level_code)
            self._decode_rng_state(game_state, level_code)
            self._decode_events_list(game_state, level_code)
            
            # Reinitialize TreeManager RNG with correct seed or restore saved state
            if hasattr(game_state, 'tree_manager') and game_state.tree_manager:
                if game_state._rng_state:
                    # Restore saved RNG state
                    game_state.tree_manager.random.setstate(game_state._rng_state)
                else:
                    # Reinitialize with deterministic seed from original level code
                    from core.rng_utils import get_deterministic_seed
                    import random
                    seed = get_deterministic_seed(game_state._original_level_code)
                    game_state.tree_manager.random = random.Random(seed)
            
            return game_state, campaign_level_index
        except Exception as e:
            print(f"Error decoding game state: {e}")
            return None, -1
    
    def _decode_campaign_level_index(self, level_code: str) -> int:
        """Decode campaign level index."""
        from save_load.format import get_section, SECTION_CAMPAIGN
        source = get_section(level_code, SECTION_CAMPAIGN)
        if not source:
            return -1
        try:
            return int(source)
        except ValueError:
            return -1

    def _decode_core_init(self, game_state: GameState, level_code: str) -> None:
        """Decode core initialization data."""
        source = get_section(level_code, SECTION_CORE_INIT)
        if not source:
            return
        # Format: "bounds_x bounds_y hex_radius"
        # For now, we'll just parse it but not use it
        # (would need to set up graph bounds)
        parts = source.split(" ")
        if len(parts) >= 3:
            try:
                bounds_x = float(parts[0])
                bounds_y = float(parts[1])
                hex_radius = float(parts[2])
                # Store if needed
            except ValueError:
                pass

    def _decode_hexes(self, game_state: GameState, level_code: str) -> None:
        """Decode hexes section."""
        source = get_section(level_code, SECTION_HEXES)
        if not source or source == "-":
            return
        
        # First, collect all hex coordinates to create the graph
        hex_coords = set()
        hex_data = []
        
        for token in source.split(","):
            if not token.strip():
                continue
            parts = token.split(" ")
            if len(parts) < 3:
                continue
            try:
                c1 = int(parts[0])
                c2 = int(parts[1])
                color_str = parts[2]
                hex_coords.add((c1, c2))
                
                # Store hex data for later processing
                hex_info = {
                    "c1": c1,
                    "c2": c2,
                    "color": color_str,
                    "piece": None,
                    "unit_id": None,
                }
                
                if len(parts) > 3:
                    # Has piece
                    piece_str = parts[3]
                    unit_id = int(parts[4]) if len(parts) > 4 else -1
                    hex_info["piece"] = piece_str
                    hex_info["unit_id"] = unit_id
                
                hex_data.append(hex_info)
            except (ValueError, IndexError):
                continue
        
        # Create all hexes first (empty, gray)
        for c1, c2 in hex_coords:
            game_state.add_hex(c1, c2, HColor.GRAY)
        
        # Build adjacency graph
        _build_adjacency_graph(game_state)
        
        # Now set colors and pieces
        events_factory = game_state.events_manager.factory
        for hex_info in hex_data:
            hex = game_state.get_hex(hex_info["c1"], hex_info["c2"])
            if not hex:
                continue
            
            # Set color
            try:
                color = HColor(hex_info["color"])
                hex.set_color(color)
            except (ValueError, KeyError):
                continue
            
            # Add piece if present
            if hex_info["piece"]:
                try:
                    piece_type = PieceType(hex_info["piece"])
                    unit_id = hex_info["unit_id"] if hex_info["unit_id"] is not None else -1
                    if unit_id == -1:
                        unit_id = game_state.get_id_for_new_unit()
                    from core.events import EventPieceAdd, EventType
                    event = events_factory.create_event(EventType.PIECE_ADD)
                    if isinstance(event, EventPieceAdd):
                        event.set_hex(hex)
                        event.set_piece_type(piece_type)
                        event.set_unit_id(unit_id)
                        game_state.events_manager.apply_event(event)
                except (ValueError, KeyError):
                    continue

    def _decode_core_current_ids(self, game_state: GameState, level_code: str) -> None:
        """Decode core current IDs."""
        source = get_section(level_code, SECTION_CORE_CURRENT_IDS)
        if not source:
            return
        parts = source.split(" ")
        if len(parts) >= 1:
            try:
                game_state.current_unit_id = int(parts[0])
            except ValueError:
                pass

    def _decode_player_entities(self, game_state: GameState, level_code: str) -> None:
        """Decode player entities."""
        source = get_section(level_code, SECTION_PLAYER_ENTITIES)
        if not source or source == "-":
            return
        game_state.entities_manager.decode(source, dead_by_default=False)

    def _decode_provinces(self, game_state: GameState, level_code: str) -> None:
        """Decode provinces."""
        source = get_section(level_code, SECTION_PROVINCES)
        if not source or source == "-":
            # Rebuild provinces from hexes
            game_state.provinces_manager.builder.grant_permission()
            game_state.provinces_manager.builder.apply()
            return
        
        # First, rebuild provinces from hex colors
        game_state.provinces_manager.builder.grant_permission()
        game_state.provinces_manager.builder.apply()
        
        # Now update province IDs, money, and city names from decoded data
        parts = source.split(">", 1)
        if len(parts) >= 1:
            try:
                game_state.provinces_manager.current_id = int(parts[0])
            except ValueError:
                game_state.provinces_manager.current_id = 0
        
        if len(parts) < 2 or not parts[1]:
            return
        
        # Create a map of (c1, c2) -> province data
        province_data_map = {}
        for token in parts[1].split(","):
            if not token.strip():
                continue
            province_parts = token.split("<")
            if len(province_parts) < 5:
                continue
            try:
                c1 = int(province_parts[0])
                c2 = int(province_parts[1])
                province_id = int(province_parts[2])
                money = int(province_parts[3])
                city_name = province_parts[4] if len(province_parts) > 4 else ""
                province_data_map[(c1, c2)] = {
                    "id": province_id,
                    "money": money,
                    "city_name": city_name,
                }
            except (ValueError, IndexError):
                continue
        
        # Update provinces by finding any hex in the province that matches the level code
        # (The level code specifies a coordinate, but it might not be the first hex in the province)
        for province in game_state.provinces_manager.provinces:
            hexes = province.get_hexes()
            if not hexes:
                continue
            
            # Try to find a matching hex coordinate in this province
            matched_data = None
            for hex in hexes:
                key = (hex.coordinate1, hex.coordinate2)
                if key in province_data_map:
                    matched_data = province_data_map[key]
                    # Remove from map so we don't match it again
                    del province_data_map[key]
                    break
            
            if matched_data:
                province.set_id(matched_data["id"])
                province.set_money(matched_data["money"])
                province.set_city_name(matched_data["city_name"])
    
    def _decode_ready(self, game_state: GameState, level_code: str) -> None:
        """Decode readiness state."""
        from save_load.format import get_section, SECTION_READY
        source = get_section(level_code, SECTION_READY)
        if not source:
            return
        game_state.readiness_manager.decode(source)

    def _decode_rules(self, game_state: GameState, level_code: str) -> None:
        """Decode rules section."""
        source = get_section(level_code, SECTION_RULES)
        if not source:
            return
        parts = source.split(" ")
        if len(parts) < 2:
            return
        try:
            rules_type = RulesType(parts[0])
            version_code = int(parts[1])
            game_state.set_ruleset(rules_type, version_code)
        except (ValueError, KeyError):
            pass

    def _decode_turn(self, game_state: GameState, level_code: str) -> None:
        """Decode turn section."""
        source = get_section(level_code, SECTION_TURN)
        if not source:
            return
        game_state.turns_manager.decode(source)

    def _decode_mail_basket(self, game_state: GameState, level_code: str) -> None:
        """Decode mail basket section."""
        # Placeholder - letters manager not yet implemented
        pass

    def _decode_fog(self, game_state: GameState, level_code: str) -> None:
        """Decode fog of war section."""
        source = get_section(level_code, SECTION_FOG)
        if source and game_state.fog_of_war_manager:
            # Enable fog of war if level code specifies it
            # Handle "true," or "true" format
            source_clean = source.strip().rstrip(',').lower()
            enabled = (source_clean == "true")
            game_state.fog_of_war_manager.set_enabled(enabled)
    
    def _decode_rng_state(self, game_state: GameState, level_code: str) -> None:
        """Decode RNG state section."""
        import pickle
        import base64
        
        source = get_section(level_code, SECTION_RNG_STATE)
        if not source or source == "-":
            return
        
        try:
            # Decode base64 string back to bytes
            rng_state_bytes = base64.b64decode(source)
            # Unpickle the RNG state tuple
            rng_state = pickle.loads(rng_state_bytes)
            # Store in game state
            game_state._rng_state = rng_state
        except Exception as e:
            print(f"Warning: Failed to decode RNG state: {e}")
            # If decoding fails, RNG will use seed from original level code
    
    def _decode_events_list(self, game_state: GameState, level_code: str) -> None:
        """Decode events list (history)."""
        from save_load.format import get_section, SECTION_EVENTS_LIST
        source = get_section(level_code, SECTION_EVENTS_LIST)
        if not source or source == "":
            return
        
        # Parse the encoded events list
        # Format: event1|author:color:name,event2|author:color:name,...
        # Or Java format: event1,event2,... (without author info)
        if not hasattr(game_state, 'history_manager') or not game_state.history_manager:
            return
        
        # Clear existing history
        game_state.history_manager.clear_all()
        
        # Parse events
        events = source.split(",")
        for event_str in events:
            if not event_str.strip():
                continue
            
            # Split event encoding from author (if present)
            event_part = event_str
            author_color = None
            author_name = None
            
            if "|author:" in event_str:
                event_part, author_part = event_str.split("|author:", 1)
                
                # Parse author
                if author_part != "-":
                    author_parts = author_part.split(":", 1)
                    if len(author_parts) >= 1:
                        try:
                            from core.enums import HColor
                            author_color = HColor(author_parts[0])
                            if len(author_parts) >= 2:
                                author_name = author_parts[1]
                        except (ValueError, KeyError):
                            pass
            
            # Decode event from event_part
            # Event format: <key> <data>
            from core.events import EventKeys
            event_parts = event_part.strip().split(" ", 1)
            if len(event_parts) < 1:
                continue
                
            event_key = event_parts[0]
            event_data = event_parts[1] if len(event_parts) > 1 else ""
            
            event_type = EventKeys.convert_key_to_type(event_key)
            if not event_type:
                continue
            
            # Create event
            event = game_state.events_manager.factory.create_event(event_type)
            if not event:
                continue
            
            # Decode event data (event-specific decoding)
            try:
                self._restore_single_event(event, event_data, game_state)
            except Exception as e:
                # If decoding fails, skip this event
                print(f"Warning: Failed to decode event {event_key}: {e}")
                continue
            
            # Create history event
            from core.history_manager import HistoryEvent
            history_event = HistoryEvent(event, author_color, author_name)
            # Add to events list (completed turns, since we're loading a saved game)
            game_state.history_manager.events_list.append(history_event)
    
    def _restore_single_event(self, event: AbstractEvent, event_data: str, game_state: GameState) -> None:
        """Restore a single event from its data string."""
        from core.events import EventType
        from core.enums import HColor
        
        event_type = event.get_type()
        parts = event_data.split(" ") if event_data else []
        
        if event_type == EventType.TURN_END:
            from core.events import EventTurnEnd
            if isinstance(event, EventTurnEnd) and len(parts) >= 2:
                try:
                    time = int(parts[0]) if parts[0] else 0
                    current_color = None if parts[1] == "null" else HColor(parts[1])
                    event.set_target_end_time(time)
                    event.set_current_color(current_color)
                except (ValueError, KeyError):
                    pass
        elif event_type == EventType.UNIT_MOVE:
            from core.events import EventUnitMove
            if isinstance(event, EventUnitMove) and len(parts) >= 4:
                try:
                    c1 = int(parts[0])
                    c2 = int(parts[1])
                    c3 = int(parts[2])
                    c4 = int(parts[3])
                    hex1 = game_state.get_hex(c1, c2)
                    hex2 = game_state.get_hex(c3, c4)
                    if hex1 and hex2:
                        event.set_hex1(hex1)
                        event.set_hex2(hex2)
                except (ValueError, KeyError):
                    pass
        elif event_type == EventType.PIECE_ADD:
            from core.events import EventPieceAdd
            if isinstance(event, EventPieceAdd) and len(parts) >= 3:
                try:
                    c1 = int(parts[0])
                    c2 = int(parts[1])
                    from core.enums import PieceType
                    piece_type = PieceType(parts[2])
                    unit_id = int(parts[3]) if len(parts) > 3 else -1
                    hex = game_state.get_hex(c1, c2)
                    if hex:
                        event.set_hex(hex)
                        event.set_piece_type(piece_type)
                        if unit_id != -1:
                            event.set_unit_id(unit_id)
                except (ValueError, KeyError):
                    pass
        elif event_type == EventType.PIECE_DELETE:
            from core.events import EventPieceDelete
            if isinstance(event, EventPieceDelete) and len(parts) >= 2:
                try:
                    c1 = int(parts[0])
                    c2 = int(parts[1])
                    hex = game_state.get_hex(c1, c2)
                    if hex:
                        event.set_hex(hex)
                except (ValueError, KeyError):
                    pass
        elif event_type == EventType.HEX_CHANGE_COLOR:
            from core.events import EventHexChangeColor
            if isinstance(event, EventHexChangeColor) and len(parts) >= 3:
                try:
                    c1 = int(parts[0])
                    c2 = int(parts[1])
                    color = HColor(parts[2])
                    hex = game_state.get_hex(c1, c2)
                    if hex:
                        event.set_hex(hex)
                        event.set_color(color)
                except (ValueError, KeyError):
                    pass
        elif event_type == EventType.SET_MONEY:
            from core.events import EventSetMoney
            if isinstance(event, EventSetMoney) and len(parts) >= 3:
                try:
                    c1 = int(parts[0])
                    c2 = int(parts[1])
                    money = int(parts[2])
                    hex = game_state.get_hex(c1, c2)
                    if hex:
                        event.set_hex(hex)
                        event.set_target_money(money)
                except (ValueError, KeyError):
                    pass
        elif event_type == EventType.PIECE_BUILD:
            from core.events import EventPieceBuild
            if isinstance(event, EventPieceBuild) and len(parts) >= 3:
                try:
                    c1 = int(parts[0])
                    c2 = int(parts[1])
                    from core.enums import PieceType
                    piece_type = PieceType(parts[2])
                    hex = game_state.get_hex(c1, c2)
                    if hex:
                        event.set_hex(hex)
                        event.set_piece_type(piece_type)
                except (ValueError, KeyError):
                    pass
        # Add more event types as needed
    
    def _decode_campaign_level_index(self, level_code: str) -> int:
        """Decode campaign level index."""
        from save_load.format import get_section, SECTION_CAMPAIGN
        source = get_section(level_code, SECTION_CAMPAIGN)
        if not source:
            return -1
        try:
            return int(source)
        except ValueError:
            return -1