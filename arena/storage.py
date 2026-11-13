from contextlib import contextmanager
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import time

ROOT = Path(__file__).resolve().parent.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','team')),
 active INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
 token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 csrf TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts(key TEXT NOT NULL, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS attempts_key ON login_attempts(key,created);
CREATE TABLE IF NOT EXISTS submissions(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 filename TEXT NOT NULL, language TEXT NOT NULL, digest TEXT NOT NULL,
 path TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'official', created REAL NOT NULL,
 size_bytes INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS tournaments(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, starts_at REAL NOT NULL,
 status TEXT NOT NULL DEFAULT 'scheduled', paired INTEGER NOT NULL DEFAULT 0,
 games_per_pair INTEGER NOT NULL DEFAULT 1,
 created REAL NOT NULL, error TEXT);
CREATE TABLE IF NOT EXISTS entries(
 tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
 user_id INTEGER NOT NULL REFERENCES users(id), submission_id INTEGER REFERENCES submissions(id),
 PRIMARY KEY(tournament_id,user_id));
CREATE TABLE IF NOT EXISTS jobs(
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
 owner_id INTEGER REFERENCES users(id), p0 INTEGER REFERENCES users(id), p1 INTEGER REFERENCES users(id),
 s0 INTEGER REFERENCES submissions(id), s1 INTEGER REFERENCES submissions(id), bot TEXT,
 seed INTEGER NOT NULL, tournament_id INTEGER REFERENCES tournaments(id), round INTEGER,
 winner INTEGER, reason TEXT, score0 INTEGER, score1 INTEGER,
 replay TEXT, error TEXT, created REAL NOT NULL, started REAL, finished REAL,
 worker TEXT, attempt INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS job_queue ON jobs(status,tournament_id,round,created);
CREATE INDEX IF NOT EXISTS job_owner ON jobs(owner_id,created);
CREATE TABLE IF NOT EXISTS invitations(
 id INTEGER PRIMARY KEY, sender INTEGER NOT NULL REFERENCES users(id),
 recipient INTEGER NOT NULL REFERENCES users(id), submission_id INTEGER NOT NULL REFERENCES submissions(id),
 status TEXT NOT NULL DEFAULT 'pending', created REAL NOT NULL, expires REAL NOT NULL,
 job_id INTEGER REFERENCES jobs(id));
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
INSERT OR IGNORE INTO meta VALUES('claim_count','0');
"""


def password_hash(password):
    salt = secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + "$" + value


def password_valid(password, encoded):
    salt, value = encoded.split("$")
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(candidate, value)


class Database:
    def __init__(self, directory=None):
        self.directory = Path(directory or os.environ.get("ARENA_DATA", ROOT / "var")).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in ("submissions", "replays"):
            (self.directory / name).mkdir(exist_ok=True, mode=0o700)
        self.path = self.directory / "arena.sqlite3"
        with self.connect() as con:
            con.executescript(SCHEMA)
            # Web and worker services may start together. Serialize migration
            # discovery and ALTER statements so only one process upgrades.
            con.execute('BEGIN IMMEDIATE')
            if 'games_per_pair' not in {row[1] for row in con.execute('PRAGMA table_info(tournaments)')}:
                con.execute('ALTER TABLE tournaments ADD COLUMN games_per_pair INTEGER NOT NULL DEFAULT 1')
                con.execute('UPDATE tournaments SET games_per_pair=CASE WHEN paired THEN 2 ELSE 1 END')
            user_columns = {row[1] for row in con.execute('PRAGMA table_info(users)')}
            for column in ('student1', 'student2'):
                if column not in user_columns:
                    con.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
            if 'size_bytes' not in {row[1] for row in con.execute('PRAGMA table_info(submissions)')}:
                con.execute('ALTER TABLE submissions ADD COLUMN size_bytes INTEGER NOT NULL DEFAULT 0')
            if 'active_submission_id' not in {row[1] for row in con.execute('PRAGMA table_info(users)')}:
                con.execute('ALTER TABLE users ADD COLUMN active_submission_id INTEGER REFERENCES submissions(id)')
                con.execute("UPDATE users SET active_submission_id=(SELECT MAX(id) FROM submissions WHERE user_id=users.id AND kind='official')")
        os.chmod(self.path, 0o600)

    def connect(self):
        con = sqlite3.connect(self.path, timeout=20)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=20000")
        # SQLite may return BUSY immediately when two processes first switch an
        # existing database into WAL, despite its normal statement busy timeout.
        deadline=time.monotonic()+20
        while True:
            try:
                con.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError as exc:
                if not any(word in str(exc).lower() for word in ('locked','busy')) or time.monotonic()>=deadline:
                    con.close()
                    raise
                time.sleep(.02)
        return con

    @contextmanager
    def transaction(self):
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def rows(self, sql, params=()):
        with self.connect() as con:
            return [dict(row) for row in con.execute(sql, params)]

    def one(self, sql, params=()):
        rows = self.rows(sql, params)
        return rows[0] if rows else None

    def add_user(self, username, name, password, role="team"):
        with self.transaction() as con:
            return con.execute("INSERT INTO users(username,name,password,role,created) VALUES(?,?,?,?,?)",
                               (username, name, password_hash(password), role, time.time())).lastrowid

    def latest(self, user_id, con=None):
        query = "SELECT * FROM submissions WHERE user_id=? AND kind='official' ORDER BY id DESC LIMIT 1"
        if con:
            row = con.execute(query, (user_id,)).fetchone()
            return dict(row) if row else None
        return self.one(query, (user_id,))

    def active_submission(self, user_id, con=None):
        query = """SELECT s.* FROM submissions s JOIN users u ON u.active_submission_id=s.id
            WHERE u.id=? AND s.user_id=u.id AND s.kind='official'"""
        if con:
            row = con.execute(query, (user_id,)).fetchone()
            return dict(row) if row else None
        return self.one(query, (user_id,))
