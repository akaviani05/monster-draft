# Validation record

## Readable administrator ZIP names (2026-11-12)

Admin exports now use the team's current name plus its stable ID for folders,
and the original source filename plus submission ID for files. Persian names
use ZIP UTF-8 metadata; path/control characters are sanitized and component
lengths bounded. IDs prevent duplicate team names or source names from colliding.
The manifest retains the original team and filename metadata. Source selection
remains tied to each submission's stored ownership and language; C++ archives
contain source.cpp contents, not compiled executables.

Python suite: 133 passed. An additional focused rerun with distinct synthetic
Python sources and a Persian source filename passed. Tests extract both archive
scopes and compare exact bytes to each submission, covering duplicate Persian
names, renamed teams, hostile names, C++ source, older selected finals and history.
JavaScript suite, syntax checks, Playwright discovery and isolation doctor passed.
The browser download scenario was blocked by loopback HTTP EPERM; no browser
execution or screenshot approval is claimed.

## Top-10 percentage and top-K selection (2026-11-12)

Tournament standings append win percentage against ranks 1–10, using completed
games only and counting draws in the denominator. It does not change ranking.
No qualifying games shows a dash. The numerical regression covers 12 teams,
exclusion of ranks 11–12, wins, draws and no ranked opponents.
Tournament creation can replace its checked teams with ranks 1–K from a completed
event. Selection validates K, rank availability and active/code-ready membership,
then shows the teams for review; ordinary server validation remains authoritative.
Submission waits for an in-flight top-K selection to finish.

Python suite: 132 passed. JavaScript suite, edited JavaScript syntax, Playwright
discovery and isolation doctor passed. A browser journey covers selecting the
exact top two and checking persisted new-event membership and the new column.
Browser execution was blocked by loopback HTTP EPERM; no browser pass or visual
approval is claimed.

## Tournament list total correction (2026-11-12)

Tournament cards and progress maxima use team-pair count multiplied by the saved
games-per-pair setting, even when the current queued job count is smaller. A
JavaScript rendering regression checks 4 teams with 4 games per pair display 24
games and progress max 24 despite a job count of 6. Browser creation coverage now
includes 1, 4 and 6 games per pair, checking card totals before starting.
Python: 131 passed. JavaScript suite, edited JavaScript syntax, Playwright
discovery and isolation doctor passed. Browser execution was blocked by loopback
HTTP EPERM; no browser pass or visual approval is claimed.

## Configurable tournament games per pair (2026-11-12)

Tournament creation accepts `games_per_pair` from 1 to 100, defaulting to 1.
The form updates its game estimate immediately and tournament cards display the
saved count. Consecutive legs swap seats and share a seed; each next two-leg set
gets a fresh seed. Odd counts add a single leg with balanced starting seats.
The migration maps legacy single/paired tournaments to 1/2 and leaves saved jobs,
seeds and frozen versions intact. Legacy `paired` API requests remain supported.

The full Python suite passed 130 tests. After adding a six-game worker regression,
both single-game and six-game real-worker checks passed (2 tests): the latter
completed 18 games and recorded 12 games per team in standings. Scheduling tests
cover 3/6 legs, seat swaps, seeds, validation, restart persistence and migration.
JavaScript suite: 3 passed; edited JavaScript syntax, Playwright discovery and
isolation doctor passed. Tournament browser scenarios were blocked by loopback
HTTP EPERM; no browser execution or visual UI approval is claimed.

The required 50-team, 6-slot, 6-core benchmark completed 1,225/1,225 games with
normal results in 31.999 seconds (38.283 games/second, observed game-count gap 1).
This measured the default single-game schedule, not a 7,350-game six-leg event.
The guide was rebuilt, all 16 PDF pages rendered and visually inspected, and the
19-file allowlisted starter ZIP regenerated. Package regression tests verified
the archive inventory and ran the extracted package.

## Administrator submission ZIP downloads (2026-11-12)

