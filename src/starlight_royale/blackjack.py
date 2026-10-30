from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
import secrets

SUITS = ("♠", "♥", "♦", "♣")
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


def shuffled_deck(rng=None) -> list[Card]:
    cards = [Card(rank, suit) for suit in SUITS for rank in RANKS]
    (rng or secrets.SystemRandom()).shuffle(cards)
    return cards


def hand_value(cards: list[Card]) -> tuple[int, bool]:
    total = sum(
        11 if card.rank == "A" else 10 if card.rank in "JQK" else int(card.rank) for card in cards
    )
    aces = sum(card.rank == "A" for card in cards)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, aces > 0


@dataclass
class Blackjack:
    wager: Decimal
    deck: list[Card] = field(default_factory=shuffled_deck)
    player: list[Card] = field(default_factory=list)
    dealer: list[Card] = field(default_factory=list)
    result: str | None = None
    doubled: bool = False

    def __post_init__(self) -> None:
        if len(self.deck) != 52 and len(self.deck) < 4:
            raise ValueError("Deck needs at least four cards.")
        self.player = [self.deck.pop(0), self.deck.pop(0)]
        self.dealer = [self.deck.pop(0), self.deck.pop(0)]
        player_natural = hand_value(self.player)[0] == 21
        dealer_natural = hand_value(self.dealer)[0] == 21
        if player_natural or dealer_natural:
            self.result = (
                "push"
                if player_natural and dealer_natural
                else "blackjack"
                if player_natural
                else "dealer blackjack"
            )

    @property
    def can_double(self) -> bool:
        return self.result is None and len(self.player) == 2 and not self.doubled

    def hit(self) -> None:
        if self.result is not None:
            raise ValueError("Hand is over.")
        self.player.append(self.deck.pop(0))
        if hand_value(self.player)[0] > 21:
            self.result = "bust"

    def stand(self) -> None:
        if self.result is not None:
            raise ValueError("Hand is over.")
        while hand_value(self.dealer)[0] < 17:
            self.dealer.append(self.deck.pop(0))
        player_total = hand_value(self.player)[0]
        dealer_total = hand_value(self.dealer)[0]
        self.result = (
            "dealer bust"
            if dealer_total > 21
            else "win"
            if player_total > dealer_total
            else "push"
            if player_total == dealer_total
            else "loss"
        )

    def double_down(self) -> None:
        if not self.can_double:
            raise ValueError("Double down is available only on the first two cards.")
        self.doubled = True
        self.wager *= 2
        self.hit()
        if self.result is None:
            self.stand()

    @property
    def returned(self) -> Decimal:
        if self.result is None:
            raise ValueError("Hand is still in play.")
        if self.result == "blackjack":
            return (self.wager * Decimal("2.5")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if self.result in ("win", "dealer bust"):
            return self.wager * 2
        if self.result == "push":
            return self.wager
        return Decimal("0.00")
