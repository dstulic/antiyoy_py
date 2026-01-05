"""
Economics Manager - handles province income and consumption calculations.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.game_state import GameState
    from core.province import Province


class EconomicsManager:
    """
    Manages economic calculations for provinces.
    
    Calculates income, consumption, and profit for provinces based on
    hexes and pieces within them.
    """

    def __init__(self, game_state: "GameState"):
        """Initialize economics manager."""
        self.game_state = game_state

    def calculate_province_income(self, province: "Province") -> int:
        """
        Calculate total income for a province.
        
        Income comes from all hexes in the province:
        - Empty hexes: 1 income
        - Farms: 5 income
        - Trees (palm/pine): 0 income
        - Other pieces: 1 income
        """
        if not self.game_state.ruleset:
            return 0
        
        income = 0
        hexes = province.get_hexes()
        if not hexes:
            # Province has no hexes - this shouldn't happen, but return 0
            return 0
        
        for hex in hexes:
            hex_income = self.game_state.ruleset.get_hex_income(hex.piece)
            income += hex_income
        
        return income

    def calculate_province_consumption(self, province: "Province") -> int:
        """
        Calculate total consumption for a province.
        
        Consumption comes from pieces that require upkeep:
        - Units (peasant, spearman, baron, knight)
        - Towers (tower, strong_tower)
        - Empty hexes and other pieces: 0 consumption
        """
        if not self.game_state.ruleset:
            return 0
        
        consumption = 0
        for hex in province.get_hexes():
            if hex.piece:
                consumption += self.game_state.ruleset.get_consumption(hex.piece)
        
        return consumption

    def calculate_province_profit(self, province: "Province") -> int:
        """
        Calculate profit (income - consumption) for a province.
        
        Returns:
            Profit amount (can be negative if consumption exceeds income)
        """
        income = self.calculate_province_income(province)
        consumption = self.calculate_province_consumption(province)
        return income - consumption
