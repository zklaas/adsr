"""Cards, Kinds and the deck file.

A deck file (JSON) names the Kinds, the card templates for each card type and
the numeric rules.  Every Kind gets the shared ``cards`` templates unless the
Kind carries its own ``cards`` block.  See deck.json for the default
"Romeo and Juliet (2x)" deck and README.md for the format.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DECK = os.path.join(os.path.dirname(HERE), "deck.json")
DECKS_DIR = os.path.join(os.path.dirname(HERE), "decks")   # extra configurations

TYPES = "ADSR"
TYPE_NAMES = {"A": "Attack", "S": "Sustain", "D": "Decay", "R": "Release"}
GLYPHS = ("sine", "cosine", "triangle", "square", "pulse", "ramp", "saw", "reverse saw",
          "noise", "wavetable", "rock", "paper", "scissors", "lizard", "alien",
          "hatfield", "mccoy", "column", "palle", "crown", "quill",
          "scales", "rapier", "balcony", "tower", "ewer", "chapel",
          "anchor", "bars", "wings", "armband", "badge",
          "bat", "baseball", "cap", "scoreboard", "ivy", "letter")

RULE_DEFAULTS = {
    "start_hp": 100,       # Hit Points each player starts with
    "hand_size": 12,       # refill to this many at the end of your turn
    "max_discard": 2,      # cards you may discard instead of attacking
    "draw_limit": 0,       # most cards drawn at the end of a turn (0 = refill fully)
    "swap_limit": 0,       # unplayable cards you may swap for new ones per turn (0 = off)
    "beat_bonus": 15,      # % added to a Decay/Release from a family that beats the Attack's
    "head_damage": 3,      # extra damage on each Attack card of a family head
    "head_bonus": 2,       # cards the target draws when a head's Attack fails
    "shift_divisor": 4,    # Sustain / Decay shift the Attack % by value / this
    "min_percent": 5,      # an Attack's chance is clamped to this range
    "max_percent": 95,
    "share_divisor": 3,    # bystander reward = their shift / this (capped)
    "max_turns": 400,      # safety net: highest HP wins after this many turns
    "max_players": 6,
}


class ConfigError(ValueError):
    pass


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


@dataclass(frozen=True)
class Kind:
    name: str
    color: str
    glyph: str
    family: str       # modifiers work on any Attack whose Kind shares this
    head: bool = False  # head of its family: stronger Attacks, a prize for stopping them


@dataclass(frozen=True)
class Card:
    id: int
    kind: int          # index into the deck's kinds
    type: str          # one of "ADSR"
    value: int         # percentile value
    need: int = 1      # must be played in a set of exactly the largest need
    damage: int = 0    # Attack cards only

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "type": self.type,
                "value": self.value, "need": self.need, "damage": self.damage}


@dataclass
class DeckConfig:
    name: str
    kinds: list[Kind]
    templates: list[dict]          # per Kind: type -> list of template dicts
    rules: dict = field(default_factory=lambda: dict(RULE_DEFAULTS))
    path: str = ""
    beats: dict = field(default_factory=dict)   # family -> {family it beats: verb}
    wild: str = ""     # card types (of "SDR") that answer an Attack of any Kind

    def __getattr__(self, item):    # cfg.start_hp etc.
        rules = self.__dict__.get("rules", {})
        if item in rules:
            return rules[item]
        raise AttributeError(item)

    def card_name(self, card) -> str:
        kind = card["kind"] if isinstance(card, dict) else card.kind
        typ = card["type"] if isinstance(card, dict) else card.type
        return f"{self.kinds[kind].name} {TYPE_NAMES[typ]}"

    def family(self, kind: int) -> str:
        return self.kinds[kind].family

    def family_kinds(self, kind: int) -> list[str]:
        fam = self.kinds[kind].family
        return [k.name for k in self.kinds if k.family == fam]

    def beat_verb(self, card_kind: int, attack_kind: int) -> str | None:
        """How `card_kind`'s family beats `attack_kind`'s ("crushes"), or None."""
        return self.beats.get(self.family(card_kind), {}).get(self.family(attack_kind))

    def has_families(self) -> bool:
        return len({k.family for k in self.kinds}) < len(self.kinds)

    def public(self) -> dict:
        """What a client needs to draw cards and explain the rules."""
        return {"name": self.name,
                "kinds": [{"name": k.name, "color": k.color, "glyph": k.glyph,
                           "family": k.family, "beats": self.beats.get(k.family, {}),
                           "head": k.head, "wild": self.wild}
                          for k in self.kinds],
                "wild": self.wild,
                "rules": dict(self.rules)}


def _template(raw, where: str, typ: str) -> dict:
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: each card entry must be an object")
    try:
        value = int(raw["value"])
    except (KeyError, TypeError, ValueError):
        raise ConfigError(f"{where}: card needs a numeric 'value'") from None
    need = int(raw.get("need", 1))
    count = int(raw.get("count", 1))
    damage = int(raw.get("damage", 0))
    if not 1 <= value <= 100:
        raise ConfigError(f"{where}: value {value} must be 1-100")
    if not 1 <= need <= 6:
        raise ConfigError(f"{where}: need {need} must be 1-6")
    if count < 0:
        raise ConfigError(f"{where}: count must not be negative")
    if typ == "A" and damage < 1:
        raise ConfigError(f"{where}: Attack cards need 'damage' of at least 1")
    return {"value": value, "need": need, "count": count,
            "damage": damage if typ == "A" else 0}


def _templates(raw, where: str) -> dict:
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: 'cards' must map A/S/D/R to lists")
    out = {}
    for typ in TYPES:
        entries = raw.get(typ, [])
        if not isinstance(entries, list):
            raise ConfigError(f"{where}: cards.{typ} must be a list")
        out[typ] = [_template(e, f"{where} {TYPE_NAMES[typ]} #{i + 1}", typ)
                    for i, e in enumerate(entries)]
    bad = set(raw) - set(TYPES)
    if bad:
        raise ConfigError(f"{where}: unknown card types {sorted(bad)}")
    return out


def parse_config(data: dict, path: str = "") -> DeckConfig:
    if not isinstance(data, dict):
        raise ConfigError("deck file must be a JSON object")
    rules = dict(RULE_DEFAULTS)
    for key, val in (data.get("rules") or {}).items():
        if key not in RULE_DEFAULTS:
            raise ConfigError(f"unknown rule '{key}'")
        try:
            rules[key] = int(val)
        except (TypeError, ValueError):
            raise ConfigError(f"rule '{key}' must be a whole number") from None
    if rules["start_hp"] < 1 or rules["hand_size"] < 1:
        raise ConfigError("start_hp and hand_size must be positive")
    if rules["draw_limit"] < 0 or rules["swap_limit"] < 0:
        raise ConfigError("draw_limit and swap_limit must be 0 or more")
    for key in ("beat_bonus", "head_damage", "head_bonus"):
        if rules[key] < 0:
            raise ConfigError(f"{key} must be 0 or more")
    if rules["shift_divisor"] < 1 or rules["share_divisor"] < 1:
        raise ConfigError("divisors must be at least 1")
    if not 0 <= rules["min_percent"] <= rules["max_percent"] <= 100:
        raise ConfigError("need 0 <= min_percent <= max_percent <= 100")

    shared = data.get("cards")
    kinds_raw = data.get("kinds")
    if not isinstance(kinds_raw, list) or not kinds_raw:
        raise ConfigError("deck file needs a non-empty 'kinds' list")
    kinds, templates = [], []
    for i, k in enumerate(kinds_raw):
        if isinstance(k, str):
            k = {"name": k}
        if not isinstance(k, dict) or not str(k.get("name", "")).strip():
            raise ConfigError(f"Kind #{i + 1} needs a 'name'")
        name = str(k["name"]).strip()
        glyph = str(k.get("glyph", name.lower() if name.lower() in GLYPHS
                          else "letter")).lower()
        if glyph not in GLYPHS:
            raise ConfigError(f"Kind {name}: glyph must be one of {', '.join(GLYPHS)}")
        family = str(k.get("family") or name).strip() or name
        kinds.append(Kind(name, str(k.get("color", _DEFAULT_COLORS[i % len(_DEFAULT_COLORS)])),
                          glyph, family))
        raw = k.get("cards", shared)
        if raw is None:
            raise ConfigError(f"Kind {name}: no 'cards' (shared or its own)")
        templates.append(_templates(raw, f"Kind {name}"))
        if not any(t["count"] for typ in TYPES for t in templates[-1][typ]):
            raise ConfigError(f"Kind {name}: has no cards")
    if not any(t["count"] for per in templates for t in per["A"]):
        raise ConfigError("the deck needs at least one Attack card")
    names = [k.name.lower() for k in kinds]
    if len(set(names)) != len(names):
        raise ConfigError("Kind names must be unique")
    heads = data.get("heads") or {}
    if not isinstance(heads, dict):
        raise ConfigError("'heads' must map a family to the Kind that heads it")
    for fam, head in heads.items():
        match = [i for i, k in enumerate(kinds) if k.name == head]
        if not match:
            raise ConfigError(f"heads: no Kind called '{head}'")
        if kinds[match[0]].family != fam:
            raise ConfigError(f"heads: {head} is not in the {fam} family")
        k = kinds[match[0]]
        kinds[match[0]] = Kind(k.name, k.color, k.glyph, k.family, True)
    return DeckConfig(str(data.get("name", "Custom deck")), kinds, templates, rules, path,
                      _beats(data.get("beats"), {k.family for k in kinds}),
                      _wild(data.get("wild")))


def _wild(raw) -> str:
    """["D", "S"]: those card types are wild - they answer an Attack of any Kind."""
    if raw is None:
        return ""
    if not isinstance(raw, list) or not all(isinstance(t, str) for t in raw):
        raise ConfigError("'wild' must be a list of card types, e.g. [\"D\", \"S\"]")
    bad = [t for t in raw if t not in "SDR" or len(t) != 1]
    if bad:
        raise ConfigError(f"wild: only S, D and R cards can be wild, not {bad}")
    return "".join(t for t in "SDR" if t in raw)


def _beats(raw, families: set) -> dict:
    """{"Rock": {"Scissors": "blunts", ...}, ...}: which families each beats.
    A list of family names is accepted too (the verb is then "beats")."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError("'beats' must map a family to the families it beats")
    out = {}
    for fam, victims in raw.items():
        if isinstance(victims, list):
            victims = {v: "beats" for v in victims}
        if not isinstance(victims, dict):
            raise ConfigError(f"beats.{fam}: give a list or an object of families")
        for f in [fam, *victims]:
            if f not in families:
                raise ConfigError(f"beats: no family called '{f}'")
        if fam in victims:
            raise ConfigError(f"beats: {fam} can't beat itself")
        out[fam] = {str(v): str(verb) for v, verb in victims.items()}
    return out


