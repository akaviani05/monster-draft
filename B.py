import random

TURNS = 30
banner = int(input())
for i in range(TURNS):
    header = input()
    A = [input() for j in range(6)]
    if header == "YOURTURN":
        if A[0][0] == 'A' or A[0][1] == '5':
            choice = 0
        else:
            choice = random.randint(0, 5)
        print(choice, flush=True)
    else:
        opponent_choice = int(input())
