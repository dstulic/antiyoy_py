"""Base classes for visual integration tests."""

import inspect
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pathlib import Path
from core.game_state import GameState
from save_load.decoder import GameStateDecoder
from save_load.encoder import GameStateEncoder


class VisualTest(ABC):
    """Base class for visual integration tests."""
    
    _registry: Dict[str, 'VisualTest'] = {}
    
    def __init__(self, name: str, description: str = ""):
        """
        Initialize a visual test.
        
        Args:
            name: Unique test name
            description: Test description
        """
        self.name = name
        self.description = description
        self._initial_state: Optional[GameState] = None
        self._final_state: Optional[GameState] = None
    
    @abstractmethod
    def setup(self) -> GameState:
        """
        Set up the initial game state for the test.
        
        Returns:
            Initial game state
        """
        pass
    
    @abstractmethod
    def run(self, game_state: GameState) -> GameState:
        """
        Run the test logic.
        
        Args:
            game_state: Initial game state
            
        Returns:
            Final game state after test execution
        """
        pass
    
    def execute(self) -> tuple[GameState, GameState]:
        """
        Execute the test and return both initial and final states.
        
        Returns:
            Tuple of (initial_state, final_state)
        """
        initial = self.setup()
        final = self.run(initial)
        return initial, final
    
    def get_map_file_path(self) -> Path:
        """
        Get the path to the map file for this test.
        
        Returns:
            Path to the map file
        """
        # Map files are stored in tests/visual/maps/ with the test name
        maps_dir = Path(__file__).parent.parent / 'visual' / 'maps'
        maps_dir.mkdir(parents=True, exist_ok=True)
        # Sanitize test name for filename (replace spaces with underscores)
        safe_name = self.name.replace(' ', '_').lower()
        return maps_dir / f"{safe_name}.map"
    
    def load_map(self) -> Optional[GameState]:
        """
        Load game state from map file.
        
        Returns:
            GameState if map file exists, None otherwise
        """
        map_file = self.get_map_file_path()
        if not map_file.exists():
            return None
        
        try:
            with open(map_file, 'r') as f:
                level_code = f.read().strip()
            
            decoder = GameStateDecoder()
            result = decoder.decode(level_code)
            
            if isinstance(result, tuple):
                game_state, _ = result
            else:
                game_state = result
            
            if game_state is None:
                return None
            
            # Ensure adjacency graph is built
            from save_load.decoder import _build_adjacency_graph
            _build_adjacency_graph(game_state)
            
            # Initialize starting money for all provinces
            for province in game_state.provinces_manager.provinces:
                if province.get_money() == 0:
                    province.set_money(10)
            
            return game_state
        except Exception as e:
            print(f"Error loading map file {map_file}: {e}")
            return None
    
    def save_map(self, game_state: GameState) -> bool:
        """
        Save game state to map file.
        
        Args:
            game_state: The game state to save
            
        Returns:
            True if successful, False otherwise
        """
        map_file = self.get_map_file_path()
        try:
            encoder = GameStateEncoder()
            # Use default client_init and camera for visual tests
            level_code = encoder.encode(
                game_state,
                client_init="small,-1",
                camera="0.65 1.04 1.0",
                campaign_level_index=-1
            )
            
            with open(map_file, 'w') as f:
                f.write(level_code)
            
            return True
        except Exception as e:
            print(f"Error saving map file {map_file}: {e}")
            return False
    
    @classmethod
    def register(cls, test: 'VisualTest') -> None:
        """Register a test in the registry."""
        cls._registry[test.name] = test
    
    @classmethod
    def get_all_tests(cls) -> List['VisualTest']:
        """Get all registered tests."""
        return list(cls._registry.values())
    
    @classmethod
    def get_test(cls, name: str) -> Optional['VisualTest']:
        """Get a test by name."""
        return cls._registry.get(name)
    
    @classmethod
    def get_test_names(cls) -> List[str]:
        """Get all registered test names."""
        return sorted(cls._registry.keys())


def visual_test(name: str, description: str = ""):
    """
    Decorator to register a visual test.
    
    Usage:
        @visual_test("test_name", "Test description")
        class MyTest(VisualTest):
            def setup(self):
                ...
            def run(self, game_state):
                ...
    """
    def decorator(test_class):
        if not issubclass(test_class, VisualTest):
            raise TypeError(f"{test_class.__name__} must inherit from VisualTest")
        
        # Create instance and register
        instance = test_class(name, description)
        VisualTest.register(instance)
        
        return test_class
    return decorator
