#!/usr/bin/env python3
"""Conservative deployment classifier for the HRMS production deploy system.

Compares base..target (git SHAs) and selects the minimum SAFE deployment
class. Ordering is conservative: any single FULL file forces FULL, any
SCHEMA file forces at least SCHEMA, etc. Unknown paths force FULL.

Classes: none | frontend | backend | schema | full
Exit 0 with JSON on stdout. Exit 2 on git/usage errors.
Standard library only.
"""

import argparse
import fnmatch
import json
import subprocess
import sys

# ---------------------------------------------------------------- patterns ---

# Anything here needs a full image rebuild (deps, base, build config).
FULL_PREFIXES = (
    "images/",
    "docker/",
    "overrides/",
)
FULL_EXACT = {
    "Dockerfile.weekly",
    ".nvmrc",
    ".python-version",
    "runtime.txt",
    "frappe-ui",  # submodule pointer bump
    ".github/helper/apps.json",
    ".github/helper/apps-production.json",
}
# Matched by basename anywhere in the tree (frontend + root manifests).
FULL_BASENAMES_ANYWHERE = {
    "package.json",
    "yarn.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
}
FULL_SUFFIXES = (
    "requirements.txt",
    "requirements-dev.txt",
    "-requirements.txt",
)
FULL_BASENAMES = (
    "Dockerfile",
    "Containerfile",
    "docker-bake.hcl",
    "docker-compose.yml",
    "compose.yaml",
)


def _is_full(path: str) -> bool:
    if path in FULL_EXACT:
        return True
    if path.startswith(FULL_PREFIXES):
        return True
    base = path.rsplit("/", 1)[-1]
    if base in FULL_BASENAMES or base in FULL_BASENAMES_ANYWHERE:
        return True
    for suffix in FULL_SUFFIXES:
        if base.endswith(suffix):
            return True
    return False


# Schema-affecting: needs backup + migrate (never a silent fast path).
def _is_schema(path: str) -> bool:
    if path == "hrms/hooks.py":
        return True
    if path.startswith(("hrms/setup/", "hrms/install.py", "hrms/uninstall.py", "hrms/fixtures/")):
        return True
    if "/doctype/" in path and path.endswith(".json"):
        return True
    if path == "hrms/patches.txt" or path.startswith("hrms/patches/"):
        return True
    return False


# Bundled by the esbuild pipeline at image-build time (not present as
# runnable files in a release checkout) -> must go through a full build.
def _needs_esbuild(path: str) -> bool:
    return path.startswith(("hrms/public/js/", "hrms/public/css/", "hrms/public/scss/"))


# Python/backend sources: restart-only, no migrate.
def _is_backend(path: str) -> bool:
    if not path.startswith("hrms/"):
        return False
    if path.endswith(".py"):
        return True
    if path.startswith(("hrms/translations/", "hrms/locale/", "hrms/templates/")):
        return True
    return False


# Static frontend assets / Vite sources (built artifacts are committed).
def _is_frontend(path: str) -> bool:
    return path.startswith(
        (
            "frontend/",
            "roster/",
            "hrms/public/frontend/",
            "hrms/public/roster/",
            "hrms/www/",
            "hrms/public/icons/",
            "hrms/public/images/",
            "hrms/public/manifest/",
            "hrms/public/favicon",
        )
    )


# No production impact at all (docs, deploy tooling itself, CI config).
def _is_none(path: str) -> bool:
    if path.startswith(("deploy/", ".github/")) and not _is_full(path):
        return True
    if path.endswith((".md", ".rst", ".txt")) and not path.startswith("hrms/"):
        return True
    base = path.rsplit("/", 1)[-1]
    if base in (
        "LICENSE",
        "license.txt",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        "crowdin.yml",
        "codecov.yml",
    ):
        return True
    return False


# ------------------------------------------------------------------ main -----


def _git(repo: str, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def classify(repo: str, base: str, target: str) -> dict:
    for sha in (base, target):
        kind = _git(repo, "cat-file", "-t", sha).strip()
        if kind != "commit":
            raise RuntimeError(f"{sha} is not a commit ({kind})")

    if base == target:
        return {
            "base": base,
            "target": target,
            "class": "none",
            "reason": "target equals deployed commit; nothing to do",
            "files": {},
            "counts": {},
        }

    raw = _git(repo, "diff", "--name-status", "-z", f"{base}..{target}")
    parts = [p for p in raw.split("\0") if p]
    files = {"full": [], "schema": [], "backend": [], "frontend": [], "none": [], "unknown": []}
    i = 0
    while i < len(parts):
        status = parts[i]
        # rename entries are "R100 <old> <new>": classify by the new path
        if status.startswith("R"):
            path = parts[i + 2] if i + 2 < len(parts) else parts[i + 1]
            i += 3
        else:
            path = parts[i + 1]
            i += 2
        if _is_full(path) or _needs_esbuild(path):
            files["full"].append(path)
        elif _is_schema(path):
            files["schema"].append(path)
        elif _is_backend(path):
            files["backend"].append(path)
        elif _is_frontend(path):
            files["frontend"].append(path)
        elif _is_none(path):
            files["none"].append(path)
        else:
            files["unknown"].append(path)

    # Unknown paths are treated as FULL (never guess toward faster).
    if files["unknown"]:
        files["full"].extend(files["unknown"])
        files["unknown"] = []

    counts = {k: len(v) for k, v in files.items()}
    if files["full"]:
        cls, why = "full", "dependency/base/build-affecting changes"
    elif files["schema"]:
        cls, why = "schema", "schema/migration-affecting changes"
    elif files["backend"]:
        cls, why = "backend", "Python/backend-only changes"
    elif files["frontend"]:
        cls, why = "frontend", "frontend-only changes"
    else:
        cls, why = "none", "no production-affecting changes"

    shown = {k: sorted(v)[:10] for k, v in files.items() if v}
    reason = f"{why} ({sum(counts.values())} files: " + ", ".join(
        f"{k}={counts[k]}" for k in ("full", "schema", "backend", "frontend", "none") if counts[k]
    ) + ")"
    return {
        "base": base,
        "target": target,
        "class": cls,
        "reason": reason,
        "files": shown,
        "counts": counts,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Classify a deployment diff.")
    ap.add_argument("--repo", default=".", help="git repository path")
    ap.add_argument("--base", required=True, help="deployed commit SHA")
    ap.add_argument("--target", required=True, help="target commit SHA")
    args = ap.parse_args()
    try:
        print(json.dumps(classify(args.repo, args.base, args.target), indent=2))
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
