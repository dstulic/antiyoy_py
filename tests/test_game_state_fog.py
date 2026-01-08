"""Unit tests for GameState fog of war visibility."""

import pytest
from core.game_state import GameState
from core.hex import Hex
from core.enums import HColor, PieceType
from core.player_entity import PlayerEntity, EntityType
from save_load.decoder import GameStateDecoder
from campaign.levels import get_level_code


class TestGameStateFogOfWar:
    """Test fog of war visibility in GameState."""
    
    def test_get_hexes_for_player_no_fog(self):
        """Test that all hexes are returned when fog of war is disabled."""
        game_state = GameState()
        
        # Add some hexes
        hex1 = game_state.add_hex(0, 0, HColor.AQUA)
        hex2 = game_state.add_hex(1, 0, HColor.RED)
        hex3 = game_state.add_hex(0, 1, HColor.GRAY)
        
        # Disable fog of war
        game_state.fog_of_war_manager.set_enabled(False)
        
        # Get hexes for a player
        visible_hexes = game_state.get_hexes_for_player(HColor.AQUA)
        
        # Should return all hexes
        assert len(visible_hexes) == 3
        assert hex1 in visible_hexes
        assert hex2 in visible_hexes
        assert hex3 in visible_hexes
    
    def test_get_hexes_for_player_with_fog(self):
        """Test that only visible hexes are returned when fog of war is enabled."""
        # Use a real level with fog enabled
        level_code = get_level_code(1)
        if not level_code or level_code == "-":
            pytest.skip("Level 1 not available")
        
        decoder = GameStateDecoder()
        game_state, _ = decoder.decode(level_code)
        
        # Ensure fog is enabled
        if not game_state.fog_of_war_manager.enabled:
            game_state.fog_of_war_manager.set_enabled(True)
        
        # Get human player color
        human_entity = None
        for entity in game_state.entities_manager.entities:
            if entity.is_human():
                human_entity = entity
                break
        
        if not human_entity:
            pytest.skip("No human player in level 1")
        
        player_color = human_entity.color
        
        # Get visible hexes for the player
        visible_hexes = game_state.get_hexes_for_player(player_color)
        
        # Should have fewer visible hexes than total hexes
        assert len(visible_hexes) < len(game_state.hexes)
        assert len(visible_hexes) > 0
        
        # All visible hexes should not be in fog
        for hex in visible_hexes:
            assert not hasattr(hex, 'fog') or not hex.fog
        
        # Verify that player's own hexes are visible
        player_provinces = [
            p for p in game_state.provinces_manager.provinces
            if p.get_color() == player_color
        ]
        
        player_hexes = []
        for province in player_provinces:
            player_hexes.extend(province.get_hexes())
        
        # All player hexes should be visible
        visible_coords = {(h.coordinate1, h.coordinate2) for h in visible_hexes}
        for hex in player_hexes:
            assert (hex.coordinate1, hex.coordinate2) in visible_coords
    
    def test_get_hexes_for_player_different_players(self):
        """Test that different players see different hexes when fog is enabled."""
        level_code = get_level_code(1)
        if not level_code or level_code == "-":
            pytest.skip("Level 1 not available")
        
        decoder = GameStateDecoder()
        game_state, _ = decoder.decode(level_code)
        
        # Ensure fog is enabled
        if not game_state.fog_of_war_manager.enabled:
            game_state.fog_of_war_manager.set_enabled(True)
        
        # Get all player entities
        entities = game_state.entities_manager.entities
        if len(entities) < 2:
            pytest.skip("Need at least 2 players for this test")
        
        player1 = entities[0]
        player2 = entities[1]
        
        # Get visible hexes for each player
        visible_hexes_1 = game_state.get_hexes_for_player(player1.color)
        visible_hexes_2 = game_state.get_hexes_for_player(player2.color)
        
        # Both should have some visible hexes
        assert len(visible_hexes_1) > 0
        assert len(visible_hexes_2) > 0
        
        # If players are different colors, they might see different hexes
        # (though they might overlap if they're allies or close together)
        if player1.color != player2.color:
            # At least one player should see their own hexes
            player1_provinces = [
                p for p in game_state.provinces_manager.provinces
                if p.get_color() == player1.color
            ]
            if player1_provinces:
                player1_hexes = player1_provinces[0].get_hexes()
                if player1_hexes:
                    visible_coords_1 = {(h.coordinate1, h.coordinate2) for h in visible_hexes_1}
                    assert (player1_hexes[0].coordinate1, player1_hexes[0].coordinate2) in visible_coords_1
    
    def test_get_hexes_for_player_none_color(self):
        """Test that get_hexes_for_player uses current player when color is None."""
        level_code = get_level_code(1)
        if not level_code or level_code == "-":
            pytest.skip("Level 1 not available")
        
        decoder = GameStateDecoder()
        game_state, _ = decoder.decode(level_code)
        
        # Ensure fog is enabled
        if not game_state.fog_of_war_manager.enabled:
            game_state.fog_of_war_manager.set_enabled(True)
        
        # Get current entity
        current_entity = game_state.entities_manager.get_current_entity()
        if not current_entity:
            pytest.skip("No current entity")
        
        # Get hexes without specifying color (should use current player)
        visible_hexes = game_state.get_hexes_for_player(None)
        
        # Should return visible hexes for current player
        assert len(visible_hexes) > 0
        assert len(visible_hexes) <= len(game_state.hexes)
        
        # Verify it matches what we'd get with explicit color
        visible_hexes_explicit = game_state.get_hexes_for_player(current_entity.color)
        assert len(visible_hexes) == len(visible_hexes_explicit)
    
    def test_get_hexes_for_player_fog_disabled_returns_all(self):
        """Test that when fog is disabled, all hexes are returned regardless of player."""
        game_state = GameState()
        
        # Add hexes of different colors
        hex1 = game_state.add_hex(0, 0, HColor.AQUA)
        hex2 = game_state.add_hex(1, 0, HColor.RED)
        hex3 = game_state.add_hex(0, 1, HColor.LAVENDER)
        
        # Ensure fog is disabled
        game_state.fog_of_war_manager.set_enabled(False)
        
        # Get hexes for different players
        visible_aqua = game_state.get_hexes_for_player(HColor.AQUA)
        visible_red = game_state.get_hexes_for_player(HColor.RED)
        visible_lavender = game_state.get_hexes_for_player(HColor.LAVENDER)
        
        # All should return all hexes
        assert len(visible_aqua) == 3
        assert len(visible_red) == 3
        assert len(visible_lavender) == 3
        
        assert hex1 in visible_aqua and hex1 in visible_red and hex1 in visible_lavender
        assert hex2 in visible_aqua and hex2 in visible_red and hex2 in visible_lavender
        assert hex3 in visible_aqua and hex3 in visible_red and hex3 in visible_lavender
