"""
Flask application for Antiyoy web interface.
"""

import os
import sys
import time
from pathlib import Path
from collections import OrderedDict

# Get the project root directory (parent of web/)
PROJECT_ROOT = Path(__file__).parent.parent

# Add project root to Python path so imports work
# This must be done BEFORE any local imports
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Now we can import Flask and other dependencies
from flask import Flask, render_template, jsonify, request, session

ASSETS_ROOT = PROJECT_ROOT.parent / "antiyoy_hd" / "assets"

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# Configure static folders
app.static_folder = 'static'
app.template_folder = 'templates'

# Store game sessions (in production, use a proper session store)
# Using OrderedDict to maintain insertion order for oldest session tracking
# Format: {session_id: {'game_state': ..., 'game_manager': ..., 'level_index': ..., 'created_at': ...}}
game_sessions = OrderedDict()
MAX_ACTIVE_SESSIONS = 5


def cleanup_oldest_session():
    """
    Remove the oldest session if we've reached the limit.
    OrderedDict maintains insertion order, so the first item is the oldest.
    """
    if len(game_sessions) >= MAX_ACTIVE_SESSIONS:
        # Remove the oldest session (first item in OrderedDict)
        oldest_session_id = next(iter(game_sessions))
        del game_sessions[oldest_session_id]
        print(f"Removed oldest session: {oldest_session_id} (limit reached)")


@app.route('/')
def index():
    """Landing page."""
    return render_template('index.html')


@app.route('/campaign')
def campaign_selector():
    """Campaign selector page."""
    from campaign.manager import CampaignManager
    
    campaign_manager = CampaignManager()
    from campaign.levels import get_level_code
    
    levels = []
    
    # Get all available levels
    last_level = campaign_manager.get_last_level_index()
    for i in range(last_level + 1):
        # Skip invalid levels (level code is "-" or too short)
        level_code = get_level_code(i)
        if not level_code or level_code == "-" or len(level_code) < 3:
            continue
        
        level_type = campaign_manager.get_level_type(i)
        difficulty = campaign_manager.get_difficulty(i)
        levels.append({
            'index': i,
            'type': level_type.value,
            'difficulty': difficulty.value,
            'completed': campaign_manager.is_level_completed(i)
        })
    
    return render_template('campaign_selector.html', levels=levels)


@app.route('/game/<int:level_index>')
def game(level_index):
    """Game screen for a specific campaign level."""
    return render_template('game.html', level_index=level_index)


@app.route('/api/campaign/levels')
def api_campaign_levels():
    """API endpoint to get campaign levels."""
    from campaign.manager import CampaignManager
    
    campaign_manager = CampaignManager()
    from campaign.levels import get_level_code
    
    levels = []
    
    last_level = campaign_manager.get_last_level_index()
    for i in range(last_level + 1):
        # Skip invalid levels (level code is "-" or too short)
        level_code = get_level_code(i)
        if not level_code or level_code == "-" or len(level_code) < 3:
            continue
        
        level_type = campaign_manager.get_level_type(i)
        difficulty = campaign_manager.get_difficulty(i)
        levels.append({
            'index': i,
            'type': level_type.value,
            'difficulty': difficulty.value,
            'completed': campaign_manager.is_level_completed(i)
        })
    
    return jsonify({'levels': levels})


