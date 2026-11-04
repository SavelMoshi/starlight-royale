from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    background: str
    surface: str
    text: str
    accent: str
    muted: str
    button: str
    focus: str


PALETTES = {
    "night_gold": Palette(
        "Night Gold", "#0c1324", "#172038", "#f3ead7", "#f4c36a", "#b9d6de", "#253650", "#765d38"
    ),
    "sapphire": Palette(
        "Sapphire", "#09172b", "#12294a", "#e5efff", "#83b9ff", "#a9cbe9", "#1c3e68", "#376d9f"
    ),
    "emerald": Palette(
        "Emerald", "#0b1d1b", "#16332d", "#e8f5ec", "#8bdab0", "#b3d5c5", "#235047", "#387b61"
    ),
    "amethyst": Palette(
        "Amethyst", "#1a1328", "#2c2040", "#f1eaff", "#cca4f2", "#d1bce5", "#44305e", "#735196"
    ),
    "ruby": Palette(
        "Ruby", "#25131b", "#3d1f2a", "#fff0ee", "#f19aaf", "#dfbec8", "#5a2d3d", "#92536a"
    ),
    "copper": Palette(
        "Copper", "#211912", "#38291d", "#fff1dd", "#e8ad71", "#d8c2a8", "#543b27", "#91613a"
    ),
    "teal": Palette(
        "Midnight Teal", "#0b1b25", "#12333e", "#e4f5f7", "#81d5d2", "#add4d6", "#1d4f58", "#347c81"
    ),
    "rose": Palette(
        "Rose Noir", "#231722", "#3a2739", "#fff0f8", "#e7a5cc", "#d8bdd1", "#573a54", "#8e5c82"
    ),
    "arctic": Palette(
        "Arctic", "#101c2c", "#1c3047", "#edf8ff", "#a5dbf5", "#b9d7e8", "#2d4964", "#537d9d"
    ),
    "slate": Palette(
        "Slate", "#161b22", "#262d35", "#f0f2f4", "#c5d0da", "#b3c0c9", "#3a4651", "#657784"
    ),
}


THEME_CSS = "\n".join(
    f"""
    Screen.theme_{key} {{ background: {p.background}; color: {p.text}; }}
    Screen.theme_{key} #brand, Screen.theme_{key} #status,
    Screen.theme_{key} #progress {{ background: {p.surface}; }}
    Screen.theme_{key} #brand {{ border-bottom: solid {p.accent}; }}
    Screen.theme_{key} #status {{ color: {p.accent}; }}
    Screen.theme_{key} #brand, Screen.theme_{key} .title {{ color: {p.accent}; }}
    Screen.theme_{key} .notice, Screen.theme_{key} #progress {{ color: {p.muted}; }}
    Screen.theme_{key} Button {{ background: {p.button}; color: {p.text}; }}
    Screen.theme_{key} Button:hover, Screen.theme_{key} Button:focus
        {{ background: {p.focus}; color: {p.text}; }}
    Screen.theme_{key} Input, Screen.theme_{key} Select
        {{ background: {p.surface}; color: {p.text}; border: tall {p.muted}; }}
    Screen.theme_{key} Input:focus, Screen.theme_{key} Select:focus
        {{ border: tall {p.accent}; }}
    Screen.theme_{key} .reels
        {{ background: {p.surface}; color: {p.accent}; border: round {p.accent}; }}
    Screen.theme_{key} .reels.moonlight_saloon
        {{ color: #a9d8ee; border: round #6a91ad; }}
    Screen.theme_{key} .reels.royal_vault
        {{ color: #e3b7e9; border: round #9a73a7; }}
    """
    for key, p in PALETTES.items()
)
