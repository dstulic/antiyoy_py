"""Base classes for visual integration tests."""

import inspect
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from core.game_state import GameState


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
