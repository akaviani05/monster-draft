from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import fcntl
import json
import logging
import os
from pathlib import Path
import signal
import threading
import time

from runner.referee import InfrastructureError, kill_group, prepare_bot, run_match
from .scheduling import claim, finish_tournaments, start_due
from .storage import ROOT
from .control import worker_settings

BOTS = {
    "random": {"name": "جوانه", "level": "easy", "file": "random.py", "description": "بررسی کارت نخست، سپس انتخاب تصادفی"},
    "greedy": {"name": "تیزچنگ", "level": "easy", "file": "greedy.py", "description": "همیشه به دنبال کارت قوی‌تر"},
    "planner": {"name": "دیده‌بان", "level": "medium", "file": "planner.py", "description": "به فکر دسته‌ها و طیف قدرت"},
    "guardian": {"name": "نگهبان", "level": "hard", "file": "guardian.py", "description": "حواسش به انتخاب‌های حریف هم هست"},
    "champion": {"name": "اژدها", "level": "hard", "file": "champion.cpp", "description": "هزاران ادامهٔ بازی را بررسی می‌کند و روش حریف را یاد می‌گیرد"},
}


def execute(db, job):
    try:
        with ExitStack() as stack:
            names, bots = [], []
            for seat in (0, 1):
                sid = job[f"s{seat}"]
                if sid:
                    submission = db.one("SELECT s.*,u.name FROM submissions s JOIN users u ON u.id=s.user_id WHERE s.id=?", (sid,))
                    bots.append(("python" if submission["language"] == "python" else "binary", submission["path"]))
                    names.append(submission["name"] + (f" · کد {seat+1}" if job["kind"] == "local" else ""))
                else:
                    bot = BOTS[job["bot"]]
                    # Built-in C++ opponents use the same isolated compiler as
                    # submissions. Keep the temporary binary alive until EOF.
                    bots.append(stack.enter_context(prepare_bot(ROOT / "bots" / bot["file"])))
                    names.append(bot["name"])
            debug_seat = next((seat for seat in (0, 1) if job[f's{seat}']), None) if job['kind'] == 'debug' else None
            options = {'debug_seat': debug_seat} if debug_seat is not None else {}
            replay = run_match(*bots, seed=job["seed"], names=names, **options)
        diagnostics = replay.pop('_diagnostics', None)
        if diagnostics is not None:
            private = db.directory / 'replays' / f"{job['id']}.debug.json"
            temporary = private.with_suffix('.tmp')
            temporary.write_text(json.dumps(diagnostics, ensure_ascii=False), encoding='utf-8')
            temporary.chmod(0o600)
            temporary.replace(private)
        replay["match_id"] = job["id"]
        replay["submissions"] = [job["s0"], job["s1"]]
        # Debug stderr remains private; replays shared with opponents contain game
        # observations and public results only.
        replay.pop("stderr", None)
        destination = db.directory / "replays" / f"{job['id']}.json"
        temp = destination.with_suffix(".tmp")
        temp.write_text(json.dumps(replay, ensure_ascii=False), encoding="utf-8")
        temp.replace(destination)
        outcome = replay["result"]
        with db.transaction() as con:
            con.execute("UPDATE jobs SET status='completed',winner=?,reason=?,score0=?,score1=?,replay=?,finished=? WHERE id=?",
                        (outcome["winner"], outcome["reason"], outcome["scores"][0]["total"], outcome["scores"][1]["total"], str(destination), time.time(), job["id"]))
    except Exception:
        logging.exception("Match %s failed", job["id"])
        with db.transaction() as con:
            con.execute("UPDATE jobs SET status='failed',error=?,finished=? WHERE id=?",
                        ("خطای زیرساخت؛ مسئول مسابقه باید اجراکننده را بررسی کند. این بازی برد یا باخت نیست.", time.time(), job["id"]))
            if job['tournament_id']:
                con.execute("UPDATE tournaments SET status='failed',error=? WHERE id=?", ("یک بازی دچار خطای زیرساخت شد. پس از رفع مشکل، تکرار خطاها را بزنید.", job['tournament_id']))


def run_worker(db, slots=6, stop=None):
    if not 1 <= slots <= 128:
        raise ValueError("slots must be 1..128")
    stop = stop or threading.Event()
    lock = open(db.directory / "worker.lock", "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError("A worker supervisor is already running for this database")
    try:
        # The supervisor owns all child processes. After a restart, retry any job
        # that had no committed result. Committed games are never re-run.
        with db.transaction() as con:
            con.execute("UPDATE jobs SET status='queued',worker=NULL,started=NULL WHERE status='running'")
            con.execute("INSERT OR IGNORE INTO meta VALUES('worker_settings',?)", (json.dumps({'slots': slots, 'paused': False}),))
        with ThreadPoolExecutor(max_workers=128) as pool:
            active = set()
            while not stop.is_set():
                start_due(db)
                settings = worker_settings(db, slots)
                active = {future for future in active if not future.done()}
                for _ in range(0 if settings['paused'] else max(0, settings['slots']-len(active))):
                    job = claim(db, f"{os.getpid()}")
                    if not job:
                        break
                    active.add(pool.submit(execute, db, job))
                finish_tournaments(db)
                with db.transaction() as con:
                    con.execute("INSERT OR REPLACE INTO meta VALUES('worker_heartbeat',?)", (json.dumps({"at": time.time(), "slots": settings['slots'], "active": len(active), 'paused': settings['paused'], 'cpus': len(os.sched_getaffinity(0))}),))
                stop.wait(.05 if active else .3)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
