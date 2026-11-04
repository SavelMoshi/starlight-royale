import json
from decimal import Decimal

import pytest

from starlight_royale.accounts import AccountStore
from starlight_royale.persistence import (
    SaveError,
    archive_corrupt,
    load,
    load_store,
    save,
    save_store,
)
from starlight_royale.wallet import Profile


def test_round_trip_and_atomic_cleanup(tmp_path):
    path = tmp_path / "nested" / "profile.json"
    p = Profile("Nova", "GBP")
    p.deposit("12.50")
    p.wager("1.25", "roulette")
    p.settle(Decimal("1.25"), Decimal("0.00"), "roulette", False)
    p.last_bets["roulette"] = "1.25"
    p.custom_bets["roulette"] = "2.50"
    p.bet_modes["roulette"] = "custom"
    p.roulette_choice = "dozen2"
    p.slot_machine = "royal_vault"
    save(p, path)
    assert load(path) == p
    assert list(path.parent.iterdir()) == [path]
    assert json.loads(path.read_text())["version"] == 3


def test_version_one_save_migrates_without_loss(tmp_path):
    path = tmp_path / "profile.json"
    save(Profile("Nova", "USD"), path)
    old = json.loads(path.read_text())["accounts"][0]
    old["version"] = 1
    for key in (
        "last_bets",
        "custom_bets",
        "bet_modes",
        "roulette_choice",
        "roulette_number",
        "slot_machine",
    ):
        del old[key]
    path.write_text(json.dumps(old))
    profile = load(path)
    assert profile.cash == Decimal("25.00")
    assert profile.bet_modes["roulette"] == "min"
    assert profile.roulette_choice == "red"
    assert json.loads(path.read_text())["version"] == 1
    save(profile, path)
    assert json.loads(path.read_text())["version"] == 3


@pytest.mark.parametrize("bad", ["{", "[]", '{"version": 99}', '{"version": 1, "name": "x"}'])
def test_invalid_save_preserved(tmp_path, bad):
    path = tmp_path / "profile.json"
    path.write_text(bad)
    with pytest.raises(SaveError):
        load(path)
    assert path.read_text() == bad
    archived = archive_corrupt(path)
    assert archived.read_text() == bad and not path.exists()


def test_rejects_tampered_balance_and_stats(tmp_path):
    path = tmp_path / "profile.json"
    save(Profile("Nova", "USD"), path)
    data = json.loads(path.read_text())
    data["accounts"][0]["cash"] = "-1.00"
    path.write_text(json.dumps(data))
    with pytest.raises(SaveError):
        load(path)
    data["accounts"][0]["cash"] = "25.00"
    data["accounts"][0]["stats"]["slots_played"] = 0
    data["accounts"][0]["stats"]["slots_won"] = 1
    path.write_text(json.dumps(data))
    with pytest.raises(SaveError):
        load(path)
    data["accounts"][0]["stats"]["slots_played"] = -1
    path.write_text(json.dumps(data))
    with pytest.raises(SaveError):
        load(path)


def test_rejects_invalid_saved_bet(tmp_path):
    path = tmp_path / "profile.json"
    save(Profile("Nova", "USD"), path)
    data = json.loads(path.read_text())
    data["accounts"][0]["custom_bets"]["blackjack"] = "-5.00"
    path.write_text(json.dumps(data))
    with pytest.raises(SaveError):
        load(path)


def test_multiple_accounts_round_trip_and_limit(tmp_path):
    path = tmp_path / "profile.json"
    store = AccountStore()
    for index in range(5):
        store.add(Profile(f"Guest {index}", "USD"))
    store.profiles[3].color_theme = "emerald"
    store.switch(3)
    save_store(store, path)
    loaded = load_store(path)
    assert len(loaded.profiles) == 5
    assert loaded.current.name == "Guest 3"
    assert loaded.current.color_theme == "emerald"
    with pytest.raises(ValueError, match="five"):
        loaded.add(Profile("Sixth", "USD"))
    loaded.delete(3)
    assert loaded.current.name == "Guest 4"
    loaded.edit(loaded.active, "Renamed", "EUR")
    assert loaded.current.currency == "EUR"


def test_version_two_save_migrates(tmp_path):
    path = tmp_path / "profile.json"
    save(Profile("Nova", "USD"), path)
    old = json.loads(path.read_text())["accounts"][0]
    old.pop("color_theme")
    old["version"] = 2
    path.write_text(json.dumps(old))
    assert load(path).color_theme == "night_gold"


def test_rejects_invalid_account_list(tmp_path):
    path = tmp_path / "profile.json"
    save(Profile("Nova", "USD"), path)
    original = json.loads(path.read_text())
    bad = dict(original)
    bad["accounts"] = original["accounts"] * 6
    path.write_text(json.dumps(bad))
    with pytest.raises(SaveError):
        load_store(path)
