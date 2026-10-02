# Realtyna HRMS Workflows

This document describes the custom contractor and manager workflows, their source
records and server-side decision boundaries. It is not a production acceptance
receipt. Use the verification checklist below for each release.

## Surfaces and Roles

- `/hrms`: contractor self-service, including personal time entries, expenses,
  leave, schedules, holidays and invoices. A project lead also has a team review
  view; it reads the same records as Desk, not another copy of them.
- `/desk`: managerial entry point. Team entries and weekly project review are
  two views of one review workflow. Final HR review is a separate stage.
- Project leads/managers see their assigned project scope. Ordinary contractors
  cannot access another contractor's personal records through self-service.
- Company Directors is a shared role profile, not a list of names in page code.
  It grants company-wide HR/project review and permitted native management
  forms. It does not replace each operation's server authorization.
- Legacy `Employee`/Company/Project/Department user filters for directors are
  archived before removal; removing the director role restores existing valid
  filters. Ordinary contractor filters are not changed.
- Native personal-record lists and direct record access are also scoped by
  contractor identity. Contractor masters, schedules, holidays and complete
  timesheets are private to the contractor or authorized HR/directors. Project
  reviewers use the existing project-scoped review APIs, not unrestricted
  access to another contractor's whole timesheet. Assigned leave/expense
  approvers retain their existing request access; role permissions still apply.
- Team availability intentionally shows the existing approved schedule view.
  It does not expose draft request forms or grant editing access to colleagues.

## Time Recording

The source is a Timesheet with Timesheet Detail children. Weekly documents have
one contractor/week key, from Sunday through Saturday. Cancelled records do not
count as another active week.

Timer favorites are reusable shortcuts, not mandatory access restrictions.
Adding a temporary project is allowed. Only one project records at a time.
Switching or pausing ends the active interval. Resuming creates a new interval;
it does not span the paused gap. Activity type and description belong to the
interval. Project selection never reassigns a running interval.

Each row owns its Start/Pause/Resume/Switch and Save controls. Save persists only
that project's unsaved intervals. Saving an inactive project leaves the active
one running. Timer state and favorites live in one private HRMS Work State per
authenticated account, shared by browsers and mobile devices. The API never
accepts another account as the target. Start/stop timestamps come from the server;
the displayed counter accounts for device-clock offset.
Timer RPCs accept authenticated POST requests only, retaining the framework's
normal request/CSRF protections. Invalid legacy timers without a project are
rejected and kept locally rather than becoming unusable shared state.

Every action locks the account row and requires a revision and operation ID.
An acknowledged operation has a durable receipt; replay returns current state
without saving intervals again. A stale revision returns a conflict and requires
refresh. All intervals of one Save share a database transaction: failure leaves
the entire pending set intact. A lost response retains the exact request for
retry, not a newly generated operation. Controls require connectivity; an already
running counter keeps advancing offline. Logout clears local request memory,
not the server timer.

Owner-stamped legacy state imports only before shared state is initialized.
Conflicting local timers stay separate and can be downloaded for recovery; they
never replace the shared timer automatically. Previous unowned browser favorites
need an explicit import confirmation. Closed-project favorites are preserved but
cannot start a new timer. Discard is secondary, confirmed and project-specific.
Two-hour paused autosave runs on the server even with all browsers closed; failed
autosaves retain time, show an error and retry with a thirty-minute backoff.
Long-running reminders are deduplicated against the server's active start.

## Weekly Review

1. A contractor saves entries. Draft means **not submitted**, not cancelled,
   rejected or approved. A lead can already inspect their project's saved team
   entries and return individual intervals with a mandatory reason.
   The first saved entry on a project notifies its lead through the existing
   notification system; repeated autosaves do not repeat the project notice.
2. The contractor submits their own week. Each project section gets a review row.
   An assigned lead reviews the project section. The lead's own project entries
   and projects without a usable lead require HR review instead of self-approval.
