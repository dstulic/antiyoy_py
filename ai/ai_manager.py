"""AI Manager - manages AI players and processes their turns."""

from typing import Optional
from core.game_state import GameState
from core.enums import EntityType, RulesType
from ai.balancer_ai import AiBalancerDefaultV1
try:
    from ai.random_ai import AiRandom
except ImportError:
    # AiRandom not implemented yet
    AiRandom = None


class AIManager:
    """Manages AI players and their decision making. Each entity's difficulty is set on the entity (ai_difficulty)."""

    def __init__(self, game_state: GameState):
        """
        Initialize AI manager.

        Args:
            game_state: The game state
        """
        self.game_state = game_state
        self.active = True

        # Create AI instances
        self.ai_random = None
        self.ai_balancer_default: Optional[AiBalancerDefaultV1] = None

        # Create AIs
        self.create_ais()
    
    def create_ais(self) -> None:
        """Create AI instances."""
        if AiRandom:
            self.ai_random = AiRandom(self.game_state)
        self.ai_balancer_default = AiBalancerDefaultV1(self.game_state)
    
    def get_ai_for_entity(self, entity) -> Optional:
        """
        Get AI instance for a player entity.
        
        Args:
            entity: Player entity
            
        Returns:
            AI instance or None
        """
        if not entity or not entity.is_artificial_intelligence():
            return None
        
        if entity.type == EntityType.AI_RANDOM:
            return self.ai_random
        elif entity.type == EntityType.AI_BALANCER:
            return self.get_balancer_ai()
        
        return None
    
    def get_balancer_ai(self):
        """Get balancer AI based on ruleset."""
        if not self.game_state.ruleset:
            return None
        
        rules_type = self.game_state.ruleset.get_rules_type()
        if rules_type == RulesType.DEF:
            return self.ai_balancer_default
        # Add other ruleset types as needed
        return self.ai_balancer_default
    
    def get_current_ai(self):
        """Get AI for current player."""
        current_entity = self.game_state.entities_manager.get_current_entity()
        if not current_entity:
            return None
        return self.get_ai_for_entity(current_entity)
    
    def process_ai_turn(self) -> bool:
        """
        Process AI turn if current player is AI.
        Uses the current entity's ai_difficulty (must be set at game init or in save).
        
        Returns:
            True if AI turn was processed, False otherwise
        """
        if not self.active:
            return False

        ai = self.get_current_ai()
        if not ai:
            return False

        current_entity = self.game_state.entities_manager.get_current_entity()
        assert current_entity is not None, "Current entity must exist when processing AI turn"
        difficulty = current_entity.get_ai_difficulty()
        assert difficulty is not None, (
            "AI entity must have ai_difficulty set. "
            "Level/save may be missing difficulty (format: type>color>name>difficulty). "
            "Start a new game from campaign or re-save."
        )
        ai.set_difficulty(difficulty)

        # Perform AI turn
        try:
            ai.perform()
            return True
        except Exception as e:
            print(f"Error processing AI turn: {e}")
            return False
    
    def process_ai_turns(self) -> None:
        """
        Process AI turns until a human player's turn is reached or the game has ended.
        """
        if not self.active:
            return

        n_entities = len(self.game_state.entities_manager.entities)
        hex_count = len(self.game_state.hexes)
        max_ai_laps = hex_count * 10
        max_iterations = max_ai_laps * n_entities
        iterations = 0
        
        while iterations < max_iterations:
            # Stop as soon as the game is over (someone won: 80% or all opponents dead)
            if self.game_state.game_end_manager.is_game_ended():
                break

            current_entity = self.game_state.entities_manager.get_current_entity()
            if not current_entity:
                break

            # If current entity is human, we're done
            if current_entity.is_human():
                break

            # If current entity is AI, process their turn
            if current_entity.is_artificial_intelligence():
                processed = self.process_ai_turn()
                if not processed:
                    break
                # After AI turn, game may have ended (e.g. reached 80%); stop immediately
                if self.game_state.game_end_manager.is_game_ended():
                    break
            else:
                break

            iterations += 1
        if iterations >= max_iterations:
            print(f"Warning: AI max turns limit reached ({max_iterations}).")

    def set_active(self, active: bool) -> None:
        """Set whether AI manager is active."""
        self.active = active
