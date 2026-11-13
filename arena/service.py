import ast
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import tempfile
import threading
import time
import unicodedata
import zipfile

from runner.referee import prepare_bot
from .scheduling import standings, team_label, friendly_stats_cutoff
from .storage import password_hash, password_valid
from .worker import BOTS
from .control import worker_settings


class APIError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def require(condition, message, status=400):
    if not condition:
        raise APIError(message, status)


def archive_name(value, fallback):
    """Readable UTF-8 ZIP names without path separators or control characters."""
    value = unicodedata.normalize('NFC', value)
    value = ''.join(c if c in ' ._-()' or unicodedata.category(c)[0] in 'LNM'
                    else '-' for c in value)
    return value.encode('utf-8')[:100].decode('utf-8', errors='ignore').strip(' .') or fallback


class Service:
    def __init__(self, db):
        self.db = db
        self.compile_slots = threading.BoundedSemaphore(2)
        self.dummy_hash = password_hash(secrets.token_hex(16))

    def login(self, body, address, required_role=None):
        username, password = str(body.get("username", "")), str(body.get("password", ""))
        failure = 'رمز مدیریت نادرست است.' if required_role == 'admin' else 'نام کاربری یا رمز نادرست است.'
        require(len(username) <= 64 and len(password) <= 128, failure, 401)
        now = time.time()
        # Both account and address counters prevent cycling names or addresses.
        keys = ["ip:"+address, "user:"+username.lower()]
        with self.db.transaction() as con:
            con.execute("DELETE FROM login_attempts WHERE created<?", (now-900,))
            for key in keys:
                count = con.execute("SELECT COUNT(*) FROM login_attempts WHERE key=? AND created>?", (key, now-300)).fetchone()[0]
                require(count < 15, "تلاش‌های ورود زیاد شده؛ پنج دقیقه صبر کنید.", 429)
            for key in keys:
                con.execute("INSERT INTO login_attempts VALUES(?,?)", (key, now))
        user = self.db.one("SELECT * FROM users WHERE username=?", (username,))
        valid = password_valid(password, user["password"] if user else self.dummy_hash)
        require(user and user["active"] and valid and (required_role is None or user['role'] == required_role), failure, 401)
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.db.transaction() as con:
            con.execute("DELETE FROM sessions WHERE expires<?", (now,))
            con.execute("INSERT INTO sessions VALUES(?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), user["id"], csrf, now+28800))
        return token, {"user": {k: user[k] for k in ("id", "name", "username", "role")}, "csrf": csrf}

    def admin_login(self, body, address):
        # init creates the administrator account. Resolve it on the server so
        # this password-only form also supports a custom administrator username.
        account = self.db.one("SELECT username FROM users WHERE role='admin' ORDER BY id LIMIT 1")
        return self.login({'username': account['username'] if account else '',
                           'password': body.get('password', '')}, address, required_role='admin')

    def authenticate(self, token):
        if not token:
            return None
        return self.db.one("SELECT u.id,u.username,u.name,u.role,s.csrf,s.token FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1",
                           (hashlib.sha256(token.encode()).hexdigest(), time.time()))

    def admin(self, user):
        require(user["role"] == "admin", "این بخش برای مدیر مسابقه است.", 403)

    def submission_archive(self, user, scope):
        self.admin(user)
        require(scope in ('all', 'final'), 'نوع دریافت کد معتبر نیست.')
        rows = self.db.rows("""SELECT s.id,s.user_id,s.filename,s.language,s.path,s.created,
            u.name,u.username,u.active_submission_id
            FROM submissions s JOIN users u ON u.id=s.user_id
            WHERE u.role='team' AND s.kind='official'""" +
            (" AND s.id=u.active_submission_id" if scope == 'final' else '') +
            " ORDER BY s.user_id,s.id")
        archive = tempfile.TemporaryFile()
        try:
            manifest = []
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
                for row in rows:
                    extension = 'py' if row['language'] == 'python' else 'cpp'
                    folder = f"{archive_name(row['name'], 'team')}--team-{row['user_id']}"
                    original = Path(row['filename'].replace('\\', '/')).stem
                    filename = f"{archive_name(original, 'source')}--submission-{row['id']}.{extension}"
                    member = f"{folder}/{filename}"
                    source = Path(row['path']).parent / f'source.{extension}'
                    require(source.is_file(), 'فایل یکی از کدها در دسترس نیست؛ دریافت کامل انجام نشد.', 409)
                    bundle.write(source, member)
                    manifest.append({'file': member, 'submission_id': row['id'],
                        'team_id': row['user_id'], 'team_name': row['name'],
                        'username': row['username'], 'filename': row['filename'],
                        'language': row['language'], 'created': row['created'],
                        'final': row['id'] == row['active_submission_id']})
                bundle.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.seek(0)
            return archive
        except BaseException:
            archive.close()
            raise

    def quota(self, con, user_id):
        recent = con.execute("SELECT COUNT(*) FROM jobs WHERE owner_id=? AND created>?", (user_id, time.time()-60)).fetchone()[0]
        require(recent < 10, "در هر دقیقه حداکثر ده بازی می‌توانید درخواست کنید.", 429)

    def submit(self, user, body, kind="official"):
        require(isinstance(body, dict), "اطلاعات فایل کد معتبر نیست.")
        source, language = body.get("source", ""), body.get("language", "python")
        require(isinstance(source, str), "کد باید متن باشد.")
        try: encoded_source = source.encode('utf-8')
        except UnicodeEncodeError: raise APIError('متن کد باید UTF-8 معتبر باشد.')
        require(0 < len(encoded_source) <= 65536, "کد باید خالی نباشد و حداکثر ۶۴ کیلوبایت باشد.")
        require(language in ("python", "cpp"), "زبان باید Python یا C++ باشد.")
        count = self.db.one("SELECT COUNT(*) AS n FROM submissions WHERE user_id=? AND created>?", (user["id"], time.time()-60))["n"]
        require(count < 10, "حداکثر ده ارسال در دقیقه مجاز است.", 429)
        daily = self.db.one("SELECT COUNT(*) AS n FROM submissions WHERE user_id=? AND created>?", (user['id'], time.time()-86400))['n']
        require(daily < 100, "حداکثر صد فایل کد در هر ۲۴ ساعت مجاز است.", 429)
        used = self.db.one("SELECT COALESCE(SUM(size_bytes),0) AS n FROM submissions WHERE user_id=?", (user['id'],))['n']
        require(used < 128*1024**2, "فضای نسخه‌های کد شما پر شده است؛ با مدیر مسابقه تماس بگیرید.", 429)
        require(self.compile_slots.acquire(blocking=False), "دو کد در حال بررسی‌اند؛ کمی بعد دوباره بفرستید.", 429)
        try:
            if language == "python":
                try:
                    ast.parse(source)
                except (SyntaxError, ValueError, RecursionError) as exc:
                    raise APIError("خطای نگارشی پایتون: " + str(exc)[:1000])
            digest = hashlib.sha256(encoded_source).hexdigest()
            key = secrets.token_hex(20)
            folder = self.db.directory / "submissions" / key
            folder.mkdir(mode=0o700)
            source_path = folder / ("source.py" if language == "python" else "source.cpp")
            source_path.write_text(source, encoding="utf-8")
            path = source_path
            try:
                if language == "cpp":
                    with prepare_bot(source_path, "cpp") as (_, executable):
                        path = folder / "bot"
                        shutil.copy2(executable, path)
                    require(path.stat().st_size <= 4*1024**2, "فایل اجرایی کامپایل‌شده باید حداکثر ۴ مگابایت باشد.")
                filename = str(body.get("filename", "bot.py" if language == "python" else "bot.cpp"))
                filename = Path(filename).name[:100]
                with self.db.transaction() as con:
                    size_bytes = source_path.stat().st_size + (path.stat().st_size if language=='cpp' else 0)
                    sid = con.execute("INSERT INTO submissions(user_id,filename,language,digest,path,kind,created,size_bytes) VALUES(?,?,?,?,?,?,?,?)",
                                      (user["id"], filename, language, digest, str(path), kind, time.time(), size_bytes)).lastrowid
                    if kind == 'official':
                        con.execute('UPDATE users SET active_submission_id=? WHERE id=?', (sid, user['id']))
            except BaseException:
                shutil.rmtree(folder, ignore_errors=True)
                raise
            return {"id": sid, "filename": filename, "digest": digest, "language": language}
        except ValueError as exc:
            raise APIError("کامپایل موفق نبود: " + str(exc)[:12000])
        finally:
            self.compile_slots.release()

    def activate_submission(self, user, sid, body):
        with self.db.transaction() as con:
            require(con.execute("SELECT 1 FROM submissions WHERE id=? AND user_id=? AND kind='official'", (sid,user['id'])).fetchone(), 'این نسخهٔ کد متعلق به تیم شما نیست یا ارسال رسمی نیست.',404)
            con.execute('UPDATE users SET active_submission_id=? WHERE id=?', (sid,user['id']))
        return {'id': sid, 'active_submission_id': sid}

    def list_submissions(self, user, page=1):
        page=max(1,min(100000,page))
        return {'items': self.db.rows("SELECT id,filename,language,digest,created FROM submissions WHERE user_id=? AND kind='official' ORDER BY id DESC LIMIT 25 OFFSET ?",(user['id'],(page-1)*25)),
                'total': self.db.one("SELECT COUNT(*) AS n FROM submissions WHERE user_id=? AND kind='official'",(user['id'],))['n'],
                'page': page}

    def create_practice(self, user, body):
        require(isinstance(body.get("bot"),str) and body["bot"] in BOTS, "ربات انتخاب‌شده وجود ندارد.")
        with self.db.transaction() as con:
            self.quota(con, user["id"])
            submission = self.db.active_submission(user["id"], con)
            require(submission, "ابتدا یک کد ارسال کنید.")
            # Alternate seats using an unpredictable fair coin; a friendly is one game.
            seat = secrets.randbelow(2)
            values = [None, None, None, None]
            values[seat], values[2+seat] = user["id"], submission["id"]
            jid = con.execute("INSERT INTO jobs(kind,owner_id,p0,p1,s0,s1,bot,seed,created) VALUES('bot',?,?,?,?,?,?,?,?)",
                              (user["id"], *values, body["bot"], secrets.randbits(63), time.time())).lastrowid
        return {"id": jid}

    def create_debug(self, user, body):
        require(user['role'] == 'team', 'این بخش مخصوص تیم‌ها است.', 403)
        require(isinstance(body.get('bot'), str) and body['bot'] in BOTS, 'ربات انتخاب‌شده وجود ندارد.')
        with self.db.transaction() as con:
            self.quota(con, user['id'])
        code = self.submit(user, body, 'local')
        with self.db.transaction() as con:
            self.quota(con, user['id'])
            seat = secrets.randbelow(2)
            values = [None, None, None, None]
            values[seat], values[2+seat] = user['id'], code['id']
            jid = con.execute("INSERT INTO jobs(kind,owner_id,p0,p1,s0,s1,bot,seed,created) VALUES('debug',?,?,?,?,?,?,?,?)",
                              (user['id'], *values, body['bot'], secrets.randbits(63), time.time())).lastrowid
        return {'id': jid, 'submission_id': code['id'], 'filename': code['filename']}

    def diagnostics(self, user, jid):
        job = self.db.one('SELECT owner_id,kind,status FROM jobs WHERE id=?', (jid,))
        require(job and job['owner_id'] == user['id'] and job['kind'] == 'debug', 'آزمایش متعلق به شما نیست.', 404)
        require(job['status'] == 'completed', 'گزارش پس از پایان آزمایش آماده می‌شود.', 409)
        path = self.db.directory / 'replays' / f'{jid}.debug.json'
        require(path.is_file(), 'گزارش این آزمایش در دسترس نیست؛ آزمایش تازه‌ای اجرا کنید.', 404)
        return json.loads(path.read_text(encoding='utf-8'))

    def local(self, user, body):
        with self.db.transaction() as con:
            self.quota(con, user["id"])
        require(isinstance(body.get("codes"), list) and len(body["codes"]) == 2, "دو فایل کد لازم است.")
        codes = [self.submit(user, code, "local") for code in body["codes"]]
        with self.db.transaction() as con:
            self.quota(con, user["id"])
            jid = con.execute("INSERT INTO jobs(kind,owner_id,p0,p1,s0,s1,seed,created) VALUES('local',?,?,?,?,?,?,?)",
                              (user["id"], user["id"], user["id"], codes[0]["id"], codes[1]["id"], secrets.randbits(63), time.time())).lastrowid
        return {"id": jid}

    def profile(self, user):
        return self.db.one("SELECT id,name,username,student1,student2 FROM users WHERE id=?", (user['id'],))

    def update_profile(self, user, body):
        require(user['role'] == 'team', 'این بخش مخصوص تیم‌ها است.', 403)
        require(set(body) == {'student1', 'student2'}, 'نام هر دو دانش‌آموز را وارد کنید.')
        names = []
        for key in ('student1', 'student2'):
            value = body[key]
            require(isinstance(value, str) and len(value.strip()) <= 80
                    and not any(ord(c) < 32 for c in value), 'هر نام باید حداکثر ۸۰ نویسه و در یک خط باشد.')
            names.append(value.strip())
        with self.db.transaction() as con:
            con.execute("UPDATE users SET student1=?,student2=? WHERE id=? AND role='team'", (*names, user['id']))
        return self.profile(user)

    def scoreboard(self, user, tournament=None):
        require(tournament is None or type(tournament) is int and 0 < tournament <= 2**63-1, 'شمارهٔ تورنمنت معتبر نیست.')
        if tournament is not None:
            require(self.db.one('SELECT id FROM tournaments WHERE id=?', (tournament,)), 'تورنمنت پیدا نشد.', 404)
        return {'items': standings(self.db, tournament)}

    def create_friendly(self, user, body):
        # Keep the old URL safe for cached clients: it creates an invitation too.
        return self.invite(user, body)

    def reset_friendly_counts(self, user):
        self.admin(user)
        with self.db.transaction() as con:
            cutoff = con.execute('SELECT COALESCE(MAX(id),0) FROM jobs').fetchone()[0]
            con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('friendly_stats_after_id',?)", (str(cutoff),))
        return {'after_job_id': cutoff}

    def invite(self, user, body):
        target = body.get("team_id")
        require(type(target) is int and 0 < target <= 2**63-1 and target != user["id"], "یک تیم دیگر را انتخاب کنید.")
        require(user['role'] == 'team', 'این بخش مخصوص تیم‌ها است.', 403)
        with self.db.transaction() as con:
            self.quota(con, user["id"])
            require(con.execute("SELECT 1 FROM users WHERE id=? AND role='team' AND active=1", (target,)).fetchone(), "تیم پیدا نشد.")
            submission = self.db.active_submission(user["id"], con)
            require(submission, "ابتدا کد خود را ارسال کنید.")
            require(self.db.active_submission(target, con), "تیم مقابل هنوز کدی ارسال نکرده است.")
            pending = con.execute("SELECT COUNT(*) FROM invitations WHERE sender=? AND created>?", (user["id"], time.time()-60)).fetchone()[0]
            require(pending < 10, "حداکثر ده دعوت در دقیقه مجاز است.", 429)
            duplicate = con.execute("SELECT 1 FROM invitations WHERE status='pending' AND expires>? AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?))", (time.time(), user["id"], target, target, user["id"])).fetchone()
            require(not duplicate, "یک دعوت باز بین شما وجود دارد.", 409)
            iid = con.execute("INSERT INTO invitations(sender,recipient,submission_id,created,expires) VALUES(?,?,?,?,?)", (user["id"], target, submission["id"], time.time(), time.time()+86400)).lastrowid
        return {"id": iid, "status": "pending", "job_id": None}

    def respond(self, user, iid, body):
        action = body.get("action")
        require(action in ("accept", "reject", "cancel"), "پاسخ معتبر نیست.")
        with self.db.transaction() as con:
            invite = con.execute("SELECT * FROM invitations WHERE id=?", (iid,)).fetchone()
            require(invite is not None, "دعوت پیدا نشد.", 404)
            require(user["id"] == invite["sender" if action == "cancel" else "recipient"], "اجازهٔ پاسخ به این دعوت را ندارید.", 403)
            require(invite["status"] == "pending" and invite["expires"] > time.time(), "این دعوت بسته شده یا زمانش تمام شده است.", 409)
            jid = None
            if action == "accept":
                self.quota(con, user["id"])
                self.quota(con, invite["sender"])
                require(con.execute("SELECT 1 FROM users WHERE id=? AND active=1", (invite["sender"],)).fetchone(), "تیم دعوت‌کننده غیرفعال است.")
                own = self.db.active_submission(user["id"], con)
                require(own, "برای پذیرش دعوت کد ارسال کنید.")
                seats = [(invite["sender"], invite["submission_id"]), (user["id"], own["id"])]
                if secrets.randbelow(2):
                    seats.reverse()
                jid = con.execute("INSERT INTO jobs(kind,owner_id,p0,p1,s0,s1,seed,created) VALUES('friendly',?,?,?,?,?,?,?)",
                                  (invite["sender"], seats[0][0], seats[1][0], seats[0][1], seats[1][1], secrets.randbits(63), time.time())).lastrowid
            status = {"accept": "accepted", "reject": "rejected", "cancel": "cancelled"}[action]
            con.execute("UPDATE invitations SET status=?,job_id=? WHERE id=?", (status, jid, iid))
        return {"id": iid, "job_id": jid, "status": status}

    def create_team(self, user, body):
        self.admin(user)
        username, name = [str(body.get(k, "")).strip() for k in ("username", "name")]
        password = body.get('password', '')
        require(re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username), "نام کاربری: ۳ تا ۳۲ حرف انگلیسی، عدد، نقطه یا خط.")
        require(1 <= len(name) <= 60 and isinstance(password,str) and 8 <= len(password) <= 128, "نام تیم لازم است؛ رمز باید ۸ تا ۱۲۸ نویسه باشد.")
        try:
            uid = self.db.add_user(username, name, password)
        except sqlite3.IntegrityError:
            raise APIError("این نام کاربری قبلاً ثبت شده است.", 409)
        return {"id": uid}

    def provision_numbered_teams(self, user, teams):
        """Local operator batch import; six-digit passwords are specific to this tool."""
        self.admin(user)
        require(isinstance(teams, list) and 1 <= len(teams) <= 1000, "Batch size must be 1..1000")
        for index, team in enumerate(teams, 1):
            expected = f"team_{index:02d}"
            require(team.get("username") == expected and team.get("name") == expected,
                    "Batch teams must be consecutively numbered from team_01")
            require(isinstance(team.get("password"), str)
                    and re.fullmatch(r"[1-9][0-9]{5}", team["password"]),
                    "Batch passwords must be six digits")
        try:
            with self.db.transaction() as con:
                con.executemany(
                    "INSERT INTO users(username,name,password,role,created) VALUES(?,?,?,'team',?)",
                    [(team["username"], team["name"], password_hash(team["password"]), time.time())
                     for team in teams])
        except sqlite3.IntegrityError:
            raise APIError("A numbered team already exists; no teams were created.", 409)

    def update_team(self, user, uid, body):
        self.admin(user)
        with self.db.transaction() as con:
            require(con.execute("SELECT 1 FROM users WHERE id=? AND role='team'", (uid,)).fetchone(), "تیم پیدا نشد.", 404)
            if 'name' in body:
                require(isinstance(body['name'],str) and 1 <= len(body['name'].strip()) <= 60, 'نام تیم باید بین ۱ تا ۶۰ نویسه باشد.')
                con.execute('UPDATE users SET name=? WHERE id=?', (body['name'].strip(), uid))
            if "password" in body:
                require(isinstance(body["password"], str) and 8 <= len(body["password"]) <= 128, "رمز باید ۸ تا ۱۲۸ نویسه باشد.")
                con.execute("UPDATE users SET password=? WHERE id=?", (password_hash(body["password"]), uid))
            if "active" in body:
                require(type(body["active"]) is bool, "وضعیت معتبر نیست.")
                con.execute("UPDATE users SET active=? WHERE id=?", (int(body["active"]), uid))
            if 'password' in body or 'active' in body:
                con.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
        return {"ok": True}

    def create_tournament(self, user, body):
        self.admin(user)
        name, start, teams = body.get("name"), body.get("starts_at"), body.get("teams")
        require(isinstance(name, str) and 1 <= len(name.strip()) <= 80, "نام تورنمنت لازم است.")
        require(type(start) in (float, int) and time.time()-60 <= start <= time.time()+366*86400, "زمان شروع معتبر نیست.")
        require(type(body.get('paired',False)) is bool, "نوع برگزاری معتبر نیست.")
        games_per_pair = body.get('games_per_pair', 2 if body.get('paired') else 1)
        require(type(games_per_pair) is int and 1 <= games_per_pair <= 100,
                'تعداد بازی برای هر جفت تیم باید عددی صحیح از ۱ تا ۱۰۰ باشد.')
        require(isinstance(teams, list) and 2 <= len(teams) <= 100 and all(type(t) is int and 0 < t <= 2**63-1 for t in teams) and len(set(teams)) == len(teams), "۲ تا ۱۰۰ تیم متفاوت انتخاب کنید.")
        with self.db.transaction() as con:
            for team in teams:
                require(con.execute("SELECT 1 FROM users WHERE id=? AND role='team' AND active=1", (team,)).fetchone(), "یکی از تیم‌ها معتبر نیست.")
                require(self.db.active_submission(team, con), "همهٔ تیم‌ها باید حداقل یک کد معتبر داشته باشند.")
            tid = con.execute("INSERT INTO tournaments(name,starts_at,paired,games_per_pair,created) VALUES(?,?,?,?,?)", (name.strip(), start, int(games_per_pair > 1), games_per_pair, time.time())).lastrowid
            con.executemany("INSERT INTO entries(tournament_id,user_id) VALUES(?,?)", [(tid, team) for team in teams])
        return {"id": tid}

    def tournament_action(self, user, tid, body):
        self.admin(user)
        with self.db.transaction() as con:
            tournament = con.execute("SELECT * FROM tournaments WHERE id=?", (tid,)).fetchone()
            require(tournament is not None, "تورنمنت پیدا نشد.", 404)
            action = body.get("action")
            if action == "start":
                require(tournament["status"] == "scheduled", "این تورنمنت قابل شروع نیست.", 409)
                con.execute("UPDATE tournaments SET starts_at=? WHERE id=?", (time.time(), tid))
            elif action == "cancel":
                require(tournament["status"] == "scheduled", "فقط تورنمنت شروع‌نشده قابل لغو است.", 409)
                con.execute("UPDATE tournaments SET status='cancelled' WHERE id=?", (tid,))
            elif action == "retry":
                require(tournament["status"] == "failed", "فقط بازی‌های دچار خطای زیرساخت دوباره اجرا می‌شوند.", 409)
                require(con.execute("SELECT 1 FROM jobs WHERE tournament_id=? AND status='failed'", (tid,)).fetchone(), "این تورنمنت بازی قابل تکرار ندارد.")
                con.execute("UPDATE jobs SET status='queued',error=NULL WHERE tournament_id=? AND status='failed'", (tid,))
                con.execute("UPDATE tournaments SET status='running',error=NULL WHERE id=?", (tid,))
            else:
                raise APIError("عملیات معتبر نیست.")
        return {"ok": True}

    def matches(self, user, page=1, tournament=None, status=None):
        require(tournament is None or type(tournament) is int and 0 < tournament <= 2**63-1, 'شمارهٔ تورنمنت معتبر نیست.')
        page = max(1, min(10000, page))
        conditions, params = [], []
        if user["role"] != "admin":
            conditions.append("(j.owner_id=? OR j.p0=? OR j.p1=? OR j.tournament_id IS NOT NULL)")
            params += [user["id"]]*3
        if tournament:
            conditions.append("j.tournament_id=?")
            params.append(tournament)
        if status:
            require(status in ('queued','running','completed','failed'), 'وضعیت مسابقه معتبر نیست.')
            conditions.append('j.status=?')
            params.append(status)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        total = self.db.one(f"SELECT COUNT(*) AS n FROM jobs j {where}", params)["n"]
        rows = self.db.rows(f"""SELECT j.id,j.kind,j.status,j.owner_id,j.p0,j.p1,j.s0,j.s1,j.bot,j.tournament_id,
            j.round,j.winner,j.reason,j.score0,j.score1,j.error,j.created,j.started,j.finished,
            u.name AS name0,v.name AS name1,u.student1 AS student0a,u.student2 AS student0b,v.student1 AS student1a,v.student2 AS student1b,t.name AS tournament_name FROM jobs j
            LEFT JOIN users u ON u.id=j.p0 LEFT JOIN users v ON v.id=j.p1
            LEFT JOIN tournaments t ON t.id=j.tournament_id {where}
            ORDER BY j.id DESC LIMIT 25 OFFSET ?""", [*params, (page-1)*25])
        for row in rows:
            for seat in (0, 1):
                students = [row.pop(f'student{seat}a'), row.pop(f'student{seat}b')]
                if row[f'name{seat}'] is not None:
                    row[f'name{seat}'] = team_label({'name': row[f'name{seat}'], 'student1': students[0], 'student2': students[1]})
            if row["bot"]:
                row["name0" if row["p0"] is None else "name1"] = BOTS[row["bot"]]["name"]
        return {"items": rows, "page": page, "total": total}

    def admin_overview(self, user):
        self.admin(user)
        dashboard = self.dashboard(user)
        teams = self.db.rows("""SELECT u.id,u.name,u.username,u.student1,u.student2,u.active,u.created,
            s.id AS submission_id,s.filename,s.language,s.created AS submitted_at,
            (SELECT COUNT(*) FROM submissions x WHERE x.user_id=u.id AND x.kind='official') AS submissions
            FROM users u LEFT JOIN submissions s ON s.id=u.active_submission_id WHERE u.role='team' ORDER BY u.id""")
        for team in teams:
            team['display_name'] = team_label(team)
        return {'teams': teams, 'worker': dashboard['worker'], 'queue': dashboard['queue'],
                'settings': worker_settings(self.db), 'tournaments': dashboard['tournaments'],
                'counts': {'teams': len(teams), 'active': sum(t['active'] for t in teams),
                           'ready': sum(bool(t['submission_id']) and bool(t['active']) for t in teams)}}

    def configure_worker(self, user, body):
        self.admin(user)
        require(body and set(body).issubset({'slots','paused'}), 'تنظیمات اجرا معتبر نیست.')
        if 'slots' in body:
            require(type(body['slots']) is int and 1 <= body['slots'] <= 128, 'ظرفیت باید عددی بین ۱ و ۱۲۸ باشد.')
        if 'paused' in body:
            require(type(body['paused']) is bool, 'وضعیت توقف معتبر نیست.')
        with self.db.transaction() as con:
            row = con.execute("SELECT value FROM meta WHERE key='worker_settings'").fetchone()
            settings = json.loads(row['value']) if row else {'slots': 6, 'paused': False}
            settings.update(body)
            con.execute("INSERT OR REPLACE INTO meta VALUES('worker_settings',?)", (json.dumps(settings),))
        return settings

    def retry_job(self, user, jid, body):
        self.admin(user)
        require(body.get('action') == 'retry', 'عملیات معتبر نیست.')
        with self.db.transaction() as con:
            job = con.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone()
            require(job is not None, 'بازی پیدا نشد.', 404)
            require(job['status'] == 'failed' and job['tournament_id'] is None,
                    'فقط بازی دوستانه با خطای زیرساخت قابل تکرار است؛ خطاهای تورنمنت را از صفحهٔ تورنمنت تکرار کنید.', 409)
            con.execute("UPDATE jobs SET status='queued',error=NULL,started=NULL,finished=NULL,worker=NULL WHERE id=?", (jid,))
        return {'id': jid, 'status': 'queued'}

    def dashboard(self, user):
        uid = user["id"]
        active=self.db.active_submission(uid)
        active={k:active[k] for k in ('id','filename','language','created')} if active else None
        heartbeat = self.db.one("SELECT value FROM meta WHERE key='worker_heartbeat'")
        heartbeat = json.loads(heartbeat["value"]) if heartbeat else {"at": 0, "slots": 0, "active": 0}
        heartbeat["online"] = time.time()-heartbeat["at"] < 10
        queue = self.db.rows("SELECT status,COUNT(*) AS n FROM jobs GROUP BY status")
        teams = self.db.rows("""SELECT u.id,u.name,u.username,u.student1,u.student2,u.active,
            u.active_submission_id AS submission_id
            FROM users u WHERE role='team' ORDER BY u.id""")
        if user["role"] != "admin":
            teams = [{k: t[k] for k in ("id", "name", "student1", "student2", "submission_id")} for t in teams if t["active"]]
        for team in teams:
            team['display_name'] = team_label(team)
        invites = self.db.rows("""SELECT i.*,a.name AS sender_name,b.name AS recipient_name,a.student1 AS sender_student1,a.student2 AS sender_student2,b.student1 AS recipient_student1,b.student2 AS recipient_student2 FROM invitations i
            JOIN users a ON a.id=i.sender JOIN users b ON b.id=i.recipient
            WHERE i.sender=? OR i.recipient=? ORDER BY CASE WHEN i.status='pending' AND i.expires>strftime('%s','now') THEN 0 ELSE 1 END,i.id DESC LIMIT 100""", (uid, uid))
        for invite in invites:
            for side in ('sender', 'recipient'):
                invite[side + '_name'] = team_label({'name': invite[side + '_name'], 'student1': invite.pop(side + '_student1'), 'student2': invite.pop(side + '_student2')})
            if invite["status"] == "pending" and invite["expires"] < time.time():
                invite["status"] = "expired"
        stats = self.db.one("""SELECT COUNT(*) AS played,
            COALESCE(SUM(CASE WHEN (winner=0 AND p0=?) OR (winner=1 AND p1=?) THEN 1 ELSE 0 END),0) AS wins,
            COALESCE(SUM(winner IS NULL),0) AS draws FROM jobs WHERE status='completed'
            AND kind NOT IN ('local','debug') AND (kind!='friendly' OR id>?) AND (p0=? OR p1=?)""", (uid,uid,friendly_stats_cutoff(self.db),uid,uid))
        tournaments = self.db.rows("""SELECT t.*,(SELECT COUNT(*) FROM entries e WHERE e.tournament_id=t.id) AS teams,
            (SELECT COUNT(*) FROM jobs j WHERE j.tournament_id=t.id) AS games,
            (SELECT COUNT(*) FROM jobs j WHERE j.tournament_id=t.id AND j.status='completed') AS completed
            FROM tournaments t WHERE t.status != 'cancelled' ORDER BY id DESC""")
        return {"profile": self.profile(user), "teams": teams, "active_submission_id": active['id'] if active else None, 'active_submission':active, "submission_count": self.db.one("SELECT COUNT(*) AS n FROM submissions WHERE user_id=? AND kind='official'",(uid,))['n'], "submissions": self.db.rows("SELECT id,filename,language,digest,created FROM submissions WHERE user_id=? AND kind='official' ORDER BY id DESC LIMIT 25", (uid,)),
                "invitations": invites, "stats": stats, "worker": heartbeat,
                "queue": {r["status"]: r["n"] for r in queue}, "matches": self.matches(user), "tournaments": tournaments}

    def replay(self, user, jid):
        job = self.db.one("SELECT * FROM jobs WHERE id=?", (jid,))
        require(job is not None, "بازی پیدا نشد.", 404)
        require(user["role"] == "admin" or job["tournament_id"] is not None or user["id"] in (job["owner_id"], job["p0"], job["p1"]), "این بازی متعلق به شما نیست.", 403)
        require(job["status"] == "completed", "بازپخش پس از پایان بازی آماده می‌شود.", 409)
        return json.loads(Path(job["replay"]).read_text(encoding="utf-8"))

    def job_status(self, user, jid):
        job = self.db.one("SELECT id,status,owner_id,p0,p1,tournament_id,error FROM jobs WHERE id=?", (jid,))
        require(job is not None, "بازی پیدا نشد.", 404)
        require(user["role"] == "admin" or job["tournament_id"] is not None or user["id"] in (job["owner_id"], job["p0"], job["p1"]), "این بازی متعلق به شما نیست.", 403)
        return job
