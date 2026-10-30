from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, Input, Select, Static

from .blackjack import Blackjack, hand_value
from .dealer import line
from .levels import level_for
from .money import money
from .persistence import SaveError, archive_corrupt, load, save, save_path
from .roulette import Bet, color, spin as roulette_spin
from .slots import NAMES, multiplier, spin as slot_spin
from .wallet import Profile


def paragraph(text: str, style: str = "copy") -> Static:
    return Static(text, classes=style, markup=False)


def reel_text(reels: tuple[str, str, str]) -> str:
    return "   ".join(f"{symbol} {NAMES[symbol]}" for symbol in reels)


class Casino(App):
    CSS = """
    Screen { background: #0c1324; color: #f3ead7; }
    #main { height: 1fr; }
    #brand { height: 3; content-align: center middle; color: #f4c36a;
             background: #172038; text-style: bold; border-bottom: solid #8e7044; }
    #content { height: 1fr; padding: 1 3; scrollbar-color: #a88650; }
    #status { height: 2; padding: 0 2; background: #172038; color: #f1d8a4; }
    #progress { height: 2; padding: 0 2; background: #172038; color: #b9d6de; }
    #size-warning { display: none; height: 1fr; content-align: center middle;
                    color: #f4c36a; text-align: center; }
    .title { color: #f4c36a; text-style: bold; margin-bottom: 1; }
    .copy { margin-bottom: 1; }
    .notice { color: #b9d6de; margin: 1 0; }
    .error { color: #ff9d88; margin: 1 0; }
    .result { color: #9fe0b8; text-style: bold; margin: 1 0; }
    .reels { text-align: center; color: #f4c36a; text-style: bold;
             background: #202a43; border: round #a88650; height: 4; margin: 1 0; }
    Button { width: 36; height: 1; min-height: 1; border: none; margin: 0 0 1 0;
             padding: 0 1; content-align: left middle; background: #253650; color: #f3ead7; }
    Button:hover, Button:focus { background: #765d38; color: #fff4dd; }
    Input, Select { width: 46; margin: 0 0 1 0; background: #1b2940;
                    border: tall #6f7890; color: #fff4dd; }
    Input:focus, Select:focus { border: tall #d3aa62; }
    """
    BINDINGS = [
        ("escape", "lobby", "Lobby"),
        ("q", "quit_app", "Quit"),
        ("1", "blackjack", "Blackjack"),
        ("2", "slots", "Slots"),
        ("3", "roulette", "Roulette"),
        ("4", "cashier", "Cashier"),
        ("5", "profile", "Profile"),
        ("6", "rules", "Rules"),
        ("7", "settings", "Settings"),
    ]

    def __init__(self, save_file: Path | None = None, **kwargs):
        super().__init__(**kwargs)
        self.save_file = save_file or save_path()
        self.profile: Profile | None = None
        self.screen_name = "lobby"
        self.notice = ""
        self.error = ""
        self.hand: Blackjack | None = None
        self.results = {"blackjack": "", "slots": "", "roulette": ""}
        self.last_reels = reel_text(("🍒", "🍋", "⭐"))
        self.spinning = False
        self.spin_frames = 0
        self.pending_reels = None
        self.pending_stake = None
        self.corrupt_reason = ""
        self.archived_save = ""

    def compose(self) -> ComposeResult:
        yield Static("✦  STARLIGHT ROYALE CASINO  ✦", id="brand", markup=False)
        yield VerticalScroll(id="content")
        yield Static("", id="status", markup=False)
        yield Static("", id="progress", markup=False)
        yield Static(
            "Enlarge the terminal to at least 70 columns × 22 rows.\n"
            "Your game is safe; controls will return when there is room.",
            id="size-warning",
            markup=False,
        )

    async def on_mount(self) -> None:
        try:
            self.profile = load(self.save_file)
        except FileNotFoundError:
            self.screen_name = "new"
        except SaveError as exc:
            self.corrupt_reason = str(exc)
            self.screen_name = "recover"
        await self.render_screen()
        self.check_size()

    def on_resize(self) -> None:
        self.check_size()

    def check_size(self) -> None:
        small = self.size.width < 70 or self.size.height < 22
        for selector in ("#brand", "#content", "#status", "#progress"):
            self.query_one(selector).display = not small
        self.query_one("#size-warning").display = small

    async def set_screen(self, name: str, notice: str = "") -> None:
        if self.profile is None and name not in ("new", "recover"):
            return
        self.screen_name = name
        self.notice = notice
        self.error = ""
        await self.render_screen()

    def persist(self) -> None:
        assert self.profile is not None
        save(self.profile, self.save_file)
        self.update_status()

    def update_status(self) -> None:
        if self.profile is None:
            self.query_one("#status", Static).update(
                "Create a profile to begin • Virtual play only"
            )
            self.query_one("#progress", Static).update("Cashier: free top-ups and 1:1 transfers")
            return
        p = self.profile
        level = level_for(p.cash)
        self.query_one("#status", Static).update(
            f"{p.name}   Cash {money(p.cash, p.symbol)}   Chips {money(p.chips, p.symbol)}"
            f"   Level {level.number}/30 · {level.rank}"
        )
        width = 24
        filled = round(level.progress * width)
        bar = "█" * filled + "░" * (width - filled)
        target = (
            "MAX LEVEL"
            if level.next_threshold is None
            else f"{money(level.threshold, p.symbol)} → {money(level.next_threshold, p.symbol)}"
        )
        self.query_one("#progress", Static).update(f"Level  [{bar}]  {target}")

    def dealer_line(self, kind: str) -> str:
        return line(kind) if self.profile and self.profile.dealer_dialogue else ""

    async def render_screen(self) -> None:
        content = self.query_one("#content", VerticalScroll)
        await content.remove_children()
        widgets = self.build_widgets()
        if self.error:
            widgets.insert(1, paragraph(self.error, "error"))
        elif self.notice:
            widgets.insert(1, paragraph(self.notice, "notice"))
        await content.mount(*widgets)
        content.scroll_home(animate=False)
        self.update_status()

    def build_widgets(self) -> list:
        screen = self.screen_name
        if screen == "new":
            return [
                paragraph("Your seat awaits", "title"),
                paragraph(
                    "Virtual play only. Start with 25.00 cash, then visit the cashier "
                    "to move cash into chips before betting."
                ),
                Input(placeholder="Display name (1–24 characters)", id="name"),
                Select(
                    [("Dollars ($)", "USD"), ("Euros (€)", "EUR"), ("Pounds (£)", "GBP")],
                    value="USD",
                    id="currency",
                ),
                Button("Create profile", id="create"),
            ]
        if screen == "recover":
            return [
                paragraph("Save needs attention", "title"),
                paragraph(self.corrupt_reason, "error"),
                paragraph(
                    "Your save was not changed. Choose a fresh profile to archive the "
                    "damaged file beside it, or quit and inspect it yourself."
                ),
                Button("Archive save and start fresh", id="archive"),
                Button("Quit", id="quit"),
            ]
        assert self.profile is not None
        p = self.profile
        if screen == "lobby":
            intro = self.notice or self.dealer_line("greeting")
            return [
                paragraph("The lobby", "title"),
                paragraph(intro, "notice"),
                paragraph(
                    "Choose a table • Tab/Shift+Tab and Enter, or press 1–7. "
                    "Esc returns here; Q quits."
                ),
                *[
                    Button(label, id=key)
                    for key, label in (
                        ("blackjack", "Blackjack 🃏"),
                        ("slots", "Slots 🎰"),
                        ("roulette", "Roulette 🎡"),
                        ("cashier", "Cashier 💰"),
                        ("profile", "Profile and Levels ⭐"),
                        ("rules", "Rules and Payouts 📖"),
                        ("settings", "Settings ⚙️"),
                        ("quit", "Quit 🚪"),
                    )
                ],
            ]
        if screen == "cashier":
            return [
                paragraph("Cashier 💰", "title"),
                paragraph(
                    "Virtual cash ↔ chips at 1:1. Deposit moves cash to chips; "
                    "withdraw moves chips to cash. Free top-ups add cash, never winnings."
                ),
                Input(placeholder="Amount, e.g. 10.00", id="amount"),
                Button("Deposit cash → chips", id="deposit"),
                Button("Withdraw chips → cash", id="withdraw"),
                Button("Free cash top-up", id="topup"),
                Button("← Lobby", id="lobby"),
            ]
        if screen == "profile":
            level = level_for(p.cash)
            next_text = (
                "Final level reached"
                if level.next_threshold is None
                else f"Next: {money(level.next_threshold, p.symbol)}"
            )
            stats = "\n".join(
                f"{game.title()}: {p.stats[game + '_won']} wins / "
                f"{p.stats[game + '_played']} played"
                for game in ("blackjack", "slots", "roulette")
            )
            return [
                paragraph("Profile and Levels ⭐", "title"),
                paragraph(
                    f"{p.name}  •  {p.currency} display  •  Level {level.number}: {level.rank}"
                ),
                paragraph(f"Current threshold: {money(level.threshold, p.symbol)}  •  {next_text}"),
                paragraph(
                    "Level follows current cash, not lifetime play. Depositing may lower it; "
                    "withdrawing or taking a free top-up may raise it."
                ),
                paragraph(
                    f"Gameplay net: {money(p.gameplay_net, p.symbol)} "
                    "(excludes cashier moves and free top-ups)"
                ),
                paragraph(stats),
                Button("← Lobby", id="lobby"),
            ]
        if screen == "blackjack":
            widgets = [paragraph("Blackjack 🃏", "title")]
            if self.hand is None:
                widgets += [
                    paragraph(
                        "Dealer stands on soft 17. Natural 3:2; ordinary win 1:1; "
                        "push returns stake. No split, insurance, or surrender."
                    ),
                    Input(placeholder="Wager in chips", id="amount"),
                    Button("Deal", id="deal"),
                ]
            else:
                hand = self.hand
                dealer_cards = (
                    "  ".join(map(str, hand.dealer)) if hand.result else str(hand.dealer[0]) + "  🂠"
                )
                dealer_value = str(hand_value(hand.dealer)[0]) if hand.result else "?"
                widgets += [
                    paragraph(f"Dealer: {dealer_cards}   ({dealer_value})"),
                    paragraph(
                        f"You:    {'  '.join(map(str, hand.player))}   "
                        f"({hand_value(hand.player)[0]})"
                    ),
                    paragraph(f"Wager: {money(hand.wager, p.symbol)}"),
                ]
                if hand.result:
                    widgets += [
                        paragraph(self.results["blackjack"], "result"),
                        Button("New hand", id="new_hand"),
                    ]
                else:
                    widgets += [Button("Hit [H]", id="hit"), Button("Stand [S]", id="stand")]
                    if hand.can_double and p.chips >= hand.wager:
                        widgets.append(Button("Double down [D]", id="double"))
            widgets.append(Button("← Lobby [Esc]", id="lobby"))
            return widgets
        if screen == "slots":
            return [
                paragraph("Slots 🎰", "title"),
                paragraph(
                    "Weighted reels: 🍒 30, 🍋 25, 🔔 20, ⭐ 15, 💎 10 per 100. "
                    "Each reel uses the same weights."
                ),
                paragraph(
                    "Three 🍒/🍋/🔔/⭐/💎: 3×/4×/6×/10×/20× total return. "
                    "Exactly two 🍒: 2×. All else: 0×."
                ),
                paragraph(self.last_reels, "reels"),
                paragraph(self.results["slots"], "result")
                if self.results["slots"]
                else paragraph("Choose a wager."),
                Input(placeholder="Wager in chips", id="amount"),
                Button("Spin [S]", id="spin_slots", disabled=self.spinning),
                Button("← Lobby [Esc]", id="lobby"),
            ]
        if screen == "roulette":
            return [
                paragraph("Roulette 🎡", "title"),
                paragraph(
                    "Single zero • one wager per spin. Red/black and odd/even 1:1; "
                    "dozens 2:1; one number 35:1. Zero loses except a bet on 0."
                ),
                Select(
                    [
                        ("Red", "red"),
                        ("Black", "black"),
                        ("Odd", "odd"),
                        ("Even", "even"),
                        ("1st dozen (1–12)", "dozen1"),
                        ("2nd dozen (13–24)", "dozen2"),
                        ("3rd dozen (25–36)", "dozen3"),
                        ("Single number (enter 0–36 below)", "number"),
                    ],
                    value="red",
                    id="bet_type",
                ),
                Input(placeholder="Number 0–36, for single-number bet", id="number"),
                Input(placeholder="Wager in chips", id="amount"),
                Button("Spin [S]", id="spin_roulette"),
                paragraph(self.results["roulette"], "result")
                if self.results["roulette"]
                else paragraph("Place a bet."),
                Button("← Lobby [Esc]", id="lobby"),
            ]
        if screen == "rules":
            return [
                paragraph("Rules and Payouts 📖", "title"),
                paragraph("All balances and wagers are virtual. Returns below include the wager."),
                paragraph(
                    "BLACKJACK 🃏  Aces count 1 or 11. Dealer stands on every 17, "
                    "including soft 17. Natural blackjack returns 2.5× stake (3:2 profit). "
                    "Ordinary win returns 2×. Push returns 1×. Loss returns 0×. "
                    "Double on the first two cards only: match your wager, draw one card, "
                    "then stand. Dealer natural is checked immediately. No split, insurance, "
                    "or surrender."
                ),
                paragraph(
                    "SLOTS 🎰  Independent weighted reels: 🍒 30%, 🍋 25%, 🔔 20%, "
                    "⭐ 15%, 💎 10%. Three of a kind pays 3×, 4×, 6×, 10×, 20× "
                    "respectively. Exactly two 🍒 pays 2×. Otherwise 0×."
                ),
                paragraph(
                    "ROULETTE 🎡  European single-zero wheel (0–36). Red/black and "
                    "odd/even return 2×; dozens return 3×; a straight number returns 36×. "
                    "Zero is green and loses all outside bets."
                ),
                Button("← Lobby", id="lobby"),
            ]
        if screen == "settings":
            return [
                paragraph("Settings ⚙️", "title"),
                paragraph(
                    f"Currency display: {p.currency} ({p.symbol}). Symbols only; "
                    "there is no exchange conversion."
                ),
                paragraph(
                    "Dealer dialogue uses short written lines; no network service is needed."
                ),
                Button(f"Dealer lines: {'On' if p.dealer_dialogue else 'Off'}", id="toggle_dealer"),
                Button("← Lobby", id="lobby"),
            ]
        return []

    async def show_error(self, message: str) -> None:
        self.error = message
        self.notice = ""
        await self.render_screen()

    def amount_input(self) -> str:
        return self.query_one("#amount", Input).value

    async def finish_hand(self) -> None:
        assert self.profile is not None and self.hand is not None
        hand = self.hand
        change = self.profile.settle(
            hand.wager,
            hand.returned,
            "blackjack",
            hand.result in ("win", "dealer bust", "blackjack"),
        )
        self.persist()
        self.results["blackjack"] = (
            f"{hand.result.title()} • wager {money(hand.wager, self.profile.symbol)} "
            f"• change {money(change, self.profile.symbol)}. "
            f"{self.dealer_line('push' if change == 0 else 'win' if change > 0 else 'loss')}"
        )
        await self.render_screen()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        key = event.button.id
        if key == "quit":
            self.exit()
            return
        if key == "archive":
            try:
                self.archived_save = str(archive_corrupt(self.save_file))
            except OSError as exc:
                await self.show_error(f"Could not archive save: {exc}")
                return
            await self.set_screen("new", f"Previous save archived at {self.archived_save}")
            return
        if key == "create":
            name = self.query_one("#name", Input).value.strip()
            currency = self.query_one("#currency", Select).value
            if not 1 <= len(name) <= 24 or any(ord(c) < 32 for c in name):
                await self.show_error("Choose a name with 1–24 printable characters.")
                return
            self.profile = Profile(name, str(currency))
            self.persist()
            await self.set_screen("lobby", "Welcome. Visit the cashier to deposit cash into chips.")
            return
        if key in (
            "lobby",
            "blackjack",
            "slots",
            "roulette",
            "cashier",
            "profile",
            "rules",
            "settings",
        ):
            await self.set_screen(key, self.dealer_line("lobby") if key == "lobby" else "")
            return
        assert self.profile is not None
        p = self.profile
        try:
            if key in ("deposit", "withdraw", "topup"):
                value = getattr(p, "top_up" if key == "topup" else key)(self.amount_input())
                self.persist()
                label = {"deposit": "Deposited", "withdraw": "Withdrew", "topup": "Free top-up"}[
                    key
                ]
                await self.set_screen("cashier", f"{label} {money(value, p.symbol)}.")
            elif key == "deal":
                stake = p.wager(self.amount_input(), "blackjack")
                self.hand = Blackjack(stake)
                self.persist()
                if self.hand.result:
                    await self.finish_hand()
                else:
                    await self.render_screen()
            elif key == "hit":
                assert self.hand is not None
                self.hand.hit()
                if self.hand.result:
                    await self.finish_hand()
                else:
                    await self.render_screen()
            elif key == "stand":
                assert self.hand is not None
                self.hand.stand()
                await self.finish_hand()
            elif key == "double":
                assert self.hand is not None
                if not self.hand.can_double:
                    raise ValueError("Double down is available only on the first two cards.")
                extra = p.wager(str(self.hand.wager))
                assert extra == self.hand.wager
                self.persist()
                self.hand.double_down()
                await self.finish_hand()
            elif key == "new_hand":
                self.hand = None
                self.results["blackjack"] = ""
                await self.render_screen()
            elif key == "toggle_dealer":
                p.dealer_dialogue = not p.dealer_dialogue
                self.persist()
                await self.render_screen()
            elif key == "spin_slots":
                if self.spinning:
                    return
                self.pending_stake = p.wager(self.amount_input(), "slots")
                self.persist()
                self.pending_reels = slot_spin()
                self.slot_change = p.settle(
                    self.pending_stake,
                    self.pending_stake * multiplier(self.pending_reels),
                    "slots",
                    multiplier(self.pending_reels) > 0,
                )
                self.persist()
                self.spinning = True
                self.spin_frames = 0
                self.set_timer(0.10, self.animate_slots)
                await self.render_screen()
            elif key == "spin_roulette":
                choice = self.query_one("#bet_type", Select).value
                if choice == "number":
                    raw = self.query_one("#number", Input).value.strip()
                    if not raw.isdecimal():
                        raise ValueError("Enter a whole number from 0 to 36.")
                    bet = Bet("number", int(raw))
                elif str(choice).startswith("dozen"):
                    bet = Bet("dozen", int(str(choice)[-1]))
                elif choice in ("red", "black"):
                    bet = Bet("color", choice)
                else:
                    bet = Bet("parity", choice)
                stake = p.wager(self.amount_input(), "roulette")
                self.persist()
                number = roulette_spin()
                returned = bet.returned(stake, number)
                change = p.settle(stake, returned, "roulette", returned > 0)
                self.persist()
                self.results["roulette"] = (
                    f"{bet.choice} • {number} {color(number)} • "
                    f"wager {money(stake, p.symbol)} • "
                    f"change {money(change, p.symbol)}. "
                    f"{self.dealer_line('win' if change > 0 else 'loss')}"
                )
                await self.render_screen()
        except ValueError as exc:
            await self.show_error(str(exc))

    async def animate_slots(self) -> None:
        self.spin_frames += 1
        if self.spin_frames < 5 and self.screen_name == "slots":
            self.query_one(".reels", Static).update(reel_text(slot_spin()))
            self.set_timer(0.10, self.animate_slots)
            return
        assert self.profile is not None and self.pending_reels and self.pending_stake
        p = self.profile
        reels = self.pending_reels
        stake = self.pending_stake
        change = self.slot_change
        self.last_reels = reel_text(reels)
        self.results["slots"] = (
            f"{multiplier(reels)}× return • wager {money(stake, p.symbol)} "
            f"• change {money(change, p.symbol)}. "
            f"{self.dealer_line('win' if change > 0 else 'push' if change == 0 else 'loss')}"
        )
        self.spinning = False
        self.pending_reels = None
        self.pending_stake = None
        if self.screen_name == "slots":
            await self.render_screen()

    async def action_lobby(self) -> None:
        await self.set_screen("lobby", self.dealer_line("lobby"))

    def action_quit_app(self) -> None:
        self.exit()

    async def action_blackjack(self) -> None:
        await self.set_screen("blackjack")

    async def action_slots(self) -> None:
        await self.set_screen("slots")

    async def action_roulette(self) -> None:
        await self.set_screen("roulette")

    async def action_cashier(self) -> None:
        await self.set_screen("cashier")

    async def action_profile(self) -> None:
        await self.set_screen("profile")

    async def action_rules(self) -> None:
        await self.set_screen("rules")

    async def action_settings(self) -> None:
        await self.set_screen("settings")

    def on_key(self, event) -> None:
        if isinstance(self.focused, Input):
            return
        keys = {
            "h": "hit",
            "s": "stand"
            if self.screen_name == "blackjack" and self.hand and self.hand.result is None
            else "spin_slots"
            if self.screen_name == "slots"
            else "spin_roulette"
            if self.screen_name == "roulette"
            else "",
            "d": "double",
        }
        key = keys.get(event.key)
        if key and self.screen_name in ("blackjack", "slots", "roulette"):
            try:
                button = self.query_one(f"#{key}", Button)
                if not button.disabled:
                    button.press()
            except NoMatches:
                pass
