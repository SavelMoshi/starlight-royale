import json
import os
from pathlib import Path
import tempfile
from decimal import Decimal, InvalidOperation

from .accounts import AccountStore, MAX_ACCOUNTS
from .bets import BET_KEYS, BET_MODES
from .money import ZERO, amount
from .slots import MACHINES
from .themes import PALETTES
from .wallet import CURRENCIES, Profile

SAVE_VERSION = 3
STAT_KEYS = frozenset(Profile("x", "USD").stats)
ROULETTE_CHOICES = ("red", "black", "odd", "even", "dozen1", "dozen2", "dozen3", "number")


class SaveError(Exception):
    pass


def save_path() -> Path:
    override = os.environ.get("STARLIGHT_SAVE")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return root / "starlight-royale" / "profile.json"


def _balance(value: object) -> Decimal:
    if value == "0.00":
        return ZERO
    if not isinstance(value, str):
        raise SaveError("A balance is missing or invalid.")
    try:
        parsed = amount(value)
    except ValueError as exc:
        raise SaveError("A balance is missing or invalid.") from exc
    if str(parsed) != value:
        raise SaveError("Balances must use two decimal places.")
    return parsed


def _saved_amounts(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != set(BET_KEYS):
        raise SaveError("Invalid saved wagers.")
    for saved in value.values():
        if not isinstance(saved, str):
            raise SaveError("Invalid saved wagers.")
        if saved:
            try:
                if str(amount(saved)) != saved:
                    raise ValueError
            except ValueError as exc:
                raise SaveError("Invalid saved wagers.") from exc
    return value


def _profile(data: object, version: int) -> Profile:
    if not isinstance(data, dict):
        raise SaveError("Invalid account data.")
    name = data["name"]
    currency = data["currency"]
    stats = data["stats"]
    if (
        not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 24
        or any(ord(c) < 32 for c in name)
    ):
        raise SaveError("Invalid display name.")
    if currency not in CURRENCIES:
        raise SaveError("Invalid display currency.")
    if (
        not isinstance(stats, dict)
        or set(stats) != STAT_KEYS
        or any(type(v) is not int or v < 0 for v in stats.values())
    ):
        raise SaveError("Invalid game statistics.")
    if any(
        stats[f"{game}_won"] > stats[f"{game}_played"]
        for game in ("blackjack", "slots", "roulette")
    ):
        raise SaveError("Game wins exceed games played.")
    net = data["gameplay_net"]
    if not isinstance(net, str):
        raise SaveError("Invalid gameplay net.")
    try:
        net_value = Decimal(net)
        if not net_value.is_finite() or net_value.as_tuple().exponent != -2:
            raise ValueError
    except (InvalidOperation, ValueError) as exc:
        raise SaveError("Invalid gameplay net.") from exc
    dialogue = data["dealer_dialogue"]
    if type(dialogue) is not bool:
        raise SaveError("Invalid settings.")
    if version == 1:
        last_bets = dict.fromkeys(BET_KEYS, "")
        custom_bets = dict.fromkeys(BET_KEYS, "")
        bet_modes = dict.fromkeys(BET_KEYS, "min")
        roulette_choice, roulette_number, slot_machine = "red", 0, "gold_rush"
    else:
        last_bets = _saved_amounts(data["last_bets"])
        custom_bets = _saved_amounts(data["custom_bets"])
        bet_modes = data["bet_modes"]
        if (
            not isinstance(bet_modes, dict)
            or set(bet_modes) != set(BET_KEYS)
            or any(value not in BET_MODES for value in bet_modes.values())
        ):
            raise SaveError("Invalid bet selections.")
        roulette_choice = data["roulette_choice"]
        roulette_number = data["roulette_number"]
        slot_machine = data["slot_machine"]
        if roulette_choice not in ROULETTE_CHOICES:
            raise SaveError("Invalid roulette selection.")
        if type(roulette_number) is not int or not 0 <= roulette_number <= 36:
            raise SaveError("Invalid roulette number.")
        if slot_machine not in MACHINES:
            raise SaveError("Invalid slot machine.")
    color_theme = data["color_theme"] if version == 3 else "night_gold"
    if color_theme not in PALETTES:
        raise SaveError("Invalid color theme.")
    return Profile(
        name.strip(),
        currency,
        _balance(data["cash"]),
        _balance(data["chips"]),
        net_value,
        stats,
        dialogue,
        last_bets,
        custom_bets,
        bet_modes,
        roulette_choice,
        roulette_number,
        slot_machine,
        color_theme,
    )


def load_store(path: Path | None = None) -> AccountStore:
    path = path or save_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") not in (1, 2, SAVE_VERSION):
            raise SaveError("Unsupported save version.")
        version = data["version"]
        if version < 3:
            return AccountStore([_profile(data, version)], 0)
        raw_accounts = data["accounts"]
        active = data["active"]
        if (
            not isinstance(raw_accounts, list)
            or len(raw_accounts) > MAX_ACCOUNTS
            or type(active) is not int
            or not 0 <= active < max(1, len(raw_accounts))
        ):
            raise SaveError("Invalid account list.")
        profiles = [_profile(raw, version) for raw in raw_accounts]
        if len({p.name.casefold() for p in profiles}) != len(profiles):
            raise SaveError("Duplicate account names.")
        return AccountStore(profiles, active)
    except FileNotFoundError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SaveError(f"Could not read save: {exc}") from exc


def load(path: Path | None = None) -> Profile:
    current = load_store(path).current
    if current is None:
        raise SaveError("No account is saved yet.")
    return current


def _profile_data(profile: Profile) -> dict:
    return {
        "name": profile.name,
        "currency": profile.currency,
        "cash": str(profile.cash),
        "chips": str(profile.chips),
        "gameplay_net": str(profile.gameplay_net),
        "stats": profile.stats,
        "dealer_dialogue": profile.dealer_dialogue,
        "last_bets": profile.last_bets,
        "custom_bets": profile.custom_bets,
        "bet_modes": profile.bet_modes,
        "roulette_choice": profile.roulette_choice,
        "roulette_number": profile.roulette_number,
        "slot_machine": profile.slot_machine,
        "color_theme": profile.color_theme,
    }


def save_store(store: AccountStore, path: Path | None = None) -> None:
    path = path or save_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": SAVE_VERSION,
        "active": store.active,
        "accounts": [_profile_data(profile) for profile in store.profiles],
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=".profile-", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save(profile: Profile, path: Path | None = None) -> None:
    save_store(AccountStore([profile], 0), path)


def archive_corrupt(path: Path | None = None) -> Path:
    path = path or save_path()
    candidate = path.with_name(path.name + ".corrupt")
    index = 1
    while candidate.exists():
        candidate = path.with_name(path.name + f".corrupt-{index}")
        index += 1
    os.replace(path, candidate)
    return candidate
