"""
Economics Manager - handles province income and consumption calculations.
"""

from typing import TYPE_CHECKING
from core.events import IEventListener, AbstractEvent
from core.enums import EventType

if TYPE_CHECKING:
    from core.game_state import GameState
    from core.province import Province


class EconomicsManager(IEventListener):
    """
    Manages economic calculations for provinces.
    
    Calculates income, consumption, and profit for provinces based on
    hexes and pieces within them.
    
    Also applies profits to province money when turns end.
    """

    def __init__(self, game_state: "GameState"):
        """Initialize economics manager."""
        self.game_state = game_state
        # Optional training handicap: scale down the *positive income* applied
        # to provinces of every colour except ``income_tax_exempt_color`` by
        # ``income_tax_rate`` (0.0 = off, 1.0 = keep nothing). Consumption is
        # untouched, so a taxed opponent keeps its usual AI logic but grows its
        # treasury more slowly (and can starve if upkeep outpaces net income).
        # Defaults are inert so real games are unaffected; the ML env sets them
        # per episode.
        self.income_tax_rate: float = 0.0
        self.income_tax_exempt_color = None
        # Register as event listener
        if game_state and game_state.events_manager:
            game_state.events_manager.add_listener(self)

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
    
    def on_event_validated(self, event: AbstractEvent) -> None:
        """Called when event is validated."""
        pass
    
    def on_event_applied(self, event: AbstractEvent) -> None:
        """Called when event is applied."""
        if event.get_type() == EventType.TURN_END:
            self._on_turn_end_event_applied()
    
    def get_listen_priority(self) -> int:
        """Get listener priority (lower = higher priority)."""
        return 8  # Same as original Java implementation
    
    def _on_turn_end_event_applied(self) -> None:
        """Handle turn end event - apply profits to provinces."""
        self._apply_profits()
    
    def _apply_profits(self) -> None:
        """
        Apply profits to provinces owned by the current entity.
        
        This matches the original game's behavior: profits are applied to provinces
        owned by the entity whose turn it is NOW (after the turn switch).
        This is called when a turn ends, and the turn has already switched.
        
        Note: Profits are NOT applied on the first lap (lap == 0).
        """
        # Don't apply economics on first lap
        if not self.game_state.turns_manager:
            return
        if self.game_state.turns_manager.lap == 0:
            return
        
        # Get the current entity (after turn switch)
        # This matches the original game's isOwnedByCurrentEntity() logic
        current_entity = self.game_state.entities_manager.get_current_entity()
        if not current_entity:
            return
        
        current_color = current_entity.color
        
        # Apply profits to all provinces owned by the current entity
        for province in self.game_state.provinces_manager.provinces:
            # Check if province is owned by the current entity
            if province.get_color() != current_color:
                continue
            
            # Calculate and apply profit. Optionally tax the positive income of
            # non-exempt (opponent) provinces as a training handicap; upkeep is
            # left intact.
            current_money = province.get_money()
            income = self.calculate_province_income(province)
            if (self.income_tax_rate > 0.0
                    and province.get_color() != self.income_tax_exempt_color):
                income = int(income * (1.0 - self.income_tax_rate))
            consumption = self.calculate_province_consumption(province)
            new_money = current_money + income - consumption
            province.set_money(new_money)