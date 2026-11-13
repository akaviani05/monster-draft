# Browser checks and screenshot capture

Run on a machine that permits loopback HTTP and Chromium:

```bash
npm install
npx playwright install chromium
npm run test:browser
npm run test:screenshots
```

Both commands create disposable installations and synthetic team accounts; they
never point at production data. The screenshot suite produces full-page PNGs,
`manifest.json` and a clickable `index.html` gallery in `output/screenshots/`.
`capture-status.json` records whether capture completed, failed or was blocked.
Password fields are masked. Each screenshot is recorded only after it is saved;
the gallery never invents images for missing states.

The planned set covers login and errors, admin login and denied access, the guide,
empty and populated student pages, submission errors and final-code selection,
invitation acceptance, team search/no-results/creation/edit/reset/disabled states,
worker settings and paused dispatch, queue filters and retry, scheduled/running/
completed tournaments, standings, replay initial/middle/final/manual analysis,
invalid logs, local-code dialog and mobile layouts/navigation.

## Latest capture (2026-11-12)

`npm run test:screenshots` passed in 42.8 seconds after the final navigation fix
and saved all 50 planned PNGs.
The gallery was visually reviewed, with detailed checks of the mobile dashboard,
replay and execution settings. Desktop/mobile layouts and empty, error, pending,
running and completed states are represented. Password inputs are masked.

The restricted command sandbox still denies loopback sockets (`EPERM`); this run
used approved host execution with disposable demo data. No production server or
database was used. `output/screenshots/capture-status.json` records `completed`;
the actual image list is in `manifest.json`. These are current captures, replacing
the earlier blocked attempt. PDF rendering remains a separate check with Poppler.
