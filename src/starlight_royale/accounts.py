from dataclasses import dataclass, field

from .wallet import Profile

MAX_ACCOUNTS = 5


@dataclass
class AccountStore:
    profiles: list[Profile] = field(default_factory=list)
    active: int = 0

    @property
    def current(self) -> Profile | None:
        return self.profiles[self.active] if self.profiles else None

    def add(self, profile: Profile) -> None:
        if len(self.profiles) >= MAX_ACCOUNTS:
            raise ValueError("The casino holds up to five local accounts.")
        if any(existing.name.casefold() == profile.name.casefold() for existing in self.profiles):
            raise ValueError("Choose a different display name for this account.")
        self.profiles.append(profile)
        self.active = len(self.profiles) - 1

    def switch(self, index: int) -> None:
        if not 0 <= index < len(self.profiles):
            raise ValueError("Account does not exist.")
        self.active = index

    def edit(self, index: int, name: str, currency: str) -> None:
        if not 0 <= index < len(self.profiles):
            raise ValueError("Account does not exist.")
        if not 1 <= len(name.strip()) <= 24 or any(ord(c) < 32 for c in name):
            raise ValueError("Choose a name with 1–24 printable characters.")
        if currency not in ("USD", "EUR", "GBP"):
            raise ValueError("Invalid display currency.")
        if any(
            i != index and p.name.casefold() == name.strip().casefold()
            for i, p in enumerate(self.profiles)
        ):
            raise ValueError("Choose a different display name for this account.")
        self.profiles[index].name = name.strip()
        self.profiles[index].currency = currency

    def delete(self, index: int) -> None:
        if not 0 <= index < len(self.profiles):
            raise ValueError("Account does not exist.")
        self.profiles.pop(index)
        if self.profiles:
            self.active = min(self.active - (index < self.active), len(self.profiles) - 1)
        else:
            self.active = 0
