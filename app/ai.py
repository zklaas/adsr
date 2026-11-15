"""Computer players.

``choose(game, pid, level, rng)`` returns an action for the engine's pending
prompt.  The players look only at public information plus their own hand.

  easy    - any legal move, chosen at random
  normal  - greedy: best expected damage at the weakest opponent, always
            defends, helps against the Hit Point leader
  hard    - weighs odds and threat: hunts eliminations, defends with everything
            it can, and attacks in Kinds it can Sustain
Normal and Hard both pass instead of discarding on draw-limited decks once
the hand is short, since the draw can't make up the cards thrown away.
"""
from __future__ import annotations

import random

from .engine import ASSIST, DEFEND, SUSTAIN, TURN, Game, set_value

LEVELS = ("easy", "normal", "hard")


def choose(game: Game, pid: int, level: str = "normal", rng: random.Random | None = None) -> dict:
    rng = rng or random.Random()
    pend = game.pending
    if not pend or pend[0] != pid:
        raise ValueError("not this player's move")
    phase = pend[1]
    fn = {"easy": _Easy, "normal": _Normal, "hard": _Hard}.get(level, _Normal)
    return fn(game, pid, rng).decide(phase)


class _Base:
    def __init__(self, game: Game, pid: int, rng: random.Random):
        self.g, self.pid, self.rng = game, pid, rng
        self.me = game.players[pid]
        self.hand = {c.id: c for c in self.me.hand}

    def cards(self, ids):
        return [self.hand[i] for i in ids]

    def value(self, ids) -> int:
        return set_value(self.cards(ids))

    def against(self, ex):
        """Sort key: a set's value against this exchange's Attack (beat bonus in)."""
        return lambda ids: self.g.play_value(self.cards(ids), ex.kind)

    def damage(self, ids) -> int:
        return sum(self.hand[i].damage for i in ids)

    def sets(self, typ, kind=None):
        return self.g.legal_sets(self.pid, typ, kind)

    def decide(self, phase):
        ex = self.g.exchange
        if phase == TURN:
            n = self.g.swap_allowed(self.pid)
            pick = self.swap_pick(n) if n else []
            if pick:
                return {"type": "swap", "cards": pick}
            return self.turn()
        if phase == DEFEND:
            return {"type": "respond", "cards": self.defend(ex)}
        if phase == ASSIST:
            return {"type": "assist", "cards": self.assist(ex)}
        if phase == SUSTAIN:
            return {"type": "sustain", "cards": self.sustain(ex)}
        raise ValueError(phase)

    # shared helpers
    def dead_cards(self) -> list[int]:
        """The hand ordered from least to most worth keeping: cards that can't
        join any legal set first, then surplus Sustains/Decays (they pile up
        because they're only spent reactively), Releases kept longest."""
        usable = set()
        for typ in "ADSR":
            for s in self.sets(typ):
                usable.update(s)
        per_type = {t: sum(c.type == t for c in self.me.hand) for t in "ADSR"}
        rank = {"S": 1, "D": 2, "A": 3, "R": 4}

        def worth(c):
            return (c.id in usable, -per_type[c.type] if c.type in "SD" else 0,
                    rank[c.type], c.value + c.damage)
        return [c.id for c in sorted(self.me.hand, key=worth)]

    KEEP_SD = 3        # Sustains / Decays of one type worth holding before swapping extras
    SWAP_ALL = False   # with no Attack to play, swap any dimmed cards to dig for one

    def swap_pick(self, n: int) -> list[int]:
        """Cards worth trading in: first those that fit no set at all (a ×2 or
        ×3 Attack with no partners), then Sustains/Decays beyond a few."""
        attackable = {i for s in self.sets("A") for i in s}
        usable = {i for t in "ADSR" for s in self.sets(t) for i in s}
        dimmed = [c for c in self.me.hand if c.id not in attackable]
        junk = [c for c in dimmed if c.id not in usable]
        for typ in "SD":               # (a ×2 with no partner is junk already)
            same = sorted((c for c in dimmed if c.type == typ and c not in junk),
                          key=lambda c: c.value)
            junk += same[:max(0, len(same) - self.KEEP_SD)]
        if self.SWAP_ALL and not attackable:
            junk += sorted((c for c in dimmed if c not in junk and c.type != "R"),
                           key=lambda c: c.value)
        return [c.id for c in junk[:n]]

    def discard(self) -> dict:
        return {"type": "discard", "cards": self.dead_cards()[:self.g.cfg.max_discard]}

    def best(self, sets, key):
        return max(sets, key=key) if sets else None


