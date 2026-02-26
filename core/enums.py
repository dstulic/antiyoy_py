"""Enum definitions for game types."""

from enum import Enum


class HColor(Enum):
    """Hex colors representing player factions."""

    GRAY = "gray"
    YELLOW = "yellow"
    GREEN = "green"
    AQUA = "aqua"
    CYAN = "cyan"
    BLUE = "blue"
    PURPLE = "purple"
    RED = "red"
    BROWN = "brown"
    MINT = "mint"
    LAVENDER = "lavender"
    BRASS = "brass"
    ICE = "ice"
    ROSE = "rose"
    ALGAE = "algae"
    ORCHID = "orchid"
    WHISKEY = "whiskey"

    def __str__(self) -> str:
        """Return string representation."""
        return self.value


class PieceType(Enum):
    """Types of pieces that can be placed on hexes."""

    PEASANT = "peasant"
    SPEARMAN = "spearman"
    BARON = "baron"
    KNIGHT = "knight"
    PALM = "palm"
    PINE = "pine"
    TOWER = "tower"
    CITY = "city"
    FARM = "farm"
    STRONG_TOWER = "strong_tower"
    GRAVE = "grave"

    def __str__(self) -> str:
        """Return string representation."""
        return self.value


class EntityType(Enum):
    """Types of player entities."""

    HUMAN = "human"
    NET_ENTITY = "net_entity"
    AI_BALANCER = "ai_balancer"
    SPECTATOR = "spectator"
    DEAD_BY_DEFAULT = "dead_by_default"
    AI_EASY = "ai_easy"
    AI_AVERAGE = "ai_average"
    AI_HARD = "ai_hard"
    AI_EXPERT = "ai_expert"

    def __str__(self) -> str:
        """Return string representation."""
        return self.value

    def is_ai(self) -> bool:
        """Check if entity type is an AI."""
        return self in (
            EntityType.AI_BALANCER,
            EntityType.AI_EASY,
            EntityType.AI_AVERAGE,
            EntityType.AI_HARD,
            EntityType.AI_EXPERT,
        )


class EventType(Enum):
    """Types of game events."""

    PIECE_ADD = "piece_add"
    UNIT_MOVE = "unit_move"
    PIECE_DELETE = "piece_delete"
    TURN_END = "turn_end"
    TURN_BEGIN = "turn_begin"
    LAP_BEGIN = "lap_begin"
    PLAYER_TURN_STATS = "player_turn_stats"
    HEX_CHANGE_COLOR = "hex_change_color"
    SET_MONEY = "set_money"
    PIECE_BUILD = "piece_build"
    GRAPH_CREATED = "graph_created"
    MATCH_STARTED = "match_started"
    MERGE = "merge"
    MERGE_ON_BUILD = "merge_on_build"
    SET_RELATION_SOFTLY = "set_relation_softly"
    SEND_LETTER = "send_letter"
    INDICATE_UNDO_LETTER = "indicate_undo_letter"
    DECLINE_LETTER = "decline_letter"
    APPLY_LETTER = "apply_letter"
    GIVE_MONEY = "give_money"
    SUBTRACT_MONEY = "subtract_money"
    SET_READY = "set_ready"

    def __str__(self) -> str:
        """Return string representation."""
        return self.value


class RelationType(Enum):
    """Diplomatic relation types between players."""

    WAR = "war"
    NEUTRAL = "neutral"
    FRIEND = "friend"
    ALLIANCE = "alliance"

    def __str__(self) -> str:
        """Return string representation."""
        return self.value


class RulesType(Enum):
    """Game ruleset types."""

    DEF = "def"
    CLASSIC = "classic"
    DUEL = "duel"
    EXPERIMENTAL = "experimental"

    def __str__(self) -> str:
        """Return string representation."""
        return self.value


class Difficulty(Enum):
    """Campaign difficulty levels."""

    TUTORIAL = "tutorial"
    EASY = "easy"
    AVERAGE = "average"
    HARD = "hard"
    EXPERT = "expert"
    BALANCER = "balancer"

    def __str__(self) -> str:
        """Return string representation."""
        return self.value
