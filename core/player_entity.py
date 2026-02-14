"""Player entity and entities management."""

from typing import Optional, List, TYPE_CHECKING
from core.enums import EntityType, HColor, RelationType

if TYPE_CHECKING:
    from core.enums import Difficulty
from core.events import IEventListener, AbstractEvent
from core.enums import EventType


class Relation:
    """Represents a diplomatic relation between two player entities."""

    def __init__(self):
        """Initialize relation."""
        self.type: Optional[RelationType] = None
        self.entity1: Optional["PlayerEntity"] = None
        self.entity2: Optional["PlayerEntity"] = None
        self.lock: int = 0

    def reset(self) -> None:
        """Reset relation to initial state."""
        self.type = None
        self.entity1 = None
        self.entity2 = None
        self.lock = 0

    def is_locked(self) -> bool:
        """Check if relation is locked."""
        return self.lock > 0

    def contains(self, player_entity: "PlayerEntity") -> bool:
        """Check if relation contains a player entity."""
        return player_entity == self.entity1 or player_entity == self.entity2

    def get_opposite(self, player_entity: "PlayerEntity") -> Optional["PlayerEntity"]:
        """Get the opposite entity in this relation."""
        if player_entity == self.entity1:
            return self.entity2
        if player_entity == self.entity2:
            return self.entity1
        return None

    def set_type(self, relation_type: RelationType) -> None:
        """Set relation type."""
        self.type = relation_type

    def set_entity1(self, entity: "PlayerEntity") -> None:
        """Set first entity."""
        self.entity1 = entity

    def set_entity2(self, entity: "PlayerEntity") -> None:
        """Set second entity."""
        self.entity2 = entity

    def set_lock(self, lock: int) -> None:
        """Set lock value."""
        self.lock = lock

    def encode(self) -> str:
        """Encode relation to string."""
        if self.type and self.entity1 and self.entity2:
            return f"{self.type.value} {self.entity1.color.value} {self.entity2.color.value} {self.lock}"
        return ""

    def __str__(self) -> str:
        """Return string representation."""
        if self.lock == 0:
            return f"[{self.type.value.capitalize() if self.type else 'None'}]"
        return f"[{self.type.value.capitalize() if self.type else 'None'}, {self.lock}]"


class PlayerEntity:
    """Represents a player entity in the game."""

    def __init__(
        self,
        entities_manager: "EntitiesManager",
        entity_type: EntityType,
        color: HColor,
    ):
        """Initialize player entity."""
        self.entities_manager = entities_manager
        self.type = entity_type
        self.color = color
        self.name = "-"
        self.relations: List[Relation] = []
        # Per-player AI difficulty (only used when type is AI). None = use game default.
        self.ai_difficulty: Optional["Difficulty"] = None

    def get_relation(self, other_entity: "PlayerEntity") -> Optional[Relation]:
        """Get relation with another entity."""
        if other_entity == self:
            # Should not happen
            return None
        for relation in self.relations:
            if relation.contains(other_entity):
                return relation
        return None

    def encode(self) -> str:
        """Encode entity to string. Optional 4th part is ai_difficulty value for AI entities."""
        base = f"{self.type.value}>{self.color.value}>{self.name}"
        if self.is_artificial_intelligence() and self.ai_difficulty is not None:
            base += f">{self.ai_difficulty.value}"
        return base

    def is_human(self) -> bool:
        """Check if entity is human."""
        return self.type == EntityType.HUMAN

    def is_artificial_intelligence(self) -> bool:
        """Check if entity is AI."""
        return self.type.is_ai()

    def set_name(self, name: str) -> None:
        """Set entity name."""
        self.name = name

    def get_ai_difficulty(self) -> Optional["Difficulty"]:
        """Get this entity's AI difficulty (None = use game default). Only relevant for AI entities."""
        return self.ai_difficulty

    def set_ai_difficulty(self, difficulty: Optional["Difficulty"]) -> None:
        """Set this entity's AI difficulty. Only relevant for AI entities."""
        self.ai_difficulty = difficulty

    def __str__(self) -> str:
        """Return string representation."""
        return f"[PlayerEntity: {self.encode()}]"


