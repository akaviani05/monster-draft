# Deployment and administration

For contest-day sequencing use the [runbook](CONTEST_RUNBOOK.md); for quick
commands see [README](../README.md). The [project map](PROJECT_STRUCTURE.md) defines
source/data ownership and the [November 12 experience](CONTEST_EXPERIENCE_2026-11-12.md)
records the organizer’s teaching and tournament process.

## Download team submissions

On the administrator's team-management page, use either ZIP download link:
all official submission versions, or only each team's selected final version.
Both include inactive teams and exclude local/debug uploads. Teams without a
selected final code have no file in the final archive. Each source has a unique
`Team Name--team-ID/original-name--submission-ID.py` or `.cpp` path. Persian names
are preserved with UTF-8 ZIP metadata. Unsafe path/control characters are replaced;
IDs prevent duplicate team names or filenames from overwriting each other.
`manifest.json` maps every source to the team, original filename and version.
Final means the current selection, not a
tournament's frozen version. Downloads require an authenticated administrator,
are sent with `Cache-Control: no-store`, and do not create public archive files.

## Host and installation

Use a dedicated, patched Linux host with at least six available CPU cores, 8 GiB
RAM and local SSD storage. The tested platform is Python 3.12 on Linux x86-64,
Landlock ABI 4 and the distro's `libseccomp2`/`g++`. ABI ≥ 3 is mandatory. No pip
installation, frontend build, Redis or external database is needed. Containers
must permit the Landlock and seccomp calls; `doctor` fails rather than disabling
isolation. Standard systemd hosting is the easiest deployment path.

1. Put the source checkout at `/opt/monster-duel`, owned by the operator and
   readable by the dedicated unprivileged `arena` account.
2. Create `/var/lib/monster-duel`, owned by that account with mode 0700.
3. Set the environment variables below in the service files or an
   operator-managed environment file. Do not put passwords in command arguments.
4. Run `python3 -m arena doctor` and `python3 -m arena init` as that account with
   `ARENA_DATA` set. Create the administrator before exposing the service.
5. Install the two sample systemd units and the reverse-proxy configuration in
   `deploy/`, adapting paths, domain and certificates to your own host.
6. Run the tests and browser suite on a staging installation, then start the web
   and worker services. Visit «مدیریت مسابقه» to create teams.

```text
ARENA_DATA=/var/lib/monster-duel
ARENA_ORIGIN=https://arena.example.org
ARENA_SECURE_COOKIE=1
ARENA_TRUSTED_PROXIES=127.0.0.1
```

The server binds `0.0.0.0` (all IPv4 interfaces) by default. Its Origin/Host checks
accept loopback only unless `ARENA_ORIGIN` is set to the URL clients use. The
sample systemd web service explicitly binds `127.0.0.1` for nginx. Production
requires HTTPS at the reverse proxy and Secure cookies. The example proxy
overwrites Host and bounds request size/time.
Login throttling uses the direct peer address by default. The example enables
`ARENA_TRUSTED_PROXIES=127.0.0.1` and nginx overwrites `X-Real-IP` with its actual
client address. Only the explicitly trusted proxy may supply this header, and
the server validates it as one IP address. Keep the backend bound to loopback.
Without this setting proxied users share one application login bucket. The nginx
configuration adds per-client rate limiting at the outer boundary as well.
Never trust arbitrary X-Forwarded-For values or list untrusted proxies.

## Capacity and scheduling

HTML responses automatically version local JavaScript and CSS URLs using their
content hashes. HTML, scripts and styles use `Cache-Control: no-cache`, so a
normal reload picks up edits without Ctrl+F5 or manual version-label changes.
Fonts and artwork retain their one-hour cache. Restart the web service when
updating Python code; asset-only edits need no server restart or frontend build.

Run one supervisor per data directory:

```bash
python3 -m arena worker --slots 6
python3 -m arena serve --host 127.0.0.1 --port 8000
```