_DEFAULT_COLORS = ["#3b7fc4", "#c4473f", "#d08a1e", "#3f9a5a", "#8a55c4", "#2aa0a0"]


def load_config(path: str | None = None) -> DeckConfig:
    path = path or DEFAULT_DECK
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as e:
        raise ConfigError(f"cannot read {path}: {e.strerror}") from None
    except json.JSONDecodeError as e:
        raise ConfigError(f"{os.path.basename(path)} line {e.lineno}: {e.msg}") from None
    return parse_config(data, path)


def bundled_decks() -> list[tuple[str, str]]:
    """(name, path) for the default deck and each readable file in decks/."""
    out = [(load_config(DEFAULT_DECK).name, DEFAULT_DECK)]
    try:
        files = sorted(f for f in os.listdir(DECKS_DIR) if f.endswith(".json"))
    except OSError:
        files = []
    for f in files:
        path = os.path.join(DECKS_DIR, f)
        try:
            out.append((load_config(path).name, path))
        except ConfigError:
            continue
    return out


def build_deck(cfg: DeckConfig) -> list[Card]:
    cards, next_id = [], 0
    for k, per_type in enumerate(cfg.templates):
        for typ in TYPES:
            for t in per_type[typ]:
                for _ in range(t["count"]):
                    dmg = t["damage"] + (cfg.head_damage if typ == "A" and cfg.kinds[k].head
                                         else 0)
                    cards.append(Card(next_id, k, typ, t["value"], t["need"], dmg))
                    next_id += 1
    return cards


