# Contest-day runbook

Use this checklist for a new event, recurring practice rounds and staged finals.
Commands run from the repository root as the operator. The admin panel is the
normal interface for tournaments; no cron job or automatic ten-minute loop is
installed. The worker starts tournaments scheduled in that panel.

## Before teams arrive

1. Follow [README setup](../README.md): install requirements, export an absolute
   `ARENA_DATA` and the exact `ARENA_ORIGIN`, then run `contest.sh doctor` and
   `contest.sh init`. Use a new data directory for a new event, not a demo database.
2. Run `bash scripts/contest.sh teams N`. The CSV and 5×2 cut-card PDF are in
   `output/pdf/team-credentials/`. Check the account count in `/admin`, print
   single-sided at actual size and cut the cards. Never project the full roster.
3. Run `bash scripts/contest.sh run`. Verify the student URL from another device,
   and `/admin` with the administrator password. The combined command includes
   the worker. For systemd hosting, start both configured services instead.
4. Have the web/PDF student guide and starter ZIP ready on the website. Check
   that downloads open and Python/C++ practice works on a disposable rehearsal
   installation. Do not run uploaded code outside the sandbox.
5. Agree on the submission deadline, practice cadence, final-stage sizes, games
   per pair and tie policy before announcing them. Ensure each qualifying stage
   can produce ranked teams: at least three completed games per team are needed.

## Opening and onboarding

1. **Introduce the challenge.** Explain the market, taking cards, team score and
   the goal of writing a strategy. Show a short replay before discussing code.
2. **Distribute materials.** Give each team only its own login card plus the
   student guide and download URL. Explain where to sign in and ask teams to
   keep passwords private.
3. **Fill profiles.** Ask teams to open «پروفایل تیم», enter the two students’
   names and save. Check names appear correctly beside teams in the admin panel.
4. **Establish a working baseline.** Ask every team to download and extract the
   starter ZIP, then upload the unchanged `B.py` from «ارسال کد» as Python. Check
   the upload succeeds and a final submission is selected. Run a bot practice
   game to distinguish a valid upload from a working game protocol.
5. **Explain implementation.** Walk through Python and C++ examples, `TURNS = 30`,
   reading one turn at a time, flushing output and choosing exactly one digit
   `0..5` only on `YOURTURN`. Explain 0.3 s/turn, 2 s/player, 256 MiB address space,
   legal slots and end of input. Refer to the guide for full protocol examples.
6. **Teach the debugger.** In the submission section, open its step-by-step
   debugger/example, move through turns and inspect input, chosen output and
   evolving game state. Then have teams test a changed strategy against a bot,
   inspect errors and replays, and check which final version is selected.
   Debug/local tests do not replace the selected official submission.

## Practice tournaments

1. Start an initial small/rehearsal round only after participating teams have
   valid selected submissions. In `/admin` → tournaments, create a named event,
   select teams and games per pair, then schedule it or choose «شروع اکنون».
2. Watch queue progress, worker heartbeat, protocol losses and infrastructure
   errors. Fix onboarding and runtime problems before increasing frequency.
3. Once stable, **aim for one practice tournament every ten minutes**. Schedule
   the next start in the panel (browser-local time). Check previous progress and
   queue depth first: 50 teams with one game per pair means 1,225 games. Ten
   minutes is an operating cadence, not a throughput guarantee; postpone a round
   if the host is falling behind. Do not overlap a backlog blindly.
4. Tell teams each start freezes their selected version. They may improve and
   upload for the next practice round while current matches retain old versions.
5. Review standings and representative replays with teams. Use clear distinct
   names such as “Practice 01” so they can choose the correct table.

## Staged qualification and final

1. Announce the submission cutoff and stage rules. Select a **completed**
   qualifying tournament as the source; do not advance from a partial scoreboard.
2. In the new-tournament form, choose that previous event, enter top K and apply
   the top-team selector. Review the selected teams before submitting. K is 2–100;
   there must be enough ranked, active teams with valid selected code. Resolve
   errors instead of silently replacing teams with lower ranks.
3. Create and run the next stage, wait for completion, then repeat qualification
   from **that stage**. Example: main field → top 16 → top 8 → top 4 → top 2.
   This is an example bracket, not an automatically configured elimination rule.
4. For a two-team final, choose at least **3 games per pair** so both teams can
   meet the standings minimum; 4 gives an even number with paired starting seats.
   With three teams, choose at least 2 games per pair for the same reason.
5. Qualification selects teams from the old event; source versions freeze anew
   when the new stage starts. A verbal upload cutoff does not disable uploads.
   Check selected versions at each start if the event requires a code freeze;
   the platform does not automatically carry the previous stage’s frozen source.
6. Review the completed final and any infrastructure failures before announcing
   results. Ranking uses win ratio, wins, draws, score difference, then team ID.
   Top-10 win percentage is informational and does not change rank.

## Recovery, reprinting and closeout

- **Lost card:** reprint from the saved CSV using `contest.sh cards CSV --pdf
  output/pdf/team-credentials/reprint.pdf`. It does not touch accounts. A password
  reset invalidates the old card; the old CSV cannot recover the new password.
- **Duplicate batch/output:** existing usernames or files are rejected. Do not
  delete accounts to reprint cards; use the export-only command and a new PDF path.
- **Infrastructure failure:** inspect logs, fix the host and run `doctor`, then
  retry failed infrastructure games in `/admin`. Their versions and seeds stay
  fixed. Protocol losses and completed results are not infrastructure retries.
- **Restart:** gracefully stop and restart with the same `ARENA_DATA`. Completed
  matches and frozen sources persist. Do not start a second worker for that data.
- **Closeout:** allow matches to finish, stop both processes, run `contest.sh
  backup --stopped --output contest/backup-after-final`, and privately copy the
  credential-export directory too. Archive announcements/notes without student
  passwords or source. Restore the full data snapshot with services stopped.

The [November 12 experience](CONTEST_EXPERIENCE_2026-11-12.md) explains the sequence
behind this checklist. See [operations](OPERATIONS.md) for production hosting and
[the Persian admin guide](ADMIN_GUIDE.md) for panel controls.
