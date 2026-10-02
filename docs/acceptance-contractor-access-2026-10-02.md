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

## Published release and read-only production checks

- Active application SHA: `27387bc5d5bd5640e06234b287154cd2a2978983`.
- Canonical deployment: `deploy-20261002-163501`, schema classification;
  migration and health both `ok`, exact mounts verified for all six services.
- Pre-migration database backup:
  `20261002_113536-frontend-database.sql.gz`.
- State recorded at `2026-10-02T16:37:05Z` (20:37:05 Asia/Yerevan);
  previous application SHA: `c04236284a6533bbc684f8b786a5d4a1e82a0b4d`.
- Final script status was nonzero only during old-release retention cleanup:
  a root-owned cache beneath release `6c6104bcf4895b9ff5e994e6785a7949a6863e3f`
  could not be chmod-ed. Health/state were already successful; subsequent
  read-only state verification confirmed the exact active SHA and free lock.
  No manual cleanup or repeat activation was performed.

Read-only checks using the reported Lucas account confirmed:

- Only Team Timesheets and Time History home cards remain.
- User list contains exactly his account; foreign User document read is denied.
- Full Project list is empty and direct master read is denied; 52 available
  project choices remain in the bounded time-logging lookup.
- His contractor record is readable but not writable.
- No foreign booking-settings or meeting records are visible.
- The team queue excludes his own entries; activity catalogue write is denied.
- Administrator and all four authorized company managers retain eleven home
  cards and actual Project/Contractor document read access.

Checks ran with transaction rollback and no business-record decisions. The
synthetic QA containers and local tunnel were stopped after acceptance.
The shared original checkout and independent production-branch commits were
not changed. Wider inherited Desk/ERP permissions remain explicitly outside
this targeted release pending the separate restriction decision and tests.
