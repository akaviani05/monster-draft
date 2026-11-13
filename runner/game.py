"""Monster Draft Duel v1.0. No I/O, dependencies, or hidden-state disclosures."""
from collections import Counter
import random

SPECIES = "ABCDE"
VERSION = "monster-draft-duel/1"


def deck():
    return [f"{s}{k}" for s in SPECIES for k in range(1, 6) for _ in range(2)]


def setup(seed):
    rng = random.Random(seed)
    banner = rng.randint(1, 5)
    cards = deck()
    rng.shuffle(cards)
    return banner, cards


def active_seat(turn):
    return (0, 1, 1, 0)[turn % 4]


def score(hand, opponent, banner):
    species = Counter(c[0] for c in hand)
    strengths = Counter(int(c[1]) for c in hand)
    other_species = Counter(c[0] for c in opponent)
    other_strengths = Counter(int(c[1]) for c in opponent)
    parts = {
        "base": sum(int(c[1]) for c in hand),
        "squads": 9 * sum(species[s] >= 3 for s in SPECIES),
        "spectrum": 15 * int(all(strengths[k] for k in range(1, 6))),
        "banner_a": 12 * int(species["A"] > other_species["A"]),
        "banner_b": 12 * int(species["B"] > other_species["B"]),
        "banner_strength": 9 * int(strengths[banner] > other_strengths[banner]),
    }
    parts["total"] = sum(parts.values())
    return parts


def result(hands, banner):
    scores = [score(hands[p], hands[1 - p], banner) for p in (0, 1)]
    keys = [(scores[p]["total"], scores[p]["base"],
             *(sum(c[1] == str(k) for c in hands[p]) for k in (5, 4, 3, 2, 1)))
            for p in (0, 1)]
    winner = None if keys[0] == keys[1] else int(keys[1] > keys[0])
    return {"scores": scores, "winner": winner, "reason": "completed"}


def simulate(seed, policies, names=None):
    """In-process baseline only; untrusted code always uses referee.run_match."""
    banner, cards = setup(seed)
    market, hidden, hands, turns = cards[:6], iter(cards[6:]), [[], []], []
    for t in range(30):
        seat = active_seat(t)
        choice = policies[seat](banner, market[:], hands[seat][:], hands[1-seat][:])
        if type(choice) is not int or choice not in range(6):
            raise ValueError("invalid policy choice")
        picked, refill = market[choice], next(hidden)
        turns.append({"turn": t, "seat": seat, "market": market[:], "choice": choice,
                      "card": picked, "refill": refill, "elapsed_ms": 0})
        hands[seat].append(picked)
        market[choice] = refill
    return {"version": VERSION, "seed": str(seed), "banner": banner,
            "players": names or ["P0", "P1"], "initial_market": cards[:6],
            "turns": turns, "hands": hands, "result": result(hands, banner),
            "timing": [{"wall_ms": 0, "cpu_ms": 0} for _ in (0, 1)]}
