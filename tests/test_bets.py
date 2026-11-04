from decimal import Decimal

import pytest

from starlight_royale.bets import range_for_cash, selected_bet
from starlight_royale.levels import THRESHOLDS
from starlight_royale.wallet import Profile


def test_wager_ranges_follow_all_cash_levels():
    ranges = [range_for_cash(Decimal(value)) for value in THRESHOLDS]
    assert len({r.minimum for r in ranges}) == 30
    assert len({r.maximum for r in ranges}) == 30
    assert ranges[0].minimum == Decimal("0.01")
    assert ranges[0].maximum == Decimal("25")
    assert ranges[-1].minimum == Decimal("10000.00")
    assert ranges[-1].maximum == Decimal("20000000")
    assert all(a.minimum < b.minimum and a.maximum < b.maximum for a, b in zip(ranges, ranges[1:]))


def test_cashier_level_drop_reduces_bet_range():
    p = Profile("Mira", "USD")
    p.top_up("1000")
    high = range_for_cash(p.cash)
    p.deposit("1000")
    low = range_for_cash(p.cash)
    assert low.minimum < high.minimum and low.maximum < high.maximum
    p.withdraw("1000")
    assert range_for_cash(p.cash) == high


def test_min_max_last_custom_and_affordability():
    bet_range = range_for_cash(Decimal("200"))
    chips = Decimal("12.00")
    assert selected_bet("min", bet_range, chips, "", "") == Decimal("0.20")
    assert selected_bet("max", bet_range, chips, "", "") == chips
    assert selected_bet("last", bet_range, chips, "2.50", "") == Decimal("2.50")
    assert selected_bet("custom", bet_range, chips, "", "3.25") == Decimal("3.25")
    assert selected_bet("custom", bet_range, chips, "", "20.00") is None
    assert selected_bet("last", bet_range, chips, "0.01", "") is None
    with pytest.raises(ValueError):
        bet_range.check(Decimal("351.00"))
