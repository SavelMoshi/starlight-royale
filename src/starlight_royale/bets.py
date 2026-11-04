from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

from .levels import level_for
from .money import CENT, ZERO

BET_KEYS = ("blackjack", "roulette", "gold_rush", "moonlight_saloon", "royal_vault")
BET_MODES = ("min", "max", "last", "custom")


@dataclass(frozen=True)
class BetRange:
    minimum: Decimal
    maximum: Decimal

    def check(self, stake: Decimal, chips: Decimal | None = None) -> None:
        if stake < self.minimum:
            raise ValueError(f"This level's minimum wager is {self.minimum:.2f}.")
        if stake > self.maximum:
            raise ValueError(f"This level's maximum wager is {self.maximum:.2f}.")
        if chips is not None and stake > chips:
            raise ValueError("Not enough chips. Visit the cashier.")


def range_for_cash(cash: Decimal) -> BetRange:
    level = level_for(cash)
    minimum = max(CENT, (level.threshold / 1000).quantize(CENT, rounding=ROUND_CEILING))
    maximum = level.next_threshold or level.threshold * 2
    return BetRange(minimum, maximum)


def selected_bet(
    mode: str, bet_range: BetRange, chips: Decimal, last: str, custom: str
) -> Decimal | None:
    if mode == "min":
        value = bet_range.minimum
    elif mode == "max":
        value = min(bet_range.maximum, chips)
    elif mode == "last" and last:
        value = Decimal(last)
    elif mode == "custom" and custom:
        value = Decimal(custom)
    else:
        return None
    if value <= ZERO:
        return None
    try:
        bet_range.check(value, chips)
    except ValueError:
        return None
    return value