class TurnsManager(IEventListener):
    """Manages turn order and progression."""

    def __init__(self, core_model):
        """Initialize turns manager."""
        self.core_model = core_model
        if core_model and core_model.events_manager:
            core_model.events_manager.add_listener(self)
        self.turn_index: int = 0
        self.lap: int = 0

    def reset(self) -> None:
        """Reset turn manager."""
        self.turn_index = 0
        self.lap = 0

    def set_by(self, source: "TurnsManager") -> None:
        """Copy from another turns manager."""
        self.turn_index = source.turn_index
        self.lap = source.lap

    def do_switch_turn_index(self) -> None:
        """Switch to next turn, skipping dead players."""
        if not self.core_model or not self.core_model.entities_manager:
            # Fallback to simple switching if no entities manager
            if self.is_turn_index_in_end_of_lap():
                self.turn_index = 0
                self.lap += 1
            else:
                self.turn_index += 1
            return
        
        max_attempts = 100  # Prevent infinite loop
        attempts = 0
        
        while attempts < max_attempts:
            if self.is_turn_index_in_end_of_lap():
                self.turn_index = 0
                self.lap += 1
            else:
                self.turn_index += 1
            
            # Check if current player is dead (has no provinces)
            current_entity = self.core_model.entities_manager.get_current_entity()
            if current_entity is None:
                break  # No entities, can't continue
            
            # Skip dead players (players with no provinces)
            if self.core_model.game_end_manager:
                if not self.core_model.game_end_manager.is_player_dead(current_entity.color):
                    # Current player is alive, stop switching
                    break
            else:
                # No game end manager, just stop
                break
            
            attempts += 1

    def is_turn_index_in_end_of_lap(self) -> bool:
        """Check if turn index is at end of lap."""
        if (
            self.core_model
            and self.core_model.entities_manager
            and self.core_model.entities_manager.entities
        ):
            return self.turn_index == len(self.core_model.entities_manager.entities) - 1
        return False

    def on_event_validated(self, event: AbstractEvent) -> None:
        """Handle event validated."""
        pass

    def on_event_applied(self, event: AbstractEvent) -> None:
        """Handle event applied."""
        if event.get_type() == EventType.TURN_END:
            self.on_turn_end_event_applied()

    def on_turn_end_event_applied(self) -> None:
        """Handle turn end event."""
        pass

    def get_listen_priority(self) -> int:
        """Get listener priority."""
        return 8

    def encode(self) -> str:
        """Encode turns manager to string."""
        return f"{self.turn_index} {self.lap}"

    def decode(self, source: str) -> None:
        """Decode turns manager from string."""
        parts = source.split(" ")
        if len(parts) >= 2:
            self.turn_index = int(parts[0])
            self.lap = int(parts[1])


