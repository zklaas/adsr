"""Tests for the ADSR rules engine, deck loading and computer players.

    python3 -m unittest test_engine
"""
import json
import random
import unittest

from app import ai
from app.cards import (DECKS_DIR, DEFAULT_DECK, Card, ConfigError, build_deck, bundled_decks, load_config,
                       parse_config)
from app.engine import ASSIST, DEFEND, OVER, SUSTAIN, TURN, Game, GameError


def deck(**rules):
    """A tiny deterministic deck: two Kinds, a few of each card."""
    return parse_config({
        "name": "test",
        "rules": {"hand_size": 7, **rules},
        "kinds": [{"name": "Sine"}, {"name": "Saw"}],
        "cards": {
            "A": [{"value": 70, "need": 1, "damage": 6, "count": 3},
                  {"value": 80, "need": 2, "damage": 8, "count": 2}],
            "S": [{"value": 60, "need": 1, "count": 4}],
            "D": [{"value": 40, "need": 1, "count": 4}],
            "R": [{"value": 60, "need": 1, "count": 1}],
        },
    })


def rig(game, hands):
    """Give each player an exact hand built from (kind, type, value, need, damage)."""
    nid = 1000
    for p, spec in zip(game.players, hands):
        p.hand = []
        for kind, typ, value, need, dmg in spec:
            p.hand.append(Card(nid, kind, typ, value, need, dmg))
            nid += 1


def rolls(game, *values):
    seq = iter(values)
    game.roll = lambda: next(seq)


def ids(game, pid, typ, value=None):
    return [c.id for c in game.players[pid].hand
            if c.type == typ and (value is None or c.value == value)]


