# Production deployment

Canonical command (run from repo root):

```sh
deploy/deploy.sh                 # deploy origin/realtyna-production tip
deploy/deploy.sh --target <sha>  # deploy an exact pushed commit
deploy/deploy.sh --plan-only     # classify only, touches nothing
deploy/deploy.sh --rollback      # back to previous known-good release
deploy/deploy.sh --target <sha> --resume-build # continue a completed full build after SSH interruption
```

Only pushed commits deploy. Tracked tree must be clean.

For an interrupted full build, first check its server build log and process.
Do not start a second build while the original is running. After it finishes,
`--resume-build` verifies the completed export log, exact tag, and stored image
digest before normal backup, activation, migration, health checks, and state
recording. An incomplete build or stale tag is rejected. The image tag includes
the UTC date, so resume this way on the same UTC day as the original build.
Read-only build probes retry SSH failures; mutating commands are never replayed
automatically.

After a proxy/realtime change, run `check_realtime_origin.py` through Python on
the production host (for example through SSH stdin). It uses only a Guest
handshake and prints no session identifiers or employee data. The site HTTPS
origin and Origin-less browser polling with same-origin Fetch Metadata must
connect. Unrelated, insecure, mismatched-host and missing-origin requests without
trusted browser metadata must receive 403. This does not bypass the external access gateway or verify
delivery of a real employee notification.

## How it works

1. `plan.py` diffs deployed commit → target and classifies:
   **frontend** (Vite/static assets) · **backend** (Python-only) ·
   **schema** (doctypes, patches, hooks/setup) · **full** (deps, base image,
   build config, anything unknown). Unknown always escalates to full.
2. App code activates via **immutable release dirs** (`/srv/hrms-releases/<sha>`,
   exact SHA, read-only) bind-mounted into containers
   (`apps/hrms` + served `assets/hrms`), never by copying files into containers.
   Releases containing `deploy/nginx.conf` also mount the versioned proxy
   configuration read-only and start nginx directly. The proxy rejects any
   browser Origin/Host pair other than the production site's HTTPS origin
   (or Origin-less same-origin polling verified by browser Fetch Metadata),
   then normalizes only the accepted realtime hop to `http://frontend:8080`.
   Frappe's session and document authorization stay intact; authentication
   requests remain internal rather than hitting the Cloudflare Access login.
   Site selection remains `frontend`.
   Older rollback targets retain their original compose proxy mount/startup.
   Origin behavior follows the [Fetch Standard](https://fetch.spec.whatwg.org/#origin-header)
   and [Fetch Metadata](https://www.w3.org/TR/fetch-metadata/).
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
  Failed migration recovery restores the complete prior compose override and
  image tag, including proxy mounts/startup, not just the HRMS source mounts.

## Health, locking, retention

- Health: 6 app containers Up, HTTP 200, `frappe.ping` pong, Redis ×2,
  MariaDB `SELECT 1`, served asset hash matches the release.
- Frontend proof nuance: HTML/Vue source comments compile out of bundles, so
  a changed comment may yield byte-identical chunks. Prove frontend activation
  by inspecting mount sources (`docker inspect` → release SHA) and served
  asset state, never by comment presence or chunk-content assumptions.
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
