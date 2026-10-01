# Realtyna HRMS Workflows

This document describes the custom employee and manager workflows, their source
records and server-side decision boundaries. It is not a production acceptance
receipt. Use the verification checklist below for each release.

## Surfaces and Roles

- `/hrms`: employee self-service, including personal time entries, expenses,
  leave, schedules, holidays and invoices. A project lead also has a team review
  view; it reads the same records as Desk, not another copy of them.
- `/desk`: managerial entry point. Team entries and weekly project review are
  two views of one review workflow. Final HR review is a separate stage.
- Project leads/managers see their assigned project scope. Ordinary employees
  cannot access another employee's personal records through self-service.
- Company Directors is a shared role profile, not a list of names in page code.
  It grants company-wide HR/project review and permitted native management
  forms. It does not replace each operation's server authorization.
- Legacy Employee/Company/Project/Department user filters for directors are
  archived before removal; removing the director role restores existing valid
  filters. Ordinary employee filters are not changed.
- Native personal-record lists and direct record access are also scoped by
  employee identity. Employee masters, schedules, holidays and complete
  timesheets are private to the employee or authorized HR/directors. Project
  reviewers use the existing project-scoped review APIs, not unrestricted
  access to another employee's whole timesheet. Assigned leave/expense
  approvers retain their existing request access; role permissions still apply.
- Team availability intentionally shows the existing approved schedule view.
  It does not expose draft request forms or grant editing access to colleagues.

## Time Recording

The source is a Timesheet with Timesheet Detail children. Weekly documents have
one employee/week key, from Sunday through Saturday. Cancelled records do not
count as another active week.

Timer favorites are reusable shortcuts, not mandatory access restrictions.
Adding a temporary project is allowed. Only one project records at a time.
Switching or pausing ends the active interval. Resuming creates a new interval;
it does not span the paused gap. Activity type and description belong to the
interval. Project selection never reassigns a running interval.

Each row owns its Start/Pause/Resume/Switch and Save controls. Save persists only
that project's unsaved intervals. Saving an inactive project leaves the active
one running. Acknowledged intervals are removed from the retry queue immediately;
the server also retains its existing idempotent interval-save protection.
Discard is secondary, confirmed and project-specific. Paused automatic saving
retains the existing two-hour policy. Logout/account ownership checks preserve
timer isolation on shared browsers.

## Weekly Review

1. An employee saves entries. Draft means **not submitted**, not cancelled,
   rejected or approved. A lead can already inspect their project's saved team
   entries and return individual intervals with a mandatory reason.
   The first saved entry on a project notifies its lead through the existing
   notification system; repeated autosaves do not repeat the project notice.
2. The employee submits their own week. Each project section gets a review row.
   An assigned lead reviews the project section. The lead's own project entries
   and projects without a usable lead require HR review instead of self-approval.
3. A lead can approve a submitted section, approve selected sections or approve
   the pending members of a project/week. Draft entries cannot be approved.
   Weekly report tables include only project/weeks with pending submitted
   review work; they are not the directory of every employee or the archive.
4. Every logged project must have exactly one completed review or a legitimate
   HR-routing exception. Pending, returned, missing or duplicate review rows
   prevent final HR closure, even if a legacy parent incorrectly says it is
   awaiting HR. Such legacy items remain visible but final approval is disabled.
5. A lead's personal week cannot reach final HR approval while the same week's
   saved team sections on projects they lead remain unsubmitted/unreviewed.
   Initial personal submission is allowed to avoid circular submission deadlocks
   between leads who work on each other's projects. Completing team reviews
   advances eligible submitted lead weeks to HR without approving them for HR.
6. HR reviews all project sections of the employee's week and can return a
   selected interval, selected intervals or the whole week with a reason.
   Final approval closes and submits the original Timesheet. `Closed` means
   final approval completed; `HR Review` does not.

A single-entry correction unlocks only the selected entry. Unselected siblings
remain locked. A whole-section return permits changes only in that project.
Resubmission requeues corrected source/destination projects while preserving
unaffected approvals. Closed weeks cannot be edited/cancelled directly.

Team queues exclude the current user's personal entries and sort by the most
recent modification. Personal entries remain in My Timesheets. Project review
and whole-week state are displayed separately; activity types remain visible.

## Expenses

The source is Expense Claim and its expense details. Employee self-service uses
the current employee and company. Each row requests date, configured claim type,
amount paid, description and optional authorized project; the parent supports
receipts. All configured claim types are loaded. Business categories and their
expense accounts must be configured deliberately, not invented by the UI.

Approved amount is the approver's reimbursement decision, not a second amount
for an employee to enter. Internal sanctioned/base amounts remain in accounting
data. Cost centers are selected automatically and limited to the company's
operational leaves, not parent/group centers or similarly named other companies.

An ordinary employee cannot create a claim for another employee. A saved claim's
employee cannot be reassigned, including by HR. Authorized HR can create a new
claim on behalf of an employee in Desk. Existing document permissions still
govern viewing, editing and approval. Approval is distinct from payment.
An ordinary employee must use the company on their employee profile for a new
claim; changing a saved claim's company is also blocked.

Empty tax/charge sections are hidden in Desk; existing tax data stays visible.
No accounting rows, companies, categories or cost centers are deleted.

## Leave, Holidays and Schedules

Leave Application and Expense Claim have separate review entry points. Leave
and expense decisions remain with the configured approver or authorized HR.
The existing operations are approval/rejection; a new correction workflow is
not implied for these documents.

Employee Holiday and Employee Schedule use their native Desk review forms.
Employee changes follow the existing approval rules. Approved/pending schedule
changes request HR approval again. Timezone values use the server's supported
schedule choices. Dark mode must preserve readable native time inputs.
New personal schedule/holiday requests can only start as Draft or Submitted.
Only authorized HR can create approved/rejected requests. Saved requests cannot
be reassigned to a different employee, including during managerial review.

## Invoices and Master Records

Employee Invoice self-service retains the desktop sidebar. Managers use the
native Desk invoice review actions, including the existing correction reason
flow. Submission, approval and payment are different states/actions.

Users, Employees and Projects link to their native Desk forms under existing
permissions. Closing/deactivating a project changes its supported status rather
than deleting its time/history records. Role/profile assignment determines future
manager access; there is no hardcoded future account list in the workspace UI.

## History, Not Another Approval Queue

Time History reads original non-cancelled entries, grouped by project, employee,
activity or month. It has date/project/employee/activity/status filters and
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
  state labels, disabled actions, latest-first order and empty states.
- Compare actual record access for all authorized directors, not just roles or
  shortcut counts. Verify an ordinary employee remains scoped to self-service.
- Inspect desktop/mobile light/dark pages, native time inputs, expense fields,
  timer controls and invoice sidebar. Check missing assets and console errors.
- Use synthetic/staging records for write decisions. Production read-only checks
  must not approve, reject, return or pay real employee documents.
- Document remaining realtime delivery, device and user acceptance gaps. Service
  health, a successful build or mocked tests are not full-system acceptance.
