# Timer Recovery and Directory Photos

## Scope

Only timer save recovery, the existing overlap-validation bug, and directory
photo rendering are changed. The user's latest choice explicitly defers broader
legacy Desk permission restrictions. No real timesheet was edited for testing.

## Findings and Correction

- A semantic save error disappeared when refresh replaced it with an empty
  server autosave error. Rejected manual operations now retain their error;
  Retry performs the failed operation instead of only rereading state.
- The current account can inspect its saved intervals intersecting pending
  timer intervals, with links to its original timesheet. Other accounts' rows
  are never returned. This preview leaves pending timer state unchanged.
- Minute-truncation created false conflicts with zero-extent sub-minute rows;
  adjacent-only comparison missed later rows nested in a longer interval.
  The existing minute policy remains, with both defects covered by tests.
- Profile pictures attached to another person's private records are correctly
  denied as original files. A separate authenticated, bounded raster thumbnail
  endpoint exposes only the current directory image, not arbitrary private files.
  Timeline image errors fall back to initials.

## Tests

- 34 focused frontend tests pass, including multi-device/lost-response behavior,
  save-error persistence, actual retry, and no interval loss.
- 25 deployment planner/recovery/mount tests pass.
- 30 installed-Frappe tests pass on the isolated synthetic QA site: five new
  recovery/photo tests, eighteen shared-state tests, and seven master-access tests.
- Frontend production build succeeds. Existing font/chunk warnings remain.
- Synthetic browser checks pass at 1280- and 390-pixel widths in dark mode:
  persistent overlap notice, actual retry, unchanged timer revision/intervals,
  private original HTTP 403, thumbnail HTTP 200/WebP/no-store and rendered
  128-pixel image. Screenshots were inspected; the timer has no page overflow.
- Live read-only verification is recorded below after publication, not inferred
  from build or container health.

## Real-Data Boundary

Lucas's pending timer interval intersects multiple previously saved intervals,
including another project. No safe evidence identifies which real data should
win. Neither interval set was deleted, moved or saved over the other. Successful
real-data save must not be claimed until that conflict is explicitly resolved.
Synthetic data is used for writable acceptance tests only.