@app.route('/api/game/init/<int:level_index>')
def api_game_init(level_index):
    """Initialize a game session for a campaign level."""
    from save_load.decoder import GameStateDecoder
    from campaign.levels import get_level_code
    from core.game_manager import GameManager, GameMode
    
    try:
        level_code = get_level_code(level_index)
        
        # Check if level code is valid
        if not level_code or level_code == "-" or len(level_code) < 3:
            return jsonify({
                'success': False, 
                'error': f'Invalid level code for level {level_index}. Level may not exist or be incomplete.'
            }), 400
        
        decoder = GameStateDecoder()
        result = decoder.decode(level_code)
        # Decoder returns (game_state, campaign_index) tuple
        if isinstance(result, tuple):
            game_state, campaign_index = result
        else:
            game_state = result
            campaign_index = -1
        
        # Check if decoding was successful
        if game_state is None:
            import traceback
            error_details = traceback.format_exc()
            print(f"Decode error for level {level_index}")
            print(f"Level code length: {len(level_code)}")
            print(f"Level code preview: {level_code[:100]}...")
            print(f"Traceback: {error_details}")
            return jsonify({
                'success': False, 
                'error': f'Failed to decode game state for level {level_index}. The level code may be corrupted or incomplete.'
            }), 500
        
        # Initialize starting money for all provinces (default is 10 if not set)
        # This matches the Java version's prepareStartingMoney() behavior
        from core.enums import EventType, PieceType
        for province in game_state.provinces_manager.provinces:
            # Only set money if it's 0 (not already set from level code)
            if province.get_money() == 0:
                event = game_state.events_manager.factory.create_event(EventType.SET_MONEY)
                if event:
                    event.province_id = province.get_id()
                    event.money = 10
                    game_state.events_manager.apply_event(event)
        
        # Update fog of war after initialization
        if game_state.fog_of_war_manager and game_state.fog_of_war_manager.enabled:
            game_state.fog_of_war_manager.apply_update()
        
        # Process AI turns to get to first human player's turn
        if game_state.ai_manager:
            game_state.ai_manager.process_ai_turns()
        
        # Create game manager
        game_manager = GameManager(game_state, GameMode.CAMPAIGN)
        
        # Store in session (for now, use a simple dict - in production use proper session store)
        session_id = session.get('session_id')
        
        # If session already exists, remove it from OrderedDict to update its position
        # (move it to the end, making it the newest)
        if session_id and session_id in game_sessions:
            # Move existing session to end (making it newest)
            game_sessions.move_to_end(session_id)
        else:
            # New session - check if we need to clean up
            cleanup_oldest_session()
            
            # Generate new session ID if needed
            if not session_id:
                import uuid
                session_id = str(uuid.uuid4())
                session['session_id'] = session_id
        
        # Store session data with timestamp
        game_sessions[session_id] = {
            'game_state': game_state,
            'game_manager': game_manager,
            'level_index': level_index,
            'created_at': time.time()
        }
        
        # Move to end to mark as most recently used
        game_sessions.move_to_end(session_id)
        
        # Return initial game state (simplified for now)
        return jsonify({
            'success': True,
            'session_id': session_id,
            'level_index': level_index
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/game/state')
def api_game_state():
    """Get current game state for rendering."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'error': 'No active game session'}), 404
    
    # Mark session as recently used (move to end)
    game_sessions.move_to_end(session_id)
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    
    # Check if game state exists
    if game_state is None:
        return jsonify({'error': 'Game state not available'}), 500
    
    # Check if game_state has hexes attribute
    if not hasattr(game_state, 'hexes'):
        return jsonify({'error': 'Invalid game state structure'}), 500
    
    # Process AI turns to get to next human player's turn
    if game_state.ai_manager:
        game_state.ai_manager.process_ai_turns()
    
    # Get current player color for fog of war
    current_player_color = None
    if hasattr(game_state, 'entities_manager') and game_state.entities_manager:
        current_entity = game_state.entities_manager.get_current_entity()
        if current_entity:
            current_player_color = current_entity.color
    
    # Get visible hexes for the current player (respects fog of war)
    # Only send hexes that are visible - fogged hexes are not sent to the client
    visible_hexes = game_state.get_hexes_for_player(current_player_color)
    
    # Get readiness information (which units can move)
    ready_hex_coords = set()
    if hasattr(game_state, 'readiness_manager') and game_state.readiness_manager:
        for hex in game_state.readiness_manager.ready_hexes:
            ready_hex_coords.add((hex.coordinate1, hex.coordinate2))
    
    # Get readiness information (which units can move)
    ready_hex_coords = set()
    if hasattr(game_state, 'readiness_manager') and game_state.readiness_manager:
        for hex in game_state.readiness_manager.ready_hexes:
            ready_hex_coords.add((hex.coordinate1, hex.coordinate2))
    
    # Serialize only visible hexes for rendering
    hexes = []
    for hex in visible_hexes:
        hex_coord = (hex.coordinate1, hex.coordinate2)
        is_ready = hex_coord in ready_hex_coords
        hex_data = {
            'coordinate1': hex.coordinate1,
            'coordinate2': hex.coordinate2,
            'color': hex.color.value if hasattr(hex.color, 'value') else str(hex.color),
            'piece': hex.piece.value if hex.piece and hasattr(hex.piece, 'value') else None,
            'unit_id': hex.unit_id,
            'is_ready': is_ready  # Whether unit can move this turn
        }
        hexes.append(hex_data)
    
    # Serialize player entities
    entities = []
    if hasattr(game_state, 'entities_manager') and game_state.entities_manager:
        if hasattr(game_state.entities_manager, 'entities') and game_state.entities_manager.entities:
            for entity in game_state.entities_manager.entities:
                entity_data = {
                    'type': entity.type.value if hasattr(entity.type, 'value') else str(entity.type),
                    'color': entity.color.value if hasattr(entity.color, 'value') else str(entity.color),
                    'name': entity.name
                }
                entities.append(entity_data)
    
    # Get current turn info (convert to string value for JSON)
    current_color_value = None
    if current_player_color:
        current_color_value = current_player_color.value if hasattr(current_player_color, 'value') else str(current_player_color)
    
    # Get turn info
    turn_index = 0
    lap = 0
    if hasattr(game_state, 'turns_manager') and game_state.turns_manager:
        turn_index = getattr(game_state.turns_manager, 'turn_index', 0)
        lap = getattr(game_state.turns_manager, 'lap', 0)
    
    # Calculate percentage of hexes owned by current player
    hex_stats = game_state.get_hex_ownership_stats(current_player_color)
    owned_hex_percentage = hex_stats['percentage']
    
    # Get event history
    event_history = []
    if hasattr(game_state, 'history_manager') and game_state.history_manager:
        all_events = game_state.history_manager.get_all_events()
        for history_event in all_events:
            event_data = {
                'type': history_event.event.get_type().value,
                'encoding': history_event.event.encode(),
                'author_color': history_event.author_color.value if history_event.author_color else None,
                'author_name': history_event.author_name
            }
            event_history.append(event_data)
    
    return jsonify({
        'success': True,
        'hexes': hexes,
        'entities': entities,
        'current_color': current_color_value,
        'turn_index': game_state.turns_manager.turn_index if game_state.turns_manager else 0,
        'lap': game_state.turns_manager.lap if game_state.turns_manager else 0,
        'owned_hex_percentage': round(owned_hex_percentage, 1),
        'event_history': event_history,
        'event_history_encoded': game_state.history_manager.encode_events_list() if hasattr(game_state, 'history_manager') and game_state.history_manager else ""
    })


@app.route('/api/game/province/<coordinate1>/<coordinate2>')
def api_game_province(coordinate1, coordinate2):
    """Get province information for a specific hex."""
    try:
        # Convert string coordinates to integers (handles negative numbers)
        coord1 = int(coordinate1)
        coord2 = int(coordinate2)
    except ValueError:
        return jsonify({'error': 'Invalid coordinates'}), 400
    
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'error': 'No active game session'}), 404
    
    # Mark session as recently used (move to end)
    game_sessions.move_to_end(session_id)
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    
    if game_state is None:
        return jsonify({'error': 'Game state not available'}), 500
    
    # Get current player color for fog of war
    current_player_color = None
    if hasattr(game_state, 'entities_manager') and game_state.entities_manager:
        current_entity = game_state.entities_manager.get_current_entity()
        if current_entity:
            current_player_color = current_entity.color
    
    # Update fog of war if enabled
    if (game_state.fog_of_war_manager and 
        game_state.fog_of_war_manager.enabled and 
        current_player_color):
        game_state.fog_of_war_manager.target_color = current_player_color
        game_state.fog_of_war_manager.apply_update()
    
    # Find the hex
    hex_obj = game_state.get_hex(coord1, coord2)
    if not hex_obj:
        return jsonify({'error': 'Hex not found'}), 404
    
    # Check if hex is visible (not in fog)
    is_visible = True
    if (game_state.fog_of_war_manager and 
        game_state.fog_of_war_manager.enabled):
        is_visible = not hasattr(hex_obj, 'fog') or not hex_obj.fog
    
    # If hex is in fog, return limited information
    if not is_visible:
        return jsonify({
            'success': True,
            'province_id': None,
            'money': 0,
            'income': 0,
            'consumption': 0,
            'profit': 0,
            'city_name': '',
            'piece_costs': {},
            'piece_maintenance': {},
            'piece_strength': {},
            'fog': True
        })
    
    # Get the province for this hex
    province = hex_obj.get_province()
    if not province:
        return jsonify({
            'success': True,
            'province_id': None,
            'money': 0,
            'income': 0,
            'consumption': 0,
            'profit': 0,
            'city_name': '',
            'piece_costs': {},
            'piece_maintenance': {},
            'piece_strength': {}
        })
    
    # Calculate income, consumption, and profit using economics manager
    if game_state.economics_manager:
        income = game_state.economics_manager.calculate_province_income(province)
        consumption = game_state.economics_manager.calculate_province_consumption(province)
        profit = game_state.economics_manager.calculate_province_profit(province)
    else:
        # Fallback if economics manager not available
        income = 0
        consumption = 0
        profit = 0
    
    # Calculate piece costs and maintenance/income for build menu
    piece_costs = {}
    piece_maintenance = {}
    if game_state.ruleset:
        from core.enums import PieceType
        piece_costs = {
            'peasant': game_state.ruleset.get_price(province, PieceType.PEASANT),
            'spearman': game_state.ruleset.get_price(province, PieceType.SPEARMAN),
            'baron': game_state.ruleset.get_price(province, PieceType.BARON),
            'knight': game_state.ruleset.get_price(province, PieceType.KNIGHT),
            'tower': game_state.ruleset.get_price(province, PieceType.TOWER),
            'strong_tower': game_state.ruleset.get_price(province, PieceType.STRONG_TOWER),
            'farm': game_state.ruleset.get_price(province, PieceType.FARM),
        }
        
        # Calculate maintenance (consumption) or income for each piece
        piece_maintenance = {
            'peasant': -game_state.ruleset.get_consumption(PieceType.PEASANT),  # Negative for cost
            'spearman': -game_state.ruleset.get_consumption(PieceType.SPEARMAN),
            'baron': -game_state.ruleset.get_consumption(PieceType.BARON),
            'knight': -game_state.ruleset.get_consumption(PieceType.KNIGHT),
            'tower': -game_state.ruleset.get_consumption(PieceType.TOWER),
            'strong_tower': -game_state.ruleset.get_consumption(PieceType.STRONG_TOWER),
            'farm': game_state.ruleset.get_hex_income(PieceType.FARM),  # Positive for income
        }
        
        # Calculate strength/defense values for units and towers
        from core.core_utils import get_strength
        piece_strength = {
            'peasant': get_strength(PieceType.PEASANT),
            'spearman': get_strength(PieceType.SPEARMAN),
            'baron': get_strength(PieceType.BARON),
            'knight': get_strength(PieceType.KNIGHT),
            'tower': game_state.ruleset.get_defense_value(PieceType.TOWER),  # Defense value for towers
            'strong_tower': game_state.ruleset.get_defense_value(PieceType.STRONG_TOWER),
            'farm': None,  # Farms don't have strength
        }
    
    # Get province color and current player color for frontend checks
    province_color_value = None
    if province:
        province_color = province.get_color()
        if province_color:
            province_color_value = province_color.value if hasattr(province_color, 'value') else str(province_color)
    
    current_color_value = None
    if current_player_color:
        current_color_value = current_player_color.value if hasattr(current_player_color, 'value') else str(current_player_color)
    
    return jsonify({
        'success': True,
        'province_id': province.get_id(),
        'money': province.get_money(),
        'income': income,
        'consumption': consumption,
        'profit': profit,
        'city_name': province.get_city_name(),
        'piece_costs': piece_costs,
        'piece_maintenance': piece_maintenance,  # Negative for cost, positive for income (farms)
        'piece_strength': piece_strength,  # Strength for units and towers
        'province_color': province_color_value,
        'current_color': current_color_value
    })


@app.route('/api/game/action', methods=['POST'])
def api_game_action():
    """Submit a game action."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'error': 'No active game session'}), 404
    
    # Mark session as recently used (move to end)
    game_sessions.move_to_end(session_id)
    
    data = request.get_json()
    # TODO: Process action
    return jsonify({'success': True})


@app.route('/api/game/valid-placement', methods=['POST'])
def api_game_valid_placement():
    """Get valid hexes for placing a piece type from a province."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'success': False, 'error': 'No active game session'}), 404
    
    # Mark session as recently used (move to end)
    game_sessions.move_to_end(session_id)
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    
    if game_state is None:
        return jsonify({'success': False, 'error': 'Game state not available'}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    # Get parameters
    try:
        province_coord1 = int(data.get('province_coordinate1'))
        province_coord2 = int(data.get('province_coordinate2'))
        piece_type_str = data.get('piece_type')
    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': f'Invalid parameters: {e}'}), 400
    
    if not piece_type_str:
        return jsonify({'success': False, 'error': 'piece_type is required'}), 400
    
    # Convert piece type string to enum
    from core.enums import PieceType
    try:
        piece_type = PieceType(piece_type_str.lower())
    except ValueError:
        return jsonify({'success': False, 'error': f'Invalid piece type: {piece_type_str}'}), 400
    
    # Get the province hex
    province_hex = game_state.get_hex(province_coord1, province_coord2)
    if not province_hex:
        return jsonify({'success': False, 'error': 'Province hex not found'}), 404
    
    # Get the province
    province = province_hex.get_province()
    if not province:
        return jsonify({'success': False, 'error': 'Hex is not in a province'}), 400
    
    # Get current player
    current_entity = game_state.entities_manager.get_current_entity()
    if not current_entity:
        return jsonify({'success': False, 'error': 'No current player'}), 400
    
    # Check if province belongs to current player
    if province.get_color() != current_entity.color:
        return jsonify({'success': False, 'error': 'Province does not belong to current player'}), 403
    
    # Calculate valid placement hexes
    from core.core_utils import is_unit, get_strength
    valid_hexes = []
    
    if is_unit(piece_type):
        # For units: hexes adjacent to province hexes (within move range)
        # Simplified: get all hexes adjacent to any province hex
        province_hexes = province.get_hexes()
        strength = get_strength(piece_type)
        
        # Get all hexes within reach (adjacent to province)
        visited_coords = set()
        for p_hex in province_hexes:
            for adj_hex in p_hex.adjacent_hexes:
                coord_key = (adj_hex.coordinate1, adj_hex.coordinate2)
                if coord_key in visited_coords:
                    continue
                visited_coords.add(coord_key)
                
                # Check if hex can accept unit
                # Units can be placed on: empty hexes, trees, graves
                # Cannot be placed on: static pieces (unless tree/grave)
                if adj_hex.is_empty():
                    valid_hexes.append({
                        'coordinate1': adj_hex.coordinate1,
                        'coordinate2': adj_hex.coordinate2
                    })
                elif adj_hex.piece in (PieceType.PINE, PieceType.PALM, PieceType.GRAVE):
                    valid_hexes.append({
                        'coordinate1': adj_hex.coordinate1,
                        'coordinate2': adj_hex.coordinate2
                    })
                elif adj_hex.has_unit() and adj_hex.color == province.get_color():
                    # Can merge with existing unit (build on top of it)
                    valid_hexes.append({
                        'coordinate1': adj_hex.coordinate1,
                        'coordinate2': adj_hex.coordinate2
                    })
    elif piece_type == PieceType.FARM:
        # For farms: empty hexes within the province that are adjacent to a city or farm
        # This matches MoveZoneManager.updateForFarm() logic
        province_hexes = province.get_hexes()
        
        # Mark hexes that are adjacent to cities or farms
        valid_hex_coords = set()
        for p_hex in province_hexes:
            # If hex has a city or farm, mark it and its adjacent hexes
            if p_hex.piece in (PieceType.CITY, PieceType.FARM):
                # Mark adjacent hexes if they're empty and in the province
                for adj_hex in p_hex.adjacent_hexes:
                    if adj_hex.color == province.get_color() and adj_hex.is_empty():
                        valid_hex_coords.add((adj_hex.coordinate1, adj_hex.coordinate2))
        
        # Convert to list format
        for coord in valid_hex_coords:
            valid_hexes.append({
                'coordinate1': coord[0],
                'coordinate2': coord[1]
            })
    elif piece_type == PieceType.TOWER:
        # For towers: empty hexes within the province
        for hex in province.get_hexes():
            if hex.is_empty():
                valid_hexes.append({
                    'coordinate1': hex.coordinate1,
                    'coordinate2': hex.coordinate2
                })
    elif piece_type == PieceType.STRONG_TOWER:
        # For strong towers: hexes with towers within the province
        for hex in province.get_hexes():
            if hex.piece == PieceType.TOWER:
                valid_hexes.append({
                    'coordinate1': hex.coordinate1,
                    'coordinate2': hex.coordinate2
                })
    
    # Filter to only visible hexes (respect fog of war)
    visible_hexes = game_state.get_hexes_for_player(current_entity.color)
    visible_coords = {(h.coordinate1, h.coordinate2) for h in visible_hexes}
    
    valid_hexes = [
        h for h in valid_hexes
        if (h['coordinate1'], h['coordinate2']) in visible_coords
    ]
    
    return jsonify({
        'success': True,
        'valid_hexes': valid_hexes
    })


@app.route('/api/game/build', methods=['POST'])
def api_game_build():
    """Build a piece on a hex."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'success': False, 'error': 'No active game session'}), 404
    
    # Mark session as recently used (move to end)
    game_sessions.move_to_end(session_id)
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    
    if game_state is None:
        return jsonify({'success': False, 'error': 'Game state not available'}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    # Get parameters
    try:
        coordinate1 = int(data.get('coordinate1'))
        coordinate2 = int(data.get('coordinate2'))
        piece_type_str = data.get('piece_type')
        # Optional: province coordinates (for units built on gray hexes)
        province_coord1 = data.get('province_coordinate1')
        province_coord2 = data.get('province_coordinate2')
    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': f'Invalid parameters: {e}'}), 400
    
    if not piece_type_str:
        return jsonify({'success': False, 'error': 'piece_type is required'}), 400
    
    # Convert piece type string to enum
    from core.enums import PieceType
    try:
        piece_type = PieceType(piece_type_str.lower())
    except ValueError:
        return jsonify({'success': False, 'error': f'Invalid piece type: {piece_type_str}'}), 400
    
    # Get the target hex (where we're building)
    hex_obj = game_state.get_hex(coordinate1, coordinate2)
    if not hex_obj:
        return jsonify({'success': False, 'error': 'Hex not found'}), 404
    
    # Get province hex if provided (for units on gray hexes)
    province_hex = None
    if province_coord1 is not None and province_coord2 is not None:
        try:
            province_hex = game_state.get_hex(int(province_coord1), int(province_coord2))
        except (ValueError, TypeError):
            pass
    
    # Get current player
    current_entity = game_state.entities_manager.get_current_entity()
    if not current_entity:
        return jsonify({'success': False, 'error': 'No current player'}), 400
    
    # Create build command
    from commands.types import BuildPieceCommand
    from commands.executor import CommandExecutor
    
    command = BuildPieceCommand(
        hex=hex_obj,
        piece_type=piece_type,
        province_hex=province_hex
    )
    
    # Execute command
    executor = CommandExecutor(game_state)
    success, error = executor.execute(command, current_entity.color)
    
    if success:
        # Get province for response
        province = province_hex.get_province() if province_hex else hex_obj.get_province()
        if not province:
            province = game_state.provinces_manager.find_province_slowly(hex_obj)
        
        return jsonify({
            'success': True,
            'message': f'Built {piece_type.value} successfully',
            'province_money': province.get_money() if province else 0
        })
    else:
        return jsonify({'success': False, 'error': error or 'Build failed'}), 400


@app.route('/api/game/restart', methods=['POST'])
def api_game_restart():
    """Restart the current game."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'error': 'No active game session'}), 404
    
    session_data = game_sessions[session_id]
    level_index = session_data['level_index']
    
    # Reinitialize the game (this will also update the session timestamp and move it to end)
    return api_game_init(level_index)


@app.route('/api/game/save', methods=['POST'])
def api_game_save():
    """Save the current game."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'success': False, 'error': 'No active game session'}), 404
    
    # Mark session as recently used (move to end)
    game_sessions.move_to_end(session_id)
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    level_index = session_data.get('level_index', 0)
    
    if game_state is None:
        return jsonify({'success': False, 'error': 'Game state not available'}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    save_name = data.get('save_name', '').strip()
    if not save_name:
        return jsonify({'success': False, 'error': 'Save name is required'}), 400
    
    try:
        # Create saves directory if it doesn't exist
        saves_dir = PROJECT_ROOT / 'saves'
        saves_dir.mkdir(exist_ok=True)
        
        # Check if save with this name already exists (will be overwritten)
        save_file = saves_dir / f"{save_name}.save"
        existing_save = save_file.exists()
        
        # Manage max 5 saves - delete oldest BEFORE saving new one
        # This ensures we maintain max 5 saves at all times
        MAX_SAVES = 5
        save_files = sorted(saves_dir.glob('*.save'), key=lambda p: p.stat().st_mtime)
        
        # If we're at the limit and not overwriting an existing save, delete the oldest
        if len(save_files) >= MAX_SAVES and not existing_save:
            # Delete oldest save(s) until we have room for the new one
            saves_to_delete = len(save_files) - (MAX_SAVES - 1)
            for old_save in save_files[:saves_to_delete]:
                old_save.unlink()
        
        # Encode game state
        from save_load.encoder import GameStateEncoder
        encoder = GameStateEncoder()
        level_code = encoder.encode(game_state, campaign_level_index=level_index)
        
        # Save to file
        with open(save_file, 'w') as f:
            f.write(level_code)
        
        return jsonify({'success': True, 'message': 'Game saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error saving game: {str(e)}'}), 500


@app.route('/api/game/list-saves', methods=['GET'])
def api_game_list_saves():
    """List all saved games."""
    try:
        saves_dir = PROJECT_ROOT / 'saves'
        saves_dir.mkdir(exist_ok=True)
        
        # Get all save files
        save_files = sorted(saves_dir.glob('*.save'), key=lambda p: p.stat().st_mtime, reverse=True)
        
        saves = []
        for save_file in save_files:
            # Extract save name (filename without .save extension)
            save_name = save_file.stem
            # Get modification time
            mtime = save_file.stat().st_mtime
            from datetime import datetime
            save_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            saves.append({
                'name': save_name,
                'date': save_date
            })
        
        return jsonify({'success': True, 'saves': saves})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error listing saves: {str(e)}'}), 500


@app.route('/api/game/load', methods=['POST'])
def api_game_load():
    """Load a saved game."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    save_name = data.get('save_name', '').strip()
    if not save_name:
        return jsonify({'success': False, 'error': 'Save name is required'}), 400
    
    try:
        saves_dir = PROJECT_ROOT / 'saves'
        save_file = saves_dir / f"{save_name}.save"
        
        if not save_file.exists():
            return jsonify({'success': False, 'error': 'Save file not found'}), 404
        
        # Read level code from file
        with open(save_file, 'r') as f:
            level_code = f.read().strip()
        
        # Decode game state
        from save_load.decoder import GameStateDecoder
        decoder = GameStateDecoder()
        result = decoder.decode(level_code)
        
        if isinstance(result, tuple):
            game_state, campaign_level_index = result
        else:
            game_state = result
            campaign_level_index = -1
        
        if game_state is None:
            return jsonify({'success': False, 'error': 'Failed to decode game state'}), 500
        
        # Create new session for the loaded game
        import uuid
        new_session_id = str(uuid.uuid4())
        
        # Ensure adjacency graph is built
        from save_load.decoder import _build_adjacency_graph
        _build_adjacency_graph(game_state)
        
        # Initialize starting money for all provinces (if not already set)
        from core.enums import EventType, PieceType
        for province in game_state.provinces_manager.provinces:
            if province.get_money() == 0:
                # Set default starting money (matching api_game_init)
                province.set_money(10)
        
        # Initialize game manager
        from core.game_manager import GameManager, GameMode
        game_manager = GameManager(game_state, GameMode.CAMPAIGN)
        
        # Store session
        cleanup_oldest_session()
        game_sessions[new_session_id] = {
            'game_state': game_state,
            'game_manager': game_manager,
            'level_index': campaign_level_index if campaign_level_index >= 0 else 0,
            'created_at': time.time()
        }
        
        # Set session ID
        session['session_id'] = new_session_id
        
        return jsonify({
            'success': True,
            'session_id': new_session_id,
            'level_index': campaign_level_index if campaign_level_index >= 0 else 0
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error loading game: {str(e)}'}), 500


@app.route('/api/game/delete-save', methods=['POST'])
def api_game_delete_save():
    """Delete a saved game."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    save_name = data.get('save_name', '').strip()
    if not save_name:
        return jsonify({'success': False, 'error': 'Save name is required'}), 400
    
    try:
        saves_dir = PROJECT_ROOT / 'saves'
        save_file = saves_dir / f"{save_name}.save"
        
        if not save_file.exists():
            return jsonify({'success': False, 'error': 'Save file not found'}), 404
        
        # Delete the save file
        save_file.unlink()
        
        return jsonify({'success': True, 'message': 'Save file deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error deleting save: {str(e)}'}), 500


@app.route('/api/game/undo', methods=['POST'])
def api_game_undo():
    """Undo the last action."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'success': False, 'error': 'No active game session'}), 404
    
    # Mark session as recently used (move to end)
    game_sessions.move_to_end(session_id)
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    
    if game_state is None:
        return jsonify({'success': False, 'error': 'Game state not available'}), 500
    
    # Check if undo is possible
    if not hasattr(game_state, 'undo_manager') or not game_state.undo_manager.can_undo():
        return jsonify({'success': False, 'error': 'Nothing to undo'}), 400
    
    # Perform undo
    try:
        success = game_state.undo_manager.undo()
        if success:
            # Update fog of war if enabled
            if game_state.fog_of_war_manager and game_state.fog_of_war_manager.enabled:
                game_state.fog_of_war_manager.apply_update()
            
            return jsonify({'success': True, 'message': 'Action undone'})
        else:
            return jsonify({'success': False, 'error': 'Failed to undo action'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error during undo: {str(e)}'}), 500


@app.route('/api/game/valid-movement', methods=['POST'])
def api_game_valid_movement():
    """Get valid hexes for moving a unit."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'success': False, 'error': 'No active game session'}), 404
    
    # Mark session as recently used (move to end)
    game_sessions.move_to_end(session_id)
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    
    if game_state is None:
        return jsonify({'success': False, 'error': 'Game state not available'}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    # Get parameters
    try:
        coord1 = int(data.get('coordinate1'))
        coord2 = int(data.get('coordinate2'))
    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': f'Invalid parameters: {e}'}), 400
    
    # Get the hex
    hex = game_state.get_hex(coord1, coord2)
    if not hex:
        return jsonify({'success': False, 'error': 'Hex not found'}), 404
    
    # Check if hex has a unit
    if not hex.has_unit():
        return jsonify({'success': False, 'error': 'Hex does not have a unit'}), 400
    
    # Get current player
    current_entity = game_state.entities_manager.get_current_entity()
    if not current_entity:
        return jsonify({'success': False, 'error': 'No current player'}), 400
    
    # Check if unit belongs to current player
    if hex.color != current_entity.color:
        return jsonify({'success': False, 'error': 'Unit does not belong to current player'}), 403
    
    # Check if unit is ready to move
    if not game_state.readiness_manager.is_ready(hex):
        return jsonify({'success': False, 'error': 'Unit has already moved this turn'}), 400
    
    # Ensure adjacency is built (if not already)
    if not hex.adjacent_hexes:
        from save_load.decoder import _build_adjacency_graph
        _build_adjacency_graph(game_state)
    
    # Use MoveZoneManager to calculate valid movement hexes (up to 4 hexes away)
    game_state.move_zone_manager.update_for_unit(hex)
    
    # Filter valid hexes based on game rules
    # Note: MoveZoneManager already filters based on can_hex_be_captured() for enemy hexes,
    # so if a hex is in the move zone, it's either:
    # 1. Empty or has tree/grave (same color)
    # 2. Has an enemy unit that can be captured
    # 3. Has a static piece (city/tower) that can be captured (if different color)
    # 4. Has a friendly unit in same province (for merging)
    valid_hexes = []
    from core.core_utils import get_merge_result, get_strength
    from core.enums import PieceType
    
    unit_strength = get_strength(hex.piece)
    
    for move_hex in game_state.move_zone_manager.hexes:
        # Skip the start hex itself
        if move_hex == hex:
            continue
        
        # Can move to empty hexes, trees, graves
        can_move = False
        
        if move_hex.is_empty():
            can_move = True
        elif move_hex.piece in (PieceType.PINE, PieceType.PALM, PieceType.GRAVE):
            can_move = True
        elif move_hex.has_unit():
            # Can move to enemy units (capture)
            if move_hex.color != hex.color:
                can_move = True
            # Can move to friendly units in same province (merge)
            elif (move_hex.get_province() == hex.get_province() and 
                  get_merge_result(hex.piece, move_hex.piece) is not None):
                can_move = True
        elif move_hex.has_static_piece():
            # Can move to enemy static pieces (cities, towers) if unit is strong enough
            if move_hex.color != hex.color:
                # Check if unit can capture this static piece
                if game_state.ruleset.can_hex_be_captured(move_hex, unit_strength):
                    can_move = True
            # Can move to friendly static pieces only if they're trees or graves
            # (already handled above)
        
        if can_move:
            valid_hexes.append({
                'coordinate1': move_hex.coordinate1,
                'coordinate2': move_hex.coordinate2
            })
    
    return jsonify({
        'success': True,
        'valid_hexes': valid_hexes
    })


@app.route('/api/game/move-unit', methods=['POST'])
def api_game_move_unit():
    """Move a unit from one hex to another."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'success': False, 'error': 'No active game session'}), 404
    
    # Mark session as recently used (move to end)
    game_sessions.move_to_end(session_id)
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    
    if game_state is None:
        return jsonify({'success': False, 'error': 'Game state not available'}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    # Get parameters
    try:
        start_coord1 = int(data.get('start_coordinate1'))
        start_coord2 = int(data.get('start_coordinate2'))
        finish_coord1 = int(data.get('finish_coordinate1'))
        finish_coord2 = int(data.get('finish_coordinate2'))
    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': f'Invalid parameters: {e}'}), 400
    
    # Get the hexes
    start_hex = game_state.get_hex(start_coord1, start_coord2)
    finish_hex = game_state.get_hex(finish_coord1, finish_coord2)
    
    if not start_hex:
        return jsonify({'success': False, 'error': 'Start hex not found'}), 404
    if not finish_hex:
        return jsonify({'success': False, 'error': 'Finish hex not found'}), 404
    
    # Get current player
    current_entity = game_state.entities_manager.get_current_entity()
    if not current_entity:
        return jsonify({'success': False, 'error': 'No current player'}), 400
    
    # Create and execute move command
    from commands.types import MoveUnitCommand
    from commands.executor import CommandExecutor
    from commands.validator import CommandValidator
    
    command = MoveUnitCommand(
        start_hex=start_hex,
        finish_hex=finish_hex,
        color_transfer_enabled=True
    )
    
    validator = CommandValidator(game_state)
    executor = CommandExecutor(game_state)
    
    # Validate command
    is_valid, error = validator.validate(command, current_entity.color)
    if not is_valid:
        return jsonify({'success': False, 'error': error}), 400
    
    # Execute command
    success, error = executor.execute(command, current_entity.color)
    if not success:
        return jsonify({'success': False, 'error': error}), 400
    
    # Update fog of war if enabled
    if game_state.fog_of_war_manager and game_state.fog_of_war_manager.enabled:
        game_state.fog_of_war_manager.apply_update()
    
    return jsonify({'success': True, 'message': 'Unit moved successfully'})


@app.route('/api/game/end-turn', methods=['POST'])
def api_game_end_turn():
    """End the current player's turn."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'success': False, 'error': 'No active game session'}), 404
    
    # Mark session as recently used (move to end)
    game_sessions.move_to_end(session_id)
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    
    if game_state is None:
        return jsonify({'success': False, 'error': 'Game state not available'}), 500
    
    # Get current player
    current_entity = game_state.entities_manager.get_current_entity()
    if not current_entity:
        return jsonify({'success': False, 'error': 'No current player'}), 400
    
    # Create and execute end turn command
    from commands.types import EndTurnCommand
    from commands.executor import CommandExecutor
    
    command = EndTurnCommand()
    executor = CommandExecutor(game_state)
    
    success, error = executor.execute(command, current_entity.color)
    
    if success:
        # Update fog of war if enabled
        if game_state.fog_of_war_manager and game_state.fog_of_war_manager.enabled:
            game_state.fog_of_war_manager.apply_update()
        
        # After ending turn, process AI turns until next human player's turn
        if game_state.ai_manager:
            game_state.ai_manager.process_ai_turns()
        
        # Get new current player after turn switch (and AI processing)
        new_current_entity = game_state.entities_manager.get_current_entity()
        new_current_color = new_current_entity.color.value if new_current_entity else None
        
        return jsonify({
            'success': True,
            'message': 'Turn ended successfully',
            'new_current_color': new_current_color
        })
    else:
        return jsonify({'success': False, 'error': error or 'Failed to end turn'}), 400


@app.route('/api/game/win-lose-status', methods=['GET'])
def api_game_win_lose_status():
    """Check if current player has won or lost."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'success': False, 'error': 'No active game session'}), 404
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    
    if game_state is None:
        return jsonify({'success': False, 'error': 'Game state not available'}), 500
    
    # Get current player
    current_entity = game_state.entities_manager.get_current_entity()
    if not current_entity:
        return jsonify({'success': False, 'error': 'No current player'}), 400
    
    current_color = current_entity.color
    
    # Check lose condition (no provinces)
    is_dead = game_state.game_end_manager.check_player_lose(current_color)
    
    # Check win condition (all opponents dead OR 80% hexes)
    has_won = False
    if not is_dead:
        has_won = game_state.game_end_manager.check_player_win(current_color)
    
    return jsonify({
        'success': True,
        'is_dead': is_dead,
        'has_won': has_won,
        'current_color': current_color.value if hasattr(current_color, 'value') else str(current_color)
    })


@app.route('/api/game/continue-after-lose', methods=['POST'])
def api_game_continue_after_lose():
    """Continue game after player loses (game continues for other players)."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'success': False, 'error': 'No active game session'}), 404
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    
    if game_state is None:
        return jsonify({'success': False, 'error': 'Game state not available'}), 500
    
    # Process AI turns to get to next human player
    if game_state.ai_manager:
        game_state.ai_manager.process_ai_turns()
    
    return jsonify({'success': True, 'message': 'Game continues'})


@app.route('/api/game/continue-after-win', methods=['POST'])
def api_game_continue_after_win():
    """Continue after player wins (return to landing page)."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'success': False, 'error': 'No active game session'}), 404
    
    # Clear the session
    if session_id in game_sessions:
        del game_sessions[session_id]
    session.pop('session_id', None)
    
    return jsonify({'success': True, 'message': 'Returning to main menu'})


@app.route('/api/game/defense-indicators', methods=['POST'])
def api_game_defense_indicators():
    """Get defense indicators for a hex (city or tower)."""
    session_id = session.get('session_id')
    if not session_id or session_id not in game_sessions:
        return jsonify({'success': False, 'error': 'No active game session'}), 404
    
    session_data = game_sessions[session_id]
    game_state = session_data.get('game_state')
    
    if game_state is None:
        return jsonify({'success': False, 'error': 'Game state not available'}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    from core.enums import PieceType
    
    try:
        coord1 = int(data.get('coordinate1'))
        coord2 = int(data.get('coordinate2'))
    except (ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': f'Invalid parameters: {e}'}), 400
    
    hex = game_state.get_hex(coord1, coord2)
    if not hex:
        return jsonify({'success': False, 'error': 'Hex not found'}), 404
    
    # Only show defense indicators for cities and towers
    if hex.piece not in (PieceType.CITY, PieceType.TOWER, PieceType.STRONG_TOWER):
        return jsonify({'success': False, 'error': 'Hex is not a city or tower'}), 400
    
    # Get defense values for adjacent hexes in the same province
    hex_province = hex.get_province()
    defense_indicators = []
    
    for adj_hex in hex.adjacent_hexes:
        # Only show indicators for hexes in the same province
        if hex_province:
            adj_province = adj_hex.get_province()
            if adj_province != hex_province:
                continue
        
        # Calculate defense value for this adjacent hex
        defense_value = game_state.ruleset.get_defense_value_hex(adj_hex)
        
        defense_indicators.append({
            'coordinate1': adj_hex.coordinate1,
            'coordinate2': adj_hex.coordinate2,
            'defense_value': defense_value
        })
    
    return jsonify({
        'success': True,
        'defense_indicators': defense_indicators
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
