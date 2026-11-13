# Project guidance

@/home/alireza/.codex/RTK.md

## Scope and architecture

- This is a self-hosted Persian RTL competition platform. Keep the frontend
  buildless and lightweight; preserve locally bundled fonts and SVG assets.
- `monster_draft_duel_implementation_spec.md` is authoritative for rules and bot
  protocol. The organizer's time limits override its suggestions: 0.3 s/turn,
  2 s/player, 256 MiB address space. Do not change gameplay while editing the UI.
- `runner/` and `arena/` must use the Python standard library only. OS libraries
  for Landlock/seccomp are allowed; optional browser/PDF build tools stay separate.
- `arena/storage.py` owns SQLite schema/migrations; `service.py` owns validation,
  permissions and transactional mutations; `server.py` exposes HTTP routes.
- Queue claims, invitations and tournament version freezing must remain atomic.
  Preserve completed games and frozen source versions across restarts.

## Security and data

- Never run uploaded contestant code outside `runner/isolate.py`, disable its
  isolation, use `shell=True`, or execute source inside the HTTP process.
  `runner/local.py` and `play.py` are explicitly for students' own trusted local
  files on desktop operating systems; the website must never call that runner.
- Compiler process limits must not impose a small UID-wide RLIMIT_NPROC: it counts
  unrelated user threads. Runtime fork/clone restrictions must remain enforced.
- Every admin API checks the role on the server. Mutations also require CSRF and
  same-origin checks. Escape untrusted names/messages before rendering HTML.
- Do not read, commit or screenshot real passwords, cookies, tokens, student
  source or `var/` runtime data. Browser tests use disposable demo databases only.
- Public screenshots and fixtures must contain synthetic data. Never seed demo
  accounts into production. No publishing or deployment is implied by local edits.

## Development and verification

- Batch related edits, then run relevant checks; avoid repeated full benchmarks
  for UI or wording changes. Do not claim a test ran when the environment blocks it.
- Backend/regression tests: `python3 -m unittest discover -v`.
- Replay/UI unit tests: `npm test`; syntax-check edited JS files.
- Isolation smoke test: `python3 -m arena doctor` after runner changes.
- Browser tests: `npm run test:browser`; screenshot coverage:
  `npm run test:screenshots`. Check desktop/mobile and empty/error/success states.
  See `docs/BROWSER_TESTS.md` for the scenario matrix and focused commands.
- Actual load benchmark, only for scheduling/runner performance changes:
  `python3 scripts/benchmark.py --teams 50 --slots 6 --cpu-cores 6`.
- If TCP/browser execution or Git metadata is unavailable, record the precise
  limitation and continue independent work. Do not fabricate screenshots/commits.

## Student documentation and artifacts

- `web/guide.html` is the shared student content source. Use clear, mildly formal
  Persian suitable for ninth graders; retain examples and avoid unexplained jargon.
- Student examples use `TURNS = 30` and a fixed range loop, never stdin iteration.
  Include Python and C++, with `using namespace std` in C++. Check the first card:
  choose 0 if its species is A or strength is 5; otherwise choose randomly.
- Keep root `A.cpp`/`B.py`, `bots/starter.cpp`/`bots/random.py`, web examples and the
  downloadable bundle synchronized. Students should run `play.py` from IDLE.
- After editing it, rebuild `python3 scripts/build_guide.py`, render every PDF
  page with Poppler, inspect the result, then run `python3 scripts/package_starter.py`.
- Regenerate the starter ZIP after runner/viewer/guide asset changes. Verify its
  contents match the current source. Keep `docs/OPERATIONS.md` and
  `docs/VALIDATION.md` accurate about behavior and checks actually performed.


## Student download boundary

- `scripts/package_starter.py` must use an explicit allowlist, never directory
  globs. Ship only play.py, A.cpp/B.py, the local engine and offline viewer assets.
- Never ship practice opponents, production referee/isolation code, admin/server
  code, accounts/configuration, replay fixtures, benchmark data or runtime files.
  Keep the student guide a separate web/PDF download.
- Check the exact ZIP inventory and execute the extracted minimal package after
  packaging changes. An offline viewer must contain no server/API calls.
- `/admin` uses a separate password-only form and `/api/admin/login` authenticates
  only the configured administrator. Never hardcode an administrator password in
  source, tests, public documentation or generated downloads.

## Playwright regression suite

- Use `tests/browser/support/fixtures.cjs`, not the base Playwright `test`, for
  regression specs. Each test owns a fresh server on an ephemeral loopback port,
  a worker and a disposable SQLite directory. Never target an existing server.
  The separately configured screenshot suite owns its own demo installation.
- The fixture driver requires an `arena-pw-` directory, marker and matching random
  token before touching data. Keep fixture mutations in the test driver; never add
  a test-only HTTP endpoint or import the driver into production code.
- Fixture credentials are synthetic and confined to temporary data. Never replace
  them with production credentials. Keep traces, screenshots, reports and runtime
  databases out of Git. Mask password inputs in review screenshots.
- Use UI interactions for user journeys and real authenticated HTTP requests for
  permission/validation checks. Successful workflows must use the real queue,
  sandbox, judge and replay. Route interception is only for explicit transport
  failure tests. History/quota fixtures are setup, not evidence of judge throughput.
- Keep acceptance assertions observable: exact frozen versions, counts, results,
  ownership and persisted state. Await responses and locator assertions, poll
  real worker state, and use Playwright's clock only for client playback timers.
  Do not advance browser time to pretend the Python worker's schedule advanced.
- Keep retries disabled, prohibit focused tests in CI, avoid fixed sleeps and
  shared ordering dependencies. One worker is the default because judge time
  budgets require available CPU. Run `npm run test:browser:repeat` to check repeat
  isolation after changes to fixtures or concurrency.
- Before finishing, run Python tests, JavaScript tests, syntax checks, Playwright
  discovery and the applicable browser scenarios in batches. Run `arena doctor`
  before executing uploaded fixture programs; never weaken isolation to pass QA.
- `npm run test:browser` exits nonzero and records `blocked` if local HTTP is
  forbidden. Discovery is not execution. Report blocked checks explicitly; do not
  claim browser passes, visual approval or exhaustive correctness from discovery.
