# Monster Draft Duel

**Version:** 1.0 (proposal for implementation)  
**Audience:** AI implementation agents, referee developers, bot developers  
**Status:** Proposed rules and normative stdin/stdout protocol. No code is required in this phase.

## 0. Scope and authoritative choices

Implement a two-player, turn-based drafting game. Each participant runs **one persistent process** (Python or C++) for the entire match. The referee communicates through line-oriented standard input and standard output.

This version deliberately fixes these details:

- There are five monster species, named **A**, **B**, **C**, **D**, and **E**. A card is written as a two-character token such as `A1`, `A5`, or `E3`. Its first character is its species; its digit is its strength.
- The **two fixed species banners** are **A** and **B**, in **every** match. They are not randomized or transmitted because they are part of the published rules.
- The **strength banner** is drawn **uniformly at random from 1, 2, 3, 4, 5** at the start of each match. **The first line of stdin to both players is precisely this one digit.**
- Each player drafts 15 cards, for 30 picks total, using a snake turn order.
- The six market slots have stable indices `0` through `5`; when a card is picked, a newly drawn card **replaces it in the same slot**.
- Every turn's input begins with `YOURTURN` or `OPPTURN` (uppercase, **no spaces**), followed by **six lines** listing the market slots in index order. For an opponent turn, one more line identifies the opponent's selected index.
- A player prints **exactly one index `0`–`5`** on `YOURTURN`; prints **nothing** on `OPPTURN`.
- The match ends after turn 30 by the referee **closing stdin**. There is no `END` or `GAMEOVER` message on the bot protocol.

These rules supersede any earlier simulator/prototype, which may have different banner selection, card naming, or market replacement behavior.

---

## 1. Deck and setup

| Parameter | Exact rule |
|---|---|
| Players | 2: player P0 and player P1. These are seats, **not** species A/B. |
| Species | `A`, `B`, `C`, `D`, `E` |
| Strengths | Integers `1`–`5` |
| Card types | 25 (`A1` through `E5`) |
| Copies | Exactly **2** indistinguishable copies of each type |
| Deck size | **50** cards total |
| Initial market | Draw **6** cards, placed in slots `0`, `1`, `2`, `3`, `4`, `5` |
| Hidden deck | Uniformly shuffle the 50-card deck at setup; unrevealed cards are not sent to players |
| Draft length | **30** picks, **15** picks by each player |
| Fixed species banners | `A` and `B` |
| Strength banner | One uniform random integer `R ∈ {1,2,3,4,5}`, public from startup |

The 30 selections are always possible: drawing the initial six cards and 30 refill cards uses 36 of the 50 cards, leaving 14 unrevealed cards after the final refill. Of the 20 cards not drafted, six are in the final market and 14 remain unrevealed.

**Important:** Card codes are categorical identifiers, not unique physical cards. There can be two copies of `B4` in the market or in players' hands, but never more than two copies across the entire match.

## 2. Turn order and draft mechanics

The snake order repeats `P0, P1, P1, P0`. For zero-based turn number `t` (`0 ≤ t < 30`):

```text
active_seat = [P0, P1, P1, P0][t % 4]
```

Thus turns 1–10 (one-based) belong to:

```text
P0 P1 P1 P0 P0 P1 P1 P0 P0 P1
```

Both seats have exactly 15 selections by the end of turn 30.

For each turn:

1. Take a snapshot of the **current** six-slot market, `market[0..5]`.
2. Give each bot the appropriate header (`YOURTURN` for the active seat; `OPPTURN` for the other seat), followed by the **same six market cards**, one card per line, slot `0` first.
3. Wait for one legal index `i` from the active bot's stdout, within the configured time limit.
4. Send the selected index `i` as a single extra stdin line **only to the inactive bot**, which had received `OPPTURN` and the six cards. This informs it of the opponent's pick.
5. Add **the old value** of `market[i]` to the active player's collection.
6. Draw the next hidden-deck card and assign it to **`market[i]`**. The other five slots are unchanged. The refill is not independently announced; players see it in the next turn's market snapshot.
7. Continue until 30 picks have been made. Calculate final scores and close both stdin streams (EOF). Any referee result/score/replay goes through a separate interface, **not** through the bots' stdin.

