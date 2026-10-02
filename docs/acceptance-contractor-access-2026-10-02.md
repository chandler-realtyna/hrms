# Contractor Desk access correction: 2026-10-02

## Baseline and scope

Production baseline: `c04236284a6533bbc684f8b786a5d4a1e82a0b4d`.
Read-only inspection of the reported ordinary project-lead account confirmed
Users/Contractors/Projects cards, 35 visible User records, 55 full Project
records and five foreign booking-settings records. The account had no HR,
system-manager or company-director role. These were inherited generic grants,
not intended company-manager authorization.

Corrected boundaries: managerial card eligibility, User list/document privacy,
read-only personal contractor master records, full Project master denial with
minimal project lookup retained, personal booking settings, host/booker meeting
privacy, and read-only activity catalogue. Self-service timesheet and timer
operations and actual project-lead team review remain available.

No global request redirects, wildcard permission hooks, module deletion or
automatic account-role removal are included. The proposed blanket restriction
was rejected because of its wider disruption risk. Other upstream ERP/metadata
grants need separate isolated tests and approval before global lockdown.

## Isolated acceptance

All write tests ran on the private `qa.local` site with synthetic accounts and
documents. No production approval, correction, business-record mutation or
test email was performed.

- 56 installed-Frappe tests passed: seven new access tests plus shared timer,
  full correction/project/HR workflow, pagination, badges, notification queue,
  personal scope and managerial Desk regressions.
- 33 focused frontend tests and 25 deployment tests passed.
- Authenticated browser test passed: foreign User and Project direct HTTP reads
  denied; generic lists scoped; real Project lookup retained; contractor master
  save denied; lead home showed only Team Timesheets and Time History.
- HR and an actual company-director profile retained master-document access.
  The QA fixture materialized the existing director permission-archive field,
  then exercised the real profile attachment and permission synchronization.

Browser evidence: `/private/tmp/hrms-contractor-desk-access.png` (local only).
Production publication and read-only post-release findings are recorded below
after canonical deployment; health alone is not complete system acceptance.
