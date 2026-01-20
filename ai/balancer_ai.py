"""AI Balancer implementation - strategic AI player."""

from typing import List, Optional
from ai.abstract_ai import AbstractAI
from core.game_state import GameState
from core.enums import Difficulty, HColor, PieceType
from core.core_utils import get_strength, get_merge_result, is_unit


class DiplomaticAI:
    """Placeholder for diplomatic AI (diplomacy not implemented)."""
    
    def __init__(self, game_state: GameState):
        """Initialize diplomatic AI."""
        self.game_state = game_state
    
    def apply(self) -> None:
        """Apply diplomatic actions."""
        pass  # Diplomacy not implemented


class AiBalancerDefaultV1(AbstractAI):
    """AI Balancer Default V1 - strategic AI implementation."""
    
    MAX_FARM_COST = 80
    
    def __init__(self, game_state: GameState):
        """Initialize AI balancer."""
        super().__init__(game_state)
        self.result: List = []
        self.hexes_in_perimeter: List = []
        self.nearby_provinces: List = []
        self.units_ready_to_move: List = []
    
    def get_version_code(self) -> int:
        """Get version code."""
        return 1
    
    def get_diplomatic_ai(self):
        """Get diplomatic AI."""
        return DiplomaticAI(self.game_state)
    
    def apply(self) -> None:
        """Apply AI decision making."""
        # Update quick stats (hex quantities) before making decisions
        if hasattr(self.game_state, 'quick_stats_manager') and self.game_state.quick_stats_manager:
            self.game_state.quick_stats_manager.update()
        
        # Main AI logic: move units, spend money, merge units, move AFK units
        self.move_units()
        self.spend_money_and_merge_units()
        self.check_to_kill_redundant_units()
        self.move_afk_units()
    
    def move_units(self) -> None:
        """Move units to attack or clean trees."""
        self.update_units_ready_to_move()
        for hex in self.units_ready_to_move:
            if not self.is_ready(hex):
                continue
            
            self.get_move_zone_manager().update_for_unit(hex)
            move_zone = self.get_move_zone_manager().hexes
            self.exclude_friendly_buildings_from_move_zone(move_zone)
            self.exclude_friendly_units_from_move_zone(move_zone)
            
            if len(move_zone) == 0:
                continue
            
            province = hex.get_province()
            if not province:
                continue
            
            self.decide_about_unit(hex, move_zone, province)
    
    def decide_about_unit(self, hex, move_zone: List, province) -> None:
        """Decide what to do with a unit."""
        if not self.is_ready(hex):
            return
        
        # Cleaning palms has highest priority (for weak units)
        strength = self.get_strength(hex)
        if strength <= 2 and self.check_to_clean_some_palms(hex, move_zone):
            return
        
        # Clean trees
        if self.check_to_clean_some_trees(hex, move_zone):
            return
        
        # Find attackable hexes
        attackable_hexes = self.find_attackable_hexes(hex.color, move_zone)
        if len(attackable_hexes) > 0:
            # Attack something
            self.try_to_attack_something(hex, attackable_hexes)
        else:
            # Nothing to attack - push unit to better defense if adjacent to enemy
            if self.is_adjacent_to_enemy(hex):
                self.push_unit_to_better_defense(hex)
    
    def check_to_clean_some_palms(self, hex, move_zone: List) -> bool:
        """Check if unit should clean palm trees."""
        if self.is_difficulty_less_than(Difficulty.HARD):
            return False
        for target_hex in move_zone:
            if target_hex.piece != PieceType.PALM:
                continue
            if target_hex.color != hex.color:
                continue
            self.command_unit_move(hex, target_hex)
            return True
        return False
    
    def check_to_clean_some_trees(self, hex, move_zone: List) -> bool:
        """Check if unit should clean trees."""
        if self.is_difficulty_less_than(Difficulty.EXPERT):
            return False
        for target_hex in move_zone:
            if target_hex.piece not in (PieceType.PINE, PieceType.PALM):
                continue
            if target_hex.color != hex.color:
                continue
            self.command_unit_move(hex, target_hex)
            return True
        return False
    
    def find_attackable_hexes(self, color: HColor, move_zone: List) -> List:
        """Find hexes that can be attacked."""
        result = []
        for hex in move_zone:
            if hex.color == color:
                continue
            result.append(hex)
        # Sort by defense (lower defense first) and owned hexes quantity
        result.sort(key=lambda h: (
            -self.number_of_adjacent_units(h),
            -self.get_owned_hexes_quantity(h.color) if h.color != HColor.GRAY else 0
        ))
        return result
    
    def number_of_adjacent_units(self, hex) -> int:
        """Count adjacent friendly units and towers."""
        count = 0
        hex_province = hex.get_province()
        for adj_hex in hex.adjacent_hexes:
            if adj_hex.color != hex.color:
                continue
            if hex_province and adj_hex.get_province() != hex_province:
                continue
            # Include units OR towers (matches Java: hasUnit() || hasTower())
            if adj_hex.piece:
                if is_unit(adj_hex.piece) or adj_hex.piece in (PieceType.TOWER, PieceType.STRONG_TOWER):
                    count += 1
        return count
    
    def get_owned_hexes_quantity(self, color: HColor) -> int:
        """Get number of hexes owned by color."""
        if color == HColor.GRAY:
            return 0
        if hasattr(self.game_state, 'quick_stats_manager') and self.game_state.quick_stats_manager:
            return self.game_state.quick_stats_manager.get_quantity(color)
        # Fallback: count manually if quick stats not available
        count = 0
        for hex in self.game_state.hexes:
            if hex.color == color:
                count += 1
        return count
    
    def try_to_attack_something(self, hex, attackable_hexes: List) -> None:
        """Try to attack an enemy hex."""
        if not self.can_unit_move_safely(hex):
            return
        
        strength = self.get_strength(hex)
        most_attackable_hex = self.find_most_attractive_hex(attackable_hexes, hex.color, strength)
        if most_attackable_hex:
            self.command_unit_move(hex, most_attackable_hex)
    
    def can_unit_move_safely(self, hex) -> bool:
        """Check if unit can move safely."""
        if self.is_difficulty_less_than(Difficulty.HARD):
            return True
        
        left_behind_count = 0
        hex_province = hex.get_province()
        for adj_hex in hex.adjacent_hexes:
            if adj_hex.color != hex.color:
                continue
            if hex_province and adj_hex.get_province() != hex_province:
                continue
            if not self.is_hex_defended_by_something_else(adj_hex, hex):
                if self.is_adjacent_to_enemy(adj_hex):
                    left_behind_count += 1
        return left_behind_count <= 3
    
    def is_hex_defended_by_something_else(self, hex, ignored_hex) -> bool:
        """Check if hex is defended by something other than ignored hex."""
        defense_without = self.get_defense_value(hex, ignored_hex)
        if defense_without == 0:
            return False
        defense_with = self.get_defense_value(hex)
        return defense_with - defense_without < 2
    
    def find_most_attractive_hex(self, attackable_hexes: List, color: HColor, strength: int):
        """Find most attractive hex to attack."""
        if self.is_difficulty_less_than(Difficulty.AVERAGE):
            if attackable_hexes:
                return self.random.choice(attackable_hexes)
            return None
        
        # For barons (strength 3) and knights (strength 4), use special logic
        if strength == 3 or strength == 4:
            hex = self.find_hex_attractive_to_baron(attackable_hexes, strength)
            if hex:
                return hex
        
        # Find hex with highest attack allure
        best_hex = None
        best_allure = -1
        for hex in attackable_hexes:
            allure = self.get_attack_allure(hex, color)
            if allure > best_allure:
                best_allure = allure
                best_hex = hex
        return best_hex
    
    def find_hex_attractive_to_baron(self, attackable_hexes: List, strength: int):
        """Find hex attractive to baron/knight (balancer difficulty only)."""
        if self.is_difficulty_less_than(Difficulty.BALANCER):
            return None
        # Prefer towers first
        for hex in attackable_hexes:
            if hex.piece == PieceType.TOWER:
                return hex
            if strength == 4 and hex.piece == PieceType.STRONG_TOWER:
                return hex
        # Then prefer hexes defended by towers
        for hex in attackable_hexes:
            if self.is_defended_by_tower(hex):
                return hex
        return None
    
    def get_attack_allure(self, hex, color: HColor) -> int:
        """Calculate attack allure for a hex."""
        allure = 0
        hex_province = hex.get_province()
        for adj_hex in hex.adjacent_hexes:
            if adj_hex.color != color:
                continue
            if hex_province and adj_hex.get_province() != hex_province:
                continue
            allure += 1
            if adj_hex.piece == PieceType.CITY:
                allure += 5
        if hex.piece == PieceType.FARM:
            allure *= 2
        return allure
    
    def push_unit_to_better_defense(self, hex) -> None:
        """Push unit to a hex with better defense."""
        if self.is_difficulty_less_than(Difficulty.EXPERT):
            return
        if not self.is_ready(hex):
            return
        
        strength = self.get_strength(hex)
        hex_province = hex.get_province()
        for adj_hex in hex.adjacent_hexes:
            if adj_hex.color != hex.color:
                continue
            if hex_province and adj_hex.get_province() != hex_province:
                continue
            if adj_hex.piece:
                continue
            defense_gain = self.predict_defense_gain_with_unit_move(hex, adj_hex)
            if defense_gain >= 3:
                self.command_unit_move(hex, adj_hex)
                break
    
    def predict_defense_gain_with_unit_move(self, current_hex, target_hex) -> int:
        """Predict defense gain from moving unit."""
        defense_gain = 0
        strength = self.get_strength(current_hex)
        
        defense_gain -= self.get_defense_value(target_hex)
        defense_gain += strength
        
        current_province = current_hex.get_province()
        for adj_hex in current_hex.adjacent_hexes:
            if adj_hex.color != current_hex.color:
                continue
            if current_province and adj_hex.get_province() != current_province:
                continue
            defense_gain -= self.get_defense_value(adj_hex)
            defense_gain += strength
        
        return defense_gain
    
    def update_units_ready_to_move(self) -> None:
        """Update list of units ready to move."""
        self.units_ready_to_move.clear()
        current_color = self.get_current_color()
        if not current_color:
            return
        
        for province in self.game_state.provinces_manager.provinces:
            if province.get_color() != current_color:
                continue
            for hex in province.get_hexes():
                if not hex.piece or not is_unit(hex.piece):
                    continue
                if not self.is_ready(hex):
                    continue
                self.units_ready_to_move.append(hex)
    
    def exclude_friendly_buildings_from_move_zone(self, move_zone: List) -> None:
        """Exclude friendly buildings from move zone."""
        self.temp_list.clear()
        current_color = self.get_current_color()
        for hex in move_zone:
            if hex.color != current_color:
                continue
            # Exclude static pieces (but not trees)
            if hex.has_static_piece() and not hex.has_tree():
                self.temp_list.append(hex)
        # Remove all items in temp_list from move_zone
        for hex in self.temp_list:
            if hex in move_zone:
                move_zone.remove(hex)
    
    def exclude_friendly_units_from_move_zone(self, move_zone: List) -> None:
        """Exclude friendly units from move zone."""
        self.temp_list.clear()
        current_color = self.get_current_color()
        for hex in move_zone:
            if hex.color != current_color:
                continue
            if hex.has_unit():
                self.temp_list.append(hex)
        # Remove all items in temp_list from move_zone
        for hex in self.temp_list:
            if hex in move_zone:
                move_zone.remove(hex)
    
    def spend_money_and_merge_units(self) -> None:
        """Spend money on buildings/units and merge units."""
        current_color = self.get_current_color()
        if not current_color:
            return
        
        for province in self.game_state.provinces_manager.provinces:
            if not province.is_valid():
                continue
            if province.get_color() != current_color:
                continue
            self.spend_money(province)
            self.merge_units(province)
    
    def spend_money(self, province) -> None:
        """Spend province money on buildings and units."""
        if not province.is_valid():
            return
        self.try_to_build_towers(province)
        self.try_to_build_farms(province)
        self.try_to_build_units(province)
    
    def try_to_build_units(self, province) -> None:
        """Try to build units."""
        if not province.is_valid():
            return
        self.try_to_build_units_on_palms(province)
        self.try_to_reinforce_units(province)
        
        for strength in range(1, 5):  # 1 to 4
            if not self.can_afford_unit(province, strength, 5):
                break
            if self.is_difficulty_less_than(Difficulty.AVERAGE) and strength == 2:
                break
            if self.is_difficulty_less_than(Difficulty.HARD) and strength == 3:
                break
            if self.is_difficulty_less_than(Difficulty.EXPERT) and strength == 4:
                break
            
            count = 50
            while count > 0 and self.can_afford_unit(province, strength):
                count -= 1
                if not self.try_to_attack_with_strength(province, strength):
                    break
                if not province.is_valid():
                    return
        
        # Kick-start province with at least one unit
        if self.can_afford_unit(province, 1) and self.how_many_units_in_province(province) <= 1:
            self.try_to_attack_with_strength(province, 1)
    
    def try_to_build_units_on_palms(self, province) -> None:
        """Try to build units on palm trees."""
        if self.is_difficulty_less_than(Difficulty.HARD):
            return
        
        count = 100
        while count > 0 and self.can_afford_unit(province, 1):
            count -= 1
            self.get_ruleset().update_move_zone_for_unit_construction(province, 1)
            self.copy_move_zone_to_temp_list()
            killed_palm = False
            for hex in self.temp_list:
                if hex.piece != PieceType.PALM:
                    continue
                if hex.color != province.get_color():
                    continue
                if self.command_unit_build(province, hex, 1):
                    killed_palm = True
                    break
            if not killed_palm:
                break
    
    def copy_move_zone_to_temp_list(self) -> None:
        """Copy move zone to temp list."""
        self.temp_list.clear()
        self.temp_list.extend(self.get_move_zone_manager().hexes)
    
    def try_to_attack_with_strength(self, province, strength: int) -> bool:
        """Try to attack with a unit of given strength."""
        self.get_ruleset().update_move_zone_for_unit_construction(province, strength)
        move_zone = self.get_move_zone_manager().hexes
        attackable_hexes = self.find_attackable_hexes(province.get_color(), move_zone)
        
        if len(attackable_hexes) == 0:
            return False
        
        best_hex = self.find_most_attractive_hex(attackable_hexes, province.get_color(), strength)
        if best_hex:
            return self.command_unit_build(province, best_hex, strength)
        return False
    
    def try_to_reinforce_units(self, province) -> None:
        """Try to reinforce units (balancer difficulty only)."""
        if self.is_difficulty_less_than(Difficulty.BALANCER):
            return
        for hex in province.get_hexes():
            if not hex.piece or not is_unit(hex.piece):
                continue
            strength = self.get_strength(hex)
            if self.unit_has_to_be_reinforced(hex) and self.can_afford_unit(province, strength + 1):
                self.command_unit_build(province, hex, 1)
    
    def unit_has_to_be_reinforced(self, unit_hex) -> bool:
        """Check if unit needs to be reinforced."""
        strength = self.get_strength(unit_hex)
        if strength == 4:
            return False
        
        self.get_move_zone_manager().update_for_unit(unit_hex)
        move_zone = self.get_move_zone_manager().hexes
        if not self.move_zone_contains_enemy_hexes(move_zone, unit_hex.color):
            return False
        
        attackable_hexes = self.find_attackable_hexes(unit_hex.color, move_zone)
        if len(attackable_hexes) > 0:
            return False
        
        return True
    
    def move_zone_contains_enemy_hexes(self, move_zone: List, color: HColor) -> bool:
        """Check if move zone contains enemy hexes."""
        for hex in move_zone:
            if hex.color != color:
                return True
        return False
    
    def how_many_units_in_province(self, province) -> int:
        """Count units in province."""
        count = 0
        for hex in province.get_hexes():
            if hex.piece and is_unit(hex.piece):
                count += 1
        return count
    
    def try_to_build_farms(self, province) -> None:
        """Try to build farms."""
        if self.is_difficulty_less_than(Difficulty.AVERAGE):
            return
        
        farm_price = self.get_ruleset().get_price(province, PieceType.FARM)
        if farm_price > self.MAX_FARM_COST:
            return
        
        count = 100
        while count > 0 and province.get_money() >= farm_price:
            count -= 1
            if not self.is_ok_to_build_new_farm(province):
                return
            hex = self.find_good_hex_for_farm(province)
            if not hex:
                return
            self.command_piece_build(province, hex, PieceType.FARM)
    
    def is_ok_to_build_new_farm(self, province) -> bool:
        """Check if it's OK to build a new farm."""
        farm_price = self.get_ruleset().get_price(province, PieceType.FARM)
        if province.get_money() > 2 * farm_price:
            return True
        
        src_army_strength = self.get_army_strength(province)
        self.update_nearby_provinces(province)
        for nearby_province in self.nearby_provinces:
            if nearby_province == province:
                continue
            army_strength = self.get_army_strength(nearby_province)
            if src_army_strength < army_strength / 2:
                return False
        
        if self.find_hex_that_needs_tower(province):
            return False
        
        return True
    
    def get_army_strength(self, province) -> int:
        """Get total army strength of province."""
        total = 0
        for hex in province.get_hexes():
            if hex.piece and is_unit(hex.piece):
                total += self.get_strength(hex)
        return total
    
    def find_good_hex_for_farm(self, province):
        """Find a good hex for building a farm."""
        if not self.has_province_good_hex_for_farm(province):
            return None
        
        count = 0
        hexes = province.get_hexes()
        while count < 1000:
            count += 1
            hex = self.random.choice(hexes)
            if self.is_hex_good_for_farm(hex):
                return hex
        return None
    
    def has_province_good_hex_for_farm(self, province) -> bool:
        """Check if province has a good hex for farm."""
        for hex in province.get_hexes():
            if self.is_hex_good_for_farm(hex):
                return True
        return False
    
    def is_hex_good_for_farm(self, hex) -> bool:
        """Check if hex is good for building a farm."""
        if hex.piece:
            return False
        hex_province = hex.get_province()
        for adj_hex in hex.adjacent_hexes:
            if adj_hex.color != hex.color:
                continue
            if hex_province and adj_hex.get_province() != hex_province:
                continue
            if adj_hex.piece == PieceType.CITY:
                return True
            if adj_hex.piece == PieceType.FARM:
                return True
        return False
    
    def try_to_build_towers(self, province) -> None:
        """Try to build towers."""
        if self.is_difficulty_less_than(Difficulty.AVERAGE):
            return
        
        tower_price = self.get_ruleset().get_price(province, PieceType.TOWER)
        count = 100
        while count > 0 and province.get_money() >= tower_price:
            count -= 1
            hex = self.find_hex_that_needs_tower(province)
            if not hex:
                break
            self.command_piece_build(province, hex, PieceType.TOWER)
        
        # Try strong towers (expert difficulty)
        if not self.is_difficulty_less_than(Difficulty.EXPERT):
            while count > 0 and self.province_can_afford_strong_tower(province):
                count -= 1
                hex = self.find_hex_for_strong_tower(province)
                if not hex:
                    break
                self.command_piece_build(province, hex, PieceType.STRONG_TOWER)
    
    def find_hex_that_needs_tower(self, province):
        """Find a hex that needs a tower."""
        for hex in province.get_hexes():
            if self.need_tower_on_hex(hex):
                return hex
        return None
    
    def need_tower_on_hex(self, hex) -> bool:
        """Check if hex needs a tower."""
        if hex.piece:
            return False
        
        self.update_nearby_provinces(hex)
        if len(self.nearby_provinces) == 0:
            return False  # Build towers only at front line
        
        if self.game_state.turns_manager.lap == 0:
            return False  # Don't build towers on first lap
        
        return self.get_predicted_defense_gain_by_new_tower(hex) >= 3
    
    def get_predicted_defense_gain_by_new_tower(self, hex) -> int:
        """Get predicted defense gain from building a tower."""
        gain = 0
        if not self.is_defended_by_tower(hex):
            gain += 1
        
        hex_province = hex.get_province()
        for adj_hex in hex.adjacent_hexes:
            if adj_hex.color != hex.color:
                continue
            if hex_province and adj_hex.get_province() != hex_province:
                continue
            if not self.is_defended_by_tower(adj_hex):
                gain += 1
            if adj_hex.piece in (PieceType.TOWER, PieceType.STRONG_TOWER):
                gain -= 1
        return gain
    
    def is_defended_by_tower(self, hex) -> bool:
        """Check if hex is defended by a tower."""
        if hex.piece in (PieceType.TOWER, PieceType.STRONG_TOWER):
            return True
        hex_province = hex.get_province()
        for adj_hex in hex.adjacent_hexes:
            if adj_hex.color != hex.color:
                continue
            if hex_province and adj_hex.get_province() != hex_province:
                continue
            if adj_hex.piece in (PieceType.TOWER, PieceType.STRONG_TOWER):
                return True
        return False
    
    def find_hex_for_strong_tower(self, province):
        """Find a hex for upgrading to strong tower."""
        for hex in province.get_hexes():
            if hex.piece != PieceType.TOWER:
                continue
            if self.needs_strong_tower_on_hex(province, hex):
                return hex
        return None
    
    def needs_strong_tower_on_hex(self, province, hex) -> bool:
        """Check if hex needs a strong tower."""
        self.update_nearby_provinces(hex)
        if len(self.nearby_provinces) == 0:
            return False
        
        for nearby_province in self.nearby_provinces:
            if len(nearby_province.get_hexes()) > len(province.get_hexes()) / 2:
                return True
        return False
    
    def province_can_afford_strong_tower(self, province) -> bool:
        """Check if province can afford strong tower."""
        strong_tower_price = self.get_ruleset().get_price(province, PieceType.STRONG_TOWER)
        if province.get_money() < strong_tower_price:
            return False
        
        peasant_price = self.get_ruleset().get_price(province, PieceType.PEASANT)
        strong_tower_consumption = self.get_ruleset().get_consumption(PieceType.STRONG_TOWER)
        profit = self.game_state.economics_manager.calculate_province_profit(province)
        return profit - strong_tower_consumption >= peasant_price / 2
    
    def update_nearby_provinces(self, src) -> None:
        """Update list of nearby enemy provinces."""
        self.nearby_provinces.clear()
        if hasattr(src, 'get_hexes'):  # It's a province
            for hex in src.get_hexes():
                for adj_hex in hex.adjacent_hexes:
                    self.check_to_add_nearby_province(hex, adj_hex)
        else:  # It's a hex - use rotated pattern
            from core.fog_of_war import DirectionsManager
            directions_manager = DirectionsManager(self.game_state)
            for dir in range(6):
                adjacent_hex = directions_manager.get_adjacent_hex(src, dir)
                if not adjacent_hex:
                    continue
                
                # Get hex in same direction
                adjacent_hex2 = directions_manager.get_adjacent_hex(adjacent_hex, dir)
                # Get hex in rotated direction
                rotated_dir = dir + 1
                if rotated_dir >= 6:
                    rotated_dir = 0
                adjacent_hex3 = directions_manager.get_adjacent_hex(adjacent_hex, rotated_dir)
                
                self.check_to_add_nearby_province(src, adjacent_hex)
                if adjacent_hex2:
                    self.check_to_add_nearby_province(src, adjacent_hex2)
                if adjacent_hex3:
                    self.check_to_add_nearby_province(src, adjacent_hex3)
    
    def check_to_add_nearby_province(self, src_hex, adj_hex) -> None:
        """Check and add nearby province."""
        if not adj_hex:
            return
        if adj_hex.color == HColor.GRAY:
            return
        if adj_hex.color == src_hex.color:
            return
        province = adj_hex.get_province()
        if province and province not in self.nearby_provinces:
            self.nearby_provinces.append(province)
    
    def merge_units(self, province) -> None:
        """Merge units in province."""
        if self.is_difficulty_less_than(Difficulty.HARD):
            return
        if not province.is_valid():
            return
        
        for hex in province.get_hexes():
            if not hex.piece or not is_unit(hex.piece):
                continue
            if not self.is_ready(hex):
                continue
            self.try_to_merge_with_someone(province, hex)
    
    def try_to_merge_with_someone(self, province, unit_hex) -> None:
        """Try to merge unit with another unit."""
        self.get_move_zone_manager().update_for_unit(unit_hex)
        move_zone = self.get_move_zone_manager().hexes
        
        if len(move_zone) == 0:
            return
        
        for hex in move_zone:
            if self.merge_conditions(province, unit_hex, hex):
                from commands.types import MoveUnitCommand
                from commands.executor import CommandExecutor
                executor = CommandExecutor(self.game_state)
                command = MoveUnitCommand(
                    start_hex=unit_hex,
                    finish_hex=hex,
                    color_transfer_enabled=True
                )
                executor.execute(command, self.get_current_color())
                break
    
    def merge_conditions(self, province, start_hex, finish_hex) -> bool:
        """Check if units can be merged."""
        if start_hex.color != finish_hex.color:
            return False
        if not start_hex.piece or not is_unit(start_hex.piece):
            return False
        if not finish_hex.piece or not is_unit(finish_hex.piece):
            return False
        if not self.is_ready(start_hex):
            return False
        if start_hex.coordinate1 == finish_hex.coordinate1 and start_hex.coordinate2 == finish_hex.coordinate2:
            return False
        
        merge_result = get_merge_result(start_hex.piece, finish_hex.piece)
        if not merge_result:
            return False
        
        merged_strength = self.get_strength(merge_result)
        return self.can_afford_unit(province, merged_strength)
    
    def check_to_kill_redundant_units(self) -> None:
        """Check and kill redundant units."""
        for province in self.game_state.provinces_manager.provinces:
            self.check_to_kill_redundant_units_in_province(province)
    
    def check_to_kill_redundant_units_in_province(self, province) -> None:
        """Check and kill redundant units in a province."""
        if self.is_difficulty_less_than(Difficulty.HARD):
            return
        
        detected_strong_units = False
        for hex in province.get_hexes():
            if not hex.piece or not is_unit(hex.piece):
                continue
            if not self.is_ready(hex):
                return
            if self.get_strength(hex) < 3:
                continue
            detected_strong_units = True
        
        if not detected_strong_units:
            return
        
        # Units are not doing anything - kill them
        self.kill_redundant_units(province)
    
    def kill_redundant_units(self, province) -> None:
        """Kill redundant units by merging with peasants."""
        peasant_price = self.get_ruleset().get_price(province, PieceType.PEASANT)
        count = 0
        while count < 1000:
            count += 1
            if not (province.get_money() >= peasant_price and 
                    self.game_state.economics_manager.calculate_province_profit(province) >= 0):
                break
            hex = self.find_strongest_unit(province, PieceType.KNIGHT)
            if not hex:
                break
            if not self.can_afford_unit(province, 1):
                break
            self.command_unit_build(province, hex, 1)
    
    def find_strongest_unit(self, province, ignored_piece_type: PieceType):
        """Find strongest unit in province (excluding ignored type)."""
        best_hex = None
        max_strength = 0
        
        for hex in province.get_hexes():
            if not hex.piece or not is_unit(hex.piece):
                continue
            if hex.piece == ignored_piece_type:
                continue
            strength = self.get_strength(hex)
            if best_hex is None or strength > max_strength:
                best_hex = hex
                max_strength = strength
        
        return best_hex
    
    def move_afk_units(self) -> None:
        """Move units that haven't moved (AFK units)."""
        if self.is_difficulty_less_than(Difficulty.EXPERT):
            return
        
        self.update_units_ready_to_move()
        for hex in self.units_ready_to_move:
            if not self.is_ready(hex):
                continue
            province = hex.get_province()
            if not province:
                continue
            if len(province.get_hexes()) <= 20:
                continue
            self.move_afk_unit(province, hex)
    
    def move_afk_unit(self, province, hex) -> None:
        """Move an AFK unit to perimeter."""
        target_hex = self.find_random_hex_in_perimeter(province)
        if not target_hex:
            return
        
        # Try to use mass march emulation first
        if not self.emulate_mass_march_for_single_unit(hex, target_hex):
            # Fallback: move quickly to prevent infinite loop
            self.move_afk_unit_quickly(hex)
    
    def move_afk_unit_quickly(self, hex) -> None:
        """Move AFK unit quickly (fallback)."""
        self.get_move_zone_manager().update_for_unit(hex)
        move_zone = self.get_move_zone_manager().hexes
        self.exclude_friendly_units_from_move_zone(move_zone)
        self.exclude_friendly_buildings_from_move_zone(move_zone)
        if len(move_zone) == 0:
            return
        target_hex = self.random.choice(move_zone)
        self.command_unit_move(hex, target_hex)
    
    def find_random_hex_in_perimeter(self, province):
        """Find a random hex in province perimeter."""
        self.hexes_in_perimeter.clear()
        for hex in province.get_hexes():
            if self.is_adjacent_to_enemy(hex):
                self.hexes_in_perimeter.append(hex)
        
        if len(self.hexes_in_perimeter) == 0:
            return None
        return self.random.choice(self.hexes_in_perimeter)