The market must be treated as an **array of fixed slots**, not as a list that removes a picked card and appends its replacement to the end.

The chosen index is public information. Both players can reconstruct both draft collections by observing all 30 turns and their own selections. Neither player can see the hidden draw order.

## 3. Scoring — exact, final-only

Let `H_p` be the 15 cards drafted by player `p`, and let `q` be the opponent. Define:

- `n(p,s)` = number of cards of species `s` in `H_p`.
- `m(p,k)` = number of cards with strength `k` in `H_p`.
- `R` = publicly announced random strength banner.

Each player's final score is the **sum** of these components:

| Component | Condition | Points |
|---|---|---:|
| Base strength | Every drafted card contributes its digit | Sum of all 15 strengths |
| Species squad | For each species `s ∈ {A,B,C,D,E}`, if `n(p,s) >= 3` | **+9 per qualifying species, once** |
| Strength spectrum | `m(p,1) >= 1`, `m(p,2) >= 1`, ..., `m(p,5) >= 1` | **+15 once** |
| Species banner A | `n(p,A) > n(q,A)` | **+12** |
| Species banner B | `n(p,B) > n(q,B)` | **+12** |
| Random strength banner | `m(p,R) > m(q,R)` | **+9** |

**Clarifications:**

- A species with four, five, or more cards still earns **only one** +9 squad bonus.
- The spectrum bonus requires at least one of **every** strength; extra copies do not multiply it.
- Banner points are awarded for a **strict majority**. If counts are equal, **neither player receives** that banner's points. A banner can be worth zero to both players.
- Banners are evaluated **only after all 30 picks**. Temporary mid-game leads do not score.
- All bonus categories stack. The same card can contribute to base strength, a squad, spectrum, and a banner.
- There are **no attacks, trading, discards, cards with special powers, or extra-turn effects**.

Formal score definition:

```text
score(p) = sum(strength(c) for c in H_p)
         + 9 * sum( n(p,s) >= 3 for s in A..E )
         + 15 * all( m(p,k) >= 1 for k in 1..5 )
         + 12 * ( n(p,A) > n(q,A) )
         + 12 * ( n(p,B) > n(q,B) )
         +  9 * ( m(p,R) > m(q,R) )
```

Boolean expressions count as 1 for true and 0 for false.

### Worked final-score example (R = 2)

```text
P0 cards:
A5 A4 A2 A1  B5 B4 B3  C5 C2 C1  D4 D3 D1  E5 E2

P1 cards:
A5 A3 A2  B5 B4 B1 B2  C5 C3 C2  D5 D4 D2  E4 E3
```

This is a valid 30-card example with no card type used more than twice.

| Component | P0 | P1 |
|---|---:|---:|
| Base strength | 47 | 50 |
| Squads (A, B, C, D; four each) | 36 | 36 |
| Spectrum (all strengths present) | 15 | 15 |
| A banner | 12 (4 A vs 3 A) | 0 |
| B banner | 0 | 12 (4 B vs 3 B) |
| Strength-2 banner | 0 (3 vs 4) | 9 |
| **Final score** | **110** | **122** |

**P1 wins.**

### Victory and tie-breaking

Compare the following values in order; the first unequal value wins:

1. Higher final score.
2. Higher sum of printed card strengths (base-strength subtotal).
3. More strength-5 cards, then more strength-4 cards, then more strength-3, then strength-2, then strength-1 cards (lexicographic comparison).
4. If all comparisons are equal, the result is an **exact draw**. The referee must support this case; it must not invent a secret/random final tiebreaker.

A tournament may give **1 point for a win, 0.5 for a draw, 0 for a loss**. Recommended: aggregate across many games and swap starting seats for fairness rather than requiring a winner in every individual match.

---

## 4. Bot stdin/stdout protocol (normative)

### 4.1 Process lifetime and languages

- Run **one persistent executable/interpreter process per bot per match**. **Do not restart it after each pick.**
- Python 3 and C++17 or later must be supported. The referee communicates identically with both languages through text stdin/stdout.
- Each bot starts with empty application state; it may retain state in memory throughout the match.
- All bot protocol fields are ASCII and newline-delimited (`\n`). Ignore a trailing `\r` when reading lines.
- The first stdin line is always a single integer token `1`, `2`, `3`, `4`, or `5`: the random strength banner. No other startup banner, seat ID, market, or metadata precedes it.

