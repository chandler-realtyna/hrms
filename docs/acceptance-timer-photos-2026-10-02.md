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
  Controls re-enable after rejection; blocked image requests show initials.

## Publication and Live Verification

- Exact pushed application SHA: `bb45d051b94c16f11c7f9a5a3b82d8b5a4162b20`.
- The canonical planner selected `backend`. All six release mounts and health
  checks passed, and deployment state advanced at 17:42 UTC. No database
  migration or fresh database backup was selected for this code-only release.
  Previous release `27387bc5d5bd5640e06234b287154cd2a2978983` remains the rollback target.
- The deploy script exited nonzero only after successful health/state advancement:
  cleanup could not chmod an old release's root-owned Python cache. This was not
  treated as a failed activation or grounds for manual production cleanup.
- Live read-only checks under Lucas's account verified both Ia and Steven return
  128-by-128 WebP/private-no-store thumbnails; every matching original private
  File remains denied. No real photo was modified or made public.
- Live timer conflict preview found five intersecting saved rows and left the
  persisted timer JSON and revision exactly unchanged. Real-data save was not attempted.
- Lucas retains only Team Timesheets and Time History cards. All four directors
  retain eleven cards. No new global legacy restriction was applied.
- The deployment lock was released; the temporary local tunnel was closed and
  only the isolated QA containers were stopped, with their volumes preserved.

## Real-Data Boundary

Lucas's pending timer interval intersects multiple previously saved intervals,
including another project. No safe evidence identifies which real data should
win. Neither interval set was deleted, moved or saved over the other. Successful
real-data save must not be claimed until that conflict is explicitly resolved.
Synthetic data is used for writable acceptance tests only.