class DeckTests(unittest.TestCase):
    def test_romeo_juliet_deck(self):
        cfg = load_config(dict(bundled_decks())["Romeo and Juliet (2x)"])
        self.assertEqual(len(cfg.kinds), 18)
        fams = ("Montagues", "Capulets", "Citizens of Verona", "Servants", "Church Figures")
        self.assertEqual([sum(k.family == f for k in cfg.kinds) for f in fams], [4, 4, 4, 4, 2])
        self.assertEqual(cfg.family_kinds(0), ["Romeo", "Lord Montague", "Lady Montague",
                                               "Benvolio"])
        cards = build_deck(cfg)
        self.assertEqual(len(cards), 320)
        self.assertEqual(len({c.id for c in cards}), 320)
        per = {t: sum(c.type == t for c in cards if c.kind == 0) for t in "ADSR"}
        self.assertEqual(per, {"A": 6, "S": 3, "D": 5, "R": 2})
        self.assertEqual(max(c.need for c in cards), 2)          # a 2x deck: no ×3 sets
        for f in fams:                                           # every family the same size
            self.assertEqual(sum(cfg.kinds[c.kind].family == f for c in cards), 64)
        self.assertEqual((cfg.name, cfg.hand_size, cfg.draw_limit, cfg.swap_limit),
                         ("Romeo and Juliet (2x)", 16, 1, 2))

    def test_3x_deck(self):
        cfg = load_config(dict(bundled_decks())["Sound waves (3x)"])
        self.assertEqual(len(cfg.kinds), 10)
        self.assertEqual({k.family for k in cfg.kinds}, {"Smooth", "Edged", "Toothed"})
        self.assertEqual(cfg.family_kinds(0), ["Sine", "Triangle", "Cosine"])
        cards = build_deck(cfg)
        self.assertEqual(len(cards), 140)
        per = {t: sum(c.type == t for c in cards if c.kind == 0) for t in "ADSR"}
        self.assertEqual(per, {"A": 7, "S": 2, "D": 4, "R": 1})
        self.assertEqual(len({c.id for c in cards}), 140)
        self.assertEqual(sum(c.need == 3 for c in cards), 10)
        self.assertEqual((cfg.hand_size, cfg.draw_limit, cfg.swap_limit), (14, 1, 2))

    def test_default_deck(self):
        cfg = load_config()
        self.assertEqual(cfg.name, "Captains (1x)")
        self.assertEqual(len(cfg.kinds), 20)
        self.assertEqual({k.glyph for k in cfg.kinds},
                         {"anchor", "bars", "wings", "armband", "badge"})
        cards = build_deck(cfg)
        self.assertEqual(len(cards), 420)
        per = {t: sum(c.type == t for c in cards if c.kind == 0) for t in "ADSR"}
        self.assertEqual(per, {"A": 6, "S": 8, "D": 5, "R": 2})
        self.assertEqual(max(c.need for c in cards), 1)          # single Attacks only

    def test_infielders_deck(self):
        cfg = load_config(dict(bundled_decks())["Infielders (2x sustains, 1x attacks)"])
        self.assertEqual(len(cfg.kinds), 35)
        self.assertEqual(len({k.family for k in cfg.kinds}), 5)
        cards = build_deck(cfg)
        self.assertEqual(len(cards), 425)
        types = {}                                               # position -> card types
        for c in cards:
            pos = cfg.kinds[c.kind].name.rsplit("(", 1)[1].rstrip(")")
            types.setdefault(pos, set()).add(c.type)
        self.assertEqual(types, {"1B": {"A"}, "C": {"A"}, "2B": {"S"}, "SS": {"S"},
                                 "3B": {"S"}, "P": {"D"}, "OF": {"R"}})
        self.assertEqual(max(c.need for c in cards if c.type == "A"), 1)
        self.assertEqual(max(c.need for c in cards if c.type == "S"), 2)

    def test_bundled_decks(self):
        import os
        decks = bundled_decks()
        on_disk = [f for f in os.listdir(DECKS_DIR) if f.endswith(".json")]
        self.assertEqual(len(decks), 1 + len(on_disk), "a file in decks/ failed to load")
        self.assertEqual(decks[0], ("Captains (1x)", DEFAULT_DECK))
        cfg = load_config(dict(decks)["Rock Paper Scissors Lizard Alien (3x)"])
        self.assertEqual(len(cfg.kinds), 15)
        self.assertEqual({k.family for k in cfg.kinds},
                         {"Rock", "Paper", "Scissors", "Lizard", "Alien"})
        self.assertEqual(len(build_deck(cfg)), 210)
        self.assertEqual((cfg.hand_size, cfg.draw_limit, cfg.swap_limit), (14, 1, 2))
        cfg = load_config(dict(decks)["Hatfields and McCoys (3x)"])
        self.assertEqual([sum(k.family == f for k in cfg.kinds) for f in ("Hatfield", "McCoy")],
                         [10, 10])
        self.assertEqual({k.glyph for k in cfg.kinds}, {"hatfield", "mccoy"})
        self.assertEqual(len(build_deck(cfg)), 280)
        cfg = load_config(dict(decks)["Balance of Power (3x)"])
        self.assertEqual([sum(k.family == f for k in cfg.kinds) for f in
                          ("Antiquity", "Renaissance", "Grand Alliance", "Concert of Europe",
                           "Between Empires")], [4, 4, 4, 4, 4])
        self.assertEqual(cfg.wild, "SD")
        cards = build_deck(cfg)
        self.assertEqual(len(cards), 280)
        self.assertEqual([sum(c.type == t for c in cards) for t in "ADSR"], [140, 60, 60, 20])

    def test_bad_configs(self):
        base = {"kinds": ["X"], "cards": {"A": [{"value": 50, "damage": 3}]}}
        parse_config(base)
        for bad in (
            {"kinds": []},
            {**base, "cards": {"A": [{"value": 150, "damage": 3}]}},
            {**base, "cards": {"A": [{"value": 50}]}},             # no damage
            {**base, "cards": {"S": [{"value": 50}]}},             # no Attack
            {**base, "kinds": [{"name": "X", "cards": {"A": [{"value": 50, "damage": 3,
                                                              "count": 0}]}}]},  # no cards
            {**base, "cards": {"A": [{"value": 50, "damage": 3}], "Q": []}},
            {**base, "rules": {"bogus": 1}},
            {**base, "kinds": ["X", "x"]},
            {**base, "kinds": [{"name": "X", "glyph": "zigzag"}]},
        ):
            with self.assertRaises(ConfigError, msg=json.dumps(bad)):
                parse_config(bad)

    def test_per_kind_cards_and_letter_glyph(self):
        cfg = parse_config({
            "kinds": ["Sine", {"name": "Fuzz", "cards": {"A": [{"value": 50, "damage": 9, "count": 4}]}}],
            "cards": {"A": [{"value": 50, "damage": 3}]}})
        self.assertEqual(cfg.kinds[0].glyph, "sine")
        self.assertEqual(cfg.kinds[1].glyph, "letter")
        noise = [c for c in build_deck(cfg) if c.kind == 1]
        self.assertEqual((len(noise), noise[0].damage), (4, 9))


