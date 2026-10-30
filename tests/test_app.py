import asyncio
from decimal import Decimal

from textual.widgets import Button, Input
from textual.css.query import NoMatches

from starlight_royale.app import Casino
from starlight_royale.persistence import load


async def ready(app, pilot, selector, kind):
    for _ in range(40):
        try:
            return app.query_one(selector, kind)
        except NoMatches:
            await pilot.pause(0.05)
    raise AssertionError(f"Control {selector} did not appear")


def test_profile_cashier_navigation_and_games(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    monkeypatch.setattr("starlight_royale.app.slot_spin", lambda: ("💎", "💎", "💎"))
    monkeypatch.setattr("starlight_royale.app.roulette_spin", lambda: 0)

    async def walk():
        app = Casino(save_file=path)
        async with app.run_test(size=(100, 30)) as pilot:
            assert app.screen_name == "new"
            (await ready(app, pilot, "#name", Input)).value = "Demo"
            (await ready(app, pilot, "#create", Button)).press()
            await pilot.pause()
            assert app.screen_name == "lobby"
            (await ready(app, pilot, "#cashier", Button)).press()
            await pilot.pause()
            (await ready(app, pilot, "#amount", Input)).value = "10.00"
            (await ready(app, pilot, "#deposit", Button)).press()
            await pilot.pause()
            assert app.profile.chips == Decimal("10.00")
            await pilot.press("escape")
            await pilot.pause()
            (await ready(app, pilot, "#slots", Button)).press()
            await pilot.pause()
            (await ready(app, pilot, "#amount", Input)).value = "1.00"
            (await ready(app, pilot, "#spin_slots", Button)).press()
            await pilot.pause(0.8)
            assert app.profile.chips == Decimal("29.00")
            assert app.profile.gameplay_net == Decimal("19.00")
            assert app.last_reels.count("Diamond") == 3
            await pilot.press("escape")
            await pilot.press("3")
            await pilot.pause()
            (await ready(app, pilot, "#amount", Input)).value = "1.00"
            (await ready(app, pilot, "#spin_roulette", Button)).press()
            await pilot.pause()
            assert "0 green" in app.results["roulette"]
            assert app.profile.chips == Decimal("28.00")
            await pilot.press("escape")
            await pilot.press("1")
            await pilot.pause()
            assert app.screen_name == "blackjack"
            assert load(path).gameplay_net == Decimal("18.00")

    asyncio.run(walk())


def test_small_terminal_message(tmp_path):
    async def walk():
        app = Casino(save_file=tmp_path / "profile.json")
        async with app.run_test(size=(60, 18)):
            assert app.query_one("#size-warning").display
            assert not app.query_one("#content").display

    asyncio.run(walk())


def test_leaving_slots_during_animation_keeps_result(tmp_path, monkeypatch):
    monkeypatch.setattr("starlight_royale.app.slot_spin", lambda: ("🍒", "🍒", "🍒"))

    async def walk():
        app = Casino(save_file=tmp_path / "profile.json")
        async with app.run_test(size=(100, 30)) as pilot:
            (await ready(app, pilot, "#name", Input)).value = "Demo"
            (await ready(app, pilot, "#create", Button)).press()
            await pilot.pause()
            (await ready(app, pilot, "#cashier", Button)).press()
            await pilot.pause()
            (await ready(app, pilot, "#amount", Input)).value = "5.00"
            (await ready(app, pilot, "#deposit", Button)).press()
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            (await ready(app, pilot, "#slots", Button)).press()
            await pilot.pause()
            (await ready(app, pilot, "#amount", Input)).value = "1.00"
            (await ready(app, pilot, "#spin_slots", Button)).press()
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause(0.2)
            assert app.screen_name == "lobby"
            assert app.profile.gameplay_net == Decimal("2.00")

    asyncio.run(walk())


def test_corrupt_save_recovery_preserves_original(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text("broken json")

    async def walk():
        app = Casino(save_file=path)
        async with app.run_test(size=(100, 30)) as pilot:
            assert app.screen_name == "recover"
            assert path.read_text() == "broken json"
            (await ready(app, pilot, "#archive", Button)).press()
            await pilot.pause()
            assert app.screen_name == "new"
            assert not path.exists()
            assert (tmp_path / "profile.json.corrupt").read_text() == "broken json"

    asyncio.run(walk())
