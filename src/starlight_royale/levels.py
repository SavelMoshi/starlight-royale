from dataclasses import dataclass
from decimal import Decimal

THRESHOLDS = (
    0,
    25,
    50,
    100,
    200,
    350,
    500,
    750,
    1000,
    1500,
    2500,
    4000,
    6000,
    8500,
    12000,
    17500,
    25000,
    40000,
    60000,
    90000,
    140000,
    220000,
    350000,
    550000,
    850000,
    1300000,
    2000000,
    3500000,
    6000000,
    10000000,
)
RANKS = (
    "Guest",
    "New Arrival",
    "Club Visitor",
    "Card Holder",
    "Table Regular",
    "House Guest",
    "Bronze Member",
    "Bronze Seat",
    "Bronze Ace",
    "Silver Ace",
    "Silver Member",
    "Silver Lounge",
    "Silver Star",
    "Gold Member",
    "Gold Spur",
    "Gold Ace",
    "Gold Circle",
    "Gold Reserve",
    "Platinum Guest",
    "Platinum Player",
    "Platinum Ace",
    "Platinum Circle",
    "High Stakes Member",
    "High Stakes Ace",
    "Frontier High Roller",
    "Royale Member",
    "Royale Ace",
    "Royale High Roller",
    "Starlight Elite",
    "Royale Legend",
)


@dataclass(frozen=True)
class Level:
    number: int
    rank: str
    threshold: Decimal
    next_threshold: Decimal | None
    progress: float


def level_for(cash: Decimal) -> Level:
    if cash < 0:
        raise ValueError("Cash cannot be negative.")
    index = max(i for i, threshold in enumerate(THRESHOLDS) if cash >= threshold)
    current = Decimal(THRESHOLDS[index])
    next_value = Decimal(THRESHOLDS[index + 1]) if index < 29 else None
    progress = 1.0 if next_value is None else float((cash - current) / (next_value - current))
    return Level(index + 1, RANKS[index], current, next_value, min(progress, 1.0))