3. A lead can approve a submitted section, approve selected sections or approve
   the pending members of a project/week. Draft entries cannot be approved.
   Weekly report tables include only project/weeks with pending submitted
   review work; they are not the directory of every contractor or the archive.
4. Every logged project must have exactly one completed review or a legitimate
   HR-routing exception. Pending, returned, missing or duplicate review rows
   prevent final HR closure, even if a legacy parent incorrectly says it is
   awaiting HR. Such legacy items remain visible but final approval is disabled.
5. A lead's personal week cannot reach final HR approval while the same week's
   saved team sections on projects they lead remain unsubmitted/unreviewed.
   Initial personal submission is allowed to avoid circular submission deadlocks
   between leads who work on each other's projects. Completing team reviews
   advances eligible submitted lead weeks to HR without approving them for HR.
6. HR reviews all project sections of the contractor's week and can return a
   selected interval, selected intervals or the whole week with a reason.
   Final approval closes and submits the original Timesheet. `Closed` means
   final approval completed; `HR Review` does not.

A single-entry correction unlocks only the selected entry. Unselected siblings
remain locked. A whole-section return permits changes only in that project.
Resubmission requeues corrected source/destination projects while preserving
unaffected approvals. Closed weeks cannot be edited/cancelled directly.

Team queues exclude the current user's personal entries. Personal entries remain
in My Timesheets. Desk and HRMS show one Review Status for the project section;
whole-week status appears only in section details, My Timesheets and HR review.
Activity types remain visible. Project approval still does not finalize a week.

Current includes authorized drafts and nonfinal contractor/project/week sections.
History contains final Closed weeks in the same team area. Both read original
Timesheet/Detail/Approval records, not copied reporting records. Server filters
and access scope apply before counting and fifty-section keyset pagination.
Current order is: actionable pending approvals (oldest week, then oldest submitted
time); drafts; returned sections; HR-routed/other waiting sections; approved
projects. Each non-actionable group uses newest modification first. Legacy missing
submission times fall back to modification time. History uses newest week, then
newest modification. Equal keys use Timesheet name and project descending.
The server orders before pagination; browsers preserve that order. Version-two
cursors bind the ordering to the account, view and filters. An old or incompatible
cursor shows a notice and replaces the list with its first page, never appending
duplicate restart rows. Counts describe matching sections, not every contractor
in the organization. Archived projects remain readable in historical scope.

Project display labels: Draft, Pending, Returned, Approved, HR.
Week display labels: Draft, Project review, Returned, HR review, Final.
Underlying stored workflow values are unchanged. Project Approved is not Final.

Desk HR review uses a `Final approval` column: `Awaiting project review` means
project/team blockers remain; `Ready to finalize` means HR can make the final
decision, not that it has already approved the week. Review details distinguish
project approval from whole-week approval. `Finalize week` asks for explicit
confirmation that the entire week will be locked, moved to history and the
contractor notified. Success is displayed only after the server accepts closure.

Desk whole-week details, Time History headings/filter/detail and CSV use:
`Not submitted`, `Awaiting project review`, `Awaiting HR approval`,
`Needs correction`, `Finalized`, `Legacy submitted`. The report explicitly
groups **hours by whole-week status**, not by a project's approval. Only Closed
contributes to Finalized hours; Submitted denotes records submitted outside the
weekly HR workflow and is not reclassified as Closed. These are display-only
changes; aggregation, access, stored statuses and approval gates are unchanged.

The employee sidebar, home team-hours card and home team-hours selector require
an actual active project-lead assignment, not merely a director/HR role. Desk
review permissions are unchanged. The Desk home shows HR weekly review first
(left), then Team Timesheets for users authorized to see both.

Timer Retry reconnects and replays any unresolved operation by its original ID.
When the server reports a failed automatic save, Retry saves completed intervals
with a new version-checked, idempotent operation; an active recording continues.
Failures preserve time and normal weekly locks still apply. The scheduler checks
the latest locked state before saving; obsolete due markers are repaired instead
of showing a false save-failure warning.
Selection is enabled only for Pending sections in a submitted project-review
week. Disabled choices explain whether submission, correction, existing approval,
HR routing or a final closed week prevents approval.