The team-management page offers all official submissions or only selected final
submissions. Archives include inactive teams, exclude local/debug code, and use
numeric team/submission paths plus a JSON manifest. Final selection is read from
one query, including older selected versions. ZIPs use temporary files and stream
to authenticated administrators with no-store headers; no public file is created.
Regression tests verify exact source bytes, membership, safe unique paths, empty
final selections, role/origin enforcement and download headers. The Python suite
passed 127 tests; JavaScript suite passed 3. Edited JavaScript syntax, Playwright
discovery and isolation doctor passed. The browser download journey was blocked
by loopback HTTP EPERM; no browser execution or visual approval is claimed.

## Minute-only game limits (2026-11-12)

Games now allow 10 requests per rolling minute, with no daily or pending-game
cap. Invitations allow 10 per rolling minute instead of per hour. This supersedes
the daily quota descriptions in earlier records below. Upload limits are unchanged.
The Python suite passed all 117 tests, including old game/invitation history,
minute limits and invitation acceptance quota checks. JavaScript suite: 3 passed;
edited JavaScript syntax and Playwright discovery passed. Isolation doctor passed.
Browser friendlies/debug execution was blocked by loopback HTTP EPERM; no browser
tests ran. Rebuilt the guide, rendered and visually inspected all 16 PDF pages,
and regenerated the 19-file allowlisted starter ZIP. Package regression tests
verified the inventory and executed the extracted package.

Updated on 2026-11-12; benchmark measurements below were recorded on 2026-11-11. Results are measured in this task environment; they are
not a promise about production hardware or arbitrary submitted algorithms.

## Friendly approval and counts-only reset (2026-11-12)

Team friendlies now require recipient acceptance. The normal invitation route
and legacy `/api/friendlies` route both create pending invitations with no job.
The UI shows «در انتظار تأیید تیم مقابل» to the sender, with no immediate-start
button. The recipient alone can accept; that transaction creates one job and
freezes the sender's invitation-time version and recipient's acceptance-time
version. Existing acceptance and quota concurrency guarantees are retained.

The requested operational reset changed only the friendly-statistics cutoff in
the configured database. No match, invitation, account, submission or tournament
record was deleted. Aggregate checks confirmed retained table counts and zero
friendly statistics immediately after the reset. A subsequent read found no
unapproved friendlies queued/running. Daily game quota accounting is retained.
The new cutoff applies to friendly standings and the friendly part of personal
stats, persists across restarts, and allows later accepted games to count normally.
Reset regression tests verify unchanged frozen jobs, invitations and tournament
results, permission enforcement, persistence and counting of later matches.

**116 Python tests passed in 25.234 s**. JavaScript tests, edited syntax checks
and `arena doctor` passed. Playwright discovers **230 scenarios in 14 specs**.
Approval/invitation/scoreboard checks passed twice: **34 executions in 37.1 s**.
The final waiting-message and PDF-download batch passed **2 tests in 3.4 s**.
These use marked disposable synthetic installations and the actual isolated
judge. Waiting-state captures at 1440/390 px were visually reviewed.

The 16-page student PDF was rebuilt and every page rendered. Page 15's approval
wording was inspected; other pages match previously reviewed images. The public
PDF matches the build output. The starter ZIP was regenerated after review;
its 19-file inventory, extracted C++/Python game and offline viewer passed all
four package checks. Restart the web service to load the approval and cutoff code.

## Daily quota, win-ratio tables and replay alignment (2026-11-12)

The rolling 24-hour game allowance is now **1,000 per team**. The minute and
pending-game limits retain their existing behavior. Boundary checks allow game
1,000 and reject request 1,001. Browser quota setup uses synthetic history; the
thousandth game itself ran through the production worker and sandbox. The quota
and public-PDF scenarios passed twice: **8 executions in 26.8 s**.