### 4.2 Turn input grammar

For each turn, each bot receives exactly **one** of these message forms:

**Active player's stdin:**

```text
YOURTURN
<slot-0-card>
<slot-1-card>
<slot-2-card>
<slot-3-card>
<slot-4-card>
<slot-5-card>
```

The active player must send one stdout line:

```text
<selected-index>
```

Where `<selected-index>` is a single ASCII digit from `0` to `5` inclusive, followed by newline, and flushed immediately.

**Inactive player's stdin:**

```text
OPPTURN
<slot-0-card>
<slot-1-card>
<slot-2-card>
<slot-3-card>
<slot-4-card>
<slot-5-card>
<opponent-selected-index>
```

The referee sends the selected-index line **after** receiving and validating the active player's output. The inactive player emits **no stdout** for this turn.

For all six slot lines, `<slot-i-card>` matches exactly the regex `[A-E][1-5]`. There are no spaces, quotes, brackets, colons, or slot labels. The six-line order defines slot indices 0–5.

There are no blank lines between turns, and there is no separate notification when a market slot is refilled. After the final turn the referee closes stdin (EOF).

### 4.3 Exact protocol example, viewed by P0

Before the first turn, both players receive this line:

```text
2
```

Turn 1 belongs to P0. P0's stdin receives:

```text
YOURTURN
A1
C4
B5
E2
D3
A5
```

P0 chooses the card in slot 2 and prints on **stdout**:

```text
2
```

The referee gives P0 the picked `B5`, and refills **slot 2 only** with `E1`.

Turn 2 belongs to P1. P0's stdin receives:

```text
OPPTURN
A1
C4
E1
E2
D3
A5
0
```

This means P1 picked `A1` from slot 0. P0 prints **nothing**. Slot 0 is then replaced by `B2`.

Turn 3 also belongs to P1. P0 receives:

```text
OPPTURN
B2
C4
E1
E2
D3
A5
5
```

P1 picked `A5` from slot 5; slot 5 is refilled with `D1`.

Turn 4 belongs to P0, so P0 receives:

```text
YOURTURN
B2
C4
E1
E2
D3
D1
```

At this point P0 again writes one number from `0` to `5` to stdout.

**P1's view is complementary:** on turn 1 it receives `OPPTURN`, the same first six cards, and then index `2`; on turns 2 and 3 it receives `YOURTURN` with the same market snapshots that P0 sees, and writes its chosen indices `0` and `5`.

**Technical note:** The above blocks represent lines in a **stream**, not independent complete input files. A Python bot must not use `sys.stdin.read()` waiting for EOF before making decisions. Use `readline()` / line iteration with explicit state. A C++ bot can use `std::getline` or `std::cin >> token` while keeping its process alive and flushing output.

### 4.4 Strict stdout requirements

- Print **one** line containing `0`, `1`, `2`, `3`, `4`, or `5` **only** in response to `YOURTURN`.
- Flush stdout after each selection (`flush=True` in Python, `std::flush` / `std::endl` in C++).
- Do **not** print prompts, logs, coordinates, explanations, or JSON to stdout.
- Debugging output may go to stderr, with limits imposed by the referee.
- A malformed response, non-integer index, extra stdout, premature exit, or time limit violation is a protocol failure and normally forfeits the match. The organizer can define a separate, explicitly documented handling policy for infrastructure failures.

### 4.5 Minimal bot loop (language-neutral pseudocode)

```text
R = int(read_one_line())                # always the first line
my_cards = []
opponent_cards = []

while (header = read_one_line_or_EOF()) is not EOF:
    assert header in {"YOURTURN", "OPPTURN"}
    market = [read_one_line() for i in 0..5]

    if header == "YOURTURN":
        i = choose_index(R, market, my_cards, opponent_cards)
        write_line_and_flush(i)          # single integer 0..5
        my_cards.append(market[i])
    else:
        i = int(read_one_line())         # opponent's selected index
        opponent_cards.append(market[i])

# On EOF: exit gracefully. Do not print a final score to stdout.
```

The bot does not need to track the hidden deck. It may compute which unseen card types remain from the original two-per-type counts and the cards it has observed in the markets and picks; it must not receive future cards in advance.

