# ADSR

A card game of **Attack, Decay, Sustain and Release**, played against the
computer, hot-seat on one screen, or over the LAN. PyQt6; otherwise
standard library only.

## Download

Ready-to-run downloads (executable programs), with nothing else to install:

* **Windows:** [ADSR-Setup-Windows.exe](https://github.com/zklaas/adsr/releases/latest/download/ADSR-Setup-Windows.exe)
* **macOS** (Apple silicon): [ADSR-macOS.dmg](https://github.com/zklaas/adsr/releases/latest/download/ADSR-macOS.dmg)
* **Linux:** [ADSR-Linux-x86_64.AppImage](https://github.com/zklaas/adsr/releases/latest/download/ADSR-Linux-x86_64.AppImage)

The first time, Windows or macOS asks before opening it; the
[release page](https://github.com/zklaas/adsr/releases/latest) says what to click.
To install from the source code at the command line instead, see below.

```
./install.sh            # puts `adsr` on your PATH and adds a dash entry
adsr                    # open the table
adsr --deck my.json     # play with another deck file
adsr rules              # print the rules (also Game ▸ How to play, F1)
adsr sim 500 --players easy,normal,hard     # computer-vs-computer stats
python3 -m unittest test_engine             # tests
```

Rules: [RULES.md](RULES.md).

## Files

| | |
|---|---|
| `adsr.py` | entry point / command line |
| `app/cards.py` | cards, Kinds, deck file loading and validation |
| `app/engine.py` | the rules: a state machine that asks one player at a time |
| `app/ai.py` | Easy / Normal / Hard computer players |
| `app/net.py` | LAN host and client (JSON lines over TCP, port 47420) |
| `app/gui.py` | the table, setup dialog, hot-seat curtain, LAN lobby |
| `app/sim.py` | `adsr sim` balance runs |
| `deck.json` | the default deck, *Captains (1x)* |
| `make_icon.py` | rebuilds `icons/` — four fanned cards behind "ADSR" (needs Pillow; lettering in Comfortaa Bold if installed via `fonts-comfortaa`, else URW Gothic Demi — free fonts only) |

## Deck files

Copy `deck.json` (or a file from `decks/`) and edit it, then pick it under **Deck** in the New game
dialog (or `adsr --deck`). Only the LAN host needs the file.

Ready-made configurations live in `decks/`; any valid `.json` dropped there is
listed by its `"name"` in the **Deck** menu next to the default, and the menu's choice is used
for the next new game (it is remembered). **Other deck file…** picks one from
anywhere.

| Configuration | Cards | Per Kind | Hand | Draw | Swap |
|---|---|---|---|---|---|
| Romeo and Juliet (2x) (`decks/romeo-juliet-2x.json`) | 320 | 6A (×1, ×2; no ×3) · 3S · 5D · 2R (the two friars double) | 16 | 1 a turn | up to 2 |
| Sound waves (3x) (`decks/sound-3x.json`) | 140 | 7A (×1, ×2, one ×3) · 2S · 4D · 1R | 14 | 1 a turn | up to 2 |
| Rock Paper Scissors Lizard Alien (3x) (`decks/rpsla-3x.json`) | 210 | same as 3x deck | 14 | 1 a turn | up to 2 |
| Hatfields and McCoys (3x) (`decks/hatfields-mccoys-3x.json`) | 280 | same as 3x deck | 14 | 1 a turn | up to 2 |
| Balance of Power (3x) (`decks/balance-of-power-3x.json`) | 280 | 7A · 3S · 3D · 1R, S and D wild | 14 | 1 a turn | up to 2 |
| Captains (1x) (default, `deck.json`) | 420 | 6A (×1 only) · 8S · 5D · 2R | 16 | 1 a turn | up to 2 |
| Infielders (putouts and assists) (`decks/infielders.json`) | 425 | one type per Kind: 1B, C 12A (×1) · 2B, SS, 3B 11S (×1, ×2) · P 20D · OF 8R | 16 | 1 a turn | up to 2 |

The **Romeo and Juliet (2x)** deck, the default for part of 2026-10-31, is a "2x"
deck: Attacks come as ×1 and ×2 cards only (the 3x deck minus its ×3), with
more Sustains, Decays and Releases than the 3x deck — per Kind 6A · 3S · 5D ·
2R. 18 Kinds in 5 families of characters from the play: Montagues (blues,
crossed rapiers) — Romeo, Lord Montague, Lady Montague, Benvolio; Capulets
(crimsons, Juliet's balcony) — Juliet, Lord Capulet, Lady Capulet, Tybalt;
Citizens of Verona (greens, a tower with Verona's swallowtail merlons) —
Prince Escalus, Mercutio, Count Paris, First Watchman; Servants (browns, a
serving jug) — Nurse, Peter, Sampson, Balthasar; Church Figures (purples, a
chapel) — Friar Laurence, Friar John. The play has only two friars, so their
Kinds carry their own `cards` block with every count doubled; each family
then holds 64 cards and a friar Decay answers as many Attacks as any other.
Simulation (3 players Easy/Normal/Hard, 150 games, draw 1, swap 2; 3x deck
for comparison: 89 turns, no Attack on 40% of turns, 8% released):

| Per Kind (S · D · R) | Hand | Turns | No Attack | Released |
|---|---|---|---|---|
| 2 · 4 · 1 | 14 | 89 | 35% | 7% |
| 3 · 5 · 1 | 14 | 101 | 43% | 7% |
| 3 · 5 · 2 | 14 | 121 | 51% | 14% |
| **3 · 5 · 2** | **16** | **119** | **48%** | **13%** |
| 3 · 5 · 2 | 18 | 107 | 44% | 12% |
| 3 · 5 · 1 | 18 | 91 | 36% | 7% |

The extra modifiers dilute the Attacks (6 of 16 cards), so the hand grows to
16 to win some back; the doubled Releases are what lengthens games most. 4
players (Normal ×2, Hard ×2): ~177 turns vs the 3x deck's ~137. Hard ~75%
in 3-player games.

The **Captains (1x)** deck, the default since 2026-10-31, has single Attacks only — no ×2 or
×3 cards (4 × 70%/6 dmg, 2 × 55%/10 dmg) — and many more Sustains: per Kind
6A · 8S · 5D · 2R, so Sustain is the most common card type (160 of 420). 20
Kinds in 5 families of captains: Mariners (blues, an anchor) — Sea Captain,
Naval Captain, Pirate Captain, Riverboat Captain; Soldiers (reds, a
captain's two collar bars) — Army Captain, Cavalry Captain, Captain of the
Guard, Militia Captain; Aviators (greens, pilot's wings) — Airline Captain,
Group Captain, Airship Captain, Starship Captain; Team Captains (browns, a
"C" armband) — Hockey, Football, Cricket and Rugby Captain; Civic Captains
(purples, a shield badge with a star) — Fire Captain, Police Captain, Port
Captain, Captain of Industry. Simulation (4 players Normal ×2, Hard ×2, 100
games): median 139 turns vs Romeo and Juliet's 180, no Attack possible on 41%
of turns (R&J 50%), 57% of Attacks hit; the extra Sustains shorten games
rather than lengthen them.

The **Infielders (putouts and assists)** deck (2026-10-31) gives each Kind a
single card type, by fielding position. Each of the 5 families is a franchise's
all-time team of seven: the **first baseman and catcher** (who record most
putouts) hold the Attacks — 12 each, all ×1 (8 × 70%/6 dmg, 4 × 55%/10 dmg);
the **second baseman, shortstop and third baseman** (who record assists) hold
the Sustains — 11 each: 5 × 40%, 2 × 60% and 4 ×2 cards at 80% (a pair of
them lifts an Attack +20); a **pitcher** holds the family's 20 Decays (12 ×
40%, 8 × 60%) and an **outfielder** its 8 Releases (55%). A family's
Sustains, Decays and Releases work on its own first baseman's and catcher's
Attacks, as in any deck. Emblems are generic baseball pictures, not team
logos:

| Family | 1B | C | 2B | SS | 3B | P | OF |
|---|---|---|---|---|---|---|---|
| Yankees (greys, bat and ball) | Lou Gehrig | Yogi Berra | Tony Lazzeri | Derek Jeter | Graig Nettles | Whitey Ford | Joe DiMaggio |
| Cardinals (reds, baseball) | Albert Pujols | Yadier Molina | Rogers Hornsby | Ozzie Smith | Ken Boyer | Bob Gibson | Stan Musial |
| Dodgers (blues, ball cap) | Gil Hodges | Roy Campanella | Jackie Robinson | Pee Wee Reese | Ron Cey | Sandy Koufax | Duke Snider |
| Red Sox (greens, scoreboard wall) | Jimmie Foxx | Carlton Fisk | Bobby Doerr | Nomar Garciaparra | Wade Boggs | Pedro Martínez | Ted Williams |
| Cubs (browns, Boston ivy leaf) | Frank Chance | Gabby Hartnett | Ryne Sandberg | Ernie Banks | Ron Santo | Fergie Jenkins | Billy Williams |

Per family that is 24A · 33S · 20D · 8R, close to a Captains family (24 · 32
· 20 · 8), and it plays alike: simulation (4 players Normal ×2, Hard ×2, 2 ×
100 games) median ~148 turns (Captains 143), no Attack possible on 41–42% of
turns, 56–57% of Attacks hit. The ×2 Sustains get played (the AI pairs
them); they first exposed an AI bug — an unpartnered ×2 counted twice when
choosing cards to swap — fixed in `ai.py`.

The Hatfields and McCoys deck has two families of ten Kinds, named for people
in the historical feud (1863–1891). Hatfield (reds and browns, a bearded
figure in a slouch hat): Devil Anse, Levicy, Johnse, Cap, Ellison, Wall,
Elias, Tennis, Preacher Anse, Floyd. McCoy (blues, a figure in a straw boater
with a pipe): Ole Ran'l, Sarah, Roseanna, Nancy, Tolbert, Pharmer, Bud,
Alifair, Calvin, Asa Harmon. In simulation 5, 8, 10 or 12 Kinds per family
all played alike (~95–104 turns; respond ~63%); ten per family gives the
most names. With twenty Kinds, ×3 Attack sets are very rare.

Each family has a **head**, marked ★: Devil Anse for the Hatfields and Ole
Ran'l for the McCoys (`"heads": {"Hatfield": "Devil Anse", "McCoy": "Ole
Ran'l"}`). A head's Attack cards deal `head_damage` (3) more each, and when a
head's Attack misses or is Released the target draws `head_bonus` (2) extra
cards (never above the hand size). Simulation: ~95 turns, Hard ~75%, Normal
~20%, Easy ~5%; teaching Hard to weigh the card prize made no difference.

The Rock Paper Scissors Lizard Alien deck has 15 Kinds in 5 families: Rock
(Granite, Obsidian, Basalt), Paper (Parchment, Papyrus, Vellum), Scissors
(Shears, Scalpel, Cleaver), Lizard (Gecko, Iguana, Chameleon) and Alien
(Spore Drifter, Crystal Mite, Methane Floater), each family with its own
emblem and colour range. With 5 families a defence matches fewer Attacks:
in simulation players could respond only ~50% of the time (3x deck ~57%), so
the deck has a `beats` table (Rock blunts Scissors and crushes Lizard; Paper
covers Rock and smothers Alien; Scissors cut Paper and snip Lizard; Lizard
eats Paper and devours Alien; Alien corrodes Scissors and dissolves Rock): a
beating family's Decays and Releases answer the Attack too, at +15%. That
lifts responding to ~67% and lengthens games from ~91 to ~117 turns
(bonus +0 → ~105, +25 → ~120: the extra answers matter more than the bonus
size). Hard ~76%, Normal ~20%, Easy ~4%. 2 Kinds per family played the same.

The Balance of Power deck has 20 Kinds in 5 families of statesmen (all
active before 1950) known for keeping a balance of power: Antiquity
(terracottas, an Ionic column) — Tissaphernes, Hiero II, Su Qin, Kautilya;
Renaissance (crimsons, the Medici balls) — Cosimo de' Medici, Lorenzo de'
Medici, Francesco Sforza, Cardinal Wolsey; Grand Alliance (purples, a crown)
— Richelieu, William III, Kaunitz, Pitt the Younger; Concert of Europe
(blues, a quill over a signature) — Metternich, Castlereagh, Talleyrand,
Bismarck; Between Empires (greens, a balance) — Chulalongkorn, Abdur Rahman
Khan, Menelik II, İsmet İnönü. Its **Sustain and Decay cards are wild**
(`"wild": ["D", "S"]`, marked WILD on the card): they answer an Attack of any
Kind. Releases still answer their own family only, and sets still never mix
Kinds. Simulation (4 players, Normal/Hard, 150–300 games each; per Kind
7A and 1R throughout, S/D counts varied):

| Per Kind | Wild | Turns | Target Decays | Bystander S / D per Attack | Hit | Leader at ⅔ wins |
|---|---|---|---|---|---|---|
| 2S · 4D | no | 134 | 32% | 0.10 / 0.17 | 59% | 73% |
| 2S · 4D | yes | 162 | 51% | 0.14 / 0.24 | 58% | 74% |
| 2S · 3D | yes | 142 | 41% | 0.14 / 0.18 | 58% | — |
| 2S · 2D | yes | 117 | 29% | 0.14 / 0.12 | 61% | — |
| **3S · 3D** | yes | 143 | 41% | 0.21 / 0.18 | 61% | **64%** |
| 2S · 2D · 2R | yes | 154 | 28% | 0.14 / 0.12 | 56% | 72% |

Wild cards are never dead in the hand, so they get played far more, but
since Sustains are wild too the Attack's odds barely move (final chance
~63–66% in every row): the change is in *who* joins, not in hit rate. With
the 3x deck's 4 Decays the extra defence only drags games out ~20%. Equal
Sustains and Decays (3 and 3, still 14 cards per Kind) gives the most
bystander play, keeps the game as long as the 3x deck, and is the only mix
that pulled a runaway leader back (the HP leader two-thirds of the way in
won 64% instead of ~73%; attacks on the leader do 5.6 damage vs 4.4 on
others), so the deck uses it. 6 players: ~220 turns (3x counts wild ~254).
3 players: ~97 turns. Hard ~75% / Normal ~10% in 4-player.

```json
{
  "name": "3x deck",
  "rules": { "start_hp": 100, "hand_size": 14, "max_discard": 2,
             "draw_limit": 1, "swap_limit": 2, "shift_divisor": 4, "min_percent": 5, "max_percent": 95,
             "share_divisor": 3, "max_turns": 400, "max_players": 6 },
  "kinds": [
    {"name": "Sine", "family": "Smooth", "color": "#3b7fc4", "glyph": "sine"},
    {"name": "Cosine", "family": "Smooth", "color": "#5b6ee1", "glyph": "cosine"},
    {"name": "Fuzz", "color": "#777777", "glyph": "letter",
     "cards": { "A": [ ... ], "R": [ ... ] }}
  ],
  "cards": { "A": [ ... ], "R": [ ... ] }}
  ],
  "cards": {
    "A": [{"value": 70, "need": 1, "damage": 6, "count": 3}, ...],
    "S": [{"value": 60, "need": 1, "count": 2}, ...],
    "D": [...],
    "R": [...]
  }
}
```

- **kinds** — any number, each with a `name`, a `color`, a `glyph` and
  optionally a `family`. Sustain, Decay and Release cards work on Attacks of
  any Kind in their family; a Kind with no `family` is a family of its own
  (exact-Kind matching). Glyphs: `sine`, `cosine`, `triangle`, `square`,
  `pulse`, `ramp`, `saw`, `reverse saw`, `noise`, `wavetable`, the emblems
  `rock`, `paper`, `scissors`, `lizard`, `alien`, the portraits `hatfield`
  and `mccoy`, the Balance of Power and Romeo and Juliet emblems `column`, `palle`, `crown`,
  `quill`, `scales`, `rapier`, `balcony`, `tower`, `ewer`, `chapel`, the Captains
  emblems `anchor`, `bars`, `wings`, `armband`, `badge`, the Infielders emblems
  `bat`, `baseball`, `cap`, `scoreboard`, `ivy`, or `letter` to
  show the Kind's initial. A Kind with its own `cards` block uses that instead
  of the shared one.
- **cards** — templates per type: `value` (1–100 %), `need` (the ×N set size),
  `count` (copies per Kind) and, for Attacks, `damage`. The deck needs at
  least one Attack and every Kind at least one card, but a Kind need not hold
  every type (in the Infielders deck each Kind holds just one).
- **rules** — any you leave out keep the defaults shown above. `draw_limit`
  is the most cards drawn at the end of a turn; 0 refills the hand fully.
  The opening deal always fills every hand. `swap_limit` lets a player, once
  a turn and before attacking, trade up to that many cards that are in no
  playable Attack set (dimmed in the hand) for new ones; 0 turns it off.
  `beat_bonus` (default 15) is the % a beating family's card gains.
- **beats** (optional) — which families beat which, e.g.
  `"beats": {"Rock": {"Scissors": "blunts", "Lizard": "crushes"}, ...}` (or a
  plain list of families; the verb is only for the game log). A Decay or
  Release from a family that beats the Attack's family may answer it, at
  `beat_bonus` % more.
- **wild** (optional) — a list of card types from `S`, `D`, `R`, e.g.
  `"wild": ["D", "S"]`: cards of those types answer an Attack of any Kind
  (sets still never mix Kinds).
- **heads** (optional) — `{"family": "Kind name"}`: that Kind heads its
  family. Its Attack cards get `head_damage` more damage, and stopping one of
  its Attacks (a miss or a Release) lets the target draw `head_bonus` cards.
  Decks without `heads` are unaffected by either rule.
  `shift_divisor`: Sustain/Decay move the Attack by value ÷ this.
  `share_divisor`: a bystander's reward is their shift ÷ this.

`adsr sim --deck my.json` is a quick way to see how a new deck plays.

## Balance notes

The 3x deck (the default until 2026-10-31) was sized by simulation (`adsr sim` reports how much choice
players get). It grew out of an earlier 110-card *Waveforms* deck (since
removed: same Kinds, 5A · 2S · 3D · 1R per Kind, ×2 Attacks only, hand 12,
full refills); findings below that mention Waveforms refer to it.

- **Hand size and the share of Attack cards** decide whether you have an
  Attack to play; adding more cards in the same mix made choices *scarcer*.
  Hand 12 was Waveforms' size.
- **Matching** decides whether you can respond, join in or Sustain. With exact
  Kind matching, more Kinds means less choice (3 Kinds ≫ 4 ≫ 5; with 10 Kinds
  you could respond only ~45% of the time). **Families** fix that: 10 Kinds in
  3 families play like 3 Kinds.
- For 10 Kinds in 3 families the best mix was **5 Attack, 2 Sustain, 3 Decay,
  1 Release per Kind** (110 cards). In 3-player games you have an Attack on 91%
  of turns, can respond when attacked 76% of the time, can join others'
  exchanges 83%, and can Sustain your own Attack 48%.
- Multi-card *modifiers* (a ×2 Decay or Sustain) and ×3 Attacks cost a lot of
  choice at these per-Kind counts (respond −12 points; ×3 Attacks lengthen
  games by ~20%), so Waveforms used ×2 Attacks only.
- The **3x deck** (the default 2026-10-17 to 10-31) adds them back the affordable way: a ×3 card replacing a ×1
  leaves no playable Attack on 41% of turns, so each Kind gains a ×3 *and* a
  ×1 Attack, one Decay to keep responses up (7 Attacks alone drop them to
  71%), and hand 14 so three of one Kind turn up more often. Sim: about 55
  turns, no Attack on ~11% of turns, ~6% of Attacks are ×3 sets, respond ~80%,
  Sustain own Attack ~39% (the one stat that stays below Waveforms) — those
  figures are with full refills. The deck now draws 1 card a turn (user's
  choice), which slows it right down: median ~154 turns, no Attack on ~62% of
  turns. Draw 2 gives ~78 turns / 27%; draw 3 plays like a full refill.
- **Computer players on draw-limited decks**: Normal and Hard pass instead of
  discarding once the draw can't refill their hand (discard 2, draw 1 only
  shrinks it). That alone beat the old Hard 87–13 head to head and fixed
  Normal losing to Easy on the 3x deck. Also rationing Decays, Releases,
  Sustains, holding back weak Attacks or targeting thin-handed opponents was
  tried and made no reliable difference. 3x deck, 3 players: Hard 60%,
  Normal 36%, Easy 4%; ~130 turns.
- **Swaps** (3x deck, `swap_limit` 2) cut that to ~88 turns. A swap that
  ended the turn instead was worse: Easy's random swaps kept pace with Normal.
  Limit 3 played like 2. Hard swaps every spare Sustain/Decay and, with no
  Attack in hand, any dimmed non-Release card (beat a cautious policy ~2:1);
  Normal keeps 3 of each and doesn't dig; Easy swaps at random. Result:
  Hard 73%, Normal 22%, Easy 5%.
- More Releases make games drag: each is a chance to cancel an Attack outright.
- Game length tracks `start_hp`: with Waveforms at 100 HP games lasted about
  36 / 50 / 72 turns for 2 / 3 / 4 players; 75 HP gave about 26 / 37 / 54.

With the 3x deck, a 3-player Easy/Normal/Hard game lasts about 89
turns and is won by Hard about 73%, Normal 22% and Easy 5% of the time.

## Windows and macOS

The same code runs on Windows and macOS. To install it there:

* **Windows:** see [WINDOWS.md](WINDOWS.md) (`install.ps1`).
* **macOS:** see [MACOS.md](MACOS.md) (`install-macos.sh`).