Friendlies and each tournament now rank teams with at least **three completed
games** by exact win ratio, wins divided by all completed games including draws.
Other teams appear in a separate lower table with no rank. Equal ratios use
wins, draws, score difference and team ID. Tests cover a 2/3 team outranking a
3/6 team, a 2/2 team remaining provisional, zero-game teams and promotion at the
third match. The tournament modal uses the same tables. Compact mobile columns
keep win percentage visible without horizontal scrolling for the tested names.

The visualizer displays the recorded market before the selected card is
replaced, highlights that card and its acting player, and names the replacement
in the caption. Hands and scores include the displayed choice. JavaScript tests
check all 30 highlights; browser checks exercise playback, seeking and the
downloaded offline viewer. No game records or bot protocol were changed.

- **115 Python tests passed in 59.239 s**; JavaScript tests, edited syntax checks
  and `arena doctor` passed. Playwright discovers **229 scenarios in 14 specs**.
- Scoreboard/tournament/navigation regressions: **34 passed in 1.4 minutes**.
  Replay/edge-case/download regressions: **47 passed in 1.7 minutes**. The final
  focused three-game ranking/mobile-column check passed in **7.9 s**. Browser
  runs used disposable synthetic installations on approved host execution.
- Desktop/mobile ranking and replay captures were visually reviewed. The mobile
  ranking capture waits for the sidebar transition to finish before capture.
- The 16-page guide was regenerated and all pages rendered; page 15 was reviewed
  after quota/ranking wording changes, with other pages pixel-identical to their
  inspected predecessors. The published PDF matches the build output.
- The 19-file starter ZIP was rebuilt with the viewer fix (90,626 bytes). Exact
  inventory, an extracted C++/Python match and the offline viewer passed all four
  package checks after the final asset changes. The fixture-bound assertion was
  updated with the larger synthetic-history allowance before the passing run.

## Interactive submission testing (2026-11-12)

The submission page can test its current Python/C++ editor contents against a
selected practice bot. Tests compile and execute through the production sandbox
and queue, retain the current official submission, and expose bounded owner-only
stdin/stdout/stderr diagnostics. Students can review each turn, see runtime and
protocol-error hints, and open the exact replay in another tab while retaining
their draft. Debug results are excluded from team stats and competition tables.

- **114 Python tests passed in 42.784 s**, including exact observed protocol
  streams, bounded capture, compilation/runtime errors, private diagnostics,
  persisted reports, unchanged final versions and existing isolation regressions.
- `arena doctor`, `npm test` and edited Python/JavaScript syntax checks passed.
- Playwright discovers **226 scenarios in 14 specs**. A repeat batch of the
  11 diagnostic scenarios passed **22 executions in 1.1 minutes**. The final
  broader batch passed **95 tests in 2.2 minutes**, covering diagnostics,
  submissions, navigation, judge failures, security and HTTP/cache behavior.
  This includes Python/C++ runs, tracebacks displayed as text, other-team/admin
  denial, CSRF/role/input checks, queue resume, preserved drafts, transport retry,
  invalid output, extra-input deadlock hints and separate-tab replay opening.
  The added interactive-area file picker then passed **five focused checks in
  17.3 s**, covering Python/C++ file loading, editor/language synchronization,
  size/type validation without draft loss, filename retention and both layouts.
- Synthetic success screenshots at 390/1440 px and a runtime-error capture were
  visually reviewed. No production credentials, student code or runtime data
  were used for browser QA. Browser runs used approved host execution.
- The starter ZIP was regenerated after the asset change. Its exact 19-file
  allowlist, extracted C++/Python match and offline viewer passed all four
  package tests. The new server/debug code and private reports are excluded.

## Guided student implementation documentation (2026-11-12)

The shared guide now explains persistent input/output, the two-stage OPPTURN
exchange, consecutive opponent/own turns, a four-turn market trace, both complete
starter programs, card indexing, flush, a first strategy improvement, optional
card tracking and IDLE practice. Complete Python/C++ guide examples were checked
byte-for-byte against the root and bot starter files. The walkthrough's four
market snapshots and choices were also checked for consistency.

