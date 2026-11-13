import argparse
import getpass
import json
import logging
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading

from .storage import Database, ROOT


def doctor():
    from runner.referee import sandbox_process, prepare_bot, run_match
    with tempfile.TemporaryDirectory() as work:
        path = Path(work) / "probe.py"
        path.write_text('''import os, socket, subprocess
for fn in [lambda: open("/etc/passwd").read(), lambda: open("/tmp/duel-escape", "w"), lambda: socket.socket(), lambda: subprocess.run(["/bin/sh", "-c", "id"]), lambda: os.fork()]:
    try: fn()
    except (OSError, PermissionError): pass
    else: raise RuntimeError("Sandbox escape")
print("isolated")
''')
        process = sandbox_process("python", path)
        stdout, stderr = process.communicate(timeout=5)
        if process.returncode or stdout.strip() != b"isolated":
            raise RuntimeError("Sandbox probe failed: " + stderr.decode(errors="replace"))
    replay = run_match(("python", ROOT / "bots/greedy.py"), ("python", ROOT / "bots/planner.py"), seed=42)
    if replay["result"]["reason"] != "completed":
        raise RuntimeError("Protocol smoke test failed: " + json.dumps(replay))
    with prepare_bot(ROOT / "bots/starter.cpp") as bot:
        replay = run_match(bot, ("python", ROOT / "bots/greedy.py"), seed=7)
        if replay["result"]["reason"] != "completed":
            raise RuntimeError("C++ sandbox check failed: " + json.dumps(replay))
    print("PASS: filesystem / shell / network / process isolation; Python + C++ protocol")


def main():
    parser = argparse.ArgumentParser(description="Monster Draft Duel competition server")
    parser.add_argument("--data", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--username", default="admin")
    init.add_argument("--password-stdin", action="store_true")
    demo = sub.add_parser("demo", help="Explicit local demonstration accounts, never for production")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--with-worker", action="store_true")
    serve.add_argument("--slots", type=int, default=6)
    worker = sub.add_parser("worker")
    worker.add_argument("--slots", type=int, default=6)
    sub.add_parser("doctor")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "doctor":
        return doctor()
    db = Database(args.data)
    if args.command == "init":
        if db.one("SELECT 1 FROM users WHERE role='admin'"):
            parser.error("Admin already exists. Use the existing account.")
        password = sys.stdin.readline().rstrip("\n") if args.password_stdin else getpass.getpass("Admin password (at least 12 characters): ")
        if not 12 <= len(password) <= 128:
            parser.error("Admin password must be 12..128 characters")
        db.add_user(args.username, "مدیر مسابقه", password, "admin")
        print("Administrator created. No default accounts are enabled.")
    elif args.command == "demo":
        from .service import Service
        service = Service(db)
        for username, name, role, bot in [("admin", "مدیر مسابقه", "admin", None), ("simorgh", "سیمرغ", "team", "planner.py"), ("phoenix", "ققنوس", "team", "greedy.py"), ("azarkhash", "آذرخش", "team", "guardian.py")]:
            row = db.one("SELECT id FROM users WHERE username=?", (username,))
            uid = row["id"] if row else db.add_user(username, name, "DemoArena1405!", role)
            if bot and not db.latest(uid):
                service.submit({"id": uid}, {"source": (ROOT/"bots"/bot).read_text(), "language": "python", "filename": bot})
        print("LOCAL DEMO ONLY: admin / simorgh / phoenix / azarkhash; password: DemoArena1405!")
    elif args.command == "worker":
        from .worker import run_worker
        doctor()
        stop = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())
        run_worker(db, args.slots, stop)
    elif args.command == "serve":
        from .server import ArenaHTTPServer
        from .service import Service
        from .worker import run_worker
        stop = threading.Event()
        thread = None
        if args.with_worker:
            doctor()
            thread = threading.Thread(target=run_worker, args=(db, args.slots, stop), daemon=True)
            thread.start()
        server = ArenaHTTPServer((args.host, args.port), Service(db))
        print(f"Local: http://{args.host}:{server.server_port}", flush=True)
        def shutdown(*_):
            stop.set()
            threading.Thread(target=server.shutdown, daemon=True).start()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, shutdown)
        try:
            server.serve_forever(poll_interval=.2)
        finally:
            server.server_close()
            stop.set()
            if thread:
                thread.join(timeout=30)


if __name__ == "__main__":
    main()
