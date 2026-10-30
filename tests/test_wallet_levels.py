from decimal import Decimal

import pytest

from starlight_royale.levels import RANKS, THRESHOLDS, level_for
from starlight_royale.money import amount, money
from starlight_royale.wallet import Profile


@pytest.mark.parametrize("raw", ["", "0", "0.00", "-1", "+1", "1.001", "1e3", "nan", "1,000"])
def test_invalid_amounts(raw):
    with pytest.raises(ValueError):
        amount(raw)


def test_decimal_precision_and_display():
    p = Profile("Mira", "EUR")
    p.top_up("0.10")
    p.top_up("0.20")
    assert p.cash == Decimal("25.30")
    assert money(p.cash, p.symbol) == "€25.30"
    assert amount(" 2.5 ") == Decimal("2.50")


def test_cashier_and_net():
    p = Profile("Mira", "USD")
    p.deposit("10.00")
    p.withdraw("2.50")
    p.top_up("100.00")
    assert (p.cash, p.chips, p.gameplay_net) == (
        Decimal("117.50"),
        Decimal("7.50"),
        Decimal("0.00"),
    )
    stake = p.wager("1.25", "slots")
    assert p.settle(stake, Decimal("2.50"), "slots", True) == Decimal("1.25")
    assert p.gameplay_net == Decimal("1.25")
    assert p.stats["slots_played"] == p.stats["slots_won"] == 1


def test_no_negative_balances_and_invalid_transfers():
    p = Profile("Mira", "USD")
    for operation, raw in (
        (p.deposit, "26"),
        (p.withdraw, "0.01"),
        (p.wager, "1"),
        (p.top_up, "-5"),
    ):
        with pytest.raises(ValueError):
            operation(raw)
    assert p.cash == Decimal("25.00")
    assert p.chips == Decimal("0.00")


def test_level_table_exactly_thirty_and_every_threshold():
    assert len(THRESHOLDS) == len(RANKS) == len(set(RANKS)) == 30
    assert THRESHOLDS[0] == 0 and THRESHOLDS[-1] == 10_000_000
    assert list(THRESHOLDS) == sorted(set(THRESHOLDS))
    for index, threshold in enumerate(THRESHOLDS):
        level = level_for(Decimal(threshold))
        assert level.number == index + 1
        assert level.rank == RANKS[index]
        assert level.threshold == threshold
        assert level.progress == (1.0 if index == 29 else 0.0)
        if index > 0:
            assert level_for(Decimal(threshold) - Decimal("0.01")).number == index


def test_level_progress_decreases_and_maximum():
    p = Profile("Mira", "USD")
    assert level_for(p.cash).number == 2
    p.deposit("20")
    assert level_for(p.cash).number == 1
    p.withdraw("20")
    assert level_for(p.cash).number == 2
    p.cash = Decimal("12000000.00")
    final = level_for(p.cash)
    assert final.number == 30 and final.next_threshold is None and final.progress == 1
    middle = level_for(Decimal("37.50"))
    assert middle.progress == 0.5
