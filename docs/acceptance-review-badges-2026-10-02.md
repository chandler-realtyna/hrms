# Review Badges, Icons and Minimal HR Email

## Scope

Six permission-scoped review counts, icons on all eleven managerial home cards,
and approved minimal new-request emails only to hr@realtyna.com. No schema,
workflow state, decision permission, business record or historical email backfill
is changed. The existing outgoing mail account and framework queues are used.

## Verified Before Publication

- 32 actual installed-Frappe/database tests passed on isolated qa.local: six mail
  event/queue tests, four badge tests, four ordering tests and eighteen shared
  timer/permission/workflow regression tests.
- Actual document insert/update hooks cover leave, holiday and invoice arrivals;
  open edits do not resend and invoice resubmission generates a new event.
- An actual delayed Email Queue with a synthetic recipient is created once on
  replay. Its MIME-decoded body has the review link and no personal details or
  attachment. No SMTP worker runs in QA and no real HR test message was sent.
- The actual background enqueue implementation registers after commit. Missing
  reference documents do not mail; caller-supplied recipients cannot override
  the fixed HR inbox.
- Badge fixtures exceed fifty items. Ready HR weeks, pending requests, inherited
  contractor/company permissions and a designated non-manager approver were
  checked against installed framework queries, not mocked permission functions.
- 33 frontend unit tests and 25 deployment regression tests passed. Desk JavaScript
  syntax passed; the existing 350-entry terminology catalog check passed.
- Authenticated Chrome QA verifies six counts (12, 64, 3, 65, 4, 5), all eleven
  native icon symbols render, exact accessible link names survive and mobile
  labels/badges do not overlap. The sidebar is closed through its normal overlay
  and every mobile card is scrolled into view and checked for obstruction.

Screenshots are local evidence only, not production acceptance:
`/private/tmp/hrms-review-badges-desktop.png`,
`/private/tmp/hrms-review-badges-mobile.png`,
`/private/tmp/hrms-review-badges-mobile-bottom.png`.

## Delivery Boundary

Minimal message disclosure was explicitly approved by the user. Test writes occur
only in a separately networked synthetic site. Production verification is read
only; mailbox delivery and the recipient's ability to open a future real-request
email are not claimed from queue tests alone. Publication receipt follows after
canonical exact-SHA deployment and health/asset verification.

## Publication Receipt

- Exact tested/pushed application commit:
  `c04236284a6533bbc684f8b786a5d4a1e82a0b4d`.
- Canonical deployment: `deploy-20261002-145528`, backend class, no image rebuild,
  migration skipped and no new database backup (no schema/data change). Prior
  known-good source remains `0ff038510e6d65673d2c24945ca0398cbca3763b` for rollback.
- All six service mounts verified; HTTP/API/database/cache/frontend health passed.
  State advanced at 2026-10-02 14:56:58 UTC, 18:56:58 Asia/Yerevan; lock released.
- The script exited nonzero after successful health/state advancement because
  retention cleanup hit the previously recorded root-owned cache permissions in
  release `6c6104bcf4895b9ff5e994e6785a7949a6863e3f`. No manual cleanup, stack rebuild
  or duplicate deployment was performed. This warning is not an activation failure.
- Served Desk JavaScript SHA-256:
  `ae47bb9545128da1fd38e9d04090f45acf10497b9ee2b809ac027e169ad5e95e`.
- Served Desk CSS SHA-256:
  `51538f4082abf9c9548164fecd8bc05b20bfbfe6604465c00a2d81d8eaf9d33e`.
- Active backend mail utility SHA-256:
  `f5b77ce45df1833201fa35d1ca335350bbf846f8b8c862f2b573bbb982e6a9d9`.
- Read-only checks under Administrator and all four configured managerial accounts
  returned eleven icon-bearing cards and the same six counts. At verification,
  counts were HR 4, leave 1, expenses 1, holidays 1, schedules 0, invoices 1. These
  are a live snapshot, not fixed application values or proof of mailbox delivery.
- The HR recipient is enabled; a default outgoing email account is configured,
  mail is not muted and the scheduler is not paused. Generated review links use
  `https://hr.realtyna.com/desk/`. No real request was created, edited or decided
  for verification and no test email was sent to the real HR inbox.
- QA containers were stopped and their local SSH tunnel closed after acceptance.
  The original unrelated dirty checkout and independent production-branch changes
  were preserved. Only the existing review branch was advanced.
