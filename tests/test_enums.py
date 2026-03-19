"""Unit tests for core/enums.py."""

import pytest
from core.enums import (
    HColor,
    PieceType,
    EntityType,
    EventType,
    RelationType,
    RulesType,
    Difficulty,
)


class TestHColor:
    """Tests for HColor enum."""

    def test_all_colors_exist(self):
        """Test that all expected colors are defined."""
        expected_colors = {
            "gray",
            "yellow",
            "green",
            "aqua",
            "cyan",
            "blue",
            "purple",
            "red",
            "brown",
            "mint",
            "lavender",
            "brass",
            "ice",
            "rose",
            "algae",
            "orchid",
            "whiskey",
        }
        actual_colors = {color.value for color in HColor}
        assert actual_colors == expected_colors

    def test_color_string_representation(self):
        """Test string representation of colors."""
        assert str(HColor.RED) == "red"
        assert str(HColor.GRAY) == "gray"
        assert str(HColor.LAVENDER) == "lavender"

    def test_color_equality(self):
        """Test color equality."""
        assert HColor.RED == HColor.RED
        assert HColor.RED != HColor.BLUE


class TestPieceType:
    """Tests for PieceType enum."""

    def test_all_piece_types_exist(self):
        """Test that all expected piece types are defined."""
        expected_types = {
            "peasant",
            "spearman",
            "baron",
            "knight",
            "palm",
            "pine",
            "tower",
            "city",
            "farm",
            "strong_tower",
            "grave",
        }
        actual_types = {piece_type.value for piece_type in PieceType}
        assert actual_types == expected_types

    def test_piece_type_string_representation(self):
        """Test string representation of piece types."""
        assert str(PieceType.PEASANT) == "peasant"
        assert str(PieceType.CITY) == "city"
        assert str(PieceType.STRONG_TOWER) == "strong_tower"


class TestEntityType:
    """Tests for EntityType enum."""

    def test_all_entity_types_exist(self):
        """Test that all expected entity types are defined."""
        expected_types = {
            "human",
            "net_entity",
            "ai_balancer",
            "spectator",
            "dead_by_default",
            "ai_easy",
            "ai_average",
            "ai_hard",
            "ai_expert",
        }
        actual_types = {entity_type.value for entity_type in EntityType}
        assert actual_types == expected_types

    def test_entity_type_string_representation(self):
        """Test string representation of entity types."""
        assert str(EntityType.HUMAN) == "human"
        assert str(EntityType.AI_BALANCER) == "ai_balancer"

    def test_is_ai_method(self):
        """Test is_ai() method."""
        assert EntityType.AI_BALANCER.is_ai() is True
        assert EntityType.AI_EASY.is_ai() is True
        assert EntityType.AI_AVERAGE.is_ai() is True
        assert EntityType.AI_HARD.is_ai() is True
        assert EntityType.AI_EXPERT.is_ai() is True
        assert EntityType.HUMAN.is_ai() is False
        assert EntityType.NET_ENTITY.is_ai() is False
        assert EntityType.SPECTATOR.is_ai() is False


class TestEventType:
    """Tests for EventType enum."""

    def test_all_event_types_exist(self):
        """Test that all expected event types are defined."""
        expected_types = {
            "piece_add",
            "unit_move",
            "piece_delete",
            "turn_end",
            "turn_begin",
            "lap_begin",
            "player_turn_stats",
            "hex_change_color",
            "set_money",
            "piece_build",
            "graph_created",
            "match_started",
            "merge",
            "merge_on_build",
            "set_relation_softly",
            "send_letter",
            "indicate_undo_letter",
            "decline_letter",
            "apply_letter",
            "give_money",
            "subtract_money",
            "set_ready",
        }
        actual_types = {event_type.value for event_type in EventType}
        assert actual_types == expected_types

    def test_event_type_string_representation(self):
        """Test string representation of event types."""
        assert str(EventType.UNIT_MOVE) == "unit_move"
        assert str(EventType.TURN_END) == "turn_end"


class TestRelationType:
    """Tests for RelationType enum."""

    def test_all_relation_types_exist(self):
        """Test that all expected relation types are defined."""
        expected_types = {"war", "neutral", "friend", "alliance"}
        actual_types = {relation_type.value for relation_type in RelationType}
        assert actual_types == expected_types

    def test_relation_type_string_representation(self):
        """Test string representation of relation types."""
        assert str(RelationType.WAR) == "war"
        assert str(RelationType.ALLIANCE) == "alliance"


class TestRulesType:
    """Tests for RulesType enum."""

    def test_all_rules_types_exist(self):
        """Test that all expected rules types are defined."""
        expected_types = {"def", "classic", "duel", "experimental"}
        actual_types = {rules_type.value for rules_type in RulesType}
        assert actual_types == expected_types

    def test_rules_type_string_representation(self):
        """Test string representation of rules types."""
        assert str(RulesType.DEF) == "def"
        assert str(RulesType.CLASSIC) == "classic"


class TestDifficulty:
    """Tests for Difficulty enum."""

    def test_all_difficulties_exist(self):
        """Test that all expected difficulties are defined."""
        expected_difficulties = {
            "tutorial",
            "easy",
            "average",
            "hard",
            "expert",
            "balancer",
        }
        actual_difficulties = {difficulty.value for difficulty in Difficulty}
        assert actual_difficulties == expected_difficulties

    def test_difficulty_string_representation(self):
        """Test string representation of difficulties."""
        assert str(Difficulty.EASY) == "easy"
        assert str(Difficulty.EXPERT) == "expert"
