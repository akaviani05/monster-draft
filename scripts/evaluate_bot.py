"""Seat-paired sandbox evaluation; never inserts games into an arena database.

--data explicitly authorizes a read-only snapshot of selected submission IDs,
languages and executable paths. Source, credentials and sessions are not read.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arena.__main__ import doctor
from arena.worker import BOTS
from runner.referee import prepare_bot, run_match


def selected_submissions(directory, submission_ids=None):
    path = (Path(directory) / 'arena.sqlite3').resolve()
    if not path.is_file():
        raise ValueError('The specified arena database does not exist')
    # Bypass Database: its initializer migrates schema and creates directories.
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as con:
        con.row_factory = sqlite3.Row
        con.execute('BEGIN')
        selection = 's.id=u.active_submission_id' if submission_ids is None else 's.id IN (' + ','.join('?' for _ in submission_ids) + ')'
        rows = con.execute("""SELECT u.id AS team_id, s.id AS submission_id,
            s.language, s.path, s.digest FROM users u JOIN submissions s
            ON s.user_id=u.id WHERE u.role='team' AND s.kind='official' AND """
            + selection + ' ORDER BY u.id', submission_ids or ()).fetchall()
    # C++ submissions already point to the frozen compiled executable. Never
    # feed that binary back into the compiler or inspect contestant source.
    return [dict(row, language='binary' if row['language'] == 'cpp' else row['language']) for row in rows]


def evaluate(candidate, opponents, seeds, seed_start=0, report_path=None):
    report = {'candidate': candidate.name,
              'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
              'seed_start': seed_start, 'seeds': seeds, 'paired_seats': True,
              'limits': {'turn_seconds': .3, 'player_seconds': 2, 'memory_mib': 256},
              'planned_opponents': len(opponents), 'complete': False, 'opponents': []}
    with ExitStack() as stack:
        bot = stack.enter_context(prepare_bot(candidate))
        for opponent in opponents:
            other = stack.enter_context(prepare_bot(opponent['path'], opponent.get('language')))
            result = {k: v for k, v in opponent.items() if k not in ('path', 'language')}
            result.update(wins=0, draws=0, losses=0, faults=0, candidate_faults=0, opponent_faults=0, max_turn_ms=0,
                          max_player_wall_ms=0, max_cpu_ms=0, games=[])
            for seed in range(seed_start, seed_start + seeds):
                for seat in (0, 1):
                    pair = (bot, other) if seat == 0 else (other, bot)
                    replay = run_match(*pair, seed=seed, names=['evaluation P0', 'evaluation P1'])
                    outcome = replay['result']
                    key = 'draws' if outcome['winner'] is None else 'wins' if outcome['winner'] == seat else 'losses'
                    result[key] += 1
                    result['faults'] += outcome['reason'] != 'completed'
                    if outcome['reason'] != 'completed':
                        result['candidate_faults' if outcome.get('loser') == seat else 'opponent_faults'] += 1
                    result['max_turn_ms'] = max(result['max_turn_ms'], *(t['elapsed_ms'] for t in replay['turns'] if t['seat'] == seat), 0)
                    result['max_player_wall_ms'] = max(result['max_player_wall_ms'], replay['timing'][seat]['wall_ms'])
                    result['max_cpu_ms'] = max(result['max_cpu_ms'], replay['timing'][seat]['cpu_ms'])
                    result['games'].append({'seed': seed, 'seat': seat, 'outcome': key,
                                            'reason': outcome['reason'],
                                            'score': outcome['scores'][seat]['total'],
                                            'opponent_score': outcome['scores'][1-seat]['total']})
                    if key == 'losses' and report_path:
                        loss = report_path.parent / (report_path.stem + '-losses')
                        loss.mkdir(parents=True, exist_ok=True)
                        # Program diagnostics may contain private text. Keep
                        # evaluation replays to public game observations only.
                        replay.pop('stderr', None)
                        (loss/f"{opponent['id']}-{seed}-{seat}.json").write_text(json.dumps(replay) + '\n')
            report['opponents'].append(result)
            if report_path:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(json.dumps(report, indent=2) + '\n')
            print(f"{result['id']}: {result['wins']} wins, {result['draws']} draws, "
                  f"{result['losses']} losses; {result['faults']} protocol faults; "
                  f"max turn {result['max_turn_ms']:.1f} ms", flush=True)
    report['complete'] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, default=ROOT/'bots/champion.cpp')
    parser.add_argument('--data', type=Path, help='Read-only arena directory; evaluate selected team submissions too')
    parser.add_argument('--seeds', type=int, default=20)
    parser.add_argument('--seed-start', type=int, default=0)
    parser.add_argument('--opponent', action='append', help='Restrict to these bot/submission IDs; repeatable')
    parser.add_argument('--submission', type=int, action='append', help='Re-evaluate these frozen official version IDs instead of current selections; requires --data')
    parser.add_argument('--report', type=Path, default=ROOT/'output/bot-evaluation.json')
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error('--seeds must be positive')
    if args.submission and not args.data:
        parser.error('--submission requires --data')
    doctor()
    opponents = [{'id': key, 'path': ROOT/'bots'/bot['file']}
                 for key, bot in BOTS.items() if (ROOT/'bots'/bot['file']).resolve() != args.candidate.resolve()]
    if args.data:
        submissions = selected_submissions(args.data, args.submission)
        if args.submission and set(args.submission) != {row['submission_id'] for row in submissions}:
            parser.error('A requested official submission version does not exist')
        print(f'Frozen {len(submissions)} team submission versions (no source or credentials read).', flush=True)
        opponents += [dict(row, id=f"submission-{row['submission_id']}") for row in submissions]
    if args.opponent:
        opponents = [opponent for opponent in opponents if opponent['id'] in args.opponent]
        missing = set(args.opponent) - {opponent['id'] for opponent in opponents}
        if missing:
            parser.error('Unknown opponent IDs: ' + ', '.join(sorted(missing)))
    report = evaluate(args.candidate, opponents, args.seeds, args.seed_start, args.report)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Report: {args.report}')
    return int(any(opponent['candidate_faults'] for opponent in report['opponents']))


if __name__ == '__main__':
    raise SystemExit(main())
