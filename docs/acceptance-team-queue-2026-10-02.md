# Team Queue Follow-up Acceptance

## Scope

One project Review Status in Desk and HRMS; whole-week status remains in details,
personal timesheets and HR review. Current queue priority is actionable oldest
week/submission first, then newest drafts, returned, HR-routed and approved
sections. History is final-only and newest-week first. Server ordering precedes
fifty-section pagination, with stable record/project tie keys and version-two
account/view/filter-bound cursors. Empty filters and omitted filters are equivalent.
An incompatible cursor restarts clearly, replacing rather than appending rows.

Employee sidebar/home team controls require an actual active project-lead
assignment; Desk permissions are unchanged. HR weekly review is first (left),
followed by Team Timesheets. Report filters now have full-width controls and
unclipped dates/options; project actions are plain links. Versioned native
stylesheet loading avoids the installed asset loader's query-string parsing bug.

Timer Retry reconnects/replays unresolved operations, then retries completed
interval saving when a server autosave error exists. Revision/idempotency checks
and weekly locks still apply. An active recording continues. The scheduler
rechecks the latest locked state before applying autosave, repairing obsolete
deadlines without presenting them as failed saves.

## Verification

- 22 installed-Frappe/database tests passed on private `qa.local`, including
  160 mixed current sections, 112 historical sections, 505-row legacy-cap
  regression, equal timestamps/project ties, all-page identity comparison,
  status/search filters, role scoping and incompatible cursor reset.
- 25 frontend tests passed: source-executed component tests preserve server order
  across pages, reset without duplicate append, discard stale failures and verify
  Retry actually invokes interval saving rather than only rereading state.
- 25 deployment planner/build/mount/recovery regressions passed.
- Actual authenticated Chromium acceptance passed for 1280px Desk and 390px
  dark HRMS: single status, paging order, detail week status, disabled historical
  approval checkboxes, no viewport overflow, working Retry with active recording
  preserved, non-lead home/sidebar hiding, HR-first home order and report filters.
  Browser exceptions: zero. Screenshots were visually inspected.
- Production checks were read-only for five authorized managerial identities:
  queue priority, next-page non-overlap, final-only history, HR-first home order
  and actual-lead visibility metadata passed. No real business record was altered
  for testing. Isolated QA containers stopped; localhost tunnel closed.
- Frontend build and 350-entry terminology catalog verification passed. Existing
  font resolution and large-chunk warnings remain unchanged.

The scheduler deadline test mocks commit/rollback only to retain its fixture
savepoint; database reads/writes, locked state and business actions are real.
Browser checks use synthetic QA records, not live employee decisions. Physical
phone/Safari, real notification delivery and broader system acceptance are not
newly claimed by this narrow follow-up.

## Publication

- Exact active application commit: `ea8f600e240d2caa2001c80a8b42dac1c2f19bae`.
- Previous known-good commit: `12aae44fd52e4cf73276617c56a3f93bc08ad039`.
- Canonical deployment: `deploy-20261002-125427`; class `backend` (includes the
  committed frontend assets); activation health passed at `2026-10-02T12:55:54Z`.
- All six app services had the exact source/asset release mounts verified;
  HTTP/API/DB/Redis/asset health passed. Deployment lock released.
- Image tag remains `deploy-20261001-cbe9746`. No schema change, image rebuild or
  migration. This code-only publication created no database backup; the prior
  schema-release backup `20261002_064225-frontend-database.sql.gz` remains the
  recorded database recovery boundary. Code rollback is not data rollback.
- Pushed to the existing review branch/PR. Independent production booking commits
  and the user's unrelated dirty original checkout were not overwritten. The
  workflow/report receipt commit after this release is documentation-only and
  does not change the active application SHA.

Workflow authority: `docs/workflows.md`. Deployment authority: `deploy/README.md`.
