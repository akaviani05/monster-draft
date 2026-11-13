# نبرد هیولاها — Monster Draft Duel

A complete self-hosted Persian competition platform: team accounts, immutable
Python/C++ submissions, rate-limited bot practice, accepted/rejected invitations,
a durable parallel queue, scheduled round robins, standings, exact replays and a
student guide. The website and referees use **Python's standard library only**;
the frontend is plain HTML/CSS/JS with locally bundled Vazirmatn and SVG artwork.

## Install and run a contest

Clone the reusable platform (contest databases and credentials are excluded):

```bash
git clone git@github.com:akaviani05/monster-draft.git
cd monster-draft
sudo apt install python3 g++ libseccomp2
python3 -m arena doctor
python3 -m arena init
```

Use Python 3.10+ on Linux with Landlock ABI ≥ 3 (normally kernel 6.2+) and
libseccomp. There is no pip install or frontend build. `doctor` verifies isolation
and Python/C++ execution; do not host submissions if it fails. `init` prompts for
a new administrator password of 12–128 characters. There is no default password.

Start the web server and worker on **0.0.0.0**:

```bash
ARENA_ORIGIN=http://192.168.1.10:8000 bash scripts/run_contest.sh
```

Replace the example IP with your server's LAN address. Students open that URL;
`0.0.0.0` is a bind address, not a browser destination. The exact origin is required
for request validation. `PORT=8000` and `SLOTS=6` are defaults; saved worker
capacity settings take precedence. Ctrl+C stops the server and worker.
For Internet hosting use HTTPS and the separate systemd/nginx examples in
[OPERATIONS.md](docs/OPERATIONS.md), with the backend bound to loopback.

The default database, submissions, replays and queue live in ignored `var/`.
To run a separate contest, set `ARENA_DATA` to a private directory consistently
for **init, team creation and server launch**. Restart using the same directory
to preserve accounts, completed matches and frozen submissions. Back up the entire
data directory with web and worker stopped; restore it together, never just the
SQLite file. Do not delete data to restart the service.

## Create teams and distribute passwords

Use the admin page, or run the local operator script on the host after `init`:

```bash
mkdir -p contest
chmod 700 contest
python3 scripts/create_team.py team01 "تیم سیمرغ" --output contest/team01-credentials.csv
python3 scripts/create_team.py team02 "تیم ققنوس" --output contest/team02-credentials.csv
```

Each invocation creates one team with a random 24-character password and writes
it to a new CSV with mode 0600. Existing usernames and output files are rejected;
passwords are never printed. The script uses server-side team validation and the
normal password hashing. It is a trusted local operator tool, requiring filesystem
access to the database. `--data /private/contest-data` overrides `ARENA_DATA`.
Keep output files in ignored `contest/`; distribute each file only to its team.
A machine interruption can leave a credential file without a created account;
check the admin page before retrying with a new output path. Reset passwords
through the admin page when needed; resets revoke existing sessions.

## Organizer workflow

1. Sign in at `/admin` with the administrator password; teams sign in at `/`.
2. Create teams and share their individual credentials and the student guide.
3. Ask every team to upload and test a Python or C++ submission. New uploads
   become the selected final version; earlier versions remain available.
4. Create a tournament in the admin page, select participating teams and schedule
   it or start immediately. Every participating team needs a valid submission.
5. Keep one worker supervisor running. Tournament start freezes source versions;
   later uploads do not change queued games. Monitor queue, results and standings.
6. For infrastructure errors, fix the cause before retrying from the admin page.
   After the contest, stop both processes and back up the private data directory.

Local contest inputs belong in ignored `contest/`; generated QA reports belong
in ignored `output/`. The reusable student PDF and starter ZIP remain distributed
with the project. No existing contest state is seeded into a fresh installation.

## Browser administration

Open **http://127.0.0.1:8000/admin** and enter the administrator password (set during `arena init`). The admin entry has
a dedicated password-only form; team credentials cannot open an admin session. The separate
admin navigation provides overview, searchable teams, tournaments, match queue
and live worker settings. Create/edit teams, reset passwords, schedule/start
competitions, inspect standings/replays, retry infrastructure failures, pause
new dispatches and change parallel capacity without editing configuration files.
See the [Persian admin guide](docs/ADMIN_GUIDE.md).

## Student desktop practice (no terminal or Linux needed)

Download the [student starter ZIP](web/downloads/runner.zip), extract it, open
`play.py` in Python IDLE and press **F5**. Its first lines are:

```python
BOT1 = "A.cpp"
BOT2 = "B.py"
OUT = "replay.json"
```

Both included examples check the first card: choose slot 0 if its species is A
or strength is 5; otherwise choose randomly. They use exactly `TURNS = 30` turns.
The C++ example uses `using namespace std`. Two Python files need Python only;
C++ also needs g++ installed. `play.py` saves the result beside itself, even when
opened from a different working directory. Open `viewer/index.html` from the
bundle to see the replay offline. Windows/macOS support is implemented but has
not been tested in this environment.

The desktop runner executes students' own trusted local programs with response
time limits; it does not provide the website judge's Linux isolation or memory/
CPU accounting. Uploaded website programs always use the isolated judge.

## Advanced isolated match runner

