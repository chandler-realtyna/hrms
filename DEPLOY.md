# Realtyna HRMS — Deployment Guide

> **Repo:** `git@github.com:chandler-realtyna/hrms.git`  
> **Branch:** `version-16`  
> **Base:** Frappe HRMS v16 (upstream `https://github.com/frappe/hrms`)

---

## Table of contents

1. [What this fork changes](#1-what-this-fork-changes)
2. [Known issues you hit — and their fixes](#2-known-issues-you-hit--and-their-fixes)
3. [How to deploy (custom image)](#3-how-to-deploy-custom-image)
4. [Updating an existing deployment](#4-updating-an-existing-deployment)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. What this fork changes

All changes live on the `version-16` branch of `github.com/chandler-realtyna/hrms`.

| Commit | Change |
|---|---|
| `684d22df` | **fix:** `hrms.setup` package — re-export all install/migrate helpers so hooks work after `bench migrate` |
| `4bc1752e` | **fix:** Timesheet minute entry no longer adds UTC-offset hours to the duration |
| `63bd398b` | **fix:** HR Setup workspace — Employee Schedule & Holiday shortcuts always appear after migrate |
| `8c93e89f` | **feat:** All timesheet logs default to billable |

---

## 2. Known issues you hit — and their fixes

### Issue A — `bench build` fails: `Could not resolve "html2canvas"`

**Why it happens**

`hrms/public/js/hierarchy_chart/hierarchy_chart_desktop.js` imports `html2canvas`. Frappe's `bench build` bundles that file with esbuild and resolves node modules relative to the app root (`apps/hrms/node_modules/`).

`html2canvas` **is already declared** in `apps/hrms/package.json`:

```json
"dependencies": {
  "html2canvas": "^1.4.1"
}
```

The build only fails when `yarn install` has **not** been run at `apps/hrms/` before `bench build`. This can happen in custom image builds that only run `cd frontend && yarn install` instead of the app-root install.

**Permanent fix (in your Docker/CI build)**

Add an explicit `yarn install` at the app root **before** `bench build`:

```dockerfile
# After the app code is in place:
RUN cd /home/frappe/frappe-bench/apps/hrms && yarn install --frozen-lockfile
RUN bench build --app hrms
```

Or in any build script:

```bash
cd /path/to/frappe-bench
yarn --cwd apps/hrms install --frozen-lockfile
bench build --app hrms
```

> `bench get-app` in a normal installation handles this automatically. The issue only surfaces in custom image builds that skip it.

---

### Issue B — White screen after deploy (frontend serves stale May 22 assets)

**Why it happens**

The production setup runs **separate** backend and frontend containers. When you deploy new code:

- **Backend** container gets rebuilt with the new HRMS version → has fresh compiled assets under `apps/hrms/hrms/public/frontend/`
- **Frontend** container is still running the **old official image** → still serves assets from May 22

They are out of sync, so the browser loads `index.html` from the frontend container but the JS/CSS chunks it references were written by the backend container. Result: blank/white screen.

**Immediate workaround** (what you already did)

Copy the public assets from the backend container to the frontend container and restart nginx:

```bash
# On the host — adjust container names to match yours
docker cp backend:/home/frappe/frappe-bench/apps/hrms/hrms/public/frontend \
           /tmp/hrms-frontend-assets

docker cp /tmp/hrms-frontend-assets \
           frontend:/home/frappe/frappe-bench/apps/hrms/hrms/public/frontend

docker restart frontend
```

**Permanent fix — build a custom image** (see [Section 3](#3-how-to-deploy-custom-image))

---

### Issue C — `hrms.setup` hook/module path broken after `bench migrate`

**Why it happens**

Python resolves `hrms.setup` to the `hrms/setup/` *package directory*, not the sibling `hrms/setup.py` file (packages win over modules with the same name). The old `setup/__init__.py` only re-exported `update_select_perm_after_install`. Every other symbol — including `after_app_install`, `before_app_uninstall`, `after_install`, and several used by patches — was silently unreachable, causing `bench migrate` hook failures.

**Fix (already committed — `684d22df`)**

`setup.py` was moved to `setup/_install.py` (inside the package) and `__init__.py` was rewritten to `from ._install import *`. No changes needed to any callers.

---

## 3. How to deploy (custom image)

The goal is a **single custom Docker image** for both backend and frontend that always contains:

- Our HRMS fork at the correct commit
- Pre-built frontend assets (`hrms/public/frontend/`)

This eliminates the asset-sync problem permanently.

### 3.1 Sample Dockerfile

```dockerfile
# ── Base: use the official Frappe image as a starting point ───────────────
FROM frappe/bench:latest AS builder

ARG HRMS_BRANCH=version-16
ARG ERPNEXT_BRANCH=version-16

USER frappe
WORKDIR /home/frappe

# Initialise bench
RUN bench init --skip-redis-config-generation frappe-bench \
    --frappe-branch ${ERPNEXT_BRANCH}

WORKDIR /home/frappe/frappe-bench

# Get ERPNext
RUN bench get-app erpnext --branch ${ERPNEXT_BRANCH}

# Get our HRMS fork (not the upstream)
RUN bench get-app hrms \
      git@github.com:chandler-realtyna/hrms.git \
      --branch ${HRMS_BRANCH}

# ── Install JS dependencies (app root — needed for html2canvas) ───────────
RUN cd apps/hrms && yarn install --frozen-lockfile

# ── Build all assets (Frappe bundles + Vite PWA frontend) ────────────────
RUN bench build --app hrms

# ── Final image ───────────────────────────────────────────────────────────
FROM frappe/bench:latest
COPY --from=builder /home/frappe/frappe-bench /home/frappe/frappe-bench
```

### 3.2 Key points

| Step | Why it matters |
|---|---|
| `bench get-app … git@github.com:chandler-realtyna/hrms.git` | Must point to **our fork**, not the official `frappe/hrms` repo |
| `cd apps/hrms && yarn install` | Installs `html2canvas` and all other app-root JS deps before `bench build` |
| `bench build --app hrms` | Runs both Frappe's esbuild pipeline (hierarchy chart) and the Vite PWA build |

### 3.3 After image is built

```bash
# Deploy a new site
bench new-site hr.yoursite.com \
  --mariadb-root-password <pass> \
  --admin-password <pass>

bench --site hr.yoursite.com install-app erpnext
bench --site hr.yoursite.com install-app hrms
bench --site hr.yoursite.com migrate
```

---

## 4. Updating an existing deployment

Every time the `version-16` branch gets new commits:

```bash
# 1. Pull latest code
cd apps/hrms
git pull origin version-16

# 2. Reinstall JS deps (only needed if package.json changed)
yarn install --frozen-lockfile

# 3. Rebuild frontend assets
cd frontend && yarn build && cd ..

# 4. Run migrations (applies DB patches + setup hooks)
bench --site <your-site> migrate

# 5. Clear cache
bench --site <your-site> clear-cache

# 6. Restart
bench restart
```

> If running containers: rebuild the custom image (step above) and redeploy so both backend and frontend containers get the same assets.

---

## 5. Troubleshooting

### `Could not resolve "html2canvas"` during `bench build`

```bash
# Make sure you're in the bench root, then:
cd apps/hrms && yarn install && cd ../..
bench build --app hrms
```

### White screen / JS chunk 404 after deploy

The frontend container is serving old assets. Either:

1. **Rebuild and redeploy** the custom image (recommended), or
2. Copy assets from backend to frontend manually (see [Issue B workaround](#immediate-workaround-what-you-already-did))

### `AttributeError: module 'hrms.setup' has no attribute 'after_app_install'`

Pull the latest `version-16` branch (`684d22df` or later) and run `bench migrate`. This was fixed by moving `setup.py` into the `setup/` package.

### `bench migrate` fails on `hrms.setup.update_select_perm_after_install`

Same fix as above — pull latest branch.

### Timesheet entries showing wrong duration (adds ~4 hours)

Fixed in `4bc1752e`. Pull latest branch and rebuild the frontend:

```bash
cd apps/hrms/frontend && yarn build
```

---

*Last updated: 2026-05-27*