class _Easy(_Base):
    def swap_pick(self, n):
        dimmed = [c.id for c in self.me.hand
                  if c.id not in {i for s in self.sets("A") for i in s}]
        if dimmed and self.rng.random() < 0.3:
            return self.rng.sample(dimmed, min(n, len(dimmed), self.rng.randint(1, n)))
        return []

    def turn(self):
        sets = self.sets("A")
        if sets and self.rng.random() < 0.85:
            tgt = self.rng.choice(self.g.opponents(self.pid)).id
            return {"type": "attack", "cards": list(self.rng.choice(sets)), "target": tgt}
        k = self.rng.randint(0, min(self.g.cfg.max_discard, len(self.me.hand)))
        return {"type": "discard", "cards": [c.id for c in self.rng.sample(self.me.hand, k)]}

    def defend(self, ex):
        out = []
        for typ in "DR":
            sets = self.sets(typ, ex.kind)
            if sets and self.rng.random() < 0.5:
                out += self.rng.choice(sets)
        return out

    def assist(self, ex):
        sets = self.sets("S", ex.kind) + self.sets("D", ex.kind)
        return list(self.rng.choice(sets)) if sets and self.rng.random() < 0.3 else []

    def sustain(self, ex):
        sets = self.sets("S", ex.kind)
        return list(self.rng.choice(sets)) if sets and self.rng.random() < 0.5 else []


class _Normal(_Base):
    def rationed(self) -> bool:
        """True when this turn's draw can't top the hand up anyway, so
        discarding only throws cards away.  In simulation (3x deck, draw 1)
        passing instead beat the always-discarding player 87-13 head to head;
        also rationing Decays, Releases, Sustains or weak Attacks made no
        reliable difference, so the rest of their play is unchanged."""
        cfg = self.g.cfg
        return bool(cfg.draw_limit) and len(self.me.hand) + cfg.draw_limit <= cfg.hand_size

    LEADER_GAP = 20      # HP ahead of everyone else that makes someone "clearly leading"
    LEADER_SHARE = 0.5   # how often Normal then attacks that leader instead of the weakest

    def turn(self):
        """Attack the weakest opponent, except that someone who has pulled clearly
        ahead gets attacked half the time.  Always ganging up on the weakest made
        Normal lose to Easy (sim, Captains deck, 2 Easy + 2 Normal, 800 games:
        Easy 28.8% vs Normal 21.2% per seat); with the leader rule Normal wins
        26.9% vs 23.1%, 1 Easy + 1 Normal + 1 Hard is unchanged (6/20/74%) and
        games run about 6% longer (2026-11-15)."""
        sets = self.sets("A")
        if sets:
            best = self.best(sets, lambda s: (self.value(s) * self.damage(s), -len(s)))
            opps = self.g.opponents(self.pid)
            tgt = min(opps, key=lambda p: (p.hp, self.rng.random()))
            lead = max(opps, key=lambda p: (p.hp, self.rng.random()))
            rest = [p.hp for p in opps if p.id != lead.id] + [self.me.hp]
            if lead.hp - max(rest) >= self.LEADER_GAP and self.rng.random() < self.LEADER_SHARE:
                tgt = lead
            return {"type": "attack", "cards": list(best), "target": tgt.id}
        if self.rationed():
            return {"type": "discard", "cards": []}     # pass: keep every card
        return self.discard()

    def defend(self, ex):
        out = []
        dec = self.best(self.sets("D", ex.kind), self.against(ex))
        if dec:
            out += dec
        rel = self.best(self.sets("R", ex.kind), self.against(ex))
        if rel and (ex.damage >= 10 or ex.damage >= self.me.hp):
            out += rel
        return out

    def leader(self, exclude=()):
        others = [p for p in self.g.opponents(self.pid) if p.id not in exclude]
        return max(others, key=lambda p: p.hp) if others else None

    def assist(self, ex):
        lead = self.leader()
        if lead is None:
            return []
        if ex.target == lead.id:
            s = self.best(self.sets("S", ex.kind), self.value)
            return list(s) if s else []
        if ex.attacker == lead.id:
            d = self.best(self.sets("D", ex.kind), self.against(ex))
            return list(d) if d else []
        return []

    def sustain(self, ex):
        s = self.best(self.sets("S", ex.kind), self.value)
        return list(s) if s else []