Weekly self-service refreshes on page entry, focus, visibility, reconnect and
private post-commit change events, with a thirty-second visible-page fallback.
Failed requests show Retry rather than indefinite loading. Refresh does not
replace unsaved edits. Saves compare the original modified version under a lock;
a stale save returns a conflict. A conflicting local draft is kept for recovery;
Review latest shows the current server version only after explicit confirmation.

## Expenses

The source is Expense Claim and its expense details. Contractor self-service uses
the current contractor and company. Each row requests date, configured claim type,
amount paid, description and optional authorized project; the parent supports
receipts. All configured claim types are loaded. Business categories and their
expense accounts must be configured deliberately, not invented by the UI.

Approved amount is the approver's reimbursement decision, not a second amount
for a contractor to enter. Internal sanctioned/base amounts remain in accounting
data. Cost centers are selected automatically and limited to the company's
operational leaves, not parent/group centers or similarly named other companies.

An ordinary contractor cannot create a claim for another contractor. A saved claim's
contractor cannot be reassigned, including by HR. Authorized HR can create a new
claim on behalf of a contractor in Desk. Existing document permissions still
govern viewing, editing and approval. Approval is distinct from payment.
An ordinary contractor must use the company on their contractor profile for a new
claim; changing a saved claim's company is also blocked.

Empty tax/charge sections are hidden in Desk; existing tax data stays visible.
No accounting rows, companies, categories or cost centers are deleted.

## Leave, Holidays and Schedules

Leave Application and Expense Claim have separate review entry points. Leave
requests created or edited by their own contractor route only to the enabled HR
account configured in HR Settings / Contractor Leave Approver. The contractor form
cannot change it, and the server enforces it. A missing or invalid HR destination
blocks a new request clearly. Already-submitted requests and decision history
are not automatically rewritten. Authorized on-behalf Desk requests keep their
existing routing. Expense decisions retain their existing configured approver.
The existing operations are approval/rejection; a new correction workflow is
not implied for these documents.

Contractor Holiday and Contractor Schedule use their native Desk review forms.
Contractor changes follow the existing approval rules. Approved/pending schedule
changes request HR approval again. Timezone values use the server's supported
schedule choices. Dark mode must preserve readable native time inputs.
New personal schedule/holiday requests can only start as Draft or Submitted.
Only authorized HR can create approved/rejected requests. Saved requests cannot
be reassigned to a different contractor, including during managerial review.

## Invoices and Master Records

Invoice self-service retains the desktop sidebar. Managers use the
native Desk invoice review actions, including the existing correction reason
flow. Submission, approval and payment are different states/actions.

An invoice's issue date comes from the server. New and editable invoices have
a read-only due date exactly fifteen calendar days after that issue date;
caller-supplied due dates cannot override it. The default billing period ends
on the issue date and starts one month earlier, independently of payment terms.
Already-approved, paid or cancelled invoices are not automatically backfilled.

English labels use Contractor/Contractors and Invoice/Invoices throughout the
HRMS and Desk translation catalog, including confirmation status labels and
invoice PDFs. Internal `Employee`, `Employee Invoice`, field keys, routes, roles
and stored `Pending Employee Confirmation` values remain unchanged. The visible
status is Pending Contractor Confirmation; authorization and workflow are unchanged.

Users, Contractors and Projects link to their native Desk forms under existing
permissions. Closing/deactivating a project changes its supported status rather
than deleting its time/history records. Role/profile assignment determines future
manager access; there is no hardcoded future account list in the workspace UI.

The shared managerial Desk sidebar contains Search, Notification and Log out
utilities only. Workflow links remain on the managerial workspace; the top
Admin Reviews return action stays available. This presentation change removes no
modules, records or underlying permissions.

## Review Badges and New-Request Email

