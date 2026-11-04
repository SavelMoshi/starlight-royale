import asyncio
from decimal import Decimal

from textual.css.query import NoMatches
from textual.widgets import Button, Input, Select

from starlight_royale.app import Casino
from starlight_royale.persistence import load, load_store


async def ready(app, pilot, selector, kind):
    for _ in range(40):
        try:
            return app.query_one(selector, kind)
        except NoMatches:
            await pilot.pause(0.05)
    raise AssertionError(f"Control {selector} did not appear")


def test_saved_bets_keyboard_slots_and_roulette(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    monkeypatch.setattr("starlight_royale.app.slot_spin", lambda machine: ("💎",) * 5)
    monkeypatch.setattr("starlight_royale.app.roulette_spin", lambda: 0)

    async def walk():
        app = Casino(save_file=path)
        async with app.run_test(size=(100, 30)) as pilot:
            (await ready(app, pilot, "#name", Input)).value = "Demo"
            (await ready(app, pilot, "#create", Button)).press()
            (await ready(app, pilot, "#cashier", Button)).press()
            (await ready(app, pilot, "#amount", Input)).value = "10.00"
            (await ready(app, pilot, "#deposit", Button)).press()
            await pilot.pause()
            assert app.profile.cash == Decimal("15.00")
            await pilot.press("escape")
            await pilot.press("2")
            await ready(app, pilot, "#machine_royal_vault", Button)
            await pilot.press("v")
            custom = await ready(app, pilot, "#custom_amount", Input)
            custom.value = "1.00"
            custom.focus()
            await pilot.press("enter")
            await pilot.pause()
            assert app.profile.custom_bets["royal_vault"] == "1.00"
            await pilot.press("s")
            await pilot.pause(0.8)
            assert app.profile.chips == Decimal("89.00")
            assert app.profile.gameplay_net == Decimal("79.00")
            assert app.slot_tones["royal_vault"] == "win"
            assert len(app.slot_reels["royal_vault"]) == 5
            assert app.profile.last_bets["royal_vault"] == "1.00"
            await pilot.press("escape")
            await pilot.press("3")
            roulette = await ready(app, pilot, "#bet_type", Select)
            roulette.value = "black"
            custom = await ready(app, pilot, "#custom_amount", Input)
            custom.value = "2.00"
            custom.focus()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            assert app.profile.roulette_choice == "black"
            assert app.query_one("#bet_type", Select).value == "black"
            assert app.profile.last_bets["roulette"] == "2.00"
            assert app.profile.chips == Decimal("87.00")
            assert app.result_tones["roulette"] == "loss"
            assert "0 green" in app.results["roulette"]
            await pilot.press("escape")
            await pilot.press("2")
            await ready(app, pilot, "#resume_machine", Button)
            await pilot.press("s")
            await ready(app, pilot, "#spin_slots", Button)
            assert app.profile.slot_machine == "royal_vault"
            assert app.profile.bet_modes["royal_vault"] == "custom"
            assert app.bet_amount("royal_vault") == Decimal("1.00")
            assert load(path).roulette_choice == "black"

    asyncio.run(walk())


def test_small_terminal_message(tmp_path):
    async def walk():
        app = Casino(save_file=tmp_path / "profile.json")
        async with app.run_test(size=(60, 18)):
            assert app.query_one("#size-warning").display
            assert not app.query_one("#content").display

    asyncio.run(walk())


def test_leaving_slots_during_animation_keeps_result(tmp_path, monkeypatch):
    monkeypatch.setattr("starlight_royale.app.slot_spin", lambda machine: ("🍒",) * 5)

    async def walk():
        app = Casino(save_file=tmp_path / "profile.json")
        async with app.run_test(size=(100, 30)) as pilot:
            (await ready(app, pilot, "#name", Input)).value = "Demo"
            (await ready(app, pilot, "#create", Button)).press()
            (await ready(app, pilot, "#cashier", Button)).press()
            (await ready(app, pilot, "#amount", Input)).value = "5.00"
            (await ready(app, pilot, "#deposit", Button)).press()
            await pilot.press("escape")
            await pilot.press("2")
            (await ready(app, pilot, "#machine_gold_rush", Button)).press()
            (await ready(app, pilot, "#spin_slots", Button)).press()
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause(0.2)
            assert app.screen_name == "lobby"
            assert app.profile.gameplay_net == Decimal("0.19")

    asyncio.run(walk())


def test_lobby_return_line_only_once(tmp_path):
    async def walk():
        app = Casino(save_file=tmp_path / "profile.json")
        async with app.run_test(size=(100, 30)) as pilot:
            (await ready(app, pilot, "#name", Input)).value = "Demo"
            (await ready(app, pilot, "#create", Button)).press()
            (await ready(app, pilot, "#profile", Button)).press()
            await pilot.press("escape")
            await pilot.pause()
            assert len(app.query(".notice")) == 1
            (await ready(app, pilot, "#profile", Button)).press()
            await pilot.press("escape")
            await pilot.pause()
            assert len(app.query(".notice")) == 0

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


def test_account_management_and_theme(tmp_path):
    path = tmp_path / "profile.json"

    async def walk():
        app = Casino(save_file=path)
        async with app.run_test(size=(100, 30)) as pilot:
            (await ready(app, pilot, "#name", Input)).value = "First"
            (await ready(app, pilot, "#create", Button)).press()
            (await ready(app, pilot, "#settings", Button)).press()
            (await ready(app, pilot, "#theme_select", Select)).value = "emerald"
            await pilot.pause()
            assert app.profile.color_theme == "emerald"
            assert app.screen.has_class("theme_emerald")
            (await ready(app, pilot, "#accounts", Button)).press()
            (await ready(app, pilot, "#create_account", Button)).press()
            (await ready(app, pilot, "#name", Input)).value = "Second"
            (await ready(app, pilot, "#create", Button)).press()
            await pilot.pause()
            assert app.profile.name == "Second"
            (await ready(app, pilot, "#settings", Button)).press()
            (await ready(app, pilot, "#accounts", Button)).press()
            (await ready(app, pilot, "#switch_0", Button)).press()
            await pilot.pause()
            assert app.profile.name == "First"
            assert app.screen.has_class("theme_emerald")
            (await ready(app, pilot, "#edit_account", Button)).press()
            (await ready(app, pilot, "#edit_name", Input)).value = "Revised"
            (await ready(app, pilot, "#edit_currency", Select)).value = "EUR"
            (await ready(app, pilot, "#save_account", Button)).press()
            await pilot.pause()
            assert app.profile.name == "Revised"
            assert app.profile.currency == "EUR"
            (await ready(app, pilot, "#delete_account", Button)).press()
            (await ready(app, pilot, "#delete_confirm", Button)).press()
            await pilot.pause()
            assert app.profile.name == "Second"
            assert not app.screen.has_class("theme_emerald")
            assert len(load_store(path).profiles) == 1

    asyncio.run(walk())
