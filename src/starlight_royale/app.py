from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button as TextualButton, Input, OptionList, Select, Static

from .accounts import AccountStore, MAX_ACCOUNTS
from .bets import range_for_cash, selected_bet
from .blackjack import Blackjack, hand_value
from .dealer import line
from .levels import level_for
from .money import amount, money
from .persistence import SaveError, archive_corrupt, load_store, save_store, save_path
from .roulette import Bet, color, spin as roulette_spin
from .slots import MACHINES, NAMES, multiplier, spin as slot_spin
from .themes import PALETTES, THEME_CSS
from .wallet import Profile


def paragraph(text: str, style: str = "copy") -> Static:
    return Static(text, classes=style, markup=False)


def reel_names(reels: tuple[str, ...]) -> str:
    return "  •  ".join(NAMES[symbol] for symbol in reels)


class Button(TextualButton):
    """Show a clear pointer for keyboard focus and mouse hover."""

    def __init__(self, label: str, **kwargs):
        self._plain_label = label
        self._hovered = False
        super().__init__(label, **kwargs)

    def _show_pointer(self) -> None:
        pointer = "☞" if self._hovered else "➤" if self.has_focus else " "
        self.label = f"{pointer} {self._plain_label}"

    def on_focus(self) -> None:
        self.label = f"{'☞' if self._hovered else '➤'} {self._plain_label}"

    def on_blur(self) -> None:
        self.label = f"{'☞' if self._hovered else ' '} {self._plain_label}"

    def on_enter(self) -> None:
        self._hovered = True
        self._show_pointer()

    def on_leave(self) -> None:
        self._hovered = False
        self._show_pointer()