```bash
python3 -m runner bots/random.py bots/planner.py --seed 42 -o replay.json
python3 -m runner bots/starter.cpp bots/guardian.py --seed 7 -o replay.json
python3 -m runner bots/champion.cpp bots/guardian.py --seed 42 -o replay.json
```

Open `/visualizer`, select the log, and use play/pause, speed, next/previous or the
timeline. The [student bundle](web/downloads/runner.zip) contains only two minimal starter
examples, the trusted local launcher/engine and an offline HTML viewer. It
contains no practice opponents, production judge, admin/server code, match
fixtures, databases or PDF. The Persian PDF is a separate website download. JSON uploads stay in the browser.
«بازی با دو کد» sends two local files to the authenticated server queue and leaves
the team's active competition submission unchanged.

The practice list includes **اژدها** (`champion`), a C++17 search opponent. It
tracks both public hands, samples the remaining deck without replacement, adapts
to observed opponent choices and calculates the final three picks exactly under
its opponent model. Earlier in the draft it compares 2,304 sampled continuations
per distinct market card. It sees only the published protocol, without the
shuffle seed or future cards. Wins on every possible shuffle are not guaranteed.

To measure it against the built-in opponents with paired seats:

```bash
python3 scripts/evaluate_bot.py --seeds 20 --seed-start 1000
# Include a read-only snapshot of every team's selected official submission:
python3 scripts/evaluate_bot.py --data /path/to/arena-data --seeds 20 --seed-start 1000
# Reproduce an immutable version from a previous report, after a newer upload:
python3 scripts/evaluate_bot.py --data /path/to/arena-data --submission 123 --opponent submission-123
```

This uses the production sandbox and normal time/memory limits, writes results
under `output/`, and creates no official games. Optional database access reads
selected IDs, languages and executable paths, without reading source or account
credentials. Reports record frozen submission IDs, outcomes and timings;
loss replays use anonymous evaluation labels.

- [Persian student guide (web)](web/guide.html)
- [Persian student guide (PDF)](output/pdf/student-guide-fa.pdf)
- [Deployment, backups and administration](docs/OPERATIONS.md)
- [Isolation, limits and threat model](docs/SECURITY.md)
- [Validation and measured performance](docs/VALIDATION.md)
- [Original normative rules](monster_draft_duel_implementation_spec.md)

## Rules and tournament policy

The supplied v1.0 specification governs the 50-card deck, six stable market slots,
snake order `P0,P1,P1,P0`, 30 picks, scoring, strict majority banners, tiebreaks and
EOF protocol. **The requested limits override the proposal: 0.3 seconds/turn and
2 seconds/player**, with 256 MiB address space. Responses must be exactly one
ASCII digit `0..5` followed by LF (CRLF also accepted), only on `YOURTURN`.

Each friendly is **one match** with random seats. A bot request uses the team's
selected final submission at request time; an invitation freezes the sender's
version when sent and the recipient's when accepted. Pending invitations expire
after 24 hours. New uploads become the final selection automatically; teams can select any earlier
version from paginated history. Games already queued keep their frozen versions.

Admin tournaments start automatically at their scheduled instant while the worker
runs, or can be started immediately. Every selected team needs a valid submission.
The worker freezes the latest versions at start, creates exactly `n*(n-1)/2`
games, and uses circle rounds with balanced starting seats. Round barriers keep
completed game counts within **one for even n**, including 50, and at most two
with odd-field byes. Optional paired mode doubles the games and reuses each pair's
seed while swapping seats. Rankings require at least **three completed games** in the selected competition
and sort by **win ratio** (wins / all completed games, including draws), then
wins, draws, score difference and stable team ID. Teams below three games appear
in a separate lower table. Infrastructure failures pause dispatch for that tournament
and never award a win; the admin can retry failed games after fixing the cause.

The queue starts with six simultaneous matches. Change capacity or pause dispatch
in the admin execution-settings page. `--slots N` sets the initial capacity for
a new data directory; saved admin settings take precedence on later starts.
Every third dispatch prefers a waiting friendly so tournaments do not monopolize
the queue. Restarting a supervisor recovers uncommitted running jobs. Only one
supervisor may own a database; all state survives website restarts.

## Tests and benchmarks

```bash
python3 -m unittest discover -v
npm test
python3 scripts/benchmark.py --teams 50 --slots 6 --cpu-cores 6
```

Optional browser tests require development-only Playwright dependencies:

```bash
npm ci
npx playwright install chromium
npm run test:browser:list
npm run test:browser
npm run test:screenshots
```

The browser suite creates a separate temporary database/server/worker
for each test. It covers authentication and permissions, uploads and final-code
history, quotas, practice, invitation races, replay analysis/downloads, local-code
games, admin controls, scheduled tournaments, persistence and responsive layouts.
Run `npm run test:browser:repeat` to check isolation on repeated executions.
It does not touch production. See the [scenario matrix and run guide](docs/BROWSER_TESTS.md).
See [screenshot coverage and execution limits](docs/SCREENSHOTS.md).
No npm package is needed to run the actual website or referee.

Rebuild distributed artifacts after editing rules or assets:

```bash
# PDF only: apt install python3-gi python3-cairo gir1.2-pango-1.0 gir1.2-rsvg-2.0
python3 scripts/build_guide.py
python3 scripts/package_starter.py
```

The PDF renderer reads the same student HTML and uses Pango/Cairo for correct
Persian shaping. Its build-time OS libraries are independent of the referee.
