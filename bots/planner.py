"""Collection-aware reference: progress toward squads, spectrum and banners."""
import sys
from collections import Counter

banner = int(sys.stdin.readline())
mine, theirs = [], []
TURNS = 30
for i in range(TURNS):
    line = sys.stdin.readline()
    market = [sys.stdin.readline().strip() for _ in range(6)]
    if line.strip() == "YOURTURN":
        species, strengths = Counter(c[0] for c in mine), Counter(int(c[1]) for c in mine)
        def value(i):
            s, k = market[i][0], int(market[i][1])
            return k + (2, 3, 8, 0)[min(species[s], 3)] + (3.5 if not strengths[k] else 0) + (1.5 if s in "AB" else 0) + (1.2 if k == banner else 0)
        pick = max(range(6), key=value)
        print(pick, flush=True)
        mine.append(market[pick])
    else:
        theirs.append(market[int(sys.stdin.readline())])
