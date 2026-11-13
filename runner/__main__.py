import argparse
from contextlib import ExitStack
import json
from pathlib import Path
from .referee import prepare_bot, run_match


def main():
    parser = argparse.ArgumentParser(description="Monster Draft Duel - Python stdlib referee")
    parser.add_argument("player0", type=Path)
    parser.add_argument("player1", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", "-o", type=Path, default=Path("replay.json"))
    args = parser.parse_args()
    with ExitStack() as stack:
        bots = [stack.enter_context(prepare_bot(p)) for p in (args.player0, args.player1)]
        replay = run_match(*bots, seed=args.seed, names=[args.player0.name, args.player1.name])
    args.output.write_text(json.dumps(replay, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(replay["result"], ensure_ascii=False))


if __name__ == "__main__":
    main()