class _Hard(_Normal):
    # Swapping (3x deck, swap 2): trading in every spare Sustain/Decay and
    # digging for an Attack when there is none beat the gentler Normal policy
    # about 2 to 1 head to head.
    KEEP_SD = 0
    SWAP_ALL = True
    def p_hit(self, value):
        return self.g.clamp(value) / 100


    def turn(self):
        sets = self.sets("A")
        opps = self.g.opponents(self.pid)
        lead_hp = max(p.hp for p in opps)
        best, best_score = None, 0.0
        for s in sets:
            # An Attack we can back with our own Sustain is worth more.
            sus = self.sets("S", self.hand[s[0]].kind)
            boost = max((self.value(x) / self.g.cfg.shift_divisor for x in sus), default=0)
            p, dmg = self.p_hit(self.value(s) + boost), self.damage(s)
            for o in opps:
                # Opponents holding many cards are likelier to defend.
                guard = 1.0 - 0.04 * max(0, len(o.hand) - 4)
                score = p * min(dmg, o.hp) * guard
                if dmg >= o.hp:
                    score += 12 * p                  # elimination
                score += 0.04 * o.hp * (o.hp == lead_hp)  # pressure the leader
                score -= 0.6 * (len(s) - 1)          # cards spent
                if score > best_score:
                    best, best_score = (s, o.id), score
        if best:
            return {"type": "attack", "cards": list(best[0]), "target": best[1]}
        if self.rationed():
            return {"type": "discard", "cards": []}     # pass: keep every card
        return self.discard()

    def threat(self, ex):
        """Expected damage of the Attack as it stands."""
        return self.p_hit(self.g.attack_percent(ex)) * ex.damage

    def defend(self, ex):
        # Simulation shows defence cards are worth more spent than held: they
        # only leave the hand reactively, so hoarding them clogs it.
        out = []
        dec = self.best(self.sets("D", ex.kind), self.against(ex))
        if dec:
            out += dec
        rel = self.best(self.sets("R", ex.kind), self.against(ex))
        if rel:
            out += rel
        return out

    def assist(self, ex):
        if len(self.me.hand) <= 2:
            return []
        lead = self.leader()
        tgt = self.g.players[ex.target]
        att = self.g.players[ex.attacker]
        sus = self.sets("S", ex.kind)
        dec = self.sets("D", ex.kind)
        # Finishing off a rival, or bleeding the leader, is worth a card.
        if sus and (ex.target == lead.id or ex.damage >= tgt.hp):
            return list(min(sus, key=lambda s: (len(s), -self.value(s))))
        # Blunt the leader's Attacks; the heal is a bonus when we're hurt.
        if dec and ex.attacker == lead.id and (att.hp > self.me.hp or
                                               self.me.hp < self.g.cfg.start_hp):
            return list(min(dec, key=lambda s: (len(s), -self.value(s))))
        return []
