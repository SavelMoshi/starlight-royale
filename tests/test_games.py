from decimal import Decimal

import pytest

from starlight_royale.blackjack import Blackjack, Card, hand_value, shuffled_deck
from starlight_royale.roulette import Bet, REDS, color
from starlight_royale.slots import SYMBOLS, multiplier, returned, spin


def cards(*ranks):
    return [Card(rank, "♠") for rank in ranks]


def game(player, dealer, rest=(), wager="10.00"):
    return Blackjack(Decimal(wager), cards(*player, *dealer, *rest))


def test_full_deck_unique_and_injected_shuffle():
    class Reverse:
        def shuffle(self, deck):
            deck.reverse()

    deck = shuffled_deck(Reverse())
    assert len(deck) == len(set(deck)) == 52
    assert deck[0] == Card("K", "♣")


@pytest.mark.parametrize(
    "ranks,value,soft",
    [
        (("A", "9"), 20, True),
        (("A", "9", "5"), 15, False),
        (("A", "A", "9"), 21, True),
        (("A", "A", "9", "9"), 20, False),
    ],
)
def test_aces(ranks, value, soft):
    assert hand_value(cards(*ranks)) == (value, soft)


def test_naturals_and_dealer_natural():
    assert game(("A", "K"), ("9", "7")).result == "blackjack"
    assert game(("A", "K"), ("9", "7")).returned == Decimal("25.00")
    assert game(("9", "7"), ("A", "K")).result == "dealer blackjack"
    assert game(("9", "7"), ("A", "K")).returned == 0
    assert game(("A", "K"), ("A", "Q")).result == "push"
    assert game(("A", "K"), ("A", "Q")).returned == Decimal("10.00")
    assert game(("A", "K"), ("9", "7"), wager="0.01").returned == Decimal("0.03")


def test_dealer_stands_soft_17_and_push():
    hand = game(("10", "7"), ("A", "6"), ("2",))
    hand.stand()
    assert hand.result == "push" and len(hand.dealer) == 2


def test_dealer_draws_and_busts():
    hand = game(("10", "8"), ("9", "6"), ("K",))
    hand.stand()
    assert hand.result == "dealer bust" and hand.returned == Decimal("20.00")


def test_player_hit_bust_and_double_one_card():
    bust = game(("10", "8"), ("9", "7"), ("5",))
    bust.hit()
    assert bust.result == "bust" and bust.returned == 0
    doubled = game(("5", "6"), ("9", "7"), ("10", "4"))
    doubled.double_down()
    assert len(doubled.player) == 3 and doubled.wager == Decimal("20.00")
    assert doubled.result == "win" and doubled.returned == Decimal("40.00")
    with pytest.raises(ValueError):
        doubled.double_down()


def test_double_unavailable_after_hit():
    hand = game(("2", "3"), ("9", "7"), ("4", "10"))
    hand.hit()
    assert not hand.can_double


@pytest.mark.parametrize(
    "reels,multiple",
    [
        (("🍒", "🍒", "🍒"), 3),
        (("🍋", "🍋", "🍋"), 4),
        (("🔔", "🔔", "🔔"), 6),
        (("⭐", "⭐", "⭐"), 10),
        (("💎", "💎", "💎"), 20),
        (("🍒", "🍒", "⭐"), 2),
        (("🍋", "🍒", "🍒"), 2),
        (("🍒", "🍋", "⭐"), 0),
        (("🍋", "🍋", "⭐"), 0),
    ],
)
def test_slots_payouts(reels, multiple):
    assert multiplier(reels) == multiple
    assert returned(Decimal("1.25"), reels) == Decimal("1.25") * multiple


def test_slots_injectable_rng():
    class Fixed:
        def choices(self, symbols, weights, k):
            assert tuple(symbols) == SYMBOLS and sum(weights) == 100 and k == 3
            return ["💎"] * 3

    assert spin(Fixed()) == ("💎", "💎", "💎")


@pytest.mark.parametrize(
    "bet,result,win,payout",
    [
        (Bet("color", "red"), 1, True, 2),
        (Bet("color", "black"), 2, True, 2),
        (Bet("parity", "odd"), 3, True, 2),
        (Bet("parity", "even"), 4, True, 2),
        (Bet("dozen", 1), 12, True, 3),
        (Bet("dozen", 2), 13, True, 3),
        (Bet("dozen", 3), 36, True, 3),
        (Bet("number", 17), 17, True, 36),
        (Bet("number", 0), 0, True, 36),
        (Bet("number", 17), 18, False, 36),
    ],
)
def test_roulette_bets(bet, result, win, payout):
    assert bet.payout == payout
    assert bet.wins(result) is win
    assert (
        bet.returned(Decimal("2.50"), result) == Decimal("2.50") * payout
        if win
        else bet.returned(Decimal("2.50"), result) == 0
    )


def test_zero_and_all_wheel_colors():
    assert len(REDS) == 18
    assert color(0) == "green"
    assert sum(color(n) == "black" for n in range(1, 37)) == 18
    for bet in (
        Bet("color", "red"),
        Bet("color", "black"),
        Bet("parity", "odd"),
        Bet("parity", "even"),
        Bet("dozen", 1),
        Bet("dozen", 2),
        Bet("dozen", 3),
    ):
        assert not bet.wins(0)


@pytest.mark.parametrize(
    "kind,choice",
    [("color", "green"), ("number", 37), ("number", True), ("dozen", 0), ("parity", "both")],
)
def test_invalid_bets(kind, choice):
    with pytest.raises(ValueError):
        Bet(kind, choice)
