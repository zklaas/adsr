"""Computer-vs-computer games from the command line, for balance testing."""
from __future__ import annotations

import random
from collections import Counter

from . import ai
from .cards import load_config, deck_summary
from .engine import TURN, Game


def attack_choices(g: Game, pid: int) -> int:
    """Distinct Attack sets `pid` could play (identical cards count once)."""
    hand = {c.id: c for c in g.players[pid].hand}
    return len({(hand[s[0]].kind, tuple(sorted((hand[i].value, hand[i].need, hand[i].damage)
                                                for i in s)))
                for s in g.legal_sets(pid, "A")})


def play(cfg, levels, seed=None, verbose=False, choices: list | None = None) -> Game:
    rng = random.Random(seed)
    names = [f"{lvl.title()} {i + 1}" for i, lvl in enumerate(levels)]
    g = Game(cfg, names, seed=rng.random(), first=rng.randrange(len(levels)))
    shown = 0
    while g.pending:
        pid, phase = g.pending
        if choices is not None and phase == TURN:
            choices.append(attack_choices(g, pid))
        g.apply(pid, ai.choose(g, pid, levels[pid], rng))
        if verbose:
            for line in g.log[shown:]:
                print(line)
            shown = len(g.log)
    return g


def run(games: int, levels: list[str], deck: str | None, seed=None, verbose=False) -> None:
    cfg = load_config(deck)
    print(deck_summary(cfg))
    print(f"Players: {', '.join(levels)}  ·  {games} game{'s' * (games != 1)}\n")
    rng = random.Random(seed)
    wins, turns, timeouts = Counter(), [], 0
    hits = tries = released = 0
    choices: list[int] = []
    for _ in range(games):
        order = levels[:]
        rng.shuffle(order)               # seat order shouldn't decide it
        g = play(cfg, order, rng.random(), verbose and games == 1, choices)
        turns.append(g.turn_no)
        timeouts += g.turn_no >= cfg.max_turns
        for w in g.winners:
            wins[order[w]] += 1 / len(g.winners)
        for line in g.log:
            if line.startswith("Attack roll"):
                tries += 1
                hits += line.endswith("hit.")
            elif "released!" in line:
                released += 1
                tries += 1
    counts = Counter(levels)
    print(f"{'level':8} {'seats':>5} {'win %':>7}")
    for lvl in sorted(counts, key=ai.LEVELS.index):
        share = 100 * wins[lvl] / (games * counts[lvl])
        print(f"{lvl:8} {counts[lvl]:>5} {share:>6.1f}%   (per seat)")
    turns.sort()
    print(f"\nturns per game: median {turns[len(turns) // 2]}, "
          f"min {turns[0]}, max {turns[-1]}; hit the turn limit {timeouts}×")
    if choices:
        none = 100 * sum(c == 0 for c in choices) / len(choices)
        print(f"choice: {sum(choices) / len(choices):.1f} Attack sets to pick from per turn; "
              f"no Attack possible on {none:.0f}% of turns")
    if tries:
        print(f"attacks: {100 * hits / tries:.0f}% hit, {100 * released / tries:.0f}% released")
