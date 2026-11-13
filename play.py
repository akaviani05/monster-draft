"""Open this file in IDLE and press F5. Change the three names below as needed.

Local practice with your own files; the website uses its separate isolated judge.
Python bots need only Python. C++ bots also need an installed g++ compiler.
"""
BOT1 = "A.cpp"
BOT2 = "B.py"
OUT = "replay.json"

import json
from pathlib import Path
from runner.local import play


def main():
    folder=Path(__file__).resolve().parent
    try:
        replay=play(folder/BOT1,folder/BOT2)
        destination=folder/OUT
        destination.write_text(json.dumps(replay,ensure_ascii=False,indent=2),encoding='utf-8')
        scores=replay['result']['scores'];winner=replay['result']['winner']
        print(f'{BOT1}: {scores[0]["total"]} | {BOT2}: {scores[1]["total"]}')
        print('Draw' if winner is None else 'Winner: '+replay['players'][winner])
        print('Result: '+replay['result']['reason'])
        print('Replay saved: '+str(destination))
        print('Open viewer/index.html and select this replay file.')
    except Exception as exc:print(str(exc))


if __name__=='__main__':main()
