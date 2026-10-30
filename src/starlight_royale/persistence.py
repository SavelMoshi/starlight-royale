import json
import os
from pathlib import Path
import tempfile

from .money import amount, ZERO
from .wallet import CURRENCIES, Profile

SAVE_VERSION = 1
STAT_KEYS = frozenset(Profile("x", "USD").stats)


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


def _balance(value: object) -> object:
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


def load(path: Path | None = None) -> Profile:
    path = path or save_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
            raise SaveError("Unsupported save version.")
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
        net = data["gameplay_net"]
        if not isinstance(net, str):
            raise SaveError("Invalid gameplay net.")
        from decimal import Decimal, InvalidOperation

        try:
            net_value = Decimal(net)
            if not net_value.is_finite() or net_value.as_tuple().exponent != -2:
                raise ValueError
        except (InvalidOperation, ValueError) as exc:
            raise SaveError("Invalid gameplay net.") from exc
        dialogue = data["dealer_dialogue"]
        if type(dialogue) is not bool:
            raise SaveError("Invalid settings.")
        return Profile(
            name.strip(),
            currency,
            _balance(data["cash"]),
            _balance(data["chips"]),
            net_value,
            stats,
            dialogue,
        )
    except FileNotFoundError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SaveError(f"Could not read save: {exc}") from exc


def save(profile: Profile, path: Path | None = None) -> None:
    path = path or save_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": SAVE_VERSION,
        "name": profile.name,
        "currency": profile.currency,
        "cash": str(profile.cash),
        "chips": str(profile.chips),
        "gameplay_net": str(profile.gameplay_net),
        "stats": profile.stats,
        "dealer_dialogue": profile.dealer_dialogue,
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


def archive_corrupt(path: Path | None = None) -> Path:
    path = path or save_path()
    candidate = path.with_name(path.name + ".corrupt")
    index = 1
    while candidate.exists():
        candidate = path.with_name(path.name + f".corrupt-{index}")
        index += 1
    os.replace(path, candidate)
    return candidate
