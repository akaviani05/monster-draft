"""Real, sandboxed, durable-queue benchmark; no in-process simulation shortcuts."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from arena.service import Service
from arena.storage import Database, ROOT
from arena.worker import run_worker
from arena.scheduling import standings


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--teams',type=int,default=50)
    parser.add_argument('--slots',type=int,default=6)
    parser.add_argument('--cpu-cores',type=int,default=6,help='Pin benchmark and bots to this many available CPUs')
    parser.add_argument('--profile',choices=['reference','budget'],default='reference')
    parser.add_argument('--output',type=Path,default=ROOT/'output/benchmark-report.json')
    args=parser.parse_args()
    if not 2<=args.teams<=100:parser.error('teams must be 2..100')
    available=sorted(os.sched_getaffinity(0))
    if not 1<=args.cpu_cores<=len(available):parser.error('cpu-cores exceeds available affinity')
    os.sched_setaffinity(0,available[:args.cpu_cores])
    with tempfile.TemporaryDirectory(prefix='duel-benchmark-') as work:
        db=Database(work);service=Service(db);ids=[]
        for i in range(args.teams):
            uid=db.add_user(f'team-{i}',f'تیم {i}','BenchmarkOnlyPassword!');ids.append(uid)
            source=(ROOT/'bots'/['greedy.py','planner.py','guardian.py'][i%3]).read_text()
            if args.profile=='budget':
                source='''import sys,time
r=int(sys.stdin.readline())
for h in sys.stdin:
    m=[sys.stdin.readline() for _ in range(6)]
    if h.strip()=='YOURTURN':
        begin=time.process_time()
        while time.process_time()-begin<.12: pass
        print(0,flush=True)
    else:sys.stdin.readline()
'''
            service.submit({'id':uid},{'source':source,'language':'python','filename':'bot.py'})
        tid=service.create_tournament({'role':'admin'},{'name':'Benchmark','teams':ids,'starts_at':time.time()})['id']
        stop=threading.Event();worker=threading.Thread(target=run_worker,args=(db,args.slots,stop));start=time.monotonic();worker.start()
        max_gap=0
        try:
            while time.monotonic()-start<1800:
                tournament=db.one('SELECT status FROM tournaments WHERE id=?',(tid,))
                # A consistent snapshot avoids counting halfway across a commit.
                table=standings(db,tid)
                played=[r['played'] for r in table]
                max_gap=max(max_gap,max(played)-min(played))
                if tournament['status'] in ('completed','failed'):break
                stop.wait(.1)
            duration=time.monotonic()-start
        finally:stop.set();worker.join(30)
        games=db.rows('SELECT * FROM jobs ORDER BY id')
        times=[(g['finished']-g['started'])*1000 for g in games if g['finished']]
        report={
            'profile':args.profile,'teams':args.teams,'games':len(games),'slots':args.slots,
            'elapsed_seconds':round(duration,3),'matches_per_second':round(len(games)/duration,3),
            'match_ms_median':round(statistics.median(times),3),'match_ms_p95':round(sorted(times)[int(.95*(len(times)-1))],3),
            'statuses':dict(Counter(g['status'] for g in games)),
            'reasons':dict(Counter(g['reason'] for g in games)),
            'maximum_observed_completed_game_gap':max_gap,
            'host_cpu_count':os.cpu_count(),'host_affinity_cpus':len(os.sched_getaffinity(0)),
            'python':sys.version.split()[0],
            'ideal_full_2s_per_player_50teams_seconds':round(1225*4/args.slots,1),
            'full_budget_round_barrier_50teams_seconds_before_overhead':49*math.ceil(25/args.slots)*4,
            'notes':'Real isolated Python processes, 30 picks/game, SQLite writes, JSON replays and round barriers. Reference bots are fast; full-budget code takes longer. No production speed guarantee.'}
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False,indent=2))
        if report['statuses']!={'completed':len(games)} or report['reasons']!={'completed':len(games)}:sys.exit(1)


if __name__=='__main__':main()
