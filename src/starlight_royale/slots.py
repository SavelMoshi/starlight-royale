from decimal import Decimal
import secrets

SYMBOLS = ("🍒", "🍋", "🔔", "⭐", "💎")
NAMES = {"🍒": "Cherry", "🍋": "Lemon", "🔔": "Bell", "⭐": "Star", "💎": "Diamond"}
WEIGHTS = (30, 25, 20, 15, 10)
TRIPLE_PAYOUTS = {"🍒": 3, "🍋": 4, "🔔": 6, "⭐": 10, "💎": 20}


def spin(rng=None) -> tuple[str, str, str]:
    chooser = rng or secrets.SystemRandom()
    return tuple(chooser.choices(SYMBOLS, weights=WEIGHTS, k=3))


def multiplier(reels: tuple[str, str, str]) -> int:
    if len(reels) != 3 or any(symbol not in SYMBOLS for symbol in reels):
        raise ValueError("Invalid reels.")
    if reels[0] == reels[1] == reels[2]:
        return TRIPLE_PAYOUTS[reels[0]]
    if reels.count("🍒") == 2:
        return 2
    return 0


def returned(stake: Decimal, reels: tuple[str, str, str]) -> Decimal:
    return stake * multiplier(reels)
