"""Unit tests for core/player_entity.py."""

import pytest
from core.player_entity import (
    Relation,
    PlayerEntity,
    EntitiesManager,
    TurnsManager,
)
from core.enums import EntityType, HColor, RelationType, EventType
from core.events import EventTurnEnd


class MockCoreModel:
    """Mock core model for testing."""

    def __init__(self):
        self.events_manager = None
        self.entities_manager = None
        self.turns_manager = None
        self.provinces_manager = None


class MockEventsManager:
    """Mock events manager."""

    def __init__(self):
        self.listeners = []

    def add_listener(self, listener):
        """Add listener."""
        if listener not in self.listeners:
            self.listeners.append(listener)


class MockProvincesManager:
    """Mock provinces manager."""

    def __init__(self):
        self.provinces_by_color = {}

    def get_province_by_color(self, color: HColor):
        """Get province by color."""
        return self.provinces_by_color.get(color)


class TestRelation:
    """Tests for Relation class."""

    def test_relation_initialization(self):
        """Test relation initialization."""
        relation = Relation()
        assert relation.type is None
        assert relation.entity1 is None
        assert relation.entity2 is None
        assert relation.lock == 0

    def test_reset(self):
        """Test relation reset."""
        relation = Relation()
        relation.type = RelationType.WAR
        relation.lock = 5
        relation.reset()
        assert relation.type is None
        assert relation.lock == 0

    def test_is_locked(self):
        """Test is_locked() method."""
        relation = Relation()
        assert relation.is_locked() is False
        relation.lock = 1
        assert relation.is_locked() is True

    def test_contains(self):
        """Test contains() method."""
        relation = Relation()
        entity1 = PlayerEntity(None, EntityType.HUMAN, HColor.RED)
        entity2 = PlayerEntity(None, EntityType.AI_BALANCER, HColor.BLUE)
        relation.set_entity1(entity1)
        relation.set_entity2(entity2)
        assert relation.contains(entity1) is True
        assert relation.contains(entity2) is True
        entity3 = PlayerEntity(None, EntityType.HUMAN, HColor.GREEN)
        assert relation.contains(entity3) is False

    def test_get_opposite(self):
        """Test get_opposite() method."""
        relation = Relation()
        entity1 = PlayerEntity(None, EntityType.HUMAN, HColor.RED)
        entity2 = PlayerEntity(None, EntityType.AI_BALANCER, HColor.BLUE)
        relation.set_entity1(entity1)
        relation.set_entity2(entity2)
        assert relation.get_opposite(entity1) == entity2
        assert relation.get_opposite(entity2) == entity1
        entity3 = PlayerEntity(None, EntityType.HUMAN, HColor.GREEN)
        assert relation.get_opposite(entity3) is None


class TestPlayerEntity:
    """Tests for PlayerEntity class."""

    def test_entity_initialization(self):
        """Test entity initialization."""
        manager = EntitiesManager(None)
        entity = PlayerEntity(manager, EntityType.HUMAN, HColor.RED)
        assert entity.type == EntityType.HUMAN
        assert entity.color == HColor.RED
        assert entity.name == "-"
        assert len(entity.relations) == 0

    def test_is_human(self):
        """Test is_human() method."""
        manager = EntitiesManager(None)
        entity = PlayerEntity(manager, EntityType.HUMAN, HColor.RED)
        assert entity.is_human() is True
        entity = PlayerEntity(manager, EntityType.AI_BALANCER, HColor.BLUE)
        assert entity.is_human() is False

    def test_is_artificial_intelligence(self):
        """Test is_artificial_intelligence() method."""
        manager = EntitiesManager(None)
        entity = PlayerEntity(manager, EntityType.AI_BALANCER, HColor.RED)
        assert entity.is_artificial_intelligence() is True
        entity = PlayerEntity(manager, EntityType.HUMAN, HColor.BLUE)
        assert entity.is_artificial_intelligence() is False

    def test_encode(self):
        """Test encode() method."""
        manager = EntitiesManager(None)
        entity = PlayerEntity(manager, EntityType.HUMAN, HColor.RED)
        entity.set_name("TestName")
        encoded = entity.encode()
        assert "human" in encoded
        assert "red" in encoded
        assert "TestName" in encoded


class TestTurnsManager:
    """Tests for TurnsManager class."""

    def test_turns_manager_initialization(self):
        """Test turns manager initialization."""
        core_model = MockCoreModel()
        core_model.events_manager = MockEventsManager()
        manager = TurnsManager(core_model)
        assert manager.turn_index == 0
        assert manager.lap == 0

    def test_reset(self):
        """Test reset() method."""
        core_model = MockCoreModel()
        manager = TurnsManager(core_model)
        manager.turn_index = 5
        manager.lap = 2
        manager.reset()
        assert manager.turn_index == 0
        assert manager.lap == 0

    def test_do_switch_turn_index(self):
        """Test do_switch_turn_index() method."""
        core_model = MockCoreModel()
        core_model.events_manager = MockEventsManager()
        manager = TurnsManager(core_model)
        entities_manager = EntitiesManager(core_model)
        entity1 = PlayerEntity(entities_manager, EntityType.HUMAN, HColor.RED)
        entity2 = PlayerEntity(entities_manager, EntityType.AI_BALANCER, HColor.BLUE)
        entities_manager.initialize([entity1, entity2])
        core_model.entities_manager = entities_manager
        manager.core_model = core_model
        initial_index = manager.turn_index
        manager.do_switch_turn_index()
        assert manager.turn_index == initial_index + 1
        manager.do_switch_turn_index()  # Should wrap to 0 and increment lap
        assert manager.turn_index == 0
        assert manager.lap == 1

    def test_encode_decode(self):
        """Test encode and decode."""
        core_model = MockCoreModel()
        manager = TurnsManager(core_model)
        manager.turn_index = 2
        manager.lap = 5
        encoded = manager.encode()
        new_manager = TurnsManager(None)
        new_manager.decode(encoded)
        assert new_manager.turn_index == 2
        assert new_manager.lap == 5