For a larger host, set the capacity from `/admin` → execution settings. The CLI
`--slots` option initializes a new installation; persistent admin settings take
precedence after that. Pause/resume controls affect new dispatches only.
Completed results are not rerun. On clean shutdown the supervisor drains its
running games; systemd allows 45 seconds. On a crash, parent-death signals kill
the bots, and startup requeues any jobs without committed results. The database
lock prevents two supervisors from dispatching the same queue. Do not start a
standalone worker and `serve --with-worker` against the same data directory.

Jobs use a local SQLite WAL database with `BEGIN IMMEDIATE` claims and transactional
invitation acceptance. Logs are written via temporary-file replacement before the
result transaction. Compiled executable/source paths are immutable and private.
SQLite must live on a local filesystem, not NFS. The server and worker must share
the same data path, source checkout, interpreter version and UID. Limit unrelated
CPU work during judging; Python startup and waiting for active replies count
toward the published wall-clock budgets. C++ compilation occurs on upload, not
inside each tournament game. Finish uploads before the scheduled start when
possible, or reserve separate CPU capacity for the website/compiler.

The built-in practice opponent **اژدها** (`champion`) is C++17. For a practice
or debug job against it, the worker compiles the bundled source through the
isolated compiler, keeps the temporary executable for that match and removes it
afterward. Compilation is outside the player's response budget and adds queue
latency. Student C++ submissions continue to use their frozen uploaded binaries;
tournament games do not compile this built-in opponent. Restart the web and
worker services after installing the new bot registry and worker support.

`python3 scripts/evaluate_bot.py --seeds 20 --seed-start 1000` runs seat-paired
games against the reference bots under the normal sandbox and limits. Add
`--data /path/to/arena-data` only when authorized to evaluate the installation's
selected team submissions. The evaluator opens SQLite read-only, freezes the
selected IDs/paths at start, never reads account credentials or student source,
and writes no jobs, statistics or results into the installation. Reports and
anonymous loss replays stay under ignored `output/`. A report is marked complete
only after all requested opponents finish. Later uploads require another run.
To reproduce a frozen official version even after the team uploads again, use
`--data /path/to/arena-data --submission ID --opponent submission-ID`. This
selects that version by ID without changing the team's current selection.

## Admin workflow

- Teams may request up to 10 games per rolling minute, enforced transactionally.
  There is no hourly, daily or pending-game cap. Invitations are limited to
  10 per rolling minute; code upload limits remain separate.
- On «کدهای من», «آزمایش تعاملی کد» runs the current editor contents against a
  selected practice bot without making it the team's final submission. This
  area has its own Python/C++ file picker (64 KiB maximum); selection updates
  the editor, filename and language, and preserves them while testing.
  The feature
  works before a team has any official submission. Tests use the normal queue,
  isolated compiler/judge and the existing submission/game quotas and time limits.
  After completion, students step through each turn's stdin/stdout, view the
  observed message order, inspect stderr/tracebacks and open the exact replay.
- `POST /api/debug` accepts `source`, `language`, `filename` and `bot`.
  `GET /api/debug/<id>` returns diagnostics only to that job's owner, after
  completion; other accounts, including administrators, cannot retrieve them.
  Worker-written `replays/<id>.debug.json` files are private (0600), atomically
  replaced and persisted with the data directory. They never enter shared
  replays or downloads. Capture is limited to 16 KiB per stream and 512 events;
  the UI identifies truncated reports. Normal games do not capture these traces.
  Debug games do not count toward friendly/tournament standings or team stats.
  Restart both web and worker services after installing this update.
- Teams enter or clear two student names on «پروفایل تیم». Each name allows up
  to 80 characters. Names appear in parentheses beside the team in opponent
  choices, matches, invitations, scoreboards and the searchable admin team list.
  Database startup adds the two empty name fields to existing accounts; existing
  results and frozen submissions are retained. Restart web and worker services
  after updating the source to apply the migration consistently.
- «بازی دوستانه» requires the selected team's acceptance. Sending a request
  shows «در انتظار تأیید تیم مقابل» and creates no match until the recipient
  accepts. The sender's version freezes at invitation time and the recipient's
  at acceptance. Both game quotas and single acceptance remain transactional.
  The old `/api/friendlies` endpoint also creates a pending invitation; it cannot
  bypass approval.
