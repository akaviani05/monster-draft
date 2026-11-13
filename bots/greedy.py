import sys

banner = int(sys.stdin.readline())
TURNS = 30
for i in range(TURNS):
    line = sys.stdin.readline()
    market = [sys.stdin.readline().strip() for _ in range(6)]
    if line.strip() == "YOURTURN":
        print(max(range(6), key=lambda i: int(market[i][1])), flush=True)
    else:
        sys.stdin.readline()
