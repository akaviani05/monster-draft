# نبرد هیولاها — Monster Draft Duel

A self-hosted Persian RTL programming contest platform. Teams submit Python or
C++ bots, practice against built-in opponents, challenge other teams and compete
in scheduled round-robin tournaments with standings and replay playback.
The server and judge use Python’s standard library; the frontend has no build step
and serves bundled fonts and artwork locally.

## 1. Install and initialize

The **contest server requires Linux**, Python 3.10+, `g++` (C++17),
`libseccomp.so.2` and Landlock ABI ≥ 3 (normally kernel 6.2+). Allow sufficient CPU
for the chosen match capacity; six available cores and 8 GiB RAM are recommended
for six parallel matches. No pip or npm installation is needed to host a contest.

```bash
git clone git@github.com:akaviani05/monster-draft.git
cd monster-draft
sudo apt install python3 g++ libseccomp2

umask 077
export ARENA_DATA="$PWD/var"
export ARENA_ORIGIN="http://192.168.1.10:8000"
python3 -m arena doctor
python3 -m arena init
```

Replace the example IP with the server’s LAN address. Use the same environment
settings in every operator terminal. `doctor` must pass before accepting uploaded
programs; isolation is mandatory. `init` runs once per data directory and prompts
for an administrator password of 12–128 characters. There is no default password.
Run the application as an ordinary, dedicated user rather than root.

`ARENA_DATA` contains the database, accounts, uploaded programs, queue and replays.
Use a different private directory for a separate contest; use the existing directory
to resume one. Never seed demo accounts into a real contest.

## 2. Create teams and credentials

Create accounts through `/admin`, or use the local operator script after `init`:

```bash
mkdir -p contest
chmod 700 contest
python3 scripts/create_team.py team01 "تیم سیمرغ" \
  --output contest/team01-credentials.csv
```

Repeat for each team. Usernames must contain 3–32 ASCII letters, digits, dots,
underscores or hyphens; display names may contain Persian text (1–60 characters).
The script generates a random 24-character password, stores its hash in the database
and writes credentials to a new CSV with private permissions (0600).
Existing usernames and output files are rejected; passwords are never printed.

For a printable Persian A4 credential sheet, install the optional PDF dependencies
and add `--pdf`:

```bash
sudo apt install python3-gi python3-cairo gir1.2-pango-1.0
python3 scripts/create_team.py team02 "تیم ققنوس" \
  --output contest/team02-credentials.csv \
  --pdf contest/team02-credentials.pdf
```

CSV and PDF contain the same credentials. Deliver each team’s files privately.
`--data PATH` overrides `ARENA_DATA`. Reset forgotten passwords in `/admin`;
resets revoke existing sessions. If provisioning is interrupted, check whether the
account exists before retrying with new output paths.

## 3. Start the contest server

From the repository, with the environment above set:

```bash
bash scripts/run_contest.sh
```

This starts the website **and queue worker**, binding to **0.0.0.0:8000**.
Teams open `http://192.168.1.10:8000`; the organizer opens the same URL with
`/admin` appended. The admin form accepts only the administrator password;
teams use their usernames and passwords on the main page. `0.0.0.0` is the bind
address, not the address to enter in a browser.

| Setting | Purpose |
| --- | --- |
| `ARENA_ORIGIN` | Exact public URL, including scheme and non-default port; required by the script. |
| `ARENA_DATA` | Private state directory; defaults to repository `var/`. |
| `PORT` | Listening port; default `8000`. Keep the origin’s port consistent. |
| `SLOTS` | Initial parallel match capacity; default `6`. Saved admin settings take precedence. |

Keep the process running throughout the contest. Ctrl+C stops it; run the same
command with the same data directory to resume. Only one worker supervisor may
own a data directory. Change capacity or pause dispatch from the admin page.

For Internet hosting or unattended operation, follow
[deployment and administration](docs/OPERATIONS.md). The provided
[systemd and nginx examples](deploy/) use a loopback backend behind HTTPS;
configure the domain, certificates, secure cookies and trusted proxy there.

## 4. Run a tournament

1. Give teams their credentials, [student guide](web/guide.html),
   [guide PDF](web/downloads/student-guide-fa.pdf) and
   [starter ZIP](web/downloads/runner.zip).
2. Have every team upload and test a Python or C++ bot. New uploads become the
   selected final version; teams can select an earlier version from history.
3. In `/admin`, create a tournament, select active teams and set its start time
   in the organizer browser’s local timezone, or choose “start now”. Every
   participant must have a valid selected submission.
4. Keep the worker running. At start, it freezes selected versions and queues
   the games. Later uploads do not change those games. Monitor progress,
   standings and replays in the admin page.
5. If infrastructure fails, fix the cause and retry failed games from the admin
   page. Such failures pause that tournament’s dispatch and do not award wins.

A normal round robin plays `n × (n − 1) / 2` matches; paired mode doubles that
and swaps starting seats with the same seed. Main standings require at least
three completed games and rank by win ratio, then wins, draws, score difference
and team ID. Teams below the minimum appear separately.

The rules use 30 picks from a 50-card deck and six market slots. Judge limits are
**0.3 seconds/turn, 2 seconds/player and 256 MiB address space**. See the
[authoritative specification](monster_draft_duel_implementation_spec.md) for the
protocol and scoring, and the [Persian admin guide](docs/ADMIN_GUIDE.md) for controls.

## 5. Student practice

Students extract the starter ZIP, open `play.py` in Python IDLE and press **F5**.
The included `A.cpp` and `B.py` are the two default players; edit the filenames at
the top of `play.py` to use other local bots. Python bots need Python; C++ bots
also need `g++`. Open `viewer/index.html` and load the saved `replay.json` to watch
the match offline. The desktop runner is for trusted local files; website uploads
always use the isolated Linux judge. Windows/macOS support has not been verified
in this environment.

## 6. Back up, restart and update

Stop the web and worker processes before taking a simple backup. Copy the **entire
`ARENA_DATA` directory**, including submissions and replays, to a private backup
location. Restore all of it together with processes stopped, then restart against
that directory. Keep referenced files for completed games and frozen versions.

To update, back up first, stop the application, pull reviewed changes, run
`python3 -m arena doctor` and restart. Do not rerun `init` or delete the database.
Use a disposable installation for testing updates before a live contest.

Git ignores `var/`, local `contest/` inputs and credentials, and generated reports.
Keep private files there or outside the checkout; never force-add them. Student
downloads remain part of the repository.

| Problem | Check |
| --- | --- |
| Other machines cannot connect | Server IP, `PORT`, firewall and network reachability. |
| Requests return 403 | `ARENA_ORIGIN` must exactly match the URL used by clients. |
| Games stay queued | Worker is running, dispatch is unpaused and capacity is available. |
| Isolation doctor fails | Kernel/Landlock, libseccomp, compiler and container restrictions; do not bypass isolation. |
| Accounts seem missing after restart | The same `ARENA_DATA` directory is selected. |

## Development checks

These are development tools, separate from hosting:

```bash
python3 -m unittest discover -v
npm ci
npm test
npx playwright install chromium
npm run test:browser
```

Browser tests use disposable data; discovery alone is not execution. See
[browser testing](docs/BROWSER_TESTS.md), [security](docs/SECURITY.md) and
[validation results](docs/VALIDATION.md) for details. Guide and download changes
require rebuilding and verification as described in [project guidance](AGENTS.md).
