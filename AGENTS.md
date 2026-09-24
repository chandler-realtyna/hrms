# AGENTS.md — instructions for coding agents in this repo

## Deploying ("deploy")

When the user asks to deploy, use the project's canonical deployment system.
Do not manually rebuild/recreate the entire production stack unless the
deployment planner selects the full deployment path.

```sh
deploy/deploy.sh                 # deploy origin/realtyna-production tip
deploy/deploy.sh --target <sha>  # exact pushed commit
deploy/deploy.sh --plan-only     # classify without touching production
deploy/deploy.sh --rollback      # previous known-good release
```

The script inspects the repo, diffs the deployed commit vs target, classifies
(frontend / backend / schema / full), and runs the minimum safe path:
release-dir bind-mounts + recreate + verify. Only pushed, clean-tree commits
deploy. Full details: `deploy/README.md`.

Key rules:

- Never `docker cp` code into live containers as a deploy (emergency only).
- Never recreate app services or run `bench migrate` by hand; use the script.
- `DEPLOY_STATE.json` (on server) advances only after health checks pass.
- Code rollback (`--rollback`) is not database rollback: schema deploys record
  a pre-migration backup; restoring production data is a deliberate manual
  procedure documented in `deploy/README.md`.
- If classification is uncertain, the planner defaults to a full rebuild.
- Production: `https://hr.realtyna.com`, single site `frontend`.
