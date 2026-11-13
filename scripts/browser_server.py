"""Disposable browser-QA installation; never points at production data."""
from pathlib import Path
import os
import signal
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='duel-e2e-') as directory:
    env={**os.environ,'ARENA_DATA':directory,'ARENA_ORIGIN':'http://127.0.0.1:8091','ARENA_SECURE_COOKIE':'0'}
    subprocess.run([sys.executable,'-m','arena','demo'],cwd=ROOT,env=env,check=True)
    if os.environ.get('ARENA_SCREENSHOT_FIXTURES') == '1':
        sys.path.insert(0,str(ROOT))
        from arena.storage import Database
        from arena.service import Service
        from arena.worker import execute
        db=Database(directory);service=Service(db)
        team=db.one("SELECT * FROM users WHERE username='simorgh'")
        jid=service.create_practice(team,{'bot':'greedy'})['id']
        execute(db,db.one('SELECT * FROM jobs WHERE id=?',(jid,)))
        failed=service.create_practice(team,{'bot':'random'})['id']
        with db.transaction() as con:
            con.execute("UPDATE jobs SET status='failed',error=? WHERE id=?",('نمونهٔ خطای زیرساخت برای بررسی رابط مدیریت',failed))
        sender=db.one("SELECT * FROM users WHERE username='phoenix'")
        service.invite(sender,{'team_id':team['id']})
    child=subprocess.Popen([sys.executable,'-m','arena','serve','--host','127.0.0.1','--port','8091','--with-worker','--slots','6'],cwd=ROOT,env=env)
    def stop(*_):child.terminate()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:sys.exit(child.wait())
    finally:
        if child.poll() is None:child.terminate();child.wait(timeout=30)