def deck_summary(cfg: DeckConfig) -> str:
    deck = build_deck(cfg)
    counts = {t: sum(1 for c in deck if c.type == t) for t in TYPES}
    per = " · ".join(f"{counts[t]} {TYPE_NAMES[t]}" for t in TYPES)
    draw = (f"draw {cfg.draw_limit} a turn" if cfg.draw_limit else "refill fully each turn")
    per += f" — hand {cfg.hand_size}, {draw}"
    if cfg.beats:
        per += f", families beat others (+{cfg.beat_bonus}%)"
    heads = [k.name for k in cfg.kinds if k.head]
    if heads:
        per += (f", heads {' and '.join(heads)} (+{cfg.head_damage} damage a card; "
                f"stop one and draw {cfg.head_bonus})")
    if cfg.wild:
        per += f", {' and '.join(TYPE_NAMES[t] for t in cfg.wild)} cards are wild (any Kind)"
    if cfg.swap_limit:
        per += f", swap up to {cfg.swap_limit} unplayable card{'s' * (cfg.swap_limit > 1)} a turn"
    if cfg.has_families():
        fams: dict[str, list[str]] = {}
        for k in cfg.kinds:
            fams.setdefault(k.family, []).append(k.name)
        groups = "; ".join(f"{f}: {', '.join(n)}" for f, n in fams.items())
        return (f"{cfg.name}: {len(deck)} cards, {len(cfg.kinds)} Kinds in {len(fams)} "
                f"families ({groups}) — {per}")
    kinds = ", ".join(k.name for k in cfg.kinds)
    return f"{cfg.name}: {len(deck)} cards in {len(cfg.kinds)} Kinds ({kinds}) — {per}"
