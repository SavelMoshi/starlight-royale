from dataclasses import dataclass, field
from decimal import Decimal

from .money import ZERO, amount

CURRENCIES = {"USD": "$", "EUR": "€", "GBP": "£"}


@dataclass
class Profile:
    name: str
    currency: str
    cash: Decimal = Decimal("25.00")
    chips: Decimal = ZERO
    gameplay_net: Decimal = ZERO
    stats: dict[str, int] = field(
        default_factory=lambda: {
            "blackjack_played": 0,
            "blackjack_won": 0,
            "slots_played": 0,
            "slots_won": 0,
            "roulette_played": 0,
            "roulette_won": 0,
        }
    )
    dealer_dialogue: bool = True

    @property
    def symbol(self) -> str:
        return CURRENCIES[self.currency]

    def deposit(self, raw: str) -> Decimal:
        value = amount(raw)
        if value > self.cash:
            raise ValueError("Not enough virtual cash.")
        self.cash -= value
        self.chips += value
        return value

    def withdraw(self, raw: str) -> Decimal:
        value = amount(raw)
        if value > self.chips:
            raise ValueError("Not enough virtual chips.")
        self.chips -= value
        self.cash += value
        return value

    def top_up(self, raw: str) -> Decimal:
        value = amount(raw)
        self.cash += value
        return value

    def wager(self, raw: str, game: str | None = None) -> Decimal:
        value = amount(raw)
        if value > self.chips:
            raise ValueError("Not enough chips. Visit the cashier.")
        self.chips -= value
        self.gameplay_net -= value
        if game is not None:
            self.stats[f"{game}_played"] += 1
        return value

    def settle(self, stake: Decimal, returned: Decimal, game: str, won: bool) -> Decimal:
        if returned < ZERO:
            raise ValueError("Payout cannot be negative.")
        self.chips += returned
        change = returned - stake
        self.gameplay_net += returned
        if won:
            self.stats[f"{game}_won"] += 1
        return change
