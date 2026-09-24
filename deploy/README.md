# Production deployment

Canonical command (run from repo root):

```sh
deploy/deploy.sh                 # deploy origin/realtyna-production tip
deploy/deploy.sh --target <sha>  # deploy an exact pushed commit
deploy/deploy.sh --plan-only     # classify only, touches nothing
deploy/deploy.sh --rollback      # back to previous known-good release
```

Only pushed commits deploy. Tracked tree must be clean.

## How it works

1. `plan.py` diffs deployed commit → target and classifies:
   **frontend** (Vite/static assets) · **backend** (Python-only) ·
   **schema** (doctypes, patches, hooks/setup) · **full** (deps, base image,
   build config, anything unknown). Unknown always escalates to full.
2. App code activates via **immutable release dirs** (`/srv/hrms-releases/<sha>`,
   exact SHA, read-only) bind-mounted into containers
   (`apps/hrms` + served `assets/hrms`), never by copying files into containers.
3. `schema` runs `bench backup` first, then `migrate`. Everything else skips both.
   App operations use `compose.yaml` only: `pwd.yml` redefines app services
   with a stale hardcoded image and must never be mixed into deploy commands.
4. Health is polled (containers, HTTP, API, Redis, DB, served assets).
   `DEPLOY_STATE.json` advances **only** on success.
5. `flock`-style lock dir prevents overlapping deploys.

## Rollback

- **Code-only**: `deploy/deploy.sh --rollback` remounts the previous release
  and recreates services (~90 s), then verifies. Safe anytime.
- **Schema-changing deploys**: code rollback does NOT undo the database.
  Each schema deploy records its pre-migration backup id in state/history.
  Recovery: inspect `tabPatch Log` + error → prefer fix-forward
  (`migrate` is idempotent, pending-only) → if data recovery is needed,
  verify the backup on a scratch site first, then restore over production
  in a maintenance window. Never auto-restore production data.

## Health, locking, retention

- Health: 6 app containers Up, HTTP 200, `frappe.ping` pong, Redis ×2,
  MariaDB `SELECT 1`, served asset hash matches the release.
- Lock: `deploy/deploy.lock` (owner+timestamp); stale >60 min needs `--break-lock`.
- Kept: 3 releases, live + previous 2 images, 7 DB backups, 5 build logs,
  30 deploy records, all `.env` backups. Builder cache pruned only above 80% disk.
- Records: `deploy/history/deploys.jsonl` on the server.

## Never do manually

- `docker cp` files into running containers as a deploy (emergency only, and
  follow with a real deploy to consolidate — container layers are ephemeral).
- Recreating app services by hand (bypasses planning, locking, verification,
  state). Always use `deploy.sh`.
- `bench migrate` outside a schema deploy (or without a backup).
- Deleting the active/rollback release, the live images, volumes, or `.env*`.
- Pushing to `realtyna-production` does NOT auto-deploy anything.
