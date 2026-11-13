# Project structure and ownership

## Reusable source

| Path | Responsibility |
| --- | --- |
| `arena/storage.py` | SQLite schema, migrations and persistence helpers. |
| `arena/service.py` | Validation, permissions and transactional mutations. |
| `arena/server.py` | HTTP routes, origin/CSRF protection and static serving. |
| `arena/worker.py`, `scheduling.py` | Durable queue, frozen versions and tournaments. |
| `runner/` | Standard-library game engine and isolated website judge; Linux isolation is mandatory. |
| `runner/local.py`, `play.py` | Desktop practice for students’ trusted local files only. |
| `A.cpp`, `B.py`, `bots/starter.cpp`, `bots/random.py` | Synchronized student examples. Other `bots/` files are website practice opponents. |
| `web/` | Buildless Persian RTL interface, bundled assets and shared student guide HTML. |
| `web/downloads/` | Distributed starter ZIP and student guide PDF; no accounts or server data. |
| `deploy/` | Example systemd units and nginx HTTPS configuration. |
| `tests/` | Unit/regression tests and disposable Playwright installations. |
| `docs/` | Operator runbook, dated experience, hosting, security and validation. |

The authoritative game/protocol specification is at the repository root; organizer
limits override its suggested budgets. No gameplay changes are part of operator
tooling. `arena/` and `runner/` retain standard-library-only runtime dependencies.

## Operator scripts

Use `bash scripts/contest.sh help` as the entry point. It dispatches to the
following scripts; it does not add another server, scheduler or worker.

| Command | Implementation / purpose |
| --- | --- |
| `doctor`, `init` | Existing `python3 -m arena` commands; isolation check and one-time admin initialization. |
| `run` | `run_contest.sh`: web plus worker on 0.0.0.0, configured through environment variables. |
| `teams N` | `create_teams.py`: atomic numbered accounts, six-digit passwords, CSV and cut-card PDF. |
| `team USER NAME --output CSV [--pdf [PDF]]` | `create_team.py`: one named account, random 24-character password, optional cut-card PDF. |
| `cards CSV [--pdf PDF]` | `export_login_cards.py`: reprint without database access or password changes. |
| `backup --stopped --output DIR` | `backup_contest.py`: complete offline data copy to a new private directory. |

**`scripts/login_cards.py` owns the only login-card PDF layout.** Both creation
scripts and CSV reprinting use it. PDFs need optional `python3-cairo`; this does
not add a dependency to the server or judge. New files are private and existing
files are never overwritten. Named-team CSV accepts `--output`; batch uses `--csv`.

Other scripts build the student guide/download bundle, run browser QA, or measure
performance. They are development tools, not prerequisites for running an event.

## Private data and generated artifacts

- `var/` (or absolute `ARENA_DATA`): accounts, hashes, sessions, submissions,
  binaries, queue and replays. Ignored, except an empty `.gitkeep`.
- `output/pdf/team-credentials/`: central credential CSVs and printable login PDFs.
  Ignored; keep private and back up separately. Existing legacy files stay in place.
- `contest/`: other local organizer inputs and offline backups. Ignored.
- `output/`: generated QA/PDF previews/reports. Ignored except the distributed
  student-guide PDF. `node_modules/` and browser results are development-only.

Do not move private state into reusable source, force-add ignored credentials,
or delete old submissions referenced by games. The student ZIP uses an explicit
allowlist and excludes production judge/server code, practice opponents, private
data and the separately distributed guide. See [project guidance](../AGENTS.md).

## Documentation map

Start at [README](../README.md) for commands, use [the runbook](CONTEST_RUNBOOK.md)
on contest day, [operations](OPERATIONS.md) for hosting/recovery and
[the November 12 experience](CONTEST_EXPERIENCE_2026-11-12.md) for organizer lessons.
The Persian [student guide](../web/guide.html) remains the shared source for the
student PDF; keep technical operator instructions out of student-facing flows.
