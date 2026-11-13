# نبرد هیولاها — Monster Draft Duel

A self-hosted Persian RTL bot competition: Python/C++ submissions, practice,
step-by-step debugging, round-robin tournaments, standings and replays.
The server and judge use Python’s standard library. The frontend is buildless,
with bundled fonts and artwork; no pip or npm install is needed for hosting.

## Prepare the server

Use Linux, Python 3.10+, C++17 `g++`, libseccomp and Landlock ABI ≥ 3
(normally kernel 6.2+). For six concurrent games, allow six available CPU cores
and about 8 GiB RAM. Run as an ordinary dedicated user, not root.

```bash
git clone git@github.com:akaviani05/monster-draft.git
cd monster-draft
sudo apt install python3 g++ libseccomp2 python3-cairo
umask 077
export ARENA_DATA="$PWD/var"
export ARENA_ORIGIN="http://192.168.1.10:8000"
bash scripts/contest.sh doctor
bash scripts/contest.sh init
```

Replace the IP with the server’s LAN address. Keep these environment settings
in each operator terminal. `doctor` must pass; never bypass isolation. `init`
runs once per data directory and prompts for a 12–128 character administrator
password. There is no default administrator password or production demo account.

## Create teams and print login cards

```bash
bash scripts/contest.sh teams 50
```

Creates `team_01` through `team_50`, each with a random six-digit numeric password,
and two private files in the central, Git-ignored directory:

- `output/pdf/team-credentials/team-credentials.csv`: complete organizer roster.
- `output/pdf/team-credentials/team-login-cards.pdf`: **5 rows × 2 columns per A4
  page**, dashed cut lines, one team per card; unused cells stay blank.

Print **single-sided at 100% / actual size**, cut and distribute each team’s own
card. Keep the complete files private. Both files have mode 0600 and are never
overwritten. Creation is atomic: duplicates or export failure add no accounts.
Count may be 1–1000. This local batch tool’s six-digit policy does not change
browser account-creation password requirements.

Reprint saved credentials **without creating accounts or changing passwords**:

```bash
bash scripts/contest.sh cards output/pdf/team-credentials/team-credentials.csv \
  --pdf output/pdf/team-credentials/reprint.pdf
```

For a named team with a random 24-character password and the same card layout:

```bash
bash scripts/contest.sh team team51 "تیم سیمرغ" \
  --output output/pdf/team-credentials/team51-credentials.csv --pdf
```

Explicit `--csv`, `--output`, `--pdf` and `--data` paths are supported by the
underlying tools; see `--help`. Reset lost passwords in `/admin`; old CSVs/cards
then become obsolete and must not be redistributed.

## Launch and run the event

```bash
bash scripts/contest.sh run
```

This runs the web server **and worker** on **0.0.0.0:8000**. Teams open
`http://192.168.1.10:8000`; organizers use `/admin` at that URL. Team login uses
username/password; the separate admin form uses only the administrator password.
`0.0.0.0` is a bind address, not a browser destination.

| Environment | Purpose |
| --- | --- |
| `ARENA_ORIGIN` | Exact browser URL, including scheme and non-default port; required. |
| `ARENA_DATA` | Private database, accounts, sources, queue and replays; default `var/`. |
| `PORT` | Listening port, default `8000`; keep the origin consistent. |
| `SLOTS` | Initial concurrency, default `6`; saved admin settings take precedence. |

The event sequence is: introduce the challenge → distribute guide and login cards
→ fill team profiles → download and submit `B.py` → explain the protocol → practice
with the submission debugger → run regular tournaments → advance teams through
completed qualifying stages to the final. Start ten-minute practice tournaments
only after the first runs are stable, and avoid building a queue backlog.

Follow the **[contest-day runbook](docs/CONTEST_RUNBOOK.md)** for the complete
checklist, timing, qualification, error recovery and closeout. The
**[November 12, 2026 experience](docs/CONTEST_EXPERIENCE_2026-11-12.md)** records
the organizer’s process and lessons. The [Persian admin guide](docs/ADMIN_GUIDE.md)
describes the panel controls.

Tournament start freezes each selected final submission; later uploads do not
change queued games. Standings require three completed games for a ranked team.
Normal round robin plays `n*(n-1)/2` games; the admin form supports 1–100 games per
pair. Judge limits are **0.3 s/turn, 2 s/player, 256 MiB address space**. See the
[authoritative rules and protocol](monster_draft_duel_implementation_spec.md).

## Student materials

Distribute the [web guide](web/guide.html), [PDF guide](web/downloads/student-guide-fa.pdf)
and [starter ZIP](web/downloads/runner.zip). Students extract the ZIP, open
`play.py` in Python IDLE and press **F5**; `A.cpp` and `B.py` are included. Python
bots need Python; C++ bots also need `g++`. The offline viewer opens at
`viewer/index.html`. The desktop runner is for trusted local programs; website
uploads always use the Linux sandbox. Windows/macOS support has not been verified
in this environment.

## Stop, back up and resume

Ctrl+C gracefully stops the combined process. For a new contest, choose a new
`ARENA_DATA`; to resume, keep the existing directory and rerun `run`, without `init`.
Only one worker supervisor may own a data directory.

With **both website and worker stopped**, create an offline backup:

```bash
mkdir -p contest
chmod 700 contest
bash scripts/contest.sh backup --stopped --output contest/backup-after-final
```

The destination must be new and outside `ARENA_DATA`. It copies the entire data
directory, including SQLite sidecars, submissions and replays. Back up the private
credential-export directory separately too. Restore a complete snapshot to a
private directory with services stopped, set `ARENA_DATA` to it and run again.
Before updating: back up, stop, pull reviewed code, run `doctor`, then restart.

For unattended or Internet hosting, use the [systemd/nginx examples](deploy/)
and [operations guide](docs/OPERATIONS.md) for HTTPS, secure cookies and a loopback
backend. For connection errors check IP/firewall/port; for 403 check the exact
origin; for queued games check worker health and paused dispatch. Never delete
contest data to fix a restart or bypass a failed isolation check.

## Project map and development

See [project structure](docs/PROJECT_STRUCTURE.md) for ownership, operator commands
and the boundary between reusable source and private contest data.

```bash
python3 -m unittest discover -v
npm ci
npm test
npx playwright install chromium
npm run test:browser
```

These are development-only checks; browser tests use disposable installations.
See [browser QA](docs/BROWSER_TESTS.md), [validation](docs/VALIDATION.md),
[security](docs/SECURITY.md) and [artifact rebuild guidance](AGENTS.md).