class EntitiesManager(IEventListener):
    """Manages all player entities."""

    def __init__(self, core_model):
        """Initialize entities manager."""
        self.core_model = core_model
        if core_model and core_model.events_manager:
            core_model.events_manager.add_listener(self)
        self.entities: Optional[List[PlayerEntity]] = None
        self._ai_only_mode: bool = False
        self._name_generator = SimpleNameGenerator()

    def initialize(self, entities: List[PlayerEntity]) -> None:
        """Initialize with list of entities."""
        self.entities = entities.copy()
        self._update_ai_only_mode()
        self._on_entities_initialized()

    def initialize_from_string(self, source: str) -> None:
        """Initialize from encoded string."""
        entities_list: List[PlayerEntity] = []
        for token in source.split(","):
            if not token.strip():
                continue
            parts = token.split(">")
            if len(parts) < 3:
                continue
            try:
                entity_type = EntityType(parts[0])
                color = HColor(parts[1])
                name = parts[2]
                entity = PlayerEntity(self, entity_type, color)
                entity.set_name(name)
                if len(parts) >= 4 and entity_type.is_ai():
                    from core.enums import Difficulty
                    try:
                        entity.set_ai_difficulty(Difficulty(parts[3]))
                    except (ValueError, KeyError):
                        pass
                entities_list.append(entity)
            except (ValueError, KeyError):
                continue
        self.initialize(entities_list)

    def _on_entities_initialized(self) -> None:
        """Called when entities are initialized."""
        if self.core_model:
            self._init_relations()

    def _init_relations(self) -> None:
        """Initialize relations between entities."""
        if not self.entities:
            return
        # Clear existing relations
        for entity in self.entities:
            entity.relations.clear()
        # Create relations between all pairs
        for i in range(len(self.entities)):
            entity1 = self.entities[i]
            for j in range(i + 1, len(self.entities)):
                entity2 = self.entities[j]
                relation = Relation()
                relation.set_entity1(entity1)
                relation.set_entity2(entity2)
                relation.set_type(RelationType.NEUTRAL)
                entity1.relations.append(relation)
                entity2.relations.append(relation)

    def contains(self, entity_type: EntityType) -> bool:
        """Check if manager contains entity type."""
        if not self.entities:
            return False
        for entity in self.entities:
            if entity.type == entity_type:
                return True
        return False

    def count(self, entity_type: EntityType) -> int:
        """Count entities of a specific type."""
        if not self.entities:
            return 0
        count = 0
        for entity in self.entities:
            if entity.type == entity_type:
                count += 1
        return count

    def get_current_entity(self) -> Optional[PlayerEntity]:
        """Get current entity based on turn index."""
        if (
            not self.entities
            or not self.core_model
            or not self.core_model.turns_manager
        ):
            return None
        turn_index = self.core_model.turns_manager.turn_index
        if 0 <= turn_index < len(self.entities):
            return self.entities[turn_index]
        return None

    def get_entity(self, color: HColor) -> Optional[PlayerEntity]:
        """Get entity by color."""
        if not self.entities:
            return None
        for entity in self.entities:
            if entity.color == color:
                return entity
        return None

    def get_current_color(self) -> Optional[HColor]:
        """Get current color."""
        current = self.get_current_entity()
        if current:
            return current.color
        return None

    def is_human_turn_currently(self) -> bool:
        """Check if it's currently a human turn."""
        current_entity = self.get_current_entity()
        if not current_entity:
            return False
        if not current_entity.is_human():
            return False
        # Check if entity has provinces (not dead)
        if (
            self.core_model
            and self.core_model.provinces_manager
            and self.core_model.provinces_manager.get_province_by_color(current_entity.color)
        ):
            # Also check if player is not marked as dead
            if self.core_model.game_end_manager:
                if self.core_model.game_end_manager.is_player_dead(current_entity.color):
                    return False
            return True
        return False

    def is_in_ai_only_mode(self) -> bool:
        """Check if in AI-only mode."""
        return self._ai_only_mode

    def _update_ai_only_mode(self) -> None:
        """Update AI-only mode flag."""
        if not self.entities or len(self.entities) == 0:
            self._ai_only_mode = False
            return
        self._ai_only_mode = True
        for entity in self.entities:
            if not entity.is_artificial_intelligence():
                self._ai_only_mode = False
                break

    def on_event_validated(self, event: AbstractEvent) -> None:
        """Handle event validated."""
        pass

    def on_event_applied(self, event: AbstractEvent) -> None:
        """Handle event applied."""
        if event.get_type() == EventType.TURN_END:
            self._on_turn_end_event_applied()

    def _on_turn_end_event_applied(self) -> None:
        """Handle turn end event."""
        pass

    def get_listen_priority(self) -> int:
        """Get listener priority."""
        return 8

    def encode(self) -> str:
        """Encode entities manager to string."""
        if not self.entities:
            return "-"
        encoded_parts = [entity.encode() for entity in self.entities]
        return ",".join(encoded_parts)

    def decode(self, source: str, dead_by_default: bool = False) -> None:
        """Decode entities manager from string."""
        entities_list: List[PlayerEntity] = []
        seen_colors = set()
        for token in source.split(","):
            if not token.strip():
                continue
            parts = token.split(">")
            if len(parts) < 3:
                continue
            try:
                entity_type = EntityType(parts[0])
                if dead_by_default:
                    entity_type = EntityType.DEAD_BY_DEFAULT
                color = HColor(parts[1])
                if color == HColor.GRAY:
                    continue  # Entity can't be neutral
                if color in seen_colors:
                    continue  # Duplicate color
                seen_colors.add(color)
                name = parts[2]
                entity = PlayerEntity(self, entity_type, color)
                entity.set_name(name)
                if len(parts) >= 4 and entity_type.is_ai():
                    from core.enums import Difficulty
                    try:
                        entity.set_ai_difficulty(Difficulty(parts[3]))
                    except (ValueError, KeyError):
                        pass
                entities_list.append(entity)
            except (ValueError, KeyError):
                continue
        self.initialize(entities_list)


class SimpleNameGenerator:
    """Simple name generator for entities."""

    def __init__(self):
        """Initialize name generator."""
        self.names = [
            "Resse",
            "Naclo",
            "Esyemo",
            "Kakamo",
            "Amako",
            "Kamak",
            "Akako",
            "Kakko",
            "Kama",
            "Kakako",
            "TheArmor",
            "DigitalBlood",
            "GrizzlyBreaker",
            "AcidSnake",
            "BlisteredOutlaws",
            "InvaderPenguin",
            "WarioRaptor",
            "SuperboyFallout",
            "FastClawDraw",
            "SystemSnap",
            "RedReaperSlice",
            "CoolCobra",
            "CutthroatRattler",
            "BruisedKnuckles",
            "HurricaneMachine",
            "WarlockAdmiral",
            "Damin",
            "Cytos",
            "Inkronos",
            "Grumblemoor",
        ]
        self.index = 0

    def generate(self) -> str:
        """Generate a name."""
        name = self.names[self.index % len(self.names)]
        self.index += 1
        return name
