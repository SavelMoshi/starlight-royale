from dataclasses import dataclass
from decimal import Decimal
import secrets

REDS = frozenset((1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36))


def color(number: int) -> str:
    if number < 0 or number > 36:
        raise ValueError("Wheel result must be 0–36.")
    return "green" if number == 0 else "red" if number in REDS else "black"


@dataclass(frozen=True)
class Bet:
    kind: str
    choice: str | int

    def __post_init__(self) -> None:
        valid = {
            "color": self.choice in ("red", "black"),
            "parity": self.choice in ("odd", "even"),
            "number": type(self.choice) is int and 0 <= self.choice <= 36,
            "dozen": type(self.choice) is int and 1 <= self.choice <= 3,
        }
        if not valid.get(self.kind, False):
            raise ValueError("Invalid roulette bet.")

    @property
    def payout(self) -> int:
        return {"color": 2, "parity": 2, "number": 36, "dozen": 3}[self.kind]

    def wins(self, number: int) -> bool:
        color(number)
        if self.kind == "number":
            return number == self.choice
        if number == 0:
            return False
        if self.kind == "color":
            return color(number) == self.choice
        if self.kind == "parity":
            return (number % 2 == 0) == (self.choice == "even")
        return (number - 1) // 12 + 1 == self.choice

    def returned(self, stake: Decimal, number: int) -> Decimal:
        return stake * self.payout if self.wins(number) else Decimal("0.00")


def spin(rng=None) -> int:
    return (rng or secrets.SystemRandom()).randrange(37)
