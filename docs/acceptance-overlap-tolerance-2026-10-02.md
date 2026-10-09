# Five-Minute Overlap Tolerance

## Approved Scope

Allow total overlap up to five minutes per weekly time entry with a warning.
Keep recorded durations, timestamps, project ownership and permission boundaries.
Do not bypass larger overlap checks or alter real records during tests.

## Implementation

- A union-of-intersections calculation prevents separate small overlaps from
  each receiving their own five-minute allowance and avoids double counting.
- The weekly Timesheet override and custom validation use the same exact-second
  policy, including external non-cancelled employee/user timesheets. Nonweekly
  Timesheets still delegate to the installed framework's original validator.
- Timer save responses and weekly-form payloads include accepted overlap
  warnings. The UI reports successful saving with a warning, not a failed save.
- The old save endpoint accepts explicit-offset timestamps, converts once to
  system-local storage, and rejects timezone-less cached-browser requests while
  preserving the draft. Shared timer operation/revision guards are unchanged.

## Lucas's Existing Conflict

Read-only version history shows the conflicting five rows were added before
shared timer initialization. The former UI formatted UTC instants into browser
local strings without offsets. The latest old row ends around nine hours after
its version-creation timestamp; subtracting nine hours makes its end precede
the next new-style interval by eleven seconds. This strongly supports a legacy
browser/system timezone mismatch, not simultaneous work.

Changing those five real timestamp pairs was separately put to the user for
approval. Until that answer arrives, no original timestamp, duration, project,
description or pending timer interval is changed. The five-minute policy alone
does not claim to repair the larger legacy-timezone conflict.

## Acceptance

- 41 installed-framework tests pass on isolated QA, including eleven new
  overlap/timezone tests, five photo/recovery tests, eighteen shared-state and
  seven master-access tests.
- 37 focused frontend tests pass, including the successful save-warning case
  and matching manual-entry/row-highlighting overlap calculations.
- 25 canonical deployment tests pass; frontend build succeeds with existing
  font/chunk warnings only.
- Real browser acceptance passes at 390/1280 pixels in dark mode: the timer
  saves, its warning is shown, the weekly form retains a warning, and original
  five- and ten-minute interval durations remain exactly unchanged. No page
  overflow or uncaught browser exceptions. Screenshots inspected.
- Exact live release receipt is recorded after publication. Writable acceptance
  scenarios use the isolated synthetic QA site only.

## Live Release Receipt

- Application commit: `35603026b22b3aa4656dbed19c2a57578833fd5e`.
- Canonical deployment: `deploy-20261002-193806`, backend path with frontend
  assets included; no schema migration or database backup was required.
- Production state advanced after health passed at `2026-10-02T19:39:32Z`.
  The deployment lock is free and all six app service mounts were verified.
- The script returned a cleanup warning about permissions on an older release's
  Python cache after health/state advancement. No manual service or file cleanup
  was attempted; the active release and successful health receipt were verified.
- A read-only production check confirmed the active limit is 300 seconds.
  On an in-memory copy only, shifting the five proposed legacy intervals back
  nine hours and adding the pending timer interval passed time-row validation.
  The real weekly rows and shared timer state/revision were verified unchanged.
- Historical data repair remains pending separate user approval. The production
  validation did not save any real interval or invoke a timer action.
