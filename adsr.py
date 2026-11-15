#!/usr/bin/env python3
"""ADSR - a card game of Attack, Decay, Sustain and Release.

  adsr                         open the game table (PyQt6)
  adsr --deck my-deck.json     ...using another deck file
  adsr sim [N] [--players normal,hard,...] [--seed S] [-v]
                               play N computer-vs-computer games and report
                               win rates, game length and hit rates
  adsr rules                   print the rules
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "sim":
        ap = argparse.ArgumentParser(prog="adsr sim")
        ap.add_argument("games", nargs="?", type=int, default=200)
        ap.add_argument("--players", default="easy,normal,hard",
                        help="comma-separated levels, one per seat")
        ap.add_argument("--deck")
        ap.add_argument("--seed", type=int)
        ap.add_argument("-v", "--verbose", action="store_true",
                        help="print the log (single game only)")
        a = ap.parse_args(argv[1:])
        from app import ai, sim
        from app.cards import ConfigError
        levels = [s.strip().lower() for s in a.players.split(",") if s.strip()]
        bad = [lvl for lvl in levels if lvl not in ai.LEVELS]
        if bad:
            ap.error(f"unknown level(s) {bad}; choose from {', '.join(ai.LEVELS)}")
        try:
            sim.run(max(1, a.games), levels, a.deck, a.seed, a.verbose)
        except ConfigError as e:
            print(f"adsr: {e}", file=sys.stderr)
            return 1
        return 0
    if argv and argv[0] == "rules":
        with open(os.path.join(HERE, "RULES.md"), encoding="utf-8") as fh:
            print(fh.read())
        return 0

    ap = argparse.ArgumentParser(prog="adsr", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deck", help="deck file (default: deck.json beside adsr.py)")
    a = ap.parse_args(argv)
    from app.gui import run
    return run(a.deck)


if __name__ == "__main__":
    sys.exit(main())
