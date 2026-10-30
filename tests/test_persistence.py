import json
from decimal import Decimal

import pytest

from starlight_royale.persistence import SaveError, archive_corrupt, load, save
from starlight_royale.wallet import Profile


def test_round_trip_and_atomic_cleanup(tmp_path):
    path = tmp_path / "nested" / "profile.json"
    p = Profile("Nova", "GBP")
    p.deposit("12.50")
    p.wager("1.25", "roulette")
    p.settle(Decimal("1.25"), Decimal("0.00"), "roulette", False)
    save(p, path)
    assert load(path) == p
    assert list(path.parent.iterdir()) == [path]
    assert json.loads(path.read_text())["version"] == 1


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
    data["cash"] = "-1.00"
    path.write_text(json.dumps(data))
    with pytest.raises(SaveError):
        load(path)
    data["cash"] = "25.00"
    data["stats"]["slots_played"] = 0
    data["stats"]["slots_won"] = 1
    path.write_text(json.dumps(data))
    with pytest.raises(SaveError):
        load(path)
    data["stats"]["slots_played"] = -1
    path.write_text(json.dumps(data))
    with pytest.raises(SaveError):
        load(path)