- Friendly-statistics resets use a stored job-ID cutoff. Existing matches,
  replays, invitations, submissions and tournament results remain intact; only
  later friendly jobs contribute to the friendly table and personal statistics.
  Game-request quota accounting is retained. No match/history records are deleted.
- «جدول امتیازها» is available to teams and the administrator. Choose team
  friendlies or any tournament. The friendly table counts completed human-team
  games only, excluding bots, local code tests and unfinished/failed jobs.
  Tournament tables use their own entries and results. Teams with at least three
  completed games in the selected competition rank by win ratio (wins divided
  by all completed games, including draws). Teams with fewer games appear in a
  separate table below, without a rank. Equal ratios use wins, draws, score
  difference and finally team ID as tiebreaks.
- Create each team and give it its own credentials. There is no self-registration.
- Students submit code and practice; Python syntax is checked and C++ is compiled
  before a version becomes active. A valid compilation is not proof of a valid
  game protocol: students should play a bot practice game to check that.
- Password reset or disabling a team revokes all its sessions. Disabled teams
  cannot log in or accept invitations. Already queued matches use their frozen
  submissions. If a selected team is inactive or lacks a code at tournament start,
  start validation fails; fix the entries/accounts and create a new tournament.
- Create a tournament, select teams, set the local-browser start time and choose
  1–100 games per pair (default 1). The API stores UTC epoch time, independent of display
  timezone. Selected active teams and their selected final versions are frozen when
  the worker starts the tournament. The worker must be running at start time;
  overdue scheduled tournaments start automatically when it returns.
- «شروع اکنون» advances a scheduled start; «لغو» works before the tournament starts.
  Completed games and protocol losses are final. A failed infrastructure job
  pauses further dispatch for that tournament; other games already running drain.
  Diagnose logs, run `doctor`, then choose «تکرار خطاهای زیرساخت». It retries only
  failed jobs, retaining seeds and submission versions. It never rewrites wins.

Tournament cards and progress maxima show the team-pair count multiplied by the
saved games-per-pair setting, independent of queue population. The default is one
game per pair. With 50 teams this is 1,225 games in 49 rounds. Seats are balanced
24/25 starts per team. Paired mode is 2,450
games in 98 dispatch rounds; identical seeds are reused with opposite seats.
For 6 games per pair, 50 teams play 7,350 games in 294 dispatch rounds.
Consecutive games swap starting seats and reuse one seed; each next two-game
set gets a fresh seed. Odd counts include one additional balanced single game.
Round barriers remain in force; odd-field byes can increase the completed-game gap.
The `games_per_pair` API field takes precedence; older `paired` requests still map
to 1 or 2 games. Migration preserves existing scheduled and completed tournaments.

## Top-team statistics and selection

Tournament standings include win percentage against the current ranked top 10:
wins divided by completed games against those opponents, including draws in the
denominator. A team never plays itself; top-10 members are not replaced by rank
11 for their own calculation. With fewer than ten ranked teams, all ranked teams
are used. No qualifying games displays a dash. This statistic does not affect rank.

In tournament creation, choose a completed previous event, enter K (2–100), then
apply the top-team selection. It replaces the checked teams with ranks 1 through
K for review before submission; manual changes remain possible. Insufficient
ranked teams, inactive teams or missing active codes produce an error rather than
silently substituting lower-ranked teams. Normal server-side team validation and
start-time code freezing still apply.

## Backups and storage

Stop submissions briefly, gracefully stop the worker, then back up **the entire
data directory** (database, WAL/SHM if present, sources/binaries and replay files).
Use SQLite's backup API for a consistent online database copy, but still retain
all files it references. Do not copy only `arena.sqlite3` while WAL writes are
in progress. Protect backups as credentials/private student source material.

Keep referenced submissions for every job/invitation/tournament. Do not delete
history rows or files independently. The site caps each source at 64 KiB,
compiled executables at 4 MiB, each team at 100 source files/day, and retained
submission bytes at about 128 MiB. Small in-flight uploads may exceed the last
threshold by up to two files. If it fills, archive the complete contest and start
a fresh data directory for the next event. Never seed demo users into that archive.
Measure disk growth and keep space for replays (usually a few KiB per game).

