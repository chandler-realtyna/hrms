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