---

## 5. Required referee behavior

### Determinism and fairness

- The referee chooses `R` uniformly from `1`–`5`, then independently shuffles the 50-card deck uniformly using a private seed.
- For reproducible testing, allow a specified seed and record it in the **referee-side** replay log; **never reveal that seed to either live bot**.
- For paired competition matches, run the same public objective and deck order twice while swapping the bots between seats P0 and P1. The snake draft does not by itself guarantee perfect seat balance.
- Do not let the language/runtime choice affect game rules or observations.
- Use a configurable, published time budget and memory limit. Suggested starting values for stress tests: **0.5 seconds per pick, 6 seconds cumulative thinking time per bot per match, 256 MiB RAM**; adjust after benchmark testing on the actual hardware and with both Python and C++.

### Required implementation artifacts (for the future implementation phase)

1. Referee/game engine with deck setup, fixed-slot market, snake turn order, and scoring.
2. Process runner supporting persistent Python and C++ bots over stdin/stdout, validating replies and enforcing time/memory limits.
3. Minimal random bot in Python and minimal random bot in C++, each obeying the exact protocol.
4. At least one deterministic greedy reference bot (e.g., highest-strength available card or immediate-score heuristic).
5. Unit tests, integration tests, deterministic seed/replay support, and clear run instructions.
6. Optional spectator viewer or replay file. This must use a separate output channel, never additional bot stdin fields.

Do **not** implement any gameplay change, additional card ability, new message type, or hidden-information reveal unless the organizers revise this specification.

## 6. Conformance and edge-case test checklist

The AI agent implementing the referee should prove all of these properties:

1. **Deck inventory:** exactly two copies of each `A1`–`E5`, totaling 50.
2. **Banners:** exactly A and B fixed in every match; `R` is a uniform random value 1–5 and the first line given to both bots.
3. **Draft order:** 30 turns; `P0,P1,P1,P0` repeated; both players get 15 cards.
4. **Market slots:** exactly six valid tokens sent on every turn; after a pick at index `i`, only `market[i]` changes. Duplicates are legal.
5. **Public picks:** both players receive the same pre-pick board; the inactive bot receives exactly one further index line; the active bot does not receive its own echoed index.
6. **Refill secrecy:** the next card is not included in the inactive bot's index line; it appears only in the next turn's market snapshot.
7. **Scoring:** squad is +9 per species at a count of 3 or more, never repeatedly per additional triple; spectrum +15 once; majority banners require strict superiority.
8. **Known score fixture:** for the 30 cards in section 3 and `R=2`, scores must be exactly **P0=110**, **P1=122**.
9. **Tie behavior:** final-score tie breaker follows the documented lexicographic order; an exact draw remains possible.
10. **Protocol correctness:** bot must output only `0`–`5` plus newline on active turns, and no output on inactive turns; wrong answers cause a clean forfeit.
11. **EOF behavior:** after 30 picks, both bot stdin streams close; no extra sentinel, result, or turn line is injected into the protocol.
12. **Runtime:** a persistent Python bot and a persistent C++ bot can successfully play a complete game against each other and against themselves without deadlock or buffering issues.
13. **Replay reproducibility:** same seed, same choices, same market snapshots and scores; optionally swapped seats with a matched deck order.
14. **Hidden deck:** no future card, seed, or opponent internal state is leaked to a bot.

## 7. Design rationale (informative, not additional rules)

- A **random** bot selects `rand(0,5)`.
- A **simple greedy** bot takes the highest printed strength.
- An **immediate-score greedy** bot considers squads and spectrum completion.
- A **planning heuristic** rewards partial squads and incomplete strength spectra.
- An **opponent-aware heuristic** estimates who will win the fixed A/B and random-strength banners, and may deny useful cards.
- A stronger bot can estimate remaining-deck probabilities, simulate future picks, and tune heuristics.

The mixed objectives make a single naive greedy rule less likely to dominate, but the organizers should still benchmark strong bots before declaring the game balanced. Fixing the A and B banners is deliberate and must not be silently changed by the referee.

---

**Change control:** Version 1.0. If any mechanic or protocol token changes (even changing `OPPTURN` to `OPPONENTTURN`), increment the version and update this specification, all example bots, and integration tests together.
