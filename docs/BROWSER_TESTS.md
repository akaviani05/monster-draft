# Browser regression tests

The suite contains 233 independent Playwright scenarios across 14 spec files.
It covers the site's supported workflows and significant boundary/error states.
No finite suite proves that every possible input or interleaving is correct.

## Installation and execution

Use Node.js 20+ and the dedicated Linux judge prerequisites documented in
[OPERATIONS.md](OPERATIONS.md). The website itself still needs no npm packages.

```bash
npm ci
npx playwright install chromium
python3 -m arena doctor
npm run test:browser:list
npm run test:browser
```

If the browser installer reports missing operating-system libraries, install
those prerequisites using your host's normal package-management process. When
the default browser cache is read-only, set `PLAYWRIGHT_BROWSERS_PATH` to a writable
directory for both the install and test commands. A browser matching the locked
Playwright version is required; an older Chromium cache is insufficient.

Focused runs and repeatability checks:

```bash
npm run test:browser -- tests/browser/auth.spec.cjs
npm run test:browser -- --grep 'invitation'
npm run test:browser -- --headed
npm run test:browser:repeat
npm run test:screenshots
```

The HTML report is `output/browser-report/index.html`, machine-readable results
are `output/browser-report/results.json`, and failure attachments/traces are
under `output/browser-results/`. Open traces with `npx playwright show-trace`.
Reports may contain synthetic fixture credentials/source: treat them as local QA
artifacts and keep them out of Git. The screenshot suite separately generates its
gallery in `output/screenshots/`; see [SCREENSHOTS.md](SCREENSHOTS.md).

The wrapper records `run-status.json` and exits nonzero if loopback serving is
blocked. A blocked run is not a pass. If an older HTML report exists, use the
latest run status and timestamp before interpreting it. `--list` checks test
discovery only; it does not launch Chromium or verify UI behavior.

## Isolation and deterministic setup

Every regression test uses `support/fixtures.cjs` to create its own random
`arena-pw-*` directory in the OS temporary folder. The Python driver requires a
matching random-token marker before accessing it, binds port zero on loopback,
and starts the production HTTP server and worker. There are no production fixture
routes. The fixture overrides production origin/proxy/cookie settings for its
local server; it never reads the operator's runtime database or credentials.
Cleanup stops the worker, closes clients and deletes temporary state even after
failure. A restart test retains its own directory and port to verify real session
and setting persistence.

Each installation has a synthetic administrator, three teams with the public
starter code, and one team without code. UI helpers sign in using the displayed
forms; API helpers maintain separate cookie stores and CSRF tokens. Two-account
flows use separate browser contexts. Destructive tests cannot affect another
test. One worker and zero retries make failures visible without competing for the
judge's strict CPU budgets. Increase parallelism only on a host with dedicated
capacity. The global setup runs `arena doctor` and fails if isolation is unavailable.

Only quota, pagination, expired-state and infrastructure-failure setup uses direct
fixture mutations. Generated completed history contains valid replay logs from
the rules engine, but is not claimed as executed judge work. Bot games, local
matches, invitation acceptance and tournament execution use the actual isolated
judge. Transport-failure cases explicitly abort a request; successful flows do
not mock API results. Browser clock control is limited to playback timers.

## Scenario matrix

