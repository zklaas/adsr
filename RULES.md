# How to play ADSR

**Attack · Decay · Sustain · Release** — a card game for 2–6 players, any mix
of people and computer players. Last player with Hit Points wins.

## The cards

Every card has a **Kind** (like a suit), which belongs to a **family**, and a
**type**:

| Type | What it does |
|---|---|
| **A — Attack** | Your way of hurting an opponent. Shows a hit chance (%) and **damage**. |
| **D — Decay** | Hurts an Attack: lowers its hit chance. |
| **S — Sustain** | Helps an Attack: raises its hit chance. |
| **R — Release** | Defeats an Attack: a roll that, if it succeeds, cancels the Attack outright. |

The default deck, **Captains (1x)**, has twenty Kinds of captain in five
families. Each family has its own colour range and emblem:

| Family | Kinds |
|---|---|
| **Mariners** (blues, an anchor) | Sea Captain, Naval Captain, Pirate Captain, Riverboat Captain |
| **Soldiers** (reds, a captain's two collar bars) | Army Captain, Cavalry Captain, Captain of the Guard, Militia Captain |
| **Aviators** (greens, pilot's wings) | Airline Captain, Group Captain, Airship Captain, Starship Captain |
| **Team Captains** (browns, a "C" armband) | Hockey Captain, Football Captain, Cricket Captain, Rugby Captain |
| **Civic Captains** (purples, a shield badge with a star) | Fire Captain, Police Captain, Port Captain, Captain of Industry |

Each Kind has 21 cards: 6 Attack (all single cards — no ×2 or ×3), 8
Sustain, 5 Decay and 2 Release; 420 in all. You hold 16 cards.

Other decks (*Romeo and Juliet (2x)*, *Sound waves (3x)* and the other
themed decks) are under **Deck** in the menu. In the *Infielders* deck each
player holds one card type by position: first basemen and catchers Attack,
second basemen, shortstops and third basemen Sustain (some as ×2 pairs),
pitchers Decay and outfielders Release — each helping only their own
franchise.

Sustain, Decay and Release cards work on an Attack of **any Kind in their
family**, at full value — a Pirate Captain Decay can answer a Sea Captain
Attack, but not an Army Captain one.

## Sets: cards that need company

Cards are always played in **sets**: one or more cards of the **same Kind and
type** (a set never mixes Kinds, even within a family). A card marked **×2**
or **×3** must be played in a set of exactly that many cards. A plain card (×1) can be played alone, or can fill out a bigger
card's set.

In the Captains deck every card is ×1, so every set is a single card. The
other decks have ×2 and ×3 cards; the set always has **exactly as many cards
as the largest ×N in it** (examples from the Romeo and Juliet deck):

- Mercutio Attack alone ✔
- Romeo Attack ×2 + Romeo Attack ×1 ✔ (two cards, largest is ×2)
- Romeo Attack ×2 alone ✘ (needs a partner)
- Nurse Attack + Nurse Attack, both ×1 ✘ (largest is ×1, so the set must be one card)
- Romeo Attack ×2 + Benvolio Attack ✘ (different Kinds)

A set's **percentage is the average** of its cards (rounded). An Attack set's
**damage is the total** of its cards, so big sets hit harder.

## A turn

Everyone starts with **100 Hit Points** and **16 cards** (14 with the
3x deck and the other themed decks). On your turn:

1. **Swap** (optional, once) — trade up to 2 cards you can't play this turn
   (the dimmed ones in your hand) for the same number from the draw pile.
2. Then either **Attack** — play an Attack set and choose a living opponent
   as the target — or **Discard** up to 2 cards (or none, to pass).

At the end of your turn you **draw 1 card** (never above your hand size). Cards you spend
defending or joining in on other turns come back slowly, so a hand can run
low. Play passes to the next living player.

### Rock Paper Scissors Lizard Alien deck

This deck has five families, and each beats two others:

| Family | beats |
|---|---|
| **Rock** | blunts Scissors, crushes Lizard |
| **Paper** | covers Rock, smothers Alien |
| **Scissors** | cut Paper, snip Lizard |
| **Lizard** | eats Paper, devours Alien |
| **Alien** | corrodes Scissors, dissolves Rock |

A **Decay or Release** from a family that beats the Attack's family can answer
it too — a Rock Decay can blunt a Scissors Attack — and gets **+15%** to its
value. Sustains still have to come from the Attack's own family. Card
tooltips list what each family beats.

### Hatfields and McCoys deck

Each family has a **head**, marked ★ on its cards: **Devil Anse** for the
Hatfields and **Ole Ran'l** for the McCoys. A head's Attack cards deal
**3 more damage** each. But if a head's Attack **misses or is Released**,
the player it was aimed at **draws 2 extra cards** (up to the full hand of 14).

### Balance of Power deck

Twenty statesmen who kept the balance of power, in five families:

| Family | Kinds |
|---|---|
| **Antiquity** | Tissaphernes, Hiero II, Su Qin, Kautilya |
| **Renaissance** | Cosimo de' Medici, Lorenzo de' Medici, Francesco Sforza, Cardinal Wolsey |
| **Grand Alliance** | Richelieu, William III, Kaunitz, Pitt the Younger |
| **Concert of Europe** | Metternich, Castlereagh, Talleyrand, Bismarck |
| **Between Empires** | Chulalongkorn, Abdur Rahman Khan, Menelik II, İsmet İnönü |

**Sustain and Decay cards are wild** (marked WILD): they can answer an
Attack of **any Kind**, from any family. Releases still have to come from
the Attack's own family, and a set still never mixes Kinds. Each Kind has
7 Attack, 3 Sustain, 3 Decay and 1 Release.

Other deck files can change these numbers — a deck can refill your hand fully
each turn, or turn swaps off. The New game dialog shows each deck's hand
size, draw and swap rules.

## An exchange

When you Attack, the exchange runs in this order:

1. **The target responds.** They may play a Decay set, a Release set, both, or nothing.
2. **Others may join in.** Every other player, in turn order, may add **one**
   Sustain set *or* one Decay set, or stay out.
3. **The attacker may Sustain.** You may add one Sustain set.
4. **Resolve.**
   - If a Release was played, roll d100: **at or under** the Release's
     percentage and the Attack is released — it fails.
   - Otherwise roll d100 for the Attack: **at or under** its chance is a hit,
     and the target loses the Attack's damage.

**The Attack's chance** is its set percentage, **plus a quarter of each Sustain
set's percentage, minus a quarter of each Decay set's**, kept between 5% and
95% (nothing is ever certain). Example: a 70% Attack, a 60% Decay (−15) and a
40% Sustain (+10) gives 65%.

Players with nothing they could legally play at a step are skipped.

## Why join someone else's fight?

- **Sustain an Attack that hits:** you deal extra damage to the target equal
  to a third of your Sustain's bonus (at most the Attack's own damage).
- **Decay an Attack that fails** (missed or released): you heal by a third of
  your Decay's reduction, up to your starting Hit Points.

So helping knock down the leader, or blunting the leader's Attacks, pays you
back directly.

## Out and winning

At 0 Hit Points you're out and your hand is discarded. The last player
standing wins. (As a safety net, if a game reaches 400 turns the player with
the most Hit Points wins.)

When the draw pile runs out, the discards are shuffled into a new one.

## Playing on screen

- **Click** cards to select them; **double-click** a card to select the
  strongest legal set it belongs to.
- Faded cards can't be used at this step.
- **Hot-seat:** with two or more people at one computer, the screen asks you
  to pass it on, and each hand stays hidden until its owner clicks.
- **LAN:** one computer hosts (Game ▸ New game ▸ Host) and shows its address;
  the others choose Join and enter that address. If a LAN player drops out, a
  Normal computer player takes over their seat.
- **Computer players:** *Easy* plays at random; *Normal* goes for the most
  expected damage on the weakest opponent and always defends; *Hard* weighs
  odds and threats, hunts eliminations, and picks its fights.
