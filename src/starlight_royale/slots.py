from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
import secrets

NAMES = {
    "🍒": "Cherry",
    "🍋": "Lemon",
    "🔔": "Bell",
    "⭐": "Star",
    "💎": "Diamond",
    "🌵": "Cactus",
    "🐎": "Horse",
    "🌙": "Moon",
    "🪙": "Coin",
    "🔑": "Key",
    "💍": "Ring",
    "👑": "Crown",
}


@dataclass(frozen=True)
class Machine:
    key: str
    name: str
    tagline: str
    symbols: tuple[str, ...]
    weights: tuple[int, ...]
    payouts: tuple[int, int, int]  # Three, four, and five matching reels.
    jackpot: int  # Five diamonds.


MACHINES = {
    "gold_rush": Machine(
        "gold_rush",
        "Gold Rush",
        "Classic casino fruit with a gold finish.",
        ("🍒", "🍋", "🔔", "⭐", "💎"),
        (30, 25, 20, 15, 10),
        (2, 6, 20),
        50,
    ),
    "moonlight_saloon": Machine(
        "moonlight_saloon",
        "Moonlight Saloon",
        "A quiet frontier table under the night sky.",
        ("🌵", "🐎", "🌙", "⭐", "💎"),
        (35, 25, 18, 14, 8),
        (2, 7, 25),
        60,
    ),
    "royal_vault": Machine(
        "royal_vault",
        "Royal Vault",
        "The high shine of the inner room.",
        ("🪙", "🔑", "💍", "👑", "💎"),
        (35, 28, 19, 12, 6),
        (2, 8, 30),
        80,
    ),
}


def spin(machine: Machine, rng=None) -> tuple[str, ...]:
    chooser = rng or secrets.SystemRandom()
    return tuple(chooser.choices(machine.symbols, weights=machine.weights, k=5))


def multiplier(machine: Machine, reels: tuple[str, ...]) -> int:
    if len(reels) != 5 or any(symbol not in machine.symbols for symbol in reels):
        raise ValueError("Invalid reels for this machine.")
    symbol, count = Counter(reels).most_common(1)[0]
    if count == 5 and symbol == "💎":
        return machine.jackpot
    return machine.payouts[count - 3] if count >= 3 else 0


def returned(machine: Machine, stake: Decimal, reels: tuple[str, ...]) -> Decimal:
    return stake * multiplier(machine, reels)