class TestEntitiesManager:
    """Tests for EntitiesManager class."""

    def test_entities_manager_initialization(self):
        """Test entities manager initialization."""
        core_model = MockCoreModel()
        core_model.events_manager = MockEventsManager()
        manager = EntitiesManager(core_model)
        assert manager.entities is None

    def test_initialize(self):
        """Test initialize() method."""
        core_model = MockCoreModel()
        manager = EntitiesManager(core_model)
        entity1 = PlayerEntity(manager, EntityType.HUMAN, HColor.RED)
        entity2 = PlayerEntity(manager, EntityType.AI_BALANCER, HColor.BLUE)
        manager.initialize([entity1, entity2])
        assert len(manager.entities) == 2
        assert entity1 in manager.entities
        assert entity2 in manager.entities

    def test_init_relations(self):
        """Test relation initialization."""
        core_model = MockCoreModel()
        manager = EntitiesManager(core_model)
        entity1 = PlayerEntity(manager, EntityType.HUMAN, HColor.RED)
        entity2 = PlayerEntity(manager, EntityType.AI_BALANCER, HColor.BLUE)
        manager.initialize([entity1, entity2])
        assert len(entity1.relations) == 1
        assert len(entity2.relations) == 1
        relation = entity1.relations[0]
        assert relation.contains(entity1) is True
        assert relation.contains(entity2) is True
        assert relation.type == RelationType.NEUTRAL

    def test_get_current_entity(self):
        """Test get_current_entity() method."""
        core_model = MockCoreModel()
        core_model.events_manager = MockEventsManager()
        manager = EntitiesManager(core_model)
        turns_manager = TurnsManager(core_model)
        core_model.turns_manager = turns_manager
        entity1 = PlayerEntity(manager, EntityType.HUMAN, HColor.RED)
        entity2 = PlayerEntity(manager, EntityType.AI_BALANCER, HColor.BLUE)
        manager.initialize([entity1, entity2])
        core_model.entities_manager = manager
        current = manager.get_current_entity()
        assert current == entity1
        turns_manager.do_switch_turn_index()
        current = manager.get_current_entity()
        assert current == entity2

    def test_get_entity(self):
        """Test get_entity() method."""
        core_model = MockCoreModel()
        manager = EntitiesManager(core_model)
        entity1 = PlayerEntity(manager, EntityType.HUMAN, HColor.RED)
        entity2 = PlayerEntity(manager, EntityType.AI_BALANCER, HColor.BLUE)
        manager.initialize([entity1, entity2])
        assert manager.get_entity(HColor.RED) == entity1
        assert manager.get_entity(HColor.BLUE) == entity2
        assert manager.get_entity(HColor.GREEN) is None

    def test_contains(self):
        """Test contains() method."""
        core_model = MockCoreModel()
        manager = EntitiesManager(core_model)
        entity1 = PlayerEntity(manager, EntityType.HUMAN, HColor.RED)
        entity2 = PlayerEntity(manager, EntityType.AI_BALANCER, HColor.BLUE)
        manager.initialize([entity1, entity2])
        assert manager.contains(EntityType.HUMAN) is True
        assert manager.contains(EntityType.AI_BALANCER) is True
        assert manager.contains(EntityType.AI_RANDOM) is False

    def test_count(self):
        """Test count() method."""
        core_model = MockCoreModel()
        manager = EntitiesManager(core_model)
        entity1 = PlayerEntity(manager, EntityType.HUMAN, HColor.RED)
        entity2 = PlayerEntity(manager, EntityType.AI_BALANCER, HColor.BLUE)
        entity3 = PlayerEntity(manager, EntityType.AI_BALANCER, HColor.GREEN)
        manager.initialize([entity1, entity2, entity3])
        assert manager.count(EntityType.HUMAN) == 1
        assert manager.count(EntityType.AI_BALANCER) == 2
        assert manager.count(EntityType.AI_RANDOM) == 0

    def test_encode_decode(self):
        """Test encode and decode."""
        core_model = MockCoreModel()
        manager = EntitiesManager(core_model)
        entity1 = PlayerEntity(manager, EntityType.HUMAN, HColor.RED)
        entity1.set_name("Player1")
        entity2 = PlayerEntity(manager, EntityType.AI_BALANCER, HColor.BLUE)
        entity2.set_name("AI1")
        manager.initialize([entity1, entity2])
        encoded = manager.encode()
        new_manager = EntitiesManager(None)
        new_manager.decode(encoded)
        assert len(new_manager.entities) == 2
        assert new_manager.get_entity(HColor.RED) is not None
        assert new_manager.get_entity(HColor.BLUE) is not None

    def test_is_in_ai_only_mode(self):
        """Test is_in_ai_only_mode() method."""
        core_model = MockCoreModel()
        manager = EntitiesManager(core_model)
        entity1 = PlayerEntity(manager, EntityType.AI_BALANCER, HColor.RED)
        entity2 = PlayerEntity(manager, EntityType.AI_RANDOM, HColor.BLUE)
        manager.initialize([entity1, entity2])
        assert manager.is_in_ai_only_mode() is True
        entity3 = PlayerEntity(manager, EntityType.HUMAN, HColor.GREEN)
        manager.initialize([entity1, entity2, entity3])
        assert manager.is_in_ai_only_mode() is False
