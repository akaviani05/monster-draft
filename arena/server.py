from functools import partial
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import html
import json
import ipaddress
import logging
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import threading
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from .scheduling import standings
from .service import APIError, Service, require
from .storage import ROOT
from .worker import BOTS

WEB = ROOT / "web"


def version_asset_links(content, document):
    """Version local scripts/styles from their bytes, without a frontend build."""
    def replace(match):
        prefix, quote, value = match.groups()
        url = urlsplit(html.unescape(value))
        if url.scheme or url.netloc:
            return match.group(0)
        asset = ((WEB / url.path.lstrip('/')) if url.path.startswith('/')
                 else document.parent / url.path).resolve()
        if not asset.is_relative_to(WEB) or asset.suffix not in ('.js', '.css') or not asset.is_file():
            return match.group(0)
        version = hashlib.sha256(asset.read_bytes()).hexdigest()[:16]
        query = [(key, val) for key, val in parse_qsl(url.query) if key != 'v']
        query.append(('v', version))
        value = urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), url.fragment))
        return prefix + quote + html.escape(value, quote=True) + quote
    return re.sub(r'''(\b(?:src|href)\s*=\s*)(["'])([^"']+)\2''', replace,
                  content.decode('utf-8'), flags=re.IGNORECASE).encode('utf-8')


class ArenaHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128

    def __init__(self, address, service):
        self.service = service
        self.connections = threading.BoundedSemaphore(64)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.connections.acquire(False):
            request.close()
            return
        super().process_request(request, address)

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.connections.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "MonsterArena"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, fmt, *args):
        # Never log request bodies, passwords, session headers or source code.
        logging.info("%s %s", self.client_address[0], fmt % args)

    def reply(self, status, value, mime="application/json; charset=utf-8", headers=None):
        stream = hasattr(value, 'read')
        raw = value if stream or isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        if stream:
            raw.seek(0, 2)
            length = raw.tell()
            raw.seek(0)
        else:
            length = len(raw)
        self.send_response(status)
        for key, val in {"Content-Type": mime, "Content-Length": str(length),
                         "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
                         "Referrer-Policy": "same-origin", "Cache-Control": "no-store",
                         "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
                         "Permissions-Policy": "camera=(), microphone=(), geolocation=()", **(headers or {})}.items():
            self.send_header(key, val)
        self.end_headers()
        if self.command != "HEAD":
            if stream:
                shutil.copyfileobj(raw, self.wfile)
            else:
                self.wfile.write(raw)

    def cookie(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            return cookie["arena_session"].value if "arena_session" in cookie else ""
        except Exception:
            return ""

    def origin_check(self):
        origin = self.headers.get("Origin")
        expected = os.environ.get("ARENA_ORIGIN")
        host = self.headers.get("Host", "")
        require(bool(host) and not any(c in host for c in "/\\@\r\n"), "میزبان معتبر نیست.", 403)
        if expected:
            require(host == urlsplit(expected).netloc, "میزبان معتبر نیست.", 403)
        else:
            # Default installation is localhost-only. Production must set origin.
            require(urlsplit("http://"+host).hostname in ("127.0.0.1", "localhost", "::1"), "ARENA_ORIGIN را برای دامنهٔ سایت تنظیم کنید.", 403)
        if origin:
            require(origin == (expected or "http://" + host), "درخواست از سایت دیگری مجاز نیست.", 403)
        require(self.headers.get("Sec-Fetch-Site", "") != "cross-site", "درخواست از سایت دیگری مجاز نیست.", 403)

    def body(self):
        require(self.headers.get_content_type() == "application/json", "درخواست JSON لازم است.", 415)
        length = self.headers.get("Content-Length", "0")
        require(length.isdigit() and 0 < int(length) <= 180000, "حجم درخواست بیش از حد مجاز است.", 413)
        require(not self.headers.get("Transfer-Encoding"), "قالب انتقال مجاز نیست.", 400)
        try:
            raw = self.rfile.read(int(length))
            require(len(raw) == int(length), "درخواست ناقص است.")
            value = json.loads(raw)
            require(isinstance(value, dict), "یک شیء JSON لازم است.")
            # Escaped lone surrogates decode in Python but cannot be stored or
            # returned as UTF-8. Reject them in every field, including nested code.
            json.dumps(value, ensure_ascii=False).encode('utf-8')
            return value
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise APIError("JSON قابل خواندن نیست.")

    def login_address(self):
        peer = self.client_address[0]
        trusted = {ip.strip() for ip in os.environ.get('ARENA_TRUSTED_PROXIES','').split(',') if ip.strip()}
        if peer in trusted:
            raw = self.headers.get('X-Real-IP','')
            try:return str(ipaddress.ip_address(raw))
            except ValueError:raise APIError('آدرس پراکسی معتبر نیست.',403)
        return peer

    def do_GET(self):
        self.handle_request()

    def do_HEAD(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    @staticmethod
    def resource_id(value):
        # SQLite IDs are signed 64-bit integers. Bound before conversion/binding.
        require(len(value) <= 19 and 0 <= int(value) <= 2**63-1, "این مورد پیدا نشد.", 404)
        return int(value)

    def handle_request(self):
        try:
            self.dispatch()
        except APIError as exc:
            self.reply(exc.status, {"error": exc.message})
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass
        except Exception:
            logging.exception("Request failed")
            self.reply(500, {"error": "خطای داخلی؛ مسئول مسابقه گزارش سرور را بررسی کند."})

    def dispatch(self):
        url = urlsplit(self.path)
        path, query, service = url.path, parse_qs(url.query), self.server.service
        if path.startswith("/api/"):
            self.origin_check()
            user = service.authenticate(self.cookie())
            if self.command in ("GET", "HEAD"):
                if path == "/api/health":
                    return self.reply(200, {"ok": True})
                if path == "/api/session":
                    return self.reply(200, {"user": {k: user[k] for k in ("id", "name", "username", "role")} if user else None, "csrf": user["csrf"] if user else None})
                if path == "/api/bots":
                    return self.reply(200, {"items": [{"id": k, **{a: v[a] for a in ("name", "level", "description")}} for k, v in BOTS.items()]})
                require(user, "برای ادامه وارد حساب تیم شوید.", 401)
                if path == '/api/profile':
                    return self.reply(200, service.profile(user))
                if path == '/api/scoreboard':
                    require('tournament' not in query or re.fullmatch(r'[0-9]+', query['tournament'][0]), 'شمارهٔ تورنمنت معتبر نیست.')
                    tid = self.resource_id(query['tournament'][0]) if 'tournament' in query else None
                    return self.reply(200, service.scoreboard(user, tid))
                if path == "/api/dashboard":
                    return self.reply(200, service.dashboard(user))
                if path == '/api/submissions':
                    try:page=int(query.get('page',['1'])[0])
                    except ValueError:raise APIError('شمارهٔ صفحه معتبر نیست.')
                    return self.reply(200,service.list_submissions(user,page))
                if path == '/api/admin/overview':
                    return self.reply(200, service.admin_overview(user))
                if path == '/api/admin/submissions.zip':
                    scope = query.get('scope', ['all'])[0]
                    with service.submission_archive(user, scope) as archive:
                        return self.reply(200, archive, 'application/zip',
                            {'Content-Disposition': f'attachment; filename="submissions-{scope}.zip"'})
                if path == '/api/admin/queue':
                    service.admin(user)
                    try: page = int(query.get('page', ['1'])[0])
                    except ValueError: raise APIError('شمارهٔ صفحه معتبر نیست.')
                    return self.reply(200, service.matches(user, page=page, status=query.get('status', [''])[0]))
                if path == "/api/matches":
                    try:
                        page = int(query.get("page", ["1"])[0])
                        tournament = int(query["tournament"][0]) if "tournament" in query else None
                    except ValueError:
                        raise APIError("شمارهٔ صفحه معتبر نیست.")
                    return self.reply(200, service.matches(user, page, tournament))
                match = re.fullmatch(r"/api/matches/(\d+)/replay", path)
                if match:
                    return self.reply(200, service.replay(user, self.resource_id(match[1])))
                match = re.fullmatch(r"/api/debug/(\d+)", path)
                if match:
                    return self.reply(200, service.diagnostics(user, self.resource_id(match[1])))
                match = re.fullmatch(r"/api/matches/(\d+)", path)
                if match:
                    return self.reply(200, service.job_status(user, self.resource_id(match[1])))
                match = re.fullmatch(r"/api/tournaments/(\d+)", path)
                if match:
                    tid = self.resource_id(match[1])
                    tournament = service.db.one("SELECT * FROM tournaments WHERE id=?", (tid,))
                    require(tournament, "تورنمنت پیدا نشد.", 404)
                    return self.reply(200, {"tournament": tournament, "standings": standings(service.db, tid)})
                match = re.fullmatch(r"/api/submissions/(\d+)", path)
                if match:
                    submission = service.db.one("SELECT * FROM submissions WHERE id=? AND user_id=?", (self.resource_id(match[1]), user["id"]))
                    require(submission, "کد پیدا نشد.", 404)
                    source = Path(submission["path"]).parent / ("source.py" if submission["language"] == "python" else "source.cpp")
                    return self.reply(200, {"source": source.read_text(encoding="utf-8"), "filename": submission["filename"], "language": submission["language"]})
            elif self.command == "POST":
                body = self.body()
                if path in ('/api/login', '/api/admin/login'):
                    authenticate = service.admin_login if path == '/api/admin/login' else service.login
                    token, data = authenticate(body, self.login_address())
                    secure = "; Secure" if os.environ.get("ARENA_SECURE_COOKIE") == "1" else ""
                    return self.reply(200, data, headers={"Set-Cookie": f"arena_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800{secure}"})
                require(user, "برای ادامه وارد حساب تیم شوید.", 401)
                require(secrets.compare_digest(self.headers.get("X-CSRF-Token", "").encode('utf-8'), user["csrf"].encode('utf-8')), "نشست معتبر نیست؛ صفحه را تازه کنید.", 403)
                if path == "/api/logout":
                    with service.db.transaction() as con:
                        con.execute("DELETE FROM sessions WHERE token=?", (user["token"],))
                    return self.reply(200, {"ok": True}, headers={"Set-Cookie": "arena_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})
                routes = {"/api/debug": service.create_debug, "/api/profile": service.update_profile, "/api/friendlies": service.create_friendly, "/api/submissions": service.submit, "/api/practice": service.create_practice,
                          "/api/local": service.local, "/api/invitations": service.invite,
                          "/api/admin/teams": service.create_team, "/api/admin/tournaments": service.create_tournament,
                          '/api/admin/worker': service.configure_worker}
                if path in routes:
                    return self.reply(201, routes[path](user, body))
                for pattern, method in ((r"/api/invitations/(\d+)", service.respond),
                                        (r'/api/submissions/(\d+)/activate', service.activate_submission),
                                        (r'/api/admin/jobs/(\d+)', service.retry_job),
                                        (r"/api/admin/teams/(\d+)", service.update_team),
                                        (r"/api/admin/tournaments/(\d+)", service.tournament_action)):
                    match = re.fullmatch(pattern, path)
                    if match:
                        if path.startswith('/api/admin/'):service.admin(user)
                        return self.reply(200, method(user, self.resource_id(match[1]), body))
            raise APIError("این مسیر پیدا نشد.", 404)
        require(self.command in ("GET", "HEAD"), "روش مجاز نیست.", 405)
        aliases = {"/": "index.html", '/admin': 'admin.html', '/admin/': 'admin.html', "/guide": "guide.html", "/visualizer": "visualizer.html", "/login": "index.html"}
        relative = aliases.get(path, path.lstrip("/"))
        resolved = (WEB / relative).resolve()
        require(resolved.is_relative_to(WEB) and resolved.is_file(), "فایل پیدا نشد.", 404)
        mime = mimetypes.guess_type(resolved)[0] or "application/octet-stream"
        content = resolved.read_bytes()
        if resolved.suffix == '.html':
            content = version_asset_links(content, resolved)
        cache = "public, max-age=3600" if path.startswith("/assets/") and resolved.suffix not in ('.js', '.css') else "no-cache"
        self.reply(200, content, mime, {"Cache-Control": cache})