The rebuilt Persian PDF has **16 pages**. All pages were rendered with Poppler
and visually inspected; unchanged pages in the final render were verified to be
pixel-identical to their inspected first renders. The web-download PDF matches
the build output. Both the header and implementation section link to it.
The starter ZIP was rebuilt after PDF review; its exact 19-file inventory and an
extracted C++/Python match passed the four package tests.

**110 Python tests passed in 41.365 s**; JavaScript tests, syntax checks and
`arena doctor` passed. Playwright discovers **214 scenarios**. The focused guide,
download and navigation batch passed **14 tests in 27.1 s** with disposable
synthetic installations on approved host execution. The new implementation link
downloaded a PDF byte-identical to the current public file without login;
desktop/mobile layouts, guide fragments, bundled font and offline viewer passed.

## Automatic asset versions and normal reloads (2026-11-12)

Served HTML now versions local JavaScript/CSS links using their content hashes.
Scripts and styles require cache revalidation; fonts and artwork retain the
existing cache. Tests verify that changing an asset changes the URL on the next
HTML request, including replacement of a previously fixed version label.

**110 Python tests passed in 40.988 s**. `npm test`, edited Python/JavaScript
syntax checks and `arena doctor` passed. Playwright discovers **214 scenarios**.
The focused HTTP, navigation and download batch passed **35 tests in 47.6 s**,
including normal browser reloads, served-content hashes, cache headers, HEAD,
mobile/desktop navigation, the guide and the offline student package. Browser
execution used approved host execution with disposable synthetic installations;
the first approval attempt timed out and the permitted retry succeeded.

## Team profiles, direct friendlies and scoreboards (2026-11-12)

- **108 Python tests passed in 38.567 s**, including name persistence, validation,
  unchanged raw team names, frozen friendly versions, opponent validation,
  concurrent queue quotas and separate friendly/tournament result aggregation.
- `npm test`, edited JavaScript/Python syntax checks and `arena doctor` passed.
- Playwright discovers **213 scenarios in 13 specs**. A focused batch covering
  friendlies, navigation, profiles, scoreboards and tournaments passed **59 tests
  in 1.8 minutes**. The six final profile/scoreboard scenarios then passed twice:
  **12 executions in 22.7 s**, without retries. These include actual isolated
  game execution and replay, escaped student names, admin name search, opponent
  selection, per-tournament selection, empty events, permission/CSRF/input checks
  and a transport-failure retry preserving entered names.
- Profile and scoreboard screenshots at 1440 px and 390 px were captured using
  synthetic accounts and visually reviewed. Navigation checks also passed at
  768 px. Artifacts are in the ignored `output/browser-results/` directory.
- The initial restricted browser attempt was blocked by loopback HTTP `EPERM`.
  The successful runs above used approved host execution, disposable databases
  and the production worker/judge. Existing production runtime data was not used.

## Default bind address update (2026-11-12)

`serve` now defaults to `0.0.0.0`; an explicit `--host` still overrides it.
The disposable screenshot helper explicitly uses loopback. CLI checks with a
mocked server verified both default and override without opening runtime data.
All **103 Python tests passed in 22.518 s**; `npm test`, Python syntax checks and
`arena doctor` passed. Playwright discovered **207 scenarios**. The focused login
browser attempt was **blocked** by loopback HTTP `EPERM`; no browser scenarios
executed for this change. The live browser results below are earlier checks.

