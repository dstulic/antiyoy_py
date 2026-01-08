"""AI Manager - manages AI players and processes their turns."""

from typing import Optional
from core.game_state import GameState
from core.enums import EntityType, RulesType, Difficulty
from ai.balancer_ai import AiBalancerDefaultV1
try:
    from ai.random_ai import AiRandom
except ImportError:
    # AiRandom not implemented yet
    AiRandom = None


class AIManager:
    """Manages AI players and their decision making."""
    
    def __init__(self, game_state: GameState, difficulty: Difficulty = Difficulty.AVERAGE):
        """
        Initialize AI manager.
        
        Args:
            game_state: The game state
            difficulty: AI difficulty level
        """
        self.game_state = game_state
        self.difficulty = difficulty
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
        
        Returns:
            True if AI turn was processed, False otherwise
        """
        if not self.active:
            return False
        
        ai = self.get_current_ai()
        if not ai:
            return False
        
        # Set difficulty
        ai.set_difficulty(self.difficulty)
        
        # Perform AI turn
        try:
            ai.perform()
            return True
        except Exception as e:
            print(f"Error processing AI turn: {e}")
            return False
    
    def set_difficulty(self, difficulty: Difficulty) -> None:
        """Set AI difficulty."""
        self.difficulty = difficulty
    
    def set_active(self, active: bool) -> None:
        """Set whether AI manager is active."""
        self.active = active