class FamilyTests(unittest.TestCase):
    def setUp(self):
        cfg = parse_config({
            "rules": {"hand_size": 7},
            "kinds": [{"name": "Sine", "family": "Smooth"}, {"name": "Cosine", "family": "Smooth"},
                      {"name": "Square", "family": "Edged"}],
            "cards": {"A": [{"value": 70, "damage": 6, "count": 4}],
                      "D": [{"value": 40, "count": 3}], "R": [{"value": 60, "count": 2}]}})
        self.g = Game(cfg, ["A", "B"], seed=1, first=0)
        rig(self.g, [[(0, "A", 70, 1, 6)],
                     [(1, "D", 40, 1, 0), (1, "D", 40, 1, 0), (0, "D", 40, 1, 0), (2, "R", 60, 1, 0)]])

    def test_family_members_answer_but_sets_stay_one_kind(self):
        g = self.g
        g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 1})
        self.assertEqual(g.pending, (1, DEFEND))
        hand = g.players[1].hand
        cos = [c.id for c in hand if c.kind == 1]
        sine = [c.id for c in hand if c.kind == 0]
        square = [c.id for c in hand if c.kind == 2]
        # Cosine Decay answers a Sine Attack; Square (Edged) does not
        self.assertEqual(sorted(g.legal_sets(1, "D", 0)), sorted([(cos[0],), (cos[1],), (sine[0],)]))
        self.assertEqual(g.legal_sets(1, "R", 0), [])
        with self.assertRaises(GameError):
            g.apply(1, {"type": "respond", "cards": square})
        with self.assertRaises(GameError):          # mixed Kinds in one set
            g.apply(1, {"type": "respond", "cards": [cos[0], sine[0]]})
        rolls(g, 99)
        g.apply(1, {"type": "respond", "cards": [cos[0]]})
        self.assertEqual(g.last.plays[0].shift, 10)

    def test_no_family_means_own_kind(self):
        cfg = deck()
        self.assertFalse(cfg.has_families())
        self.assertEqual(cfg.family_kinds(0), ["Sine"])


class SetTests(unittest.TestCase):
    def setUp(self):
        self.g = Game(deck(), ["A", "B"], seed=1, first=0)
        rig(self.g, [[(0, "A", 70, 1, 6), (0, "A", 70, 1, 6), (0, "A", 80, 2, 8),
                      (1, "A", 80, 2, 8), (0, "S", 60, 1, 0)], []])

    def test_legal_sets_follow_need(self):
        sets = self.g.legal_sets(0, "A")
        sizes = sorted(len(s) for s in sets)
        # two singles, and the x2 paired with either single; the lone Saw x2 can't play
        self.assertEqual(sizes, [1, 1, 2, 2])

    def test_check_set_errors(self):
        a70, b70 = ids(self.g, 0, "A", 70)
        a80 = [c.id for c in self.g.players[0].hand if c.value == 80 and c.kind == 0][0]
        saw80 = [c.id for c in self.g.players[0].hand if c.kind == 1][0]
        self.g.check_set(0, [a80, a70], "A")
        with self.assertRaises(GameError):
            self.g.check_set(0, [a70, b70], "A")       # x1 cards: set must be 1
        with self.assertRaises(GameError):
            self.g.check_set(0, [a80], "A")            # x2 needs a partner
        with self.assertRaises(GameError):
            self.g.check_set(0, [a80, saw80], "A")     # mixed Kinds
        with self.assertRaises(GameError):
            self.g.check_set(0, [9999], "A")           # not in hand


