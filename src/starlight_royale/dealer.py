import secrets

LINES = {
    "greeting": ("Welcome to Starlight Royale.", "The tables are ready when you are."),
    "win": ("A fine hand. Well played.", "The house tips its hat."),
    "loss": ("A tough turn. Take your time.", "The next hand is a fresh one."),
    "push": ("Even at the table. Your wager returns.",),
    "lobby": ("The tables will be here when you return.",),
}


def line(kind: str, rng=None) -> str:
    return (rng or secrets.SystemRandom()).choice(LINES[kind])