## Student downloads

`web/downloads/runner.zip` contains only the two minimal starter examples, local practice
launcher/engine and an offline viewer. Practice opponents, the production judge,
admin/server files and match data are excluded by an exact allowlist. The Persian
guide is distributed separately. Run `scripts/package_starter.py`
after changing the runner or assets. `scripts/build_guide.py` regenerates the PDF
from the same guide HTML with Pango/Cairo so Persian letters remain joined.
The guide includes a four-turn implementation walkthrough, the two-stage OPPTURN
exchange, line-by-line Python/C++ explanations and optional card tracking.
Both the guide header and the implementation walkthrough link to the current
`web/downloads/student-guide-fa.pdf`; it remains separate from the starter ZIP.
The build script requires OS GI/Cairo/Pango/Rsvg bindings; they are not site or judge
runtime dependencies. Verify PDF pages visually after content edits.

The browser admin workflow is documented in [ADMIN_GUIDE.md](ADMIN_GUIDE.md).
Students now use `play.py` from IDLE for trusted local practice on desktop systems;
the isolated website judge remains Linux-only.

Each visualizer step shows the market at the moment of that step's selection.
The highlighted card and player match the recorded choice; hands and scores
include that choice. The replacement card is named in the step caption and
appears in the next selection's market. This applies to web and offline viewers.

## Local acceptance checks

Run the Python/JavaScript tests, `python3 -m arena doctor`,
`npm run test:browser:repeat` and `npm run test:screenshots` before accepting a
release. The browser suite creates a fresh server, worker and marked temporary
database for each scenario; never point it at a running contest installation.
The screenshot suite owns a separate disposable demo installation. See
[BROWSER_TESTS.md](BROWSER_TESTS.md) for the coverage matrix and report paths.

The 2026-11-12 live QA run uses Playwright 1.65.0 with Chromium, actual Linux isolation
and real loopback HTTP. Restricted command sandboxes can still block sockets even
when the host supports Playwright: use an authorized host execution context for
these checks. A `blocked` status is not a pass. Windows/macOS execution and other
browser engines remain outside this Linux/Chromium acceptance record.

## Repository operator scripts and login exports

`bash scripts/contest.sh` provides `doctor`, `init`, `teams`, `team`, `cards`,
`run` and `backup`. Use `help`, or a subcommand’s `--help`, for arguments.
`run` uses `ARENA_ORIGIN`, `ARENA_DATA`, `PORT` and `SLOTS` and includes the worker.
Tournament schedules, top-K qualification and infrastructure retries are managed
in `/admin`; no recurring cron task is installed by the scripts.

`contest.sh teams N` creates numbered accounts and defaults both exports to
`output/pdf/team-credentials/`. `contest.sh team USER NAME --output CSV --pdf`
creates one account and a PDF in that same directory. All login PDFs use the
single layout in `scripts/login_cards.py`: ten cards per A4 page, five rows by
two columns with dashed cut lines. Print single-sided at actual size and hand
each team only its own card. Optional `python3-cairo` is the only PDF dependency.

Use `contest.sh cards CSV --pdf NEW.pdf` to reprint saved credentials without
account/database changes. Never recreate or delete accounts just to reprint.
Reset passwords through the admin panel; old cards and CSV values are then stale.
Creation/reprinting rejects existing output files and uses mode 0600. Keep the
central export directory private and backed up; Git ignores it, including legacy
files. Do not publish real credential PDFs as screenshots or fixtures.

After stopping both website and worker, `contest.sh backup --stopped --output DIR`
copies the complete data directory to a new private directory outside the source.
`--stopped` is the operator’s confirmation, not automatic process detection. A
failed copy may leave a partial backup; only a successful exit indicates completion.
Store credential exports separately, since they are not part of ARENA_DATA.
Restore the full snapshot with services stopped and point ARENA_DATA to it before
starting again. The backup tool does not erase data, restore over a live database,
or stop systemd services automatically.
