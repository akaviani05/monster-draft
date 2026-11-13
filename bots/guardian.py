"""Opponent-aware heuristic, deliberately inexpensive."""
import sys
from collections import Counter

banner = int(sys.stdin.readline())
mine, theirs = [], []
TURNS = 30
for i in range(TURNS):
    line = sys.stdin.readline()
    market = [sys.stdin.readline().strip() for _ in range(6)]
    if line.strip() == "YOURTURN":
        a, b = Counter(c[0] for c in mine), Counter(c[0] for c in theirs)
        x, y = Counter(int(c[1]) for c in mine), Counter(int(c[1]) for c in theirs)
        def value(i):
            s, k = market[i][0], int(market[i][1])
            v = k + (2.1, 3.7, 8, 0)[min(a[s], 3)] + (4 if not x[k] else 0)
            v += (3.1 if abs(a[s]-b[s]) <= 1 else .6) if s in "AB" else 0
            v += (2.8 if abs(x[k]-y[k]) <= 1 else .4) if k == banner else 0
            return v + (1.5 if b[s] == 2 else 0)
        pick = max(range(6), key=value)
        print(pick, flush=True)
        mine.append(market[pick])
    else:
        theirs.append(market[int(sys.stdin.readline())])
