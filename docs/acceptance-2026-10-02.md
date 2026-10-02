# HRMS completion acceptance - 2026-10-02

## Release boundaries

The urgent permission/loading repair was independently published as
`a80677b83f18f2626fb7b502fb7d9023c6a6c06c` using the canonical deploy script.
Production health passed. Read-only framework checks confirmed personal draft
read/write and denied foreign writes. No employee business decision was taken.

The second candidate adds shared timer state, fixed personal leave routing,
weekly freshness/conflicts, scoped team pagination/history and utilities-only
Desk navigation. Its final activation receipt is recorded below after deployment.
The original dirty checkout and independent production-branch changes remain
untouched. The review branch does not force-update the production branch.

## Isolated verification

Writes ran only on `qa.local`, created from an empty MariaDB database on a private
Docker network with independent Redis/sites/logs. No production database, user
sessions, documents or credentials were copied. The QA image uses the same
installed Frappe/ERPNext runtime as the production base. Synthetic account names
end in `@qa.invalid`. Mail and background scheduling are paused for QA.

- 14 real framework/database acceptance tests passed: actual own/foreign
  permissions, original Timesheet writes, locked sibling correction, project
  review then final HR closure, optimistic save conflict, account-private state,
  timer replay/failure preservation, legacy migration/guard, fixed leave routing,
  two-hour autosave and 505 source-record pagination fixtures.
- 67 existing focused regressions passed in that runtime, for a combined
  81-test run. These include mock-based tests and are not all end-to-end tests.
- Four independent-connection/Redis checks passed: conflicting devices,
  simultaneous identical operation replay, private after-commit notification,
  and simultaneous weekly saves with one explicit version conflict.
- 17 frontend script tests passed: retry/deadline/stale-route loading, shared
  timer/favorites, clock offset, response loss, offline controls, migration,
  concurrent metadata preservation, weekly freshness and draft conflicts.
- Real authenticated HTTP/browser flows passed in two separate contexts at
  desktop and mobile viewport sizes: start, observe, pause, resume, switch,
  save an inactive project without stopping the active one and offline controls.
- Real weekly browser checks passed: automatic thirty-second refresh without
  reload, an offline unsaved note retained, and explicit remote version conflict.
- Real Desk browser check passed: visible sidebar text is Search, Notification,
  Log out; team navigation stays in Desk.
- Visual checks passed at widths 1280 and 390 in light/dark modes. Native time
  inputs have dark backgrounds and contrasting text. Build and whitespace/JS
  syntax checks passed; existing font/chunk-size build warnings remain.

## Reproduction

Use the isolated checkout transfer procedure and `deploy/qa-isolated.sh`; never
point the write runners at the production site. Runner site names and browser
origins are fixed to isolated QA/local tunnel destinations.

```sh
env/bin/python apps/hrms/deploy/qa_acceptance.py \
  hrms.tests.test_shared_work_state hrms.tests.test_personal_scope \
  hrms.tests.test_admin_desk hrms.tests.test_director_profiles \
  hrms.tests.test_director_scope hrms.tests.test_timesheet_entry_corrections \
  hrms.tests.test_workflow_readiness hrms.tests.test_management_reports
env/bin/python apps/hrms/deploy/qa_concurrency.py
env/bin/python apps/hrms/deploy/qa_http_fixture.py

# Frontend checkout; HTTP runners require the private QA SSH tunnel on 18880.
node --test tests/timer.test.cjs tests/form_loading.test.cjs tests/weekly_freshness.test.cjs
node tests/visual.test.cjs
node tests/qa_http.test.cjs
node tests/qa_desk.test.cjs
```

Set `PLAYWRIGHT_MODULE` and `CHROME_PATH` to the installed runtime/browser paths
when they are not available through the default Node module lookup.

## Readiness limits

Mobile viewport emulation is not acceptance on a physical phone or Safari.
Private event publication to actual Redis was verified; a complete Socket.IO
notification delivery to a real employee browser was not exercised by the QA
web server. Visible-page polling provides the tested fallback. Two-hour autosave
logic ran with a controlled clock; an unattended two-hour wall-clock scheduler
run remains a post-release observation, not a claimed completed test.

No real leave approval, expense approval, correction, invoice decision or final
employee timesheet closure was executed in production. Existing submitted leave
destinations/history are intentionally unchanged. Historical malformed workflow
records are not automatically closed or rewritten.

## Production activation

Pending the final exact-commit canonical deployment and read-only health checks.

The behavioral reference is [workflows.md](workflows.md). Production health and
QA acceptance are distinct; health alone does not prove each employee journey.