## Executed checks

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -v` | **103 passed**, 44.738 s, including live loopback HTTP |
| Replay + admin + login JS tests | **31 passed**; `npm test` also passes |
| `python3 -m arena doctor` | Filesystem, shell, network, process isolation and Python/C++ smoke checks passed |
| Extracted student ZIP in a new directory | Complete local C++/Python 30-turn match passed |
| Python compilation and JS syntax checks | Passed |
| Static HTML links/assets/downloads | No broken local links |
| Student PDF | 10 pages, rendered and visually inspected; Persian text joins correctly |
| Playwright discovery | **207 scenarios in 12 regression specs** |
| Final `npm run test:browser:repeat` | **414 passed**, 9.7 minutes; all 207 scenarios passed twice, zero retries/failures/skips/flaky results |
| Targeted live browser regressions | **82 passed**, 2.1 minutes |
| `npm run test:screenshots` | **Passed**, 42.8 s after the final navigation fix; all 50 planned screenshots captured and gallery reviewed |

Python coverage includes inventory, banner range/distribution, exact snake order,
stable market replacement, the 110/122 score fixture, all bonus categories,
strict majorities, draws and tiebreaks; Python/C++ persistence, startup grammar,
EOF and CRLF; invalid/extra/inactive/flooded output; real per-turn timeout,
cumulative response and inactive CPU limits; memory exhaustion; compilation
errors; shell/network/fork/host-file restrictions; parent death and preventing
its removal; and the pipe-EOF/process-exit race found during CPU-constrained load.

Service coverage includes password salting and session-token hashing, throttled
login, session revocation, CSRF/Origin/admin authorization, trusted proxy handling,
source/replay access control, upload and queue quotas, immutable versions,
concurrent invite acceptance, reject/cancel/expiry, local-code isolation from the
active version, scheduling/freezing, paired seeds, barriers, concurrent claims,
crash recovery, replay commits, standings, infrastructure failure and retry.
Circle schedules for every size 2 through 51 verify every unordered pair exactly
once, each round a matching, all teams getting n−1 games, and first-seat counts
within one. JavaScript tests independently verify replay scoring and reject
corrupt versions, banners, seats, markets, choices, refills, inventories, hands,
results and winners; they also exercise HTML escaping.

## Complete 50-team tournament benchmark

[Raw report](../output/benchmark-report.json)

```bash
python3 scripts/benchmark.py --teams 50 --slots 6 --cpu-cores 6
```

- **1,225 of 1,225 games completed normally**, no protocol or infrastructure losses.
- **31.478 seconds** from worker start through tournament completion.
- Six simultaneous match slots, entire benchmark and all children pinned to **six
  CPUs** out of the host's 20 available CPUs.
- **38.916 matches/second**; median game 98.089 ms, p95 137.815 ms.
- Maximum observed difference in teams' completed-game counts: **one**.
- Real persistent Python processes, real Landlock/seccomp isolation, all 30 turns,
  immutable submissions, SQLite claims/result commits and replay-file writes.
- Mix of greedy, collection-planning and opponent-aware reference bots; compilation
  happens before judging. This is **not** an in-process rules-only simulation.

The first pinned run exposed a shutdown race: EOF can arrive before `waitpid`
reports exit. The corrected referee waits for both within the existing grace
window; the final complete run and a dedicated regression test passed.

## Full-budget expectations

[CPU-heavy sample report](../output/benchmark-budget.json)

The budget profile performs 120 ms of actual CPU work on every active turn,
about 1.8 seconds/player, rather than sleeping or selecting instantly. It uses
the same referee, sandbox and scheduler as production. This characterizes a
different workload from the reference-bot benchmark.

The measured sample used **12 teams, 66 games, six slots pinned to six CPUs**.
All 66 games completed normally in **42.297 seconds**; median game 3,780.147 ms,
p95 3,824.551 ms. There were no timeout/protocol/infrastructure losses and the
maximum observed completed-game gap was one. At that per-game cost, a 50-team
round-barrier event would take approximately 15.4 minutes before extra load.

There is a hard capacity constraint: 1,225 games × two players × two seconds is
**4,900 player-seconds**. On six cores the ideal lower bound at full CPU budgets
is **816.7 seconds (13.6 minutes)** even without overhead. With this deliberately
balanced round-barrier schedule, 49 rounds × ceil(25/6) waves × four seconds is
about **980 seconds (16.3 minutes)** before overhead. Fast bots easily meet a
5–10-minute target; **all possible full-budget submissions cannot be guaranteed
to do so on six cores**. Nine dedicated cores/slots give approximately 588 seconds
before overhead with these barriers; thirteen give approximately 392 seconds.
Paired-seat tournaments double the games. Re-run the benchmark on the actual
contest host and leave headroom for uploads, compilers and HTTP activity.

## Live browser verification

The restricted command sandbox still denies loopback sockets (`EPERM`). The
current live checks use approved host execution, real disposable HTTP servers,
Chromium and the production worker/judge with isolation enabled. Earlier blocked
attempts are historical; they are superseded by the live results above. Python
HTTP tests also pass with real sockets; their socket-free fallback remains
available for restricted environments.

Each browser regression owns a fresh marked temporary database, server and worker.
The screenshot suite separately owns disposable demo data and captured all 50
desktop/mobile states. The gallery was reviewed, including detailed mobile
dashboard/replay/settings checks. Password fields are masked. See
[BROWSER_TESTS.md](BROWSER_TESTS.md) for the matrix and actual report paths, and
[SCREENSHOTS.md](SCREENSHOTS.md) for capture details. These are Linux/Chromium
checks; other browser engines and desktop operating systems remain unverified.

## Desktop compiler regression

A reported `cc1plus: vfork: Resource temporarily unavailable` failure was reproduced
by holding 140 unrelated threads open under the same real UID during C++ compilation.
The compiler's artificial UID-wide `RLIMIT_NPROC=128` caused the failure. Compilation
now inherits the operator's OS process limit and deployment TasksMax; filesystem,
network, time and memory restrictions remain enforced. Contestant runtime process
and thread creation remains prohibited. The new regression test, then-current 64-test
Python suite and `python3 -m arena doctor` pass. The distributed student ZIP was
rebuilt with the fix.

No public deployment or public security audit was performed. The reverse-proxy
and systemd files are supplied for the operator-controlled Linux installation.


## Earlier admin and student workflow update (2026-11-12)

The 82-test Python run includes admin permission/CSRF checks, live capacity and
pause/resume (running games finish), queue retry restrictions, selected final
submission ownership/pagination/concurrent migration/freezing, and the portable trusted-file
local runner. C++ and Python examples both use 30 fixed turns and the first-card
A-or-5 condition; the C++ example uses `using namespace std`. The local launcher's
path handling was tested from a different working directory, and hanging local
bots are terminated. Local and isolated greedy games agree on cards and results.
Windows/macOS execution remains unverified; Linux local practice tests pass.

The 23 JavaScript tests include all admin page renderers, escaping team/filename
text, slower playback and explicit manual single-step analysis. Edited JS passes
syntax checks. The PDF was regenerated from the revised, mildly formal Persian
HTML and reviewed as ten pages. The current downloadable bundle includes play.py,
A.cpp, B.py and the local runner only; production isolation/referee code is excluded.

The initial screenshot attempt was blocked by the restricted sandbox. The current
host execution captured all 50 desktop/mobile states; the gallery and manifest
include only actual saved PNGs. See the latest record above and docs/SCREENSHOTS.md.

Earlier Git discovery found an empty read-only metadata directory. The current
checkout has since been initialized; commit status for the present task is
reported separately rather than inheriting that earlier limitation.

## Password-only administration and minimal download

`/admin` now serves its own page and password-only form; `/api/admin/login`
resolves the configured administrator on the server, rejects team credentials
and checks the role before creating a session. Tests cover custom administrator
usernames, disabled/missing administrators, throttling, cross-site rejection,
the actual HTTP handler and rendering with an existing student session.

The configured administrator credential was updated only in the private runtime
database, with scrypt hashing and session invalidation. Password-only login and
an authenticated administrator session were verified through the production HTTP
handler, then the verification session was logged out. No credential was added
to source or downloadable files. That earlier record predates the current live
browser checks, which use disposable synthetic installations only.

The student ZIP now uses an explicit 19-file allowlist, approximately 90 KB. It
contains only the two requested starter examples, local launcher/rules/engine,
README and standalone offline viewer assets. Practice opponents, production
referee/isolation modules, server/admin code, PDF, replay fixtures and all runtime
or account files are excluded. Exact inventory, no-network viewer contents and
an extracted complete C++/Python game pass automated checks. The guide remains
available as a separate website/PDF download.


## Playwright regression fixes (2026-11-12)

The first live 190-scenario run found three failures: replay seeking lost keyboard
focus on redraw, the queue test could match a stale filtered row before the next
refresh, and the empty-body test unintentionally sent a JSON string. Replay now
restores focus; queue assertions await the filter response and the exact game's
replay link; raw HTTP-body tests send exact byte buffers.

Sixteen added browser scenarios reproduced and now cover uppercase C++ detection
in uploads and local games, history pagination after upload/account changes,
skip links changing the hash route, malformed replay card types, and HTTP 500s
from lone Unicode surrogates, non-ASCII forged CSRF and oversized SQLite IDs.
The API rejects invalid UTF-8 text throughout nested JSON and bounds IDs before
database binding. Administrator authorization remains enforced. Replay validation
checks card types before replacing the loaded game. The student ZIP was rebuilt;
all 19 entries match current source bytes and the extracted C++/Python game passes.

The targeted 82-scenario rerun passes. A subsequent full repeat run caught another
race after 411 passes: rendering a new page before fetching its data could erase
a file selected immediately after navigation. Navigation now renders the page
only when ready; refreshes preserve the latest route, account and pagination and
discard older responses. Administrator data loads also discard old responses
after reset/logout. Both the new immediate-navigation case and C++ upload pass
ten repetitions each (20 passes in 56.8 seconds).

There are 103 passing Python tests, including three new HTTP regressions, and 31
passing JavaScript tests covering malformed refill types and four deterministic
late-response cases. All 28 JavaScript files pass syntax checks, and `arena doctor`
passes. The browser suite now has 207 independent scenarios.

The final full repeat run passes **414 of 414 executions in 9.7 minutes**. Every
scenario runs twice with its own disposable server, worker and database. The JSON
report records zero unexpected, skipped or flaky results, every execution passed
on attempt zero, and the wrapper records `completed`. This supersedes the earlier
failed repeat run. No known regression failure remains in the tested
Linux/Chromium configuration; finite coverage does not prove all possible inputs,
timings or deployment environments correct.

Regression work corrected three behaviors: administrator-created passwords retain
surrounding spaces, a source string containing invalid Unicode receives a clean
validation error, and a tournament fails start validation if any selected team
has become disabled instead of silently removing that team. Backend regressions
for all three pass. HTTP address reuse also permits immediate same-port server
restart; its live behavior is covered by the pending browser persistence case.

The checkout now has initialized Git metadata, but staging was attempted and
failed: Git cannot create .git/index.lock because that directory is read-only
in this session. No commit was created.
## Cancelled tournament lists (2026-11-12)

Dashboard tournament lists exclude cancelled events for administrators and teams;
the cancelled records remain stored. Python regression suite: 116 passed.
JavaScript suite: 3 passed. Browser spec syntax and Playwright discovery passed.
Isolation doctor passed. The focused cancellation browser scenario was blocked
because loopback HTTP binding returned EPERM; no browser tests executed.

## Repository preparation (2026-11-13)

Added an explicit all-interface launch script and a local team provisioning tool.
Synthetic temporary-data smoke checks passed for account creation, password hash
verification, mode-0600 credential output and refusal to overwrite credentials.
JavaScript tests passed (3); Python and Bash syntax checks passed. Isolation doctor
passed. Playwright discovery found 237 tests. Browser execution was blocked before
any scenario ran: loopback HTTP binding returned EPERM. No visual approval is
claimed for this change. Runtime databases, submissions, credentials, local contest
inputs and generated reports are excluded from Git. Earlier Git staging limitations
were resolved with filesystem escalation for this repository preparation.

Final Python regression run: `python3 -m unittest discover -v` passed all
133 tests in 64.152 seconds. The package regression regenerated the starter ZIP
and verified its 19-file allowlist. No runner or viewer assets changed.
