"""ADSR rules engine - a pure state machine with no GUI or network code.

Every decision is a reply to the engine's pending prompt: ``game.pending``
names the player and the phase, and ``game.apply(pid, action)`` validates
their answer and advances the game.  Hot-seat humans, computer players and
LAN clients all answer prompts the same way.

An exchange runs:  turn (attacker plays an Attack set at a target, or
discards) -> defend (target may play a Decay set and/or a Release set) ->
assist (each other player may add one Sustain or Decay set) -> sustain
(attacker may add a Sustain set) -> resolve.  Players with nothing legal to
play in a phase are skipped automatically.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import combinations

from .cards import TYPE_NAMES, Card, DeckConfig, build_deck, round_half_up

TURN, DEFEND, ASSIST, SUSTAIN, OVER = "turn", "defend", "assist", "sustain", "over"
LOG_KEEP = 400


class GameError(ValueError):
    pass


@dataclass
class Player:
    id: int
    name: str
    hp: int
    hand: list = field(default_factory=list)
    alive: bool = True


@dataclass
class Play:
    player: int
    role: str          # "target" | "bystander" | "attacker"
    type: str          # "S" | "D" | "R"
    cards: list
    value: int         # average of the cards' values
    shift: int = 0     # change to the Attack % (S/D only; sign applied later)

    def to_dict(self) -> dict:
        return {"player": self.player, "role": self.role, "type": self.type,
                "cards": [c.to_dict() for c in self.cards],
                "value": self.value, "shift": self.shift}


@dataclass
class Exchange:
    attacker: int
    target: int
    kind: int
    cards: list
    value: int
    damage: int
    turn_no: int
    plays: list = field(default_factory=list)
    queue: list = field(default_factory=list)    # bystanders still to ask
    result: dict | None = None


def set_value(cards) -> int:
    """The percentile of a set is the average of its cards, rounded."""
    return round_half_up(sum(c.value for c in cards) / len(cards))


class Game:
    def __init__(self, cfg: DeckConfig, names: list[str], seed=None, first: int = 0):
        if not 2 <= len(names) <= cfg.max_players:
            raise GameError(f"ADSR needs 2-{cfg.max_players} players")
        deck = build_deck(cfg)
        if len(deck) < cfg.hand_size * len(names) + 4:
            raise GameError(f"the deck ({len(deck)} cards) is too small for "
                            f"{len(names)} hands of {cfg.hand_size}")
        self.cfg = cfg
        self.rng = random.Random(seed)
        self.players = [Player(i, n, cfg.start_hp) for i, n in enumerate(names)]
        self.rng.shuffle(deck)
        self.deck: list[Card] = deck
        self.discard: list[Card] = []
        self.log: list[str] = []
        self.turn_no = 1
        self.current = first % len(names)
        self.phase = TURN
        self.exchange: Exchange | None = None
        self.last: Exchange | None = None
        self.winners: list[int] = []
        self.swapped = False           # this turn's swap is used
        for p in self.players:
            self._refill(p)
        self._say(f"— Turn 1: {self.players[self.current].name} —")

    # ---------------------------------------------------------------- helpers
    def roll(self) -> int:
        return self.rng.randint(1, 100)

    def _say(self, text: str) -> None:
        self.log.append(text)
        if len(self.log) > LOG_KEEP:
            del self.log[:len(self.log) - LOG_KEEP]

    def name(self, pid: int) -> str:
        return self.players[pid].name

    def card_name(self, c: Card) -> str:
        return self.cfg.card_name(c)

    def _draw(self) -> Card | None:
        if not self.deck and self.discard:
            self.deck, self.discard = self.discard, []
            self.rng.shuffle(self.deck)
            self._say("The discard pile is shuffled into a new draw pile.")
        return self.deck.pop() if self.deck else None

    def _refill(self, p: Player, limit: int = 0) -> int:
        """Draw up to a full hand, or at most `limit` cards when limit > 0."""
        n = 0
        while len(p.hand) < self.cfg.hand_size and not (limit and n >= limit):
            c = self._draw()
            if c is None:
                break
            p.hand.append(c)
            n += 1
        return n

    def clamp(self, pct: int) -> int:
        return max(self.cfg.min_percent, min(self.cfg.max_percent, pct))

    def alive(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    def opponents(self, pid: int) -> list[Player]:
        return [p for p in self.players if p.alive and p.id != pid]

    # -------------------------------------------------------------- card sets
    def fits(self, card: Card, kind: int | None) -> bool:
        """Can `card` be played on an Attack of `kind`?  Any Kind in the
        Attack's family will do (without families, each Kind is its own), as
        will a wild card type, and a Decay or Release from a family that beats
        the Attack's family."""
        if kind is None or card.type in self.cfg.wild or \
                self.cfg.family(card.kind) == self.cfg.family(kind):
            return True
        return card.type in "DR" and self.cfg.beat_verb(card.kind, kind) is not None

    def play_value(self, cards, kind: int) -> int:
        """A set's value against an Attack of `kind`, with any beat bonus."""
        value = set_value(cards)
        if self.cfg.family(cards[0].kind) != self.cfg.family(kind) and \
                self.cfg.beat_verb(cards[0].kind, kind):
            value = min(100, value + self.cfg.beat_bonus)
        return value

    def legal_sets(self, pid: int, typ: str, kind: int | None = None) -> list[tuple]:
        """Every playable set of card ids: one Kind and type, exactly as many
        cards as the largest 'need' among them, and (given `kind`) in that
        Kind's family."""
        groups: dict[int, list[Card]] = {}
        for c in self.players[pid].hand:
            if c.type == typ and self.fits(c, kind):
                groups.setdefault(c.kind, []).append(c)
        out = []
        for cards in groups.values():
            for size in range(1, len(cards) + 1):
                for combo in combinations(cards, size):
                    if max(c.need for c in combo) == size:
                        out.append(tuple(sorted(c.id for c in combo)))
        return out

    def check_set(self, pid: int, ids, typ: str, kind: int | None = None) -> list[Card]:
        hand = {c.id: c for c in self.players[pid].hand}
        ids = list(ids)
        if not ids:
            raise GameError("no cards chosen")
        if len(set(ids)) != len(ids):
            raise GameError("a card was chosen twice")
        try:
            cards = [hand[int(i)] for i in ids]
        except (KeyError, ValueError, TypeError):
            raise GameError("that card is not in your hand") from None
        if any(c.type != typ for c in cards):
            raise GameError(f"only {TYPE_NAMES[typ]} cards can go in this set")
        kinds = {c.kind for c in cards}
        if len(kinds) != 1:
            raise GameError("all cards in a set must share one Kind")
        if not self.fits(cards[0], kind):
            if self.cfg.has_families():
                fam = self.cfg.family(kind)
                over = [f for f, v in self.cfg.beats.items() if fam in v]
                extra = (f", or Decay/Release from {' or '.join(over)}" if over else "")
                raise GameError(f"this Attack is {self.cfg.kinds[kind].name} "
                                f"({fam}); cards must be one of "
                                f"{', '.join(self.cfg.family_kinds(kind))}{extra}")
            raise GameError(f"this exchange is {self.cfg.kinds[kind].name}; "
                            "cards must match the Attack's Kind")
        need = max(c.need for c in cards)
        if len(cards) != need:
            raise GameError(f"that set needs exactly {need} card{'s' * (need > 1)} "
                            f"(you chose {len(cards)})")
        return cards

    def _take(self, pid: int, cards: list[Card]) -> None:
        hand = self.players[pid].hand
        for c in cards:
            hand.remove(c)

    def attack_percent(self, ex: Exchange | None = None) -> int:
        ex = ex or self.exchange
        pct = ex.value
        for p in ex.plays:
            if p.type == "S":
                pct += p.shift
            elif p.type == "D":
                pct -= p.shift
        return self.clamp(pct)

    # ------------------------------------------------------------------ flow
    @property
    def pending(self) -> tuple[int, str] | None:
        if self.phase == OVER:
            return None
        if self.phase == TURN:
            return self.current, TURN
        ex = self.exchange
        if self.phase == DEFEND:
            return ex.target, DEFEND
        if self.phase == ASSIST:
            return ex.queue[0], ASSIST
        return ex.attacker, SUSTAIN

    def legal(self, pid: int) -> dict:
        """The sets `pid` may play right now (empty when it's not their move)."""
        pend = self.pending
        if not pend or pend[0] != pid:
            return {}
        phase = pend[1]
        if phase == TURN:
            return {"A": self.legal_sets(pid, "A")}
        k = self.exchange.kind
        if phase == DEFEND:
            return {"D": self.legal_sets(pid, "D", k), "R": self.legal_sets(pid, "R", k)}
        if phase == ASSIST:
            return {"S": self.legal_sets(pid, "S", k), "D": self.legal_sets(pid, "D", k)}
        return {"S": self.legal_sets(pid, "S", k)}

    def apply(self, pid: int, action: dict) -> None:
        pend = self.pending
        if pend is None:
            raise GameError("the game is over")
        if pid != pend[0]:
            raise GameError(f"it is {self.name(pend[0])}'s move")
        if not isinstance(action, dict):
            raise GameError("bad action")
        phase = pend[1]
        ids = action.get("cards") or []
        if not isinstance(ids, (list, tuple)):
            raise GameError("bad card list")
        if phase == TURN:
            self._do_turn(pid, action, ids)
        elif phase == DEFEND:
            self._do_defend(pid, ids)
        elif phase == ASSIST:
            self._do_assist(pid, ids)
        else:
            self._do_sustain(pid, ids)
        self._advance()

    def _do_turn(self, pid: int, action: dict, ids) -> None:
        kind = action.get("type")
        me = self.players[pid]
        if kind == "attack":
            try:
                tgt = int(action.get("target"))
            except (TypeError, ValueError):
                raise GameError("choose a target") from None
            if tgt == pid or not 0 <= tgt < len(self.players) or not self.players[tgt].alive:
                raise GameError("choose a living opponent as the target")
            cards = self.check_set(pid, ids, "A")
            self._take(pid, cards)
            ex = Exchange(pid, tgt, cards[0].kind, cards, set_value(cards),
                          sum(c.damage for c in cards), self.turn_no)
            self.exchange = ex
            self.phase = DEFEND
            n = len(cards)
            self._say(f"{me.name} attacks {self.name(tgt)} with "
                      f"{'a ' if n == 1 else f'{n}× '}{self.card_name(cards[0])} "
                      f"({ex.value}%, {ex.damage} damage).")
        elif kind == "swap":
            self._swap(pid, ids)
        elif kind == "discard":
            if len(ids) > self.cfg.max_discard:
                raise GameError(f"you may discard at most {self.cfg.max_discard} cards")
            hand = {c.id: c for c in me.hand}
            if len(set(ids)) != len(ids) or any(i not in hand for i in ids):
                raise GameError("those cards are not all in your hand")
            cards = [hand[i] for i in ids]
            self._take(pid, cards)
            self.discard.extend(cards)
            if cards:
                self._say(f"{me.name} discards {len(cards)} card{'s' * (len(cards) > 1)}.")
            else:
                self._say(f"{me.name} passes.")
            self._end_turn()
        else:
            raise GameError("on your turn, attack, swap or discard")

    def _split(self, pid: int, ids) -> dict[str, list]:
        hand = {c.id: c for c in self.players[pid].hand}
        parts: dict[str, list] = {}
        for i in ids:
            if i not in hand:
                raise GameError("that card is not in your hand")
            parts.setdefault(hand[i].type, []).append(i)
        return parts

    def _play(self, pid: int, role: str, typ: str, ids) -> Play:
        ex = self.exchange
        cards = self.check_set(pid, ids, typ, ex.kind)
        value = self.play_value(cards, ex.kind)
        verb = (self.cfg.beat_verb(cards[0].kind, ex.kind)
                if self.cfg.family(cards[0].kind) != self.cfg.family(ex.kind) else None)
        if verb:
            self._say(f"{self.cfg.family(cards[0].kind)} {verb} "
                      f"{self.cfg.family(ex.kind)}! +{self.cfg.beat_bonus}% "
                      f"for the {self.card_name(cards[0])}.")
        shift = round_half_up(value / self.cfg.shift_divisor) if typ in "SD" else 0
        return Play(pid, role, typ, cards, value, shift)

    def _commit(self, play: Play) -> None:
        self._take(play.player, play.cards)
        self.exchange.plays.append(play)
        n = len(play.cards)
        what = f"{'a ' if n == 1 else f'{n}× '}{self.card_name(play.cards[0])} ({play.value}%)"
        if play.type == "R":
            self._say(f"{self.name(play.player)} answers with {what}.")
        else:
            sign = "+" if play.type == "S" else "−"
            self._say(f"{self.name(play.player)} adds {what}: {sign}{play.shift} → "
                      f"Attack now {self.attack_percent()}%.")

    def _do_defend(self, pid: int, ids) -> None:
        parts = self._split(pid, ids)
        if set(parts) - {"D", "R"}:
            raise GameError("respond with Decay and/or Release cards only")
        plays = [self._play(pid, "target", t, parts[t]) for t in ("D", "R") if t in parts]
        for p in plays:
            self._commit(p)
        if not plays:
            self._say(f"{self.name(pid)} lets it come.")
        self._start_assist()

    def _do_assist(self, pid: int, ids) -> None:
        self.exchange.queue.pop(0)
        if not ids:
            return
        parts = self._split(pid, ids)
        if len(parts) != 1 or set(parts) - {"S", "D"}:
            self.exchange.queue.insert(0, pid)
            raise GameError("add one Sustain set or one Decay set")
        typ = next(iter(parts))
        try:
            play = self._play(pid, "bystander", typ, parts[typ])
        except GameError:
            self.exchange.queue.insert(0, pid)
            raise
        self._commit(play)

    def _do_sustain(self, pid: int, ids) -> None:
        if ids:
            self._commit(self._play(pid, "attacker", "S", ids))
        self._resolve()

    def _start_assist(self) -> None:
        ex = self.exchange
        n = len(self.players)
        order = [(ex.attacker + i) % n for i in range(1, n)]
        ex.queue = [i for i in order if i != ex.target and self.players[i].alive]
        self.phase = ASSIST

    def _advance(self) -> None:
        """Skip prompts nobody can answer."""
        while True:
            ex = self.exchange
            if self.phase == DEFEND:
                if not (self.legal_sets(ex.target, "D", ex.kind)
                        or self.legal_sets(ex.target, "R", ex.kind)):
                    what = ("" if "D" in self.cfg.wild else
                            f"{self.cfg.family(ex.kind)} " if self.cfg.has_families()
                            else f"{self.cfg.kinds[ex.kind].name} ")
                    self._say(f"{self.name(ex.target)} has no {what}defence.")
                    self._start_assist()
                    continue
            elif self.phase == ASSIST:
                while ex.queue and not (self.legal_sets(ex.queue[0], "S", ex.kind)
                                        or self.legal_sets(ex.queue[0], "D", ex.kind)):
                    ex.queue.pop(0)
                if not ex.queue:
                    self.phase = SUSTAIN
                    continue
            elif self.phase == SUSTAIN:
                if not self.legal_sets(ex.attacker, "S", ex.kind):
                    self._resolve()
                    continue
            return

    def _resolve(self) -> None:
        ex = self.exchange
        cfg = self.cfg
        tgt = self.players[ex.target]
        pct = self.attack_percent(ex)
        res = {"percent": pct, "released": False, "hit": False,
               "release_roll": None, "attack_roll": None, "damage": 0,
               "extras": [], "heals": [], "eliminated": False}
        rel = next((p for p in ex.plays if p.type == "R"), None)
        if rel:
            r = self.roll()
            res["release_roll"] = r
            if r <= rel.value:
                res["released"] = True
                self._say(f"Release roll {r} vs {rel.value}% — released! The Attack fails.")
            else:
                self._say(f"Release roll {r} vs {rel.value}% — the Release slips.")
        if not res["released"]:
            r = self.roll()
            res["attack_roll"] = r
            res["hit"] = r <= pct
            self._say(f"Attack roll {r} vs {pct}% — {'hit' if res['hit'] else 'miss'}.")

        if res["hit"]:
            tgt.hp -= ex.damage
            res["damage"] = ex.damage
            self._say(f"{tgt.name} takes {ex.damage} damage.")
            for p in ex.plays:
                if p.role == "bystander" and p.type == "S":
                    extra = min(round_half_up(p.shift / cfg.share_divisor), ex.damage)
                    tgt.hp -= extra
                    res["extras"].append({"player": p.player, "amount": extra})
                    self._say(f"{self.name(p.player)}'s Sustain deals {extra} more.")
        else:
            for p in ex.plays:
                if p.role == "bystander" and p.type == "D":
                    pl = self.players[p.player]
                    heal = min(round_half_up(p.shift / cfg.share_divisor), ex.damage,
                               cfg.start_hp - pl.hp)
                    if heal > 0:
                        pl.hp += heal
                        res["heals"].append({"player": p.player, "amount": heal})
                        self._say(f"{pl.name}'s Decay held — {pl.name} heals {heal}.")

        head = cfg.kinds[ex.kind]
        if head.head and not res["hit"] and cfg.head_bonus:
            got = 0
            while got < cfg.head_bonus and len(tgt.hand) < cfg.hand_size:
                c = self._draw()
                if c is None:
                    break
                tgt.hand.append(c)
                got += 1
            res["head_bonus"] = got
            self._say(f"{head.name}, head of the {head.family}s, is beaten back! "
                      f"{tgt.name} draws {got} card{'s' * (got != 1)}.")

        self.discard.extend(ex.cards)
        for p in ex.plays:
            self.discard.extend(p.cards)
        if tgt.hp <= 0:
            tgt.hp = 0
            tgt.alive = False
            self.discard.extend(tgt.hand)
            tgt.hand = []
            res["eliminated"] = True
            self._say(f"{tgt.name} is out!")
        ex.result = res
        self.last = ex
        self.exchange = None
        self._end_turn()

    def swap_allowed(self, pid: int) -> int:
        """How many cards `pid` may swap right now (0 = none)."""
        if (self.phase != TURN or self.current != pid or self.swapped
                or not self.cfg.swap_limit):
            return 0
        return self.cfg.swap_limit

    def _swap(self, pid: int, ids) -> None:
        """Trade cards that can't be played this turn (in no legal Attack set,
        i.e. not highlighted) for new ones.  The turn goes on."""
        limit = self.swap_allowed(pid)
        if not limit:
            raise GameError("you can't swap cards now")
        me = self.players[pid]
        hand = {c.id: c for c in me.hand}
        if not ids or len(ids) > limit:
            raise GameError(f"swap 1 to {limit} cards")
        if len(set(ids)) != len(ids) or any(i not in hand for i in ids):
            raise GameError("those cards are not all in your hand")
        playable = {i for s in self.legal_sets(pid, "A") for i in s}
        if playable & set(ids):
            raise GameError("only cards you can't play this turn may be swapped")
        cards = [hand[i] for i in ids]
        self._take(pid, cards)
        got = 0
        for _ in cards:                # draw before discarding: no swap-back
            c = self._draw()
            if c is None:
                break
            me.hand.append(c)
            got += 1
        self.discard.extend(cards)
        self.swapped = True
        self._say(f"{me.name} swaps {len(cards)} card{'s' * (len(cards) > 1)}"
                  + ("." if got == len(cards) else f" and draws {got}."))

    def _end_turn(self) -> None:
        att = self.players[self.current]
        if att.alive:
            short = len(att.hand) < self.cfg.hand_size
            n = self._refill(att, self.cfg.draw_limit)
            if self.cfg.draw_limit and short:
                self._say(f"{att.name} draws {n} card{'s' * (n != 1)} and now holds "
                          f"{len(att.hand)} (a full hand is {self.cfg.hand_size}).")
        alive = self.alive()
        if len(alive) <= 1:
            self.winners = [p.id for p in alive]
            self.phase = OVER
            if alive:
                self._say(f"★ {alive[0].name} wins! ★")
            return
        if self.turn_no >= self.cfg.max_turns:
            top = max(p.hp for p in alive)
            self.winners = [p.id for p in alive if p.hp == top]
            self.phase = OVER
            self._say(f"Turn limit reached — {', '.join(self.name(i) for i in self.winners)} "
                      f"lead{'s' if len(self.winners) == 1 else ''} with {top} HP.")
            return
        n = len(self.players)
        nxt = self.current
        for _ in range(n):
            nxt = (nxt + 1) % n
            if self.players[nxt].alive:
                break
        self.current = nxt
        self.swapped = False
        self.turn_no += 1
        self.phase = TURN
        self._say(f"— Turn {self.turn_no}: {self.name(nxt)} —")

    # ------------------------------------------------------------------ views
    def _ex_dict(self, ex: Exchange | None) -> dict | None:
        if ex is None:
            return None
        return {"attacker": ex.attacker, "target": ex.target, "kind": ex.kind,
                "cards": [c.to_dict() for c in ex.cards], "value": ex.value,
                "damage": ex.damage, "turn_no": ex.turn_no,
                "plays": [p.to_dict() for p in ex.plays],
                "percent": self.attack_percent(ex), "result": ex.result}

    def view(self, pid: int | None) -> dict:
        """Everything player `pid` may see (None = a spectator, no hand)."""
        pend = self.pending
        me = self.players[pid] if pid is not None else None
        return {
            "you": pid,
            "deck": self.cfg.public(),
            "players": [{"id": p.id, "name": p.name, "hp": p.hp,
                         "max_hp": self.cfg.start_hp, "hand_count": len(p.hand),
                         "alive": p.alive} for p in self.players],
            "hand": [c.to_dict() for c in sorted(
                me.hand, key=lambda c: (c.kind, "ADSR".index(c.type), -c.value))] if me else [],
            "turn_no": self.turn_no,
            "current": self.current,
            "phase": self.phase,
            "pending": pend[0] if pend else None,
            "legal": {t: [list(s) for s in sets] for t, sets in self.legal(pid).items()}
                     if pid is not None else {},
            "exchange": self._ex_dict(self.exchange),
            "last": self._ex_dict(self.last),
            "swap": self.swap_allowed(pid) if pid is not None else 0,
            "draw_count": len(self.deck),
            "discard_count": len(self.discard),
            "winners": list(self.winners),
            "log": self.log[-200:],
        }
