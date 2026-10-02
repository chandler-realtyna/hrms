# Final Approval And History Clarity

## Scope

Desk presentation only: HR queue readiness/filter, whole-week detail labels,
explicit finalization confirmation and success feedback, Time History headings,
filter labels, detail labels and CSV. Project approvals, persisted states, report
aggregation and authorization remain unchanged. No frontend bundle rebuild is
needed: the changed JavaScript is served directly by the native Desk page.

The HR list distinguishes `Awaiting project review` from `Ready to finalize`
under `Final approval`. A ready week still needs an explicit HR decision.
Finalization confirms whole-week locking, history and contractor notification.
There is no finalization button for a blocked week. Server rejection never
produces a success message. Existing server gates remain the authority.

History uses whole-week labels consistently in headings, filters, details and
CSV: `Not submitted`, `Awaiting project review`, `Awaiting HR approval`,
`Needs correction`, `Finalized`, `Legacy submitted`. Finalized hours still count
only Closed; the Submitted bucket is preserved separately. The report names
the unit and scope: hours by whole-week status, not project-section approval.

## Verification

- Thirty Node tests passed, including five new behavioral tests for readiness
  filtering, labels, confirmation, server rejection and unchanged report buckets.
- Twenty-two tests passed against actual Frappe/MariaDB on private `qa.local`:
  authorization, correction/project/HR workflow, shared timer and queue paging.
- Twenty-five deployment tests passed; JavaScript syntax and the existing
  350-entry terminology catalog passed unchanged.
- Authenticated Chromium QA passed: existing queue/timer/navigation regressions,
  blocked versus ready HR dialogs, explicit finalization confirmation at desktop
  and 390px widths, no page errors or viewport overflow, whole-week report
  labels and unchanged filter values. The confirmation was cancelled: this
  browser check did not finalize even the synthetic week.
- The synthetic HR browser fixture now removes only that QA account's inherited
  personal Company/Employee filters, so it exercises an organization-wide review
  account. Production roles and permissions were not modified.
- Synthetic screenshots were inspected: `/private/tmp/hrms-final-approval-mobile.png`
  and `/private/tmp/hrms-history-styled-desktop.png`.

## Boundaries

No real contractor records were modified for acceptance. Physical phone/Safari
and actual production notification delivery were not retested. This change
does not introduce a new workflow or reclassify historical Submitted records.
The independently dirty original checkout remains untouched.

## Publication

Canonical release `deploy-20261002-140851` activated
`0ff038510e6d65673d2c24945ca0398cbca3763b` on 2026-10-02 at 18:10:17
Asia/Yerevan (14:10:17 UTC). The previous known-good application release is
`ea8f600e240d2caa2001c80a8b42dac1c2f19bae`.

Classification was frontend-only. All six source/assets mounts matched the exact
release; HTTP/API, database, Redis and frontend asset checks passed. Migration
was skipped and no fresh database backup was taken for this display-only release.
The existing schema-backup policy and code rollback remain unchanged.

The served approval JavaScript SHA-256 matches the tested local source:
`fec8d9b42d1f7c1cd8dc039308a805246936ef60ed18872a53aee39d3ace8dbf`.
State records this exact active SHA with health `ok`; the deployment lock is absent.

The command exited nonzero **after** health success and state advancement: old
release retention could not chmod a root-owned Python cache in unrelated release
`6c6104bcf4895b9ff5e994e6785a7949a6863e3f`. No manual cleanup, second activation
or rollback was attempted. This is a retention warning, not an unverified active
release; future maintenance should address that old cache ownership separately.
Private QA containers were stopped and the temporary tunnel closed.
