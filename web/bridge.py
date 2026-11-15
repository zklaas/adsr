"""The web version's link to ADSR's own engine and computer players.

Runs inside the browser (Pyodide).  The web page calls these with JSON strings;
the rules, the deck and the computer players are exactly the desktop version's
(app/cards.py, app/engine.py, app/ai.py), unchanged.
"""
import json
import random

from app import ai
from app.cards import ConfigError, load_config
from app.engine import Game, GameError


class Session:
    """One game.  seats: [{"name": ..., "kind": "human" | "computer", "level": ...}]."""

    def __init__(self, deck_file: str, seats_json: str):
        self.seats = json.loads(seats_json)
        cfg = load_config(deck_file)
        self.game = Game(cfg, [s["name"] for s in self.seats],
                         first=random.randrange(len(self.seats)))
        self.rng = random.Random()

    def view(self, pid: int) -> str:
        return json.dumps(self.game.view(pid if pid >= 0 else None))

    def pending(self) -> int:
        p = self.game.pending
        return -1 if p is None else p[0]

    def is_computer(self, pid: int) -> bool:
        return 0 <= pid < len(self.seats) and self.seats[pid]["kind"] == "computer"

    def act(self, pid: int, action_json: str) -> str:
        """Play a human's move; '' when it worked, else what was wrong."""
        try:
            self.game.apply(pid, json.loads(action_json))
            return ""
        except GameError as e:
            return str(e)

    def computer_step(self) -> int:
        """Let the computer player whose move it is make it; returns who moved (-1: none)."""
        pid = self.pending()
        if not self.is_computer(pid):
            return -1
        action = ai.choose(self.game, pid, self.seats[pid].get("level", "normal"), self.rng)
        self.game.apply(pid, action)
        return pid


def deck_info(deck_file: str) -> str:
    """Name, player limit and rules of a deck, for the setup screen."""
    try:
        cfg = load_config(deck_file)
    except ConfigError as e:
        return json.dumps({"error": str(e)})
    return json.dumps({"name": cfg.name, "max_players": cfg.max_players, **cfg.public()})