class ExchangeTests(unittest.TestCase):
    def make(self, hands, n=3):
        g = Game(deck(), ["Att", "Tgt", "By"][:n], seed=1, first=0)
        rig(g, hands)
        return g

    def test_average_value_and_summed_damage(self):
        g = self.make([[(0, "A", 70, 1, 6), (0, "A", 80, 2, 8)], [], []])
        rolls(g, 75)
        g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 1})
        # nobody can respond -> resolved: avg 75, roll 75 hits, damage 14
        self.assertEqual(g.last.value, 75)
        self.assertTrue(g.last.result["hit"])
        self.assertEqual(g.players[1].hp, 86)
        self.assertEqual(g.phase, TURN)
        self.assertEqual(g.current, 1)

    def test_full_exchange_with_shifts_and_bystander_share(self):
        g = self.make([[(0, "A", 70, 1, 6), (0, "S", 40, 1, 0)],
                       [(0, "D", 60, 1, 0)],
                       [(0, "S", 60, 1, 0)]])
        g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 1})
        self.assertEqual(g.pending, (1, DEFEND))
        g.apply(1, {"type": "respond", "cards": ids(g, 1, "D")})      # -15 -> 55
        self.assertEqual(g.pending, (2, ASSIST))
        g.apply(2, {"type": "assist", "cards": ids(g, 2, "S")})       # +15 -> 70
        self.assertEqual(g.pending, (0, SUSTAIN))
        self.assertEqual(g.attack_percent(), 70)
        rolls(g, 80)
        g.apply(0, {"type": "sustain", "cards": ids(g, 0, "S")})      # +10 -> 80
        res = g.last.result
        self.assertEqual(res["percent"], 80)
        self.assertTrue(res["hit"])
        # 6 damage + bystander share round(15/3)=5, capped at 6
        self.assertEqual(g.players[1].hp, 100 - 6 - 5)
        self.assertEqual(res["extras"], [{"player": 2, "amount": 5}])

    def test_release_cancels_and_decay_bystander_heals(self):
        g = self.make([[(0, "A", 70, 1, 6)], [(0, "R", 60, 1, 0)], [(0, "D", 40, 1, 0)]])
        g.players[2].hp = 50
        g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 1})
        g.apply(1, {"type": "respond", "cards": ids(g, 1, "R")})
        rolls(g, 60)                      # release roll at the line: released
        g.apply(2, {"type": "assist", "cards": ids(g, 2, "D")})
        res = g.last.result
        self.assertTrue(res["released"])
        self.assertIsNone(res["attack_roll"])
        self.assertEqual(g.players[1].hp, 100)
        self.assertEqual(g.players[2].hp, 53)          # heal round(10/3)=3

    def test_failed_release_then_attack_roll(self):
        g = self.make([[(0, "A", 70, 1, 6)], [(0, "R", 60, 1, 0)]], n=2)
        g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 1})
        rolls(g, 61, 70)
        g.apply(1, {"type": "respond", "cards": ids(g, 1, "R")})
        self.assertFalse(g.last.result["released"])
        self.assertTrue(g.last.result["hit"])

    def test_clamped_percent(self):
        g = self.make([[(0, "A", 10, 1, 6)], [(0, "D", 100, 1, 0)]], n=2)
        g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 1})
        rolls(g, 6)
        g.apply(1, {"type": "respond", "cards": ids(g, 1, "D")})
        self.assertEqual(g.last.result["percent"], 5)
        self.assertFalse(g.last.result["hit"])

    def test_kind_must_match(self):
        g = self.make([[(0, "A", 70, 1, 6)], [(1, "D", 60, 1, 0), (0, "D", 40, 1, 0)]], n=2)
        g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 1})
        saw = [c.id for c in g.players[1].hand if c.kind == 1]
        with self.assertRaises(GameError):
            g.apply(1, {"type": "respond", "cards": saw})
        self.assertEqual(g.pending, (1, DEFEND))

    def test_wrong_player_and_bad_actions(self):
        g = self.make([[(0, "A", 70, 1, 6), (0, "S", 60, 1, 0)], [(0, "D", 40, 1, 0)], []])
        with self.assertRaises(GameError):
            g.apply(1, {"type": "discard", "cards": []})
        with self.assertRaises(GameError):
            g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 0})
        with self.assertRaises(GameError):
            g.apply(0, {"type": "discard", "cards": [c.id for c in g.players[0].hand] * 2})
        with self.assertRaises(GameError):
            g.apply(0, {"type": "attack", "cards": ids(g, 0, "S"), "target": 1})

    def test_elimination_and_win(self):
        g = self.make([[(0, "A", 70, 1, 6)], []], n=2)
        g.players[1].hp = 4
        rolls(g, 1)
        g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 1})
        self.assertFalse(g.players[1].alive)
        self.assertEqual(g.phase, OVER)
        self.assertEqual(g.winners, [0])
        self.assertIsNone(g.pending)

    def test_discard_and_refill(self):
        g = Game(deck(), ["A", "B"], seed=3, first=0)
        two = [c.id for c in g.players[0].hand[:2]]
        g.apply(0, {"type": "discard", "cards": two})
        self.assertEqual(len(g.players[0].hand), 7)
        self.assertFalse(set(two) & {c.id for c in g.players[0].hand})
        with self.assertRaises(GameError):
            g.apply(1, {"type": "discard", "cards": [c.id for c in g.players[1].hand[:3]]})

    def test_draw_limit(self):
        g = Game(deck(draw_limit=1), ["A", "B"], seed=3, first=0)
        self.assertEqual(len(g.players[0].hand), 7)        # the deal still fills hands
        g.apply(0, {"type": "discard", "cards": [c.id for c in g.players[0].hand[:2]]})
        self.assertEqual(len(g.players[0].hand), 6)        # drew only one
        self.assertIn("A draws 1 card and now holds 6 (a full hand is 7).", g.log)
        with self.assertRaises(ConfigError):
            deck(draw_limit=-1)

    def test_beats(self):
        cfg = load_config(dict(bundled_decks())["Rock Paper Scissors Lizard Alien (3x)"])
        fam = {k.family: i for i, k in reversed(list(enumerate(cfg.kinds)))}
        g = Game(cfg, ["A", "B"], seed=1, first=0)
        rig(g, [[(fam["Scissors"], "A", 70, 1, 6)],
                [(fam["Rock"], "D", 40, 1, 0), (fam["Rock"], "R", 55, 1, 0),
                 (fam["Rock"], "S", 60, 1, 0), (fam["Paper"], "D", 40, 1, 0)]])
        g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 1})
        legal = g.legal(1)                          # Rock beats Scissors; Paper loses
        rock_d = [c.id for c in g.players[1].hand if c.type == "D" and c.kind == fam["Rock"]]
        self.assertEqual(legal["D"], [tuple(rock_d)])
        self.assertEqual(len(legal["R"]), 1)
        rolls(g, 99, 99)
        g.apply(1, {"type": "respond", "cards": rock_d + [c.id for c in g.players[1].hand
                                                          if c.type == "R"]})
        dec, rel = g.last.plays if g.last else g.exchange.plays
        self.assertEqual((dec.value, rel.value), (55, 70))   # +15 each
        self.assertIn("Rock blunts Scissors! +15% for the Granite Decay.", g.log)
        self.assertIsNone(cfg.beat_verb(fam["Rock"], fam["Paper"]))
        with self.assertRaises(ConfigError):
            parse_config({"kinds": [{"name": "X"}], "cards": {"A": [{"value": 50, "damage": 1}]},
                          "beats": {"X": ["Nope"]}})

    def test_wild(self):
        cfg = load_config(dict(bundled_decks())["Balance of Power (3x)"])
        fam = {k.family: i for i, k in reversed(list(enumerate(cfg.kinds)))}
        g = Game(cfg, ["A", "B", "C"], seed=1, first=0)
        far = fam["Between Empires"]                 # not the Attack's family
        rig(g, [[(fam["Antiquity"], "A", 70, 1, 6), (far, "S", 60, 1, 0)],
                [(far, "D", 40, 1, 0), (far, "R", 55, 1, 0), (fam["Antiquity"] + 1, "R", 55, 1, 0)],
                [(far, "S", 40, 1, 0), (far, "D", 60, 1, 0)]])
        g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 1})
        legal = g.legal(1)                           # any Decay; Release still by family
        self.assertEqual(len(legal["D"]), 1)
        self.assertEqual([g.players[1].hand[2].id], [i for s in legal["R"] for i in s])
        g.apply(1, {"type": "respond", "cards": ids(g, 1, "D")})
        self.assertEqual(len(g.legal(2)["S"]), 1)
        self.assertEqual(len(g.legal(2)["D"]), 1)
        rolls(g, 1)
        g.apply(2, {"type": "assist", "cards": ids(g, 2, "S")})
        g.apply(0, {"type": "sustain", "cards": ids(g, 0, "S")})
        self.assertEqual(g.last.result["percent"], 70 - 10 + 10 + 15)
        self.assertEqual(load_config().wild, "")     # other decks: none
        for bad in (["A"], "DS", ["DS"]):
            with self.assertRaises(ConfigError):
                parse_config({"kinds": [{"name": "X"}],
                              "cards": {"A": [{"value": 50, "damage": 1}]}, "wild": bad})

    def test_heads(self):
        cfg = load_config(dict(bundled_decks())["Hatfields and McCoys (3x)"])
        heads = {k.name: i for i, k in enumerate(cfg.kinds) if k.head}
        self.assertEqual(set(heads), {"Devil Anse", "Ole Ran'l"})
        cards = build_deck(cfg)
        anse = max(c.damage for c in cards if c.kind == heads["Devil Anse"])
        levicy = max(c.damage for c in cards if c.kind == 1)
        self.assertEqual(anse, levicy + 3)
        for hit, drawn in ((False, 2), (True, 0)):
            g = Game(cfg, ["A", "B"], seed=1, first=0)
            rig(g, [[(heads["Devil Anse"], "A", 70, 1, 9)], [(15, "A", 70, 1, 6)]])
            rolls(g, 1 if hit else 99)
            before = len(g.players[1].hand)
            g.apply(0, {"type": "attack", "cards": ids(g, 0, "A"), "target": 1})
            while g.pending and g.pending[1] != TURN:
                g.apply(g.pending[0], {"type": g.pending[1] == "sustain" and "sustain"
                                       or "respond", "cards": []})
            self.assertEqual(len(g.players[1].hand) - before, drawn)
            self.assertEqual(g.last.result.get("head_bonus", 0), drawn)
        self.assertFalse(any(k.head for k in load_config().kinds))   # other decks: none
        with self.assertRaises(ConfigError):
            parse_config({"kinds": [{"name": "X"}], "cards": {"A": [{"value": 50, "damage": 1}]},
                          "heads": {"X": "Nobody"}})

    def test_swap(self):
        g = Game(deck(), ["A", "B"], seed=3, first=0)
        with self.assertRaises(GameError):                      # off by default
            g.apply(0, {"type": "swap", "cards": [g.players[0].hand[0].id]})
        g = Game(deck(swap_limit=2), ["A", "B"], seed=3, first=0)
        rig(g, [[(0, "A", 70, 1, 6), (0, "A", 80, 2, 8), (0, "D", 40, 1, 0),
                 (0, "S", 60, 1, 0)], [(1, "D", 40, 1, 0)]])
        a1, a2, dec, sus = (c.id for c in g.players[0].hand)
        with self.assertRaises(GameError):                      # highlighted: playable
            g.apply(0, {"type": "swap", "cards": [a1]})
        with self.assertRaises(GameError):
            g.apply(0, {"type": "swap", "cards": [a2, dec, sus]})   # over the limit
        g.apply(0, {"type": "swap", "cards": [dec, sus]})
        self.assertEqual(g.pending, (0, TURN))                  # the turn goes on
        hand = {c.id for c in g.players[0].hand}
        self.assertEqual(len(hand), 4)
        self.assertFalse({dec, sus} & hand)
        self.assertEqual(g.view(0)["swap"], 0)
        with self.assertRaises(GameError):                      # once a turn
            g.apply(0, {"type": "swap", "cards": [a2]})

    def test_hard_passes_rather_than_discard_when_rationed(self):
        g = Game(deck(draw_limit=1), ["A", "B"], seed=3, first=0)
        rig(g, [[(0, "D", 40, 1, 0)] * 5, [(1, "D", 40, 1, 0)] * 5])   # no Attacks
        self.assertEqual(ai.choose(g, 0, "hard", random.Random(1)),
                         {"type": "discard", "cards": []})
        g = Game(deck(), ["A", "B"], seed=3, first=0)                   # full refill
        rig(g, [[(0, "D", 40, 1, 0)] * 5, [(1, "D", 40, 1, 0)] * 5])
        self.assertEqual(len(ai.choose(g, 0, "hard", random.Random(1))["cards"]), 2)

    def test_view_is_json_and_private(self):
        g = Game(load_config(), ["A", "B", "C"], seed=2)
        v = g.view(1)
        json.dumps(v)
        self.assertEqual({c["id"] for c in v["hand"]}, {c.id for c in g.players[1].hand})
        self.assertEqual(g.view(None)["hand"], [])