| Spec | Coverage |
| --- | --- |
| `auth.spec.cjs` | Team login/reload/logout, password-only administration, student session at `/admin`, invalid credentials, custom admin username, disabled users, expired sessions, password reset/revocation, throttling, required fields |
| `security.spec.cjs` | Anonymous and team/admin boundaries on GET/POST, missing/forged CSRF, hostile Origin and Fetch Metadata, source/final/replay ownership, private-data exclusion, CSP/security headers, private-file/traversal requests |
| `submissions.spec.cjs` | Empty history, Python/C++ uploads, compilation/syntax failures, automatic final selection, restore/reload, pagination, exact download, file size/extension, malformed Unicode/types/languages, storage/minute/daily quotas |
| `friendlies.spec.cjs` | All five practice opponents, exact-game replay links, champion card/artwork/queue selection at 390/1440 px, missing code, malformed requests, quota boundaries, frozen invitation versions, accept/reject/cancel via API and two UI accounts, duplicate/self/expired/outsider invitations, concurrent acceptance, local C++/Python pair without changing the final code |
| `debug.spec.cjs` | Current Python/C++ editor runs through the real sandbox, local file picker and editor/language synchronization, file-size/type errors, per-turn stdin/stdout and startup banner, replay integration, syntax/compiler/runtime errors, escaped tracebacks, owner-only diagnostics, preserved final code/editor, CSRF/role/input checks, queue waiting/resume, transport retry, invalid output and input deadlock hints, desktop/mobile review captures |
| `profiles-scoreboard.spec.cjs` | Two student names, persistence and escaping, admin name search, waiting for recipient approval before queueing a real team game, frozen versions, friendly scoreboard, per-tournament selector, CSRF/role/authentication checks, invalid tournament input, profile transport failure/retry, desktop/mobile review captures |
| `http.spec.cjs` | Normal reload and content-versioned JS/CSS cache headers, malformed/non-object/empty/oversized bodies, content type, invalid filters/pages, nonexistent resources, HEAD, forged cookies, pagination bounds, external redirect rejection |
| `judge.spec.cjs` | Invalid choices/output, infinite loop termination, blocked shell attempt, committed technical losses, no infrastructure retry for a loss, continued server health and usable replay |
| `admin.spec.cjs` | Account creation/search/rename/disable/enable/password reset, duplicates and invalid usernames, whitespace passwords, literal HTML names, team filters, capacity/pause persistence across restart, invalid settings, pause/resume, infrastructure retry, queue filters and pagination |
| `tournaments.spec.cjs` | UI creation/estimate/start/standings, automatic scheduled start, every pair in single/paired mode, balanced seats, same seed with swapped seats, frozen selected versions, cancellation, invalid participants/settings, disabled or code-less team at start, infrastructure failure/retry, shared results and final-state conflicts |
| `replay.spec.cjs` | Empty/public/logged-in states, exact market replacement/hands/scores, manual steps and bounds, timed playback/pause/speed/restart, keyboard/timeline, download preserving decimal seeds, corrupt log fields/JSON/size, escaped names, private deep-link login return, queued/completed/failed/forbidden views, local-file errors |
| `navigation.spec.cjs` | Every team/admin page at 390/768/1440 px, RTL and horizontal layout, mobile menu, modal Escape, direct admin hash denial, request failure/retry, preserved upload text, match paging/refresh/empty events |
| `downloads.spec.cjs` | Exact 19-file student ZIP, public example bytes, extracted file:// viewer under offline context, manual stepping with zero HTTP requests, no bot/admin/server payload, bundled Persian font, PDF signature, guide fragments/assets |
| `edge-cases.spec.cjs` | Uppercase Python/C++ uploads and local games, immediate file selection after navigation, returning to newest history after upload, clearing pagination across team logins, consecutive keyboard replay steps, skip-link focus without route changes, malformed card types preserving a loaded replay, invalid Unicode in login/admin/nested code fields, non-ASCII forged CSRF, oversized database IDs |

The existing unit/integration suites complement browser coverage with exhaustive
round-robin sizes 2–51, scoring and tiebreak fixtures, CPU/memory/output limits,
isolation/parent-death checks, migration and queue-claim races. Run them together:

```bash
python3 -m unittest discover -v
npm test
```

## Current verification record (2026-11-12)

- Playwright 1.65.0 with Chromium discovers all 207 scenarios successfully.
- Final `npm run test:browser:repeat`: **414 passed in 9.7 minutes**. Every one of
  the 207 scenarios passed twice in fresh disposable installations, with one
  worker, zero retries, zero failures, zero skipped cases and zero flaky results.
  The JSON report and `run-status.json` agree; the run status is `completed`.
- The first live 190-scenario run found three failures; additional edge cases
  reproduced upload, pagination, keyboard, replay validation and API-input bugs.
  The fixes pass all 82 targeted browser regressions in 2.1 minutes.
- 103 Python tests pass in 44.738 seconds, including live HTTP, actual judging,
  isolation, fixture safety, source privacy and the added API regressions.
- A full repeat run caught a further navigation race after 411 passing executions:
  initial page refresh could erase a just-selected file. Pages now render once
  their data is ready and ignore stale responses, including after logout. Both
  C++ upload and immediate-navigation tests pass ten repetitions each (20 passes,
  56.8 seconds). Four deterministic JavaScript tests cover late-response ordering.
- `npm test` passes; all 31 individual JavaScript tests also pass with
  `--test-isolation=none`. All 28 JavaScript files pass syntax checks. `arena doctor`
  passes; its global setup check also runs before every live browser batch.
- The screenshot suite passes in 42.8 seconds after the navigation fix and saves
  all 50 planned images.
  The gallery was reviewed, including detailed mobile dashboard/replay/settings
  checks. The rebuilt 19-file ZIP matches source bytes and its extracted
  C++/Python match and offline viewer pass.
- The restricted command sandbox still returns loopback `EPERM`. The successful
  live checks use approved host execution and disposable data, with actual server,
  worker, sandbox and judge. Earlier blocked attempts are superseded by these runs.
  Other browser engines and Windows/macOS remain unverified. No new performance
  benchmark is claimed for these fixes.