Every managerial home card has a native framework icon. Numeric badges appear
on HR Weekly Timesheet Review, Leave Requests, Expense Requests, Holiday
Approvals, Schedule Approvals and Invoices only. Counts use the current account's
document and row permissions; hidden queues disclose no count. They count the
full matching set, not just the first page.

The HR badge counts weekly drafts in Pending HR Review only when every required
project/team check allows final approval. Leave counts Open drafts; expenses
count Draft approval-status drafts; holidays/schedules count Submitted requests;
invoices count Pending HR Review, not payment or contractor confirmation.
Non-manager designated approvers count only their assigned leave/expense requests.
Counts refresh every thirty seconds while the home page is visible and on entry
or explicit refresh. Zero means an empty queue; a dash means unavailable, never
an assumed empty queue. Counts do not grant permission or approve anything.

New Open leave requests, holidays entering Submitted and invoices entering
Pending HR Review queue an email only to `hr@realtyna.com`. The approved message
contains request type and an authenticated Desk review link only: no contractor
name, amount, leave dates, description or attachment. Existing open-request
edits do not resend; a new submission cycle can notify again. Existing approval,
rejection and paid-invoice messages remain separate and unchanged. No historical
requests are automatically mailed.

The background notification is registered after the request transaction commits.
The reference lock and deterministic mail identifier prevent duplicate queue
creation on replay; SMTP retries use the same framework Email Queue. Background
job failures remain visible to administrators; retry the failed job, not the
business request. The standard configured outgoing account/scheduler delivers
queued mail. Queue creation and enabled configuration do not prove inbox delivery.

## History, Not Another Approval Queue

Time History reads original non-cancelled entries, grouped by project, contractor,
activity or month. It has date/project/contractor/activity/status filters and
read-only drill-down/export. Recorded hours and finally closed hours are distinct.
Legacy submitted non-weekly sheets are labeled Submitted, not final HR approval.
Project leads/managers are restricted to their project scope, including closed
projects for history; HR/directors have authorized company-wide scope.

Date ranges are limited to one year and queries to ten thousand entries. Oversized
results require narrower filters rather than silently dropping data. CSV export
escapes fields and neutralizes spreadsheet formulas. No summary creates another
Timesheet or acts as an approval.

## Release Verification

Canonical release procedure: `deploy/README.md`. Pushed clean commits only, backed
up schema changes, exact release/mount/asset verification and recoverable rollback.
The raw Desk stylesheet has a versioned URL. Increment its version when changing
that file, so browser/CDN caches cannot retain old review/history layout rules.
The review page adds its versioned stylesheet through a native link element;
the installed framework asset loader misidentifies file extensions when given
a query string, so do not pass that versioned URL to `frappe.require`.
The versioned proxy rejects unmatched browser Origin/Host pairs before the
realtime upstream. Only the valid production HTTPS origin is normalized to the
private frontend endpoint, so Frappe's session/document checks do not encounter
the external access-login page. It never normalizes an unvalidated origin.
Origin-less polling is accepted only with same-origin browser Fetch Metadata
and the production host. Unrelated or unverified missing origins are rejected.
Verify both a legitimate connection and rejection of an unrelated origin.

- Run correction-scope, workflow readiness, director scope/profile, Desk and
  history tests under the installed Frappe runtime with synthetic documents.
- Run timer interval/switch/partial-save tests and build the frontend.
- Check both the native Desk entry and direct links; verify names, activity types,
  state labels, disabled actions, server queue priority/history order and empty states.
- Compare actual record access for all authorized directors, not just roles or
  shortcut counts. Verify an ordinary contractor remains scoped to self-service.
- Inspect desktop/mobile light/dark pages, native time inputs, expense fields,
  timer controls and invoice sidebar. Check missing assets and console errors.
- Use synthetic/staging records for write decisions. Production read-only checks
  must not approve, reject, return or pay real contractor documents.
- Document remaining realtime delivery, device and user acceptance gaps. Service
  health, a successful build or mocked tests are not full-system acceptance.