class Casino(App):
    CSS = (
        """
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
    .win { color: #9fe0b8; text-style: bold; margin: 1 0; }
    .loss { color: #ff9d88; text-style: bold; margin: 1 0; }
    .push { color: #b9d6de; text-style: bold; margin: 1 0; }
    .reels { text-align: center; color: #f4c36a; text-style: bold;
             background: #202a43; border: round #a88650; height: 3; margin: 0 0 1 0; }
    .reels.moonlight_saloon { color: #a9d8ee; border: round #6a91ad; }
    .reels.royal_vault { color: #e3b7e9; border: round #9a73a7; }
    .bet-row { height: 2; }
    .bet-row Button { width: 25; margin: 0 2 0 0; }
    .custom-row { height: 3; }
    .custom-row Input { width: 34; }
    .custom-row Button { width: 22; margin: 1 0 0 1; }
    .tight { margin: 0; }
    .section { color: #f4c36a; text-style: bold; margin: 1 0; }
    .table { height: 5; border: round #8e7044; padding: 0 1; margin: 1 0; }
    .game-action { width: 32; margin: 1 0; text-style: bold; }
    .account-button { width: 60; }
    Button { width: 36; height: 1; min-height: 1; border: none; margin: 0 0 1 0;
             padding: 0 1; content-align: left middle; background: #253650; color: #f3ead7; }
    Button:hover, Button:focus { background: #765d38; color: #fff4dd; text-style: bold; }
    Input, Select { width: 46; margin: 0 0 1 0; background: #1b2940;
                    border: tall #6f7890; color: #fff4dd; }
    Input:hover, Select:hover, Input:focus, Select:focus {
        border: tall #d3aa62; background: #253650; }
    """
        + THEME_CSS
    )
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
        self.accounts = AccountStore()
        self.profile: Profile | None = None
        self.screen_name = "lobby"
        self.notice = ""
        self.error = ""
        self.hand: Blackjack | None = None
        self.results = {"blackjack": "", "roulette": ""}
        self.result_tones = {"blackjack": "push", "roulette": "push"}
        self.slot_results = dict.fromkeys(MACHINES, "")
        self.slot_tones = dict.fromkeys(MACHINES, "push")
        self.slot_reels = {key: machine.symbols for key, machine in MACHINES.items()}
        self.lobby_return_seen = False
        self.spinning = False
        self.spin_frames = 0
        self.pending_reels = None
        self.pending_stake = None
        self.pending_machine = None
        self.pending_profile = None
        self.corrupt_reason = ""
        self.archived_save = ""
        self._rendered_screen = None
        self._focus_after_render = None
        self.blackjack_frames: list[tuple[int, int, str]] = []
        self.blackjack_animating = False
        self.blackjack_frame = (0, 0, "")
        self.blackjack_profile: Profile | None = None
        self.blackjack_hand: Blackjack | None = None
        self.roulette_animating = False
        self.roulette_frame = 0
        self.roulette_profile: Profile | None = None

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
            self.accounts = load_store(self.save_file)
            self.profile = self.accounts.current
            if self.profile is None:
                self.screen_name = "new"
        except FileNotFoundError:
            self.screen_name = "new"
        except SaveError as exc:
            self.corrupt_reason = str(exc)
            self.screen_name = "recover"
        self.apply_theme()
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
        save_store(self.accounts, self.save_file)
        self.update_status()

    def apply_theme(self) -> None:
        for theme_key in PALETTES:
            self.screen.remove_class(f"theme_{theme_key}")
        self.screen.add_class(f"theme_{self.profile.color_theme if self.profile else 'night_gold'}")

    def reset_game_view(self) -> None:
        self.hand = None
        self.blackjack_animating = False
        self.blackjack_frames = []
        self.blackjack_profile = None
        self.blackjack_hand = None
        self.roulette_animating = False
        self.roulette_profile = None
        self.results = {"blackjack": "", "roulette": ""}
        self.result_tones = {"blackjack": "push", "roulette": "push"}
        self.slot_results = dict.fromkeys(MACHINES, "")
        self.slot_tones = dict.fromkeys(MACHINES, "push")
        self.slot_reels = {key: machine.symbols for key, machine in MACHINES.items()}

    def update_status(self) -> None:
        if self.profile is None:
            self.query_one("#status", Static).update(
                "Create a profile to begin • Virtual play only"
            )
            self.query_one("#progress", Static).update(
                "Cashier: free top-ups and 1:1 transfers\n"
                "↑↓←→ / WASD move  •  Enter choose  •  Tab leaves text fields"
            )
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
        self.query_one("#progress", Static).update(
            f"Level  [{bar}]  {target}\n↑↓←→ / WASD move  •  Enter choose  •  Esc lobby"
        )

    def dealer_line(self, kind: str) -> str:
        return line(kind) if self.profile and self.profile.dealer_dialogue else ""

    async def go_lobby(self) -> None:
        message = self.dealer_line("lobby") if not self.lobby_return_seen else ""
        self.lobby_return_seen = True
        await self.set_screen("lobby", message)

    def bet_key(self) -> str:
        assert self.profile is not None
        return self.profile.slot_machine if self.screen_name == "slots" else self.screen_name

    def bet_amount(self, key: str):
        assert self.profile is not None
        p = self.profile
        bet_range = range_for_cash(p.cash)
        stake = selected_bet(
            p.bet_modes[key], bet_range, p.chips, p.last_bets[key], p.custom_bets[key]
        )
        if stake is None:
            raise ValueError("Choose an affordable wager within this level's range.")
        return stake

    def bet_amount_or_none(self, key: str):
        try:
            return self.bet_amount(key)
        except ValueError:
            return None

    def wager(self, key: str, game: str):
        assert self.profile is not None
        stake = self.bet_amount(key)
        self.profile.wager(str(stake), game)
        self.profile.last_bets[key] = str(stake)
        self.persist()
        return stake

    def bet_widgets(self, key: str) -> list:
        assert self.profile is not None
        p = self.profile
        bet_range = range_for_cash(p.cash)
        selected = selected_bet(
            p.bet_modes[key], bet_range, p.chips, p.last_bets[key], p.custom_bets[key]
        )
        max_available = min(bet_range.maximum, p.chips)
        last_label = money(amount(p.last_bets[key]), p.symbol) if p.last_bets[key] else "—"
        custom_label = money(amount(p.custom_bets[key]), p.symbol) if p.custom_bets[key] else "—"
        return [
            paragraph("Wager", "section"),
            paragraph(
                f"Level {level_for(p.cash).number} wager range: "
                f"{money(bet_range.minimum, p.symbol)}–{money(bet_range.maximum, p.symbol)}. "
                "Choose a preset or save a custom amount.",
                "tight",
            ),
            Horizontal(
                Button(
                    f"Min {money(bet_range.minimum, p.symbol)}",
                    id="bet_min",
                    classes="chosen" if p.bet_modes[key] == "min" else "",
                ),
                Button(
                    f"Max {money(max_available, p.symbol)}",
                    id="bet_max",
                    classes="chosen" if p.bet_modes[key] == "max" else "",
                ),
                classes="bet-row",
            ),
            Horizontal(
                Button(
                    f"Last {last_label}",
                    id="bet_last",
                    disabled=not p.last_bets[key],
                    classes="chosen" if p.bet_modes[key] == "last" else "",
                ),
                Button(
                    f"Custom {custom_label}",
                    id="bet_custom",
                    disabled=not p.custom_bets[key],
                    classes="chosen" if p.bet_modes[key] == "custom" else "",
                ),
                classes="bet-row",
            ),
            Horizontal(
                Input(value=p.custom_bets[key], placeholder="Custom wager", id="custom_amount"),
                Button("Save custom", id="save_custom"),
                classes="custom-row",
            ),
            paragraph(
                f"Selected {p.bet_modes[key].title()}: "
                f"{money(selected, p.symbol) if selected is not None else 'unavailable'}"
                "  •  Visit the Cashier for more chips.",
                "tight",
            ),
        ]

    async def render_screen(self) -> None:
        content = self.query_one("#content", VerticalScroll)
        previous = (
            self.focused.id
            if self.focused is not None and self._rendered_screen == self.screen_name
            else None
        )
        await content.remove_children()
        widgets = self.build_widgets()
        if self.error:
            widgets.insert(1, paragraph(self.error, "error"))
        elif self.notice and self.screen_name != "lobby":
            widgets.insert(1, paragraph(self.notice, "notice"))
        await content.mount(*widgets)
        content.scroll_home(animate=False)
        self.update_status()
        requested_focus = self._focus_after_render
        self._focus_after_render = None
        defaults = {
            "new": "name",
            "recover": "archive",
            "lobby": "blackjack",
            "cashier": "amount",
            "blackjack": "deal"
            if self.hand is None
            else "deal_again"
            if self.hand.result and not self.blackjack_animating
            else "hit",
            "slots_select": "resume_machine",
            "slots": "spin_slots",
            "roulette": "bet_type",
            "settings": "theme_select",
        }
        for target in (requested_focus, previous, defaults.get(self.screen_name)):
            if not target:
                continue
            try:
                widget = content.query_one(f"#{target}")
                if widget.can_focus and not widget.disabled:
                    widget.focus()
                    break
            except NoMatches:
                continue
        self._rendered_screen = self.screen_name

    def blackjack_table(self) -> Static:
        assert self.hand is not None
        hand = self.hand
        if self.blackjack_animating:
            player_count, dealer_count, _ = self.blackjack_frame
        else:
            player_count = len(hand.player)
            dealer_count = len(hand.dealer) if hand.result else 1
        player_cards = "  ".join(map(str, hand.player[:player_count])) or "🂠"
        if dealer_count == 0:
            dealer_cards, dealer_value = "🂠  🂠", "?"
        elif dealer_count == 1:
            dealer_cards, dealer_value = f"{hand.dealer[0]}  🂠", "?"
        else:
            dealer_cards = "  ".join(map(str, hand.dealer[:dealer_count]))
            dealer_value = str(hand_value(hand.dealer[:dealer_count])[0])
        player_value = str(hand_value(hand.player[:player_count])[0]) if player_count else "?"
        return paragraph(
            f"Dealer  {dealer_cards}   ({dealer_value})\nYou     {player_cards}   ({player_value})",
            "table",
        )

    def build_widgets(self) -> list:
        screen = self.screen_name
        if screen == "new":
            return [
                paragraph(
                    f"Create account ({len(self.accounts.profiles) + 1}/{MAX_ACCOUNTS})", "title"
                ),
                paragraph(
                    "Virtual play only. Start with 25.00 cash, then visit the cashier "
                    "to move cash into chips before betting."
                ),
                Input(placeholder="Display name (1–24 characters)", id="name"),
                Select(
                    [("Dollars ($)", "USD"), ("Euros (€)", "EUR"), ("Pounds (£)", "GBP")],
                    value="USD",
                    allow_blank=False,
                    type_to_search=False,
                    id="currency",
                ),
                Button("Create account", id="create"),
                *([Button("← Accounts", id="accounts")] if self.accounts.profiles else []),
                Button("Quit [Q]", id="quit"),
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
            intro = self.notice or (
                self.dealer_line("greeting") if not self.lobby_return_seen else ""
            )
            return [
                paragraph("The lobby", "title"),
                *([paragraph(intro, "notice")] if intro else []),
                paragraph(
                    "Choose a table with ↑↓ or W/S, then press Enter. Tab and 1–7 also work."
                ),
                *[
                    Button(label, id=key)
                    for key, label in (
                        ("blackjack", "Blackjack 🃏"),
                        ("slots_select", "Slots 🎰"),
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
            bets = range_for_cash(p.cash)
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
                    f"Current wager range: {money(bets.minimum, p.symbol)}–"
                    f"{money(bets.maximum, p.symbol)} (also limited by available chips)."
                ),
                paragraph(
                    "Level follows current cash, not lifetime play. Depositing may lower it; "
                    "withdrawing or taking a free top-up may raise it. Wager limits follow it."
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
                        "push returns stake. No split, insurance, or surrender.",
                        "tight",
                    ),
                    Button(
                        "Deal cards",
                        id="deal",
                        disabled=self.bet_amount_or_none("blackjack") is None,
                        classes="game-action",
                    ),
                    *self.bet_widgets("blackjack"),
                ]
            else:
                hand = self.hand
                widgets += [
                    self.blackjack_table(),
                    paragraph(f"Wager  {money(hand.wager, p.symbol)}", "tight"),
                ]
                if self.blackjack_animating:
                    widgets.append(paragraph(self.blackjack_frame[2], "notice"))
                elif hand.result:
                    widgets += [
                        paragraph(self.results["blackjack"], self.result_tones["blackjack"]),
                        Button(
                            "Deal again",
                            id="deal_again",
                            disabled=self.bet_amount_or_none("blackjack") is None,
                            classes="game-action",
                        ),
                        Button("Change wager", id="new_hand"),
                    ]
                else:
                    widgets += [
                        Button("Hit", id="hit", classes="game-action"),
                        Button("Stand", id="stand"),
                    ]
                    if (
                        hand.can_double
                        and p.chips >= hand.wager
                        and hand.wager * 2 <= range_for_cash(p.cash).maximum
                    ):
                        widgets.append(Button("Double down", id="double"))
            widgets.append(Button("← Lobby", id="lobby"))
            return widgets
        if screen == "slots_select":
            return [
                paragraph("Choose a slot machine 🎰", "title"),
                paragraph("Five reels on every machine. Choose with arrows or WASD, then Enter."),
                Button(f"Resume {MACHINES[p.slot_machine].name}", id="resume_machine"),
                *[
                    widget
                    for machine in MACHINES.values()
                    for widget in (
                        Button(machine.name, id=f"machine_{machine.key}"),
                        paragraph(machine.tagline),
                    )
                ],
                Button("← Lobby", id="lobby"),
            ]
        if screen == "slots":
            machine = MACHINES[p.slot_machine]
            reels = self.slot_reels[machine.key]
            weights = "  ".join(
                f"{symbol} {weight}" for symbol, weight in zip(machine.symbols, machine.weights)
            )
            return [
                paragraph(f"{machine.name} Slots 🎰", "title"),
                paragraph(
                    f"3 / 4 / 5 matching: {machine.payouts[0]}× / "
                    f"{machine.payouts[1]}× / {machine.payouts[2]}×. "
                    f"Five 💎: {machine.jackpot}×. All else: 0×.",
                    "tight",
                ),
                paragraph("  ".join(reels), f"reels {machine.key}"),
                paragraph(self.slot_results[machine.key], f"{self.slot_tones[machine.key]} tight")
                if self.slot_results[machine.key]
                else paragraph("Choose a wager.", "tight"),
                Button(
                    "Spin reels",
                    id="spin_slots",
                    disabled=self.spinning or self.bet_amount_or_none(machine.key) is None,
                    classes="game-action",
                ),
                *self.bet_widgets(machine.key),
                paragraph(reel_names(reels)),
                paragraph(f"Independent reel weights / 100: {weights}"),
                Button("Change machine", id="slots_select"),
                Button("← Lobby", id="lobby"),
            ]
        if screen == "roulette":
            return [
                paragraph("Roulette 🎡", "title"),
                paragraph(
                    "Single zero • one wager per spin. Red/black and odd/even 1:1; "
                    "dozens 2:1; one number 35:1. Zero loses except a bet on 0.",
                    "tight",
                ),
                paragraph("Choose a bet", "section"),
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
                    value=p.roulette_choice,
                    allow_blank=False,
                    type_to_search=False,
                    id="bet_type",
                ),
                *(
                    [
                        Input(
                            value=str(p.roulette_number),
                            placeholder="Number 0–36",
                            id="number",
                        )
                    ]
                    if p.roulette_choice == "number"
                    else []
                ),
                paragraph(f"Wheel turning  {'◴◷◶◵'[self.roulette_frame % 4]}", "notice")
                if self.roulette_animating
                else paragraph(self.results["roulette"], self.result_tones["roulette"])
                if self.results["roulette"]
                else paragraph("Place a bet.", "tight"),
                Button(
                    "Spin wheel",
                    id="spin_roulette",
                    disabled=self.roulette_animating or self.bet_amount_or_none("roulette") is None,
                    classes="game-action",
                ),
                *self.bet_widgets("roulette"),
                Button("← Lobby", id="lobby"),
            ]
        if screen == "rules":
            machine_rules = [
                paragraph(
                    f"{machine.name}: {machine.payouts[0]}× / {machine.payouts[1]}× / "
                    f"{machine.payouts[2]}× for 3 / 4 / 5 matching reels; "
                    f"five 💎 pays {machine.jackpot}×. Weights / 100: "
                    + ", ".join(
                        f"{symbol} {weight}"
                        for symbol, weight in zip(machine.symbols, machine.weights)
                    )
                )
                for machine in MACHINES.values()
            ]
            return [
                paragraph("Rules and Payouts 📖", "title"),
                paragraph("All balances and wagers are virtual. Returns below include the wager."),
                paragraph(
                    "Wagers: minimum is 0.1% of the current cash level threshold, "
                    "rounded up to a cent (at least 0.01). Maximum is the next level "
                    "threshold; at level 30 it is 20,000,000. Available chips can lower "
                    "the amount you can actually place. Cashier moves can change your level."
                ),
                paragraph(
                    "BLACKJACK 🃏  Aces count 1 or 11. Dealer stands on every 17, "
                    "including soft 17. Natural blackjack returns 2.5× stake (3:2 profit). "
                    "Ordinary win returns 2×. Push returns 1×. Loss returns 0×. "
                    "Double on the first two cards only: match your wager, draw one card, "
                    "then stand. Dealer natural is checked immediately. No split, insurance, "
                    "or surrender."
                ),
                paragraph(
                    "SLOTS 🎰  Five independent reels per machine. The highest matching "
                    "symbol count determines the return. Fewer than three matches pays 0×."
                ),
                *machine_rules,
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
                paragraph("Casino color theme"),
                Select(
                    [(palette.name, key) for key, palette in PALETTES.items()],
                    value=p.color_theme,
                    allow_blank=False,
                    type_to_search=False,
                    id="theme_select",
                ),
                Button(f"Accounts ({len(self.accounts.profiles)}/{MAX_ACCOUNTS})", id="accounts"),
                Button("← Lobby", id="lobby"),
            ]
        if screen == "accounts":
            return [
                paragraph(f"Accounts ({len(self.accounts.profiles)}/{MAX_ACCOUNTS})", "title"),
                paragraph(
                    "Local accounts have separate balances, stats, wagers, and themes. "
                    "Move to an account and press Enter to switch."
                ),
                *[
                    Button(
                        f"{'● ' if index == self.accounts.active else '  '}{profile.name} "
                        f"· {profile.currency} · Level {level_for(profile.cash).number}",
                        id=f"switch_{index}",
                        classes="account-button",
                    )
                    for index, profile in enumerate(self.accounts.profiles)
                ],
                Button(
                    "Create account",
                    id="create_account",
                    disabled=len(self.accounts.profiles) >= MAX_ACCOUNTS,
                ),
                Button("Edit current account", id="edit_account"),
                Button("Delete current account", id="delete_account"),
                Button("← Settings", id="settings"),
            ]
        if screen == "edit":
            return [
                paragraph("Edit account", "title"),
                paragraph("Currency changes the display symbol only; balances stay the same."),
                Input(value=p.name, id="edit_name"),
                Select(
                    [("Dollars ($)", "USD"), ("Euros (€)", "EUR"), ("Pounds (£)", "GBP")],
                    value=p.currency,
                    allow_blank=False,
                    type_to_search=False,
                    id="edit_currency",
                ),
                Button("Save changes", id="save_account"),
                Button("Cancel", id="accounts"),
            ]
        if screen == "confirm_delete":
            return [
                paragraph("Delete account", "title"),
                paragraph(
                    f"Delete {p.name} and its local balances and stats? "
                    "This cannot be undone in the app."
                ),
                Button("Delete this account", id="delete_confirm"),
                Button("Cancel", id="accounts"),
            ]
        return []

    async def show_error(self, message: str) -> None:
        self.error = message
        self.notice = ""
        await self.render_screen()

    def amount_input(self) -> str:
        return self.query_one("#amount", Input).value

    async def finish_hand(self, render: bool = True) -> None:
        assert self.profile is not None and self.hand is not None
        hand = self.hand
        change = self.profile.settle(
            hand.wager,
            hand.returned,
            "blackjack",
            hand.result in ("win", "dealer bust", "blackjack"),
        )
        self.persist()
        self.result_tones["blackjack"] = "win" if change > 0 else "loss" if change < 0 else "push"
        self.results["blackjack"] = (
            f"{hand.result.title()} • wager {money(hand.wager, self.profile.symbol)} "
            f"• change {money(change, self.profile.symbol)}. "
            f"{self.dealer_line('push' if change == 0 else 'win' if change > 0 else 'loss')}"
        )
        if render:
            await self.render_screen()

    async def start_blackjack_animation(self, frames: list[tuple[int, int, str]]) -> None:
        self.blackjack_animating = True
        self.blackjack_frames = frames[1:]
        self.blackjack_frame = frames[0]
        self.blackjack_profile = self.profile
        self.blackjack_hand = self.hand
        await self.render_screen()
        self.set_timer(0.23, self.advance_blackjack)

    async def advance_blackjack(self) -> None:
        if not self.blackjack_animating:
            return
        if self.profile is not self.blackjack_profile or self.hand is not self.blackjack_hand:
            self.blackjack_animating = False
            self.blackjack_frames = []
            return
        if self.blackjack_frames:
            self.blackjack_frame = self.blackjack_frames.pop(0)
            if self.screen_name == "blackjack":
                await self.render_screen()
            self.set_timer(0.23, self.advance_blackjack)
            return
        self.blackjack_animating = False
        self.blackjack_profile = None
        self.blackjack_hand = None
        if self.screen_name == "blackjack":
            self._focus_after_render = "deal_again" if self.hand.result else "hit"
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
            try:
                self.accounts.add(Profile(name, str(currency)))
            except ValueError as exc:
                await self.show_error(str(exc))
                return
            self.profile = self.accounts.current
            self.reset_game_view()
            self.persist()
            self.apply_theme()
            await self.set_screen("lobby", "Welcome. Visit the cashier to deposit cash into chips.")
            return
        if key == "create_account":
            await self.set_screen("new")
            return
        if key and key.startswith("switch_"):
            self.accounts.switch(int(key.removeprefix("switch_")))
            self.profile = self.accounts.current
            self.reset_game_view()
            self.persist()
            self.apply_theme()
            await self.set_screen("accounts", f"Now playing as {self.profile.name}.")
            return
        if key == "edit_account":
            await self.set_screen("edit")
            return
        if key == "delete_account":
            await self.set_screen("confirm_delete")
            return
        if key == "save_account":
            try:
                self.accounts.edit(
                    self.accounts.active,
                    self.query_one("#edit_name", Input).value,
                    str(self.query_one("#edit_currency", Select).value),
                )
            except ValueError as exc:
                await self.show_error(str(exc))
                return
            self.persist()
            await self.set_screen("accounts", "Account updated.")
            return
        if key == "delete_confirm":
            self.accounts.delete(self.accounts.active)
            self.profile = self.accounts.current
            self.reset_game_view()
            self.persist()
            self.apply_theme()
            await self.set_screen("accounts" if self.profile else "new", "Account deleted.")
            return
        if key == "lobby":
            await self.go_lobby()
            return
        if key in (
            "blackjack",
            "slots_select",
            "roulette",
            "cashier",
            "profile",
            "rules",
            "settings",
            "accounts",
        ):
            await self.set_screen(key)
            return
        assert self.profile is not None
        p = self.profile
        if self.blackjack_animating and key in (
            "deal",
            "deal_again",
            "hit",
            "stand",
            "double",
            "new_hand",
        ):
            return
        try:
            if key and key.startswith("machine_"):
                p.slot_machine = key.removeprefix("machine_")
                self.persist()
                await self.set_screen("slots")
            elif key == "resume_machine":
                await self.set_screen("slots")
            elif key and key.startswith("bet_"):
                p.bet_modes[self.bet_key()] = key.removeprefix("bet_")
                self.persist()
                await self.render_screen()
            elif key == "save_custom":
                bet_key = self.bet_key()
                value = amount(self.query_one("#custom_amount", Input).value)
                range_for_cash(p.cash).check(value)
                p.custom_bets[bet_key] = str(value)
                p.bet_modes[bet_key] = "custom"
                self.persist()
                self._focus_after_render = {
                    "blackjack": "deal",
                    "roulette": "spin_roulette",
                }.get(self.screen_name, "spin_slots")
                await self.render_screen()
            elif key in ("deposit", "withdraw", "topup"):
                value = getattr(p, "top_up" if key == "topup" else key)(self.amount_input())
                self.persist()
                label = {"deposit": "Deposited", "withdraw": "Withdrew", "topup": "Free top-up"}[
                    key
                ]
                await self.set_screen("cashier", f"{label} {money(value, p.symbol)}.")
            elif key in ("deal", "deal_again"):
                stake = self.wager("blackjack", "blackjack")
                self.hand = Blackjack(stake)
                if self.hand.result:
                    await self.finish_hand(render=False)
                await self.start_blackjack_animation(
                    [
                        (1, 0, "The first card slides across the felt…"),
                        (1, 1, "The dealer takes a card…"),
                        (2, 1, "Your hand is in view…"),
                        (2, 2 if self.hand.result else 1, "Dealer checks the table…"),
                    ]
                )
            elif key == "hit":
                assert self.hand is not None
                self.hand.hit()
                if self.hand.result:
                    await self.finish_hand(render=False)
                player_count = len(self.hand.player)
                frames = [
                    (player_count - 1, 1, "A card comes your way…"),
                    (player_count, 1, "Card dealt."),
                ]
                if self.hand.result:
                    frames.append((player_count, 2, "The dealer reveals the hole card…"))
                await self.start_blackjack_animation(frames)
            elif key == "stand":
                assert self.hand is not None
                self.hand.stand()
                await self.finish_hand(render=False)
                count = len(self.hand.player)
                await self.start_blackjack_animation(
                    [
                        (count, 1, "Dealer turns the hole card…"),
                        (count, 2, "Dealer checks the total…"),
                    ]
                    + [
                        (count, shown, "Dealer draws another card…")
                        for shown in range(3, len(self.hand.dealer) + 1)
                    ]
                )
            elif key == "double":
                assert self.hand is not None
                if not self.hand.can_double:
                    raise ValueError("Double down is available only on the first two cards.")
                range_for_cash(p.cash).check(self.hand.wager * 2)
                extra = p.wager(str(self.hand.wager))
                assert extra == self.hand.wager
                self.persist()
                self.hand.double_down()
                await self.finish_hand(render=False)
                count = len(self.hand.player)
                await self.start_blackjack_animation(
                    [
                        (count - 1, 1, "One card, then the dealer plays…"),
                        (count, 1, "Your final card lands…"),
                        (count, 2, "Dealer turns the hole card…"),
                    ]
                    + [
                        (count, shown, "Dealer draws another card…")
                        for shown in range(3, len(self.hand.dealer) + 1)
                    ]
                )
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
                machine = MACHINES[p.slot_machine]
                self.pending_machine = machine.key
                self.pending_profile = p
                self.pending_stake = self.wager(machine.key, "slots")
                self.pending_reels = slot_spin(machine)
                self.slot_change = p.settle(
                    self.pending_stake,
                    self.pending_stake * multiplier(machine, self.pending_reels),
                    "slots",
                    multiplier(machine, self.pending_reels) > 0,
                )
                self.persist()
                self.spinning = True
                self.spin_frames = 0
                self.set_timer(0.10, self.animate_slots)
                await self.render_screen()
            elif key == "spin_roulette":
                if self.roulette_animating:
                    return
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
                stake = self.wager("roulette", "roulette")
                p.roulette_choice = str(choice)
                if choice == "number":
                    p.roulette_number = bet.choice
                self.persist()
                number = roulette_spin()
                returned = bet.returned(stake, number)
                change = p.settle(stake, returned, "roulette", returned > 0)
                self.persist()
                self.result_tones["roulette"] = "win" if change > 0 else "loss"
                self.results["roulette"] = (
                    f"{bet.choice} • {number} {color(number)} • "
                    f"wager {money(stake, p.symbol)} • "
                    f"change {money(change, p.symbol)}. "
                    f"{self.dealer_line('win' if change > 0 else 'loss')}"
                )
                self.roulette_animating = True
                self.roulette_frame = 0
                self.roulette_profile = p
                self.set_timer(0.13, self.animate_roulette)
                await self.render_screen()
        except ValueError as exc:
            await self.show_error(str(exc))

    async def animate_slots(self) -> None:
        self.spin_frames += 1
        assert self.pending_machine is not None
        machine = MACHINES[self.pending_machine]
        if (
            self.spin_frames < 5
            and self.screen_name == "slots"
            and self.profile is self.pending_profile
            and self.profile.slot_machine == machine.key
        ):
            self.query_one(".reels", Static).update("  ".join(slot_spin(machine)))
            self.set_timer(0.10, self.animate_slots)
            return
        assert self.pending_profile is not None and self.pending_reels and self.pending_stake
        p = self.pending_profile
        reels = self.pending_reels
        stake = self.pending_stake
        change = self.slot_change
        if self.profile is p:
            self.slot_reels[machine.key] = reels
            self.slot_tones[machine.key] = "win" if change > 0 else "loss"
            self.slot_results[machine.key] = (
                f"{multiplier(machine, reels)}× return • wager {money(stake, p.symbol)} "
                f"• change {money(change, p.symbol)}. "
                f"{line('win' if change > 0 else 'loss') if p.dealer_dialogue else ''}"
            )
        self.spinning = False
        self.pending_reels = None
        self.pending_stake = None
        self.pending_machine = None
        self.pending_profile = None
        if self.screen_name == "slots" and self.profile is p and p.slot_machine == machine.key:
            await self.render_screen()

    async def animate_roulette(self) -> None:
        if not self.roulette_animating:
            return
        if self.profile is not self.roulette_profile:
            self.roulette_animating = False
            self.roulette_profile = None
            return
        self.roulette_frame += 1
        if self.roulette_frame < 4:
            self.set_timer(0.13, self.animate_roulette)
        else:
            self.roulette_animating = False
            self.roulette_profile = None
            self._focus_after_render = "spin_roulette" if self.screen_name == "roulette" else None
        if self.screen_name == "roulette":
            await self.render_screen()

    async def action_lobby(self) -> None:
        await self.go_lobby()

    def action_quit_app(self) -> None:
        self.exit()

    async def action_blackjack(self) -> None:
        await self.set_screen("blackjack")

    async def action_slots(self) -> None:
        await self.set_screen("slots_select")

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

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "custom_amount":
            self.query_one("#save_custom", Button).press()

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "theme_select" and self.profile is not None:
            if event.value in PALETTES and self.profile.color_theme != event.value:
                self.profile.color_theme = str(event.value)
                self.persist()
                self.apply_theme()
        if event.select.id == "bet_type" and self.profile is not None:
            choice = event.value
            if choice in ("red", "black", "odd", "even", "dozen1", "dozen2", "dozen3", "number"):
                if self.profile.roulette_choice != choice:
                    self.profile.roulette_choice = choice
                    self.persist()
                    if self.screen_name == "roulette":
                        self._focus_after_render = "bet_type"
                        await self.render_screen()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "number" and self.profile is not None:
            raw = event.value.strip()
            if raw.isdecimal() and int(raw) <= 36 and self.profile.roulette_number != int(raw):
                self.profile.roulette_number = int(raw)
                self.persist()

    def move_focus(self, direction: str) -> None:
        content = self.query_one("#content", VerticalScroll)
        controls = [
            widget
            for widget in content.query("Button, Input, Select")
            if widget.can_focus and widget.display and not widget.disabled
        ]
        if not controls:
            return
        current = self.focused
        if current not in controls:
            controls[0 if direction in ("down", "right") else -1].focus()
            return
        center_x = current.region.x + current.region.width / 2
        center_y = current.region.y + current.region.height / 2
        if direction in ("left", "right"):
            row = [
                widget
                for widget in controls
                if abs(widget.region.y + widget.region.height / 2 - center_y) < 1
            ]
            if len(row) > 1:
                row.sort(key=lambda widget: widget.region.x)
                index = row.index(current)
                row[(index + (1 if direction == "right" else -1)) % len(row)].focus()
            else:
                index = controls.index(current)
                controls[(index + (1 if direction == "right" else -1)) % len(controls)].focus()
            return
        choices = []
        for widget in controls:
            if widget is current:
                continue
            dx = widget.region.x + widget.region.width / 2 - center_x
            dy = widget.region.y + widget.region.height / 2 - center_y
            primary, secondary = (dy, abs(dx)) if direction == "down" else (-dy, abs(dx))
            if primary > 0:
                choices.append((primary, secondary, widget))
        if choices:
            min(choices, key=lambda item: (item[0], item[1]))[2].focus()
        else:
            controls[0 if direction in ("down", "right") else -1].focus()

    def on_key(self, event) -> None:
        directions = {
            "up": "up",
            "w": "up",
            "down": "down",
            "s": "down",
            "left": "left",
            "a": "left",
            "right": "right",
            "d": "right",
        }
        if event.key in directions:
            expanded = next(
                (
                    selector
                    for selector in self.query_one("#content", VerticalScroll).query("Select")
                    if selector.expanded
                ),
                None,
            )
            if expanded is not None:
                if event.key in ("w", "s"):
                    overlay = expanded.query_one(OptionList)
                    if event.key == "w":
                        overlay.action_cursor_up()
                    else:
                        overlay.action_cursor_down()
                    event.stop()
                return
            if isinstance(self.focused, Input) and event.key not in ("up", "down"):
                return
            self.move_focus(directions[event.key])
            event.stop()
            return
        if isinstance(self.focused, Input):
            return
        if self.screen_name == "slots_select":
            keys = {
                "g": "machine_gold_rush",
                "m": "machine_moonlight_saloon",
                "v": "machine_royal_vault",
            }
        elif self.screen_name in ("blackjack", "slots", "roulette"):
            keys = {"m": "bet_min", "x": "bet_max", "l": "bet_last", "c": "bet_custom"}
            if self.screen_name == "blackjack":
                keys.update({"h": "hit", "n": "new_hand"})
            elif self.screen_name == "slots":
                keys["t"] = "slots_select"
        else:
            return
        if event.key == "c" and self.screen_name in ("blackjack", "slots", "roulette"):
            try:
                custom = self.query_one("#bet_custom", Button)
                if custom.disabled:
                    self.query_one("#custom_amount", Input).focus()
                    return
            except NoMatches:
                return
        key = keys.get(event.key)
        if key:
            try:
                button = self.query_one(f"#{key}", Button)
                if not button.disabled:
                    button.press()
            except NoMatches:
                pass