class AITests(unittest.TestCase):
    def test_games_finish_at_every_level(self):
        cfg = load_config()
        rng = random.Random(7)
        for levels in (["easy", "easy"], ["normal", "hard", "easy"],
                       ["hard"] * 6, ["normal", "normal", "hard", "hard"]):
            for _ in range(5):
                g = Game(cfg, [f"P{i}" for i in range(len(levels))], seed=rng.random())
                steps = 0
                while g.pending:
                    pid, _ = g.pending
                    g.apply(pid, ai.choose(g, pid, levels[pid], rng))
                    steps += 1
                    self.assertLess(steps, 20000)
                self.assertTrue(g.winners)
                cards = sum(len(p.hand) for p in g.players) + len(g.deck) + len(g.discard)
                self.assertEqual(cards, len(build_deck(cfg)))   # no card lost or duplicated

    def test_hard_beats_easy(self):
        from app import sim
        cfg = load_config()
        rng = random.Random(11)
        wins = 0
        for i in range(60):
            order = ["hard", "easy"] if i % 2 else ["easy", "hard"]
            g = sim.play(cfg, order, rng.random())
            wins += any(order[w] == "hard" for w in g.winners)
        self.assertGreater(wins, 45)



class NormalTargets(unittest.TestCase):
    def test_clear_leader_is_attacked_sometimes(self):
        """Normal attacks the weakest, but a clear leader (20+ HP ahead) about half the time."""
        import random
        from app import ai
        cfg = load_config(DEFAULT_DECK)
        on_leader = attacks = 0
        for seed in range(400):
            g = Game(cfg, ["Me", "Lead", "Weak"], seed=seed, first=0)
            g.players[1].hp, g.players[2].hp, g.players[0].hp = 100, 40, 60
            rng = random.Random(seed)
            act = ai.choose(g, 0, "normal", rng)
            while act["type"] == "swap":           # swaps come first; the turn goes on
                g.apply(0, act)
                act = ai.choose(g, 0, "normal", rng)
            if act["type"] == "attack":
                attacks += 1
                on_leader += act["target"] == 1
        self.assertGreater(attacks, 300)
        self.assertTrue(0.35 < on_leader / attacks < 0.65, on_leader / attacks)

        # nobody clearly ahead: always the weakest
        g = Game(cfg, ["Me", "A", "B"], seed=1, first=0)
        g.players[1].hp, g.players[2].hp = 90, 80
        rng = random.Random(1)
        act = ai.choose(g, 0, "normal", rng)
        while act["type"] == "swap":
            g.apply(0, act)
            act = ai.choose(g, 0, "normal", rng)
        if act["type"] == "attack":
            self.assertEqual(act["target"], 2)

if __name__ == "__main__":
    unittest.main()
