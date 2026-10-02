#!/usr/bin/env bash
# Canonical production deployment for Realtyna HRMS.
#
# Future agents: run this script to deploy. Do NOT hand-roll docker/bench
# commands. See deploy/README.md and AGENTS.md.
#
#   deploy/deploy.sh                  # deploy origin/realtyna-production tip
#   deploy/deploy.sh --target <sha>   # deploy an exact commit (must be pushed)
#   deploy/deploy.sh --plan-only      # classify only, touch nothing on prod
#   deploy/deploy.sh --rollback       # back to previous known-good release
#
# Exit codes: 0 ok / nothing to do, 1 failure (prod left on previous release),
# 2 usage/precondition error.
set -euo pipefail

# ------------------------------------------------------------ configuration ---
PROD_BRANCH="${PROD_BRANCH:-realtyna-production}"
SERVER="${DEPLOY_SSH_HOST:-147.135.76.43}"
SSH_USER="${DEPLOY_SSH_USER:-ubuntu}"
SSH_KEY="${DEPLOY_SSH_KEY:-$HOME/.ssh/hr}"
SSH_PORT="${DEPLOY_SSH_PORT:-22}"
REMOTE_DIR="${PROD_COMPOSE_PATH:-/home/ubuntu/frappe_docker}"
RELEASES_DIR="/srv/hrms-releases"
SITE="${PROD_SITE_NAME:-frontend}"
SERVICES="backend frontend websocket scheduler queue-short queue-long"
OVERRIDE_FILE="deploy/compose.hrms-release.yaml"
STATE_FILE="deploy/DEPLOY_STATE.json"
LOCK_DIR="deploy/deploy.lock"
HISTORY_DIR="deploy/history"
LOG_DIR="deploy/logs"
KEEP_RELEASES=3
KEEP_IMAGES=3
KEEP_BACKUPS=7
KEEP_BUILD_LOGS=5
DISK_PRUNE_THRESHOLD=80

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_ID="deploy-$(date -u +%Y%m%d-%H%M%S)"
START_EPOCH="$(date +%s)"
LOCK_HELD=0

# ------------------------------------------------------------------ logging ---
log()  { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { printf '[%s] ERROR: %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; exit 1; }

# Run a command on the server. Never enable tracing: secrets may be in env.
rssh() {
	ssh -i "$SSH_KEY" -o BatchMode=yes -o ConnectTimeout=20 \
		-o ServerAliveInterval=15 -o ServerAliveCountMax=6 \
		-p "$SSH_PORT" "$SSH_USER@$SERVER" "$@"
}

# Retry only read-only probes; replaying migration or activation is unsafe.
rssh_read() {
	local attempt result
	for attempt in 1 2 3; do
		if rssh "$@"; then return 0; else result=$?; fi
		[ "$result" = "255" ] || return "$result"
		sleep 5
	done
	return "$result"
}

release_lock() {
	if [ "$LOCK_HELD" = "1" ]; then
		# rm -rf (not rmdir): the dir contains the owner file.
		rssh "rm -rf '$REMOTE_DIR/$LOCK_DIR'" 2>/dev/null || true
		LOCK_HELD=0
	fi
}
trap release_lock EXIT

usage() {
	sed -n '2,14p' "$0"
	exit 2
}

# ------------------------------------------------------------------ parsing --
TARGET=""
PLAN_ONLY=0
ROLLBACK=0
BOOTSTRAP=""
BREAK_LOCK=0
RESUME_BUILD=0
while [ $# -gt 0 ]; do
	case "$1" in
		--target)    TARGET="${2:?}"; shift 2 ;;
		--rollback)  ROLLBACK=1; shift ;;
		--plan-only) PLAN_ONLY=1; shift ;;
		--bootstrap) BOOTSTRAP="${2:?}"; shift 2 ;;
		--break-lock) BREAK_LOCK=1; shift ;;
		--resume-build) RESUME_BUILD=1; shift ;;
		-h|--help) usage ;;
		*) fail "unknown flag: $1 (see --help)" ;;
	esac
done

command -v python3 >/dev/null || fail "python3 is required (planner)"
[ -f "$SSH_KEY" ] || fail "SSH key not found: $SSH_KEY"

# ------------------------------------------------------- 1. repo inspection --
cd "$REPO_ROOT"
git rev-parse --show-toplevel >/dev/null || fail "not a git repository"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
	git status --short | head -n 10 >&2
	fail "tracked working tree is dirty — commit or stash first (only pushed commits deploy)"
fi
UNTRACKED="$(git status --porcelain | grep -c '^??' || true)"
[ "$UNTRACKED" -gt 0 ] && log "note: $UNTRACKED untracked file(s) ignored (only committed code deploys)"

git fetch -q origin "$PROD_BRANCH" || fail "cannot fetch origin/$PROD_BRANCH"
if [ -z "$TARGET" ]; then
	TARGET="$(git rev-parse "origin/$PROD_BRANCH")"
else
	TARGET="$(git rev-parse --verify "$TARGET" 2>/dev/null)" || fail "unknown ref: $TARGET"
fi
# Target must exist on origin — the server clones from there.
# (Capture first: piping a live command into `grep -q` races SIGPIPE.)
LSR="$(git ls-remote origin 2>/dev/null)" || fail "cannot reach origin"
TARGET_ON_ORIGIN=0
while read -r REMOTE_SHA REMOTE_REF; do
	if git cat-file -e "$REMOTE_SHA^{commit}" 2>/dev/null \
		&& git merge-base --is-ancestor "$TARGET" "$REMOTE_SHA"; then
		TARGET_ON_ORIGIN=1
		break
	fi
done <<< "$LSR"
[ "$TARGET_ON_ORIGIN" = "1" ] \
	|| fail "target $TARGET is not reachable from origin — push first (only pushed commits deploy)"
log "target commit: $TARGET"

# ------------------------------------------------------- 2. remote state -----
STATE_JSON="$(rssh "cat '$REMOTE_DIR/$STATE_FILE' 2>/dev/null" || true)"
if [ -z "$STATE_JSON" ]; then
	[ -n "$BOOTSTRAP" ] || fail "no $STATE_FILE on server — first run needs --bootstrap <live-sha>"
	ACTIVE_SHA="$BOOTSTRAP"
	PREV_SHA=""
	ACTIVE_MODE="image"
	log "bootstrapping state: live=$ACTIVE_SHA (asserted, image mode)"
else
	ACTIVE_SHA="$(printf '%s' "$STATE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["active_sha"])')"
	PREV_SHA="$(printf '%s' "$STATE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("prev_sha") or "")')"
	ACTIVE_MODE="$(printf '%s' "$STATE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("mode") or "mount")')"
fi
log "deployed commit: ${ACTIVE_SHA:-none}"

if [ "$ROLLBACK" = "1" ]; then
	[ -n "$PREV_SHA" ] || fail "no previous release recorded — cannot roll back"
	TARGET="$PREV_SHA"
	log "rollback requested → target=$TARGET"
fi

# ------------------------------------------------------- 3. plan ------------
PLAN_JSON="$(python3 "$REPO_ROOT/deploy/plan.py" --repo "$REPO_ROOT" --base "$ACTIVE_SHA" --target "$TARGET")" \
	|| fail "planner failed"
CLASS="$(printf '%s' "$PLAN_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["class"])')"
REASON="$(printf '%s' "$PLAN_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["reason"])')"
HAS_SCHEMA="$(printf '%s' "$PLAN_JSON" | python3 -c 'import json,sys; print(1 if json.load(sys.stdin)["files"].get("schema") else 0)')"
log "plan: class=$CLASS — $REASON"

if [ "$CLASS" = "none" ]; then
	log "nothing to deploy."
	exit 0
fi
if [ "$PLAN_ONLY" = "1" ]; then
	printf '%s\n' "$PLAN_JSON"
	exit 0
fi

# ------------------------------------------------------- 4. snapshot --------
SNAP_TAG="$(rssh "grep '^CUSTOM_TAG=' '$REMOTE_DIR/.env' | cut -d= -f2")"
SNAP_DISK="$(rssh "df / | tail -n 1 | awk '{print \$5}'")"
log "live tag=$SNAP_TAG disk=$SNAP_DISK; previous=$PREV_SHA"

# ------------------------------------------------------- 5. lock ------------
LOCK_INFO="$DEPLOY_ID|$USER@$(hostname)|$(date -u +%FT%TZ)"
if rssh "mkdir '$REMOTE_DIR/$LOCK_DIR' 2>/dev/null"; then
	rssh "printf '%s' '$LOCK_INFO' > '$REMOTE_DIR/$LOCK_DIR/owner'"
	LOCK_HELD=1
else
	OWNER="$(rssh "cat '$REMOTE_DIR/$LOCK_DIR/owner' 2>/dev/null" || echo unknown)"
	TS="$(printf '%s' "$OWNER" | cut -d'|' -f3)"
	AGE="$(python3 -c 'import datetime,sys,time
try:
    ts = datetime.datetime.strptime(sys.argv[1].strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()
    print(max(0, int(time.time() - ts)))
except Exception:
    print(0)' "$TS")"
	if [ "$AGE" -gt 3600 ] && [ "$BREAK_LOCK" = "1" ]; then
		log "breaking stale lock ($OWNER)"
		rssh "rm -rf '$REMOTE_DIR/$LOCK_DIR' && mkdir '$REMOTE_DIR/$LOCK_DIR' && printf '%s' '$LOCK_INFO' > '$REMOTE_DIR/$LOCK_DIR/owner'"
		LOCK_HELD=1
	else
		fail "deployment locked by $OWNER (age ${AGE}s) — refusing to overlap; use --break-lock only if stale"
	fi
fi
log "lock acquired"

# ------------------------------------------------------- 6. prepare release -
SHORT="$(printf '%s' "$TARGET" | cut -c1-7)"
rssh "mkdir -p '$RELEASES_DIR' '$REMOTE_DIR/deploy' '$REMOTE_DIR/$HISTORY_DIR' '$REMOTE_DIR/$LOG_DIR'"
REL_EXISTS="$(rssh "git -C '$RELEASES_DIR/$TARGET' rev-parse HEAD 2>/dev/null || cat '$RELEASES_DIR/$TARGET/.release-sha' 2>/dev/null" || true)"
if [ "$REL_EXISTS" != "$TARGET" ]; then
	log "fetching release $TARGET (exact-SHA tarball)"
	rssh "rm -rf '$RELEASES_DIR/$TARGET' && mkdir -p '$RELEASES_DIR/$TARGET' && curl -sL --retry 5 --retry-all-errors --max-time 300 'https://github.com/chandler-realtyna/hrms/archive/$TARGET.tar.gz' -o /tmp/release-$TARGET.tgz && EXPECT=\$(tar tzf /tmp/release-$TARGET.tgz 2>/dev/null | grep -vc '/\$') && tar xzf /tmp/release-$TARGET.tgz -C '$RELEASES_DIR/$TARGET' --strip-components=1 && GOT=\$(find '$RELEASES_DIR/$TARGET' -type f | wc -l) && rm -f /tmp/release-$TARGET.tgz && [ \"\$GOT\" -ge \"\$((EXPECT * 95 / 100))\" ] && printf '%s' '$TARGET' > '$RELEASES_DIR/$TARGET/.release-sha'" \
		|| fail "cannot fetch a COMPLETE target commit tarball from origin (flaky download?)"
fi
rssh "grep -qx '$TARGET' '$RELEASES_DIR/$TARGET/.release-sha' \
	&& test -f '$RELEASES_DIR/$TARGET/hrms/hooks.py' \
	&& test -f '$RELEASES_DIR/$TARGET/hrms/public/frontend/index.html'" \
	|| fail "release $TARGET failed verification"
# Freeze AFTER all writes: read-only for everyone (container uid == host uid).
rssh "chmod -R a-w '$RELEASES_DIR/$TARGET'"
log "release ready: $RELEASES_DIR/$TARGET (exact sha, immutable)"

# ------------------------------------------------------- 7. compose override -
# Dual mounts (app source + served assets) for every app service. Written but
# inert until containers are recreated in step 8.
OVERRIDE_BACKUP="$REMOTE_DIR/$OVERRIDE_FILE.backup-deploy-$DEPLOY_ID"
rssh "if [ -f '$REMOTE_DIR/$OVERRIDE_FILE' ]; then cp '$REMOTE_DIR/$OVERRIDE_FILE' '$OVERRIDE_BACKUP'; else printf 'services: {}\n' > '$OVERRIDE_BACKUP'; fi" \
	|| fail "cannot snapshot the previous release mounts"
FRONTEND_COMMAND=""
FRONTEND_PROXY_MOUNT=""
if git cat-file -e "$TARGET:deploy/nginx.conf" 2>/dev/null; then
	FRONTEND_COMMAND='    command: ["nginx", "-g", "daemon off;"]'
	FRONTEND_PROXY_MOUNT="      - $RELEASES_DIR/$TARGET/deploy/nginx.conf:/etc/nginx/conf.d/frappe.conf:ro"
fi
rssh "set -e
cat > '$REMOTE_DIR/$OVERRIDE_FILE' <<'OVERRIDEEOF'
# Managed by deploy/deploy.sh — release mounts. DO NOT EDIT MANUALLY.
# Release: $TARGET
services:
  backend:
    volumes:
      - $RELEASES_DIR/$TARGET:/home/frappe/frappe-bench/apps/hrms:ro
      - $RELEASES_DIR/$TARGET/hrms/public:/home/frappe/frappe-bench/assets/hrms:ro
    environment:
      PYTHONDONTWRITEBYTECODE: \"1\"
  frontend:
$FRONTEND_COMMAND
    volumes:
      - $RELEASES_DIR/$TARGET:/home/frappe/frappe-bench/apps/hrms:ro
      - $RELEASES_DIR/$TARGET/hrms/public:/home/frappe/frappe-bench/assets/hrms:ro
$FRONTEND_PROXY_MOUNT
  websocket:
    volumes:
      - $RELEASES_DIR/$TARGET:/home/frappe/frappe-bench/apps/hrms:ro
      - $RELEASES_DIR/$TARGET/hrms/public:/home/frappe/frappe-bench/assets/hrms:ro
  scheduler:
    volumes:
      - $RELEASES_DIR/$TARGET:/home/frappe/frappe-bench/apps/hrms:ro
      - $RELEASES_DIR/$TARGET/hrms/public:/home/frappe/frappe-bench/assets/hrms:ro
    environment:
      PYTHONDONTWRITEBYTECODE: \"1\"
  queue-short:
    volumes:
      - $RELEASES_DIR/$TARGET:/home/frappe/frappe-bench/apps/hrms:ro
      - $RELEASES_DIR/$TARGET/hrms/public:/home/frappe/frappe-bench/assets/hrms:ro
    environment:
      PYTHONDONTWRITEBYTECODE: \"1\"
  queue-long:
    volumes:
      - $RELEASES_DIR/$TARGET:/home/frappe/frappe-bench/apps/hrms:ro
      - $RELEASES_DIR/$TARGET/hrms/public:/home/frappe/frappe-bench/assets/hrms:ro
    environment:
      PYTHONDONTWRITEBYTECODE: \"1\"
OVERRIDEEOF
grep -qx '# Release: $TARGET' '$REMOTE_DIR/$OVERRIDE_FILE'
cd '$REMOTE_DIR' && sudo docker compose -f compose.yaml -f '$OVERRIDE_FILE' config -q" \
	|| fail "cannot write or validate the exact release override"
# NOTE: pwd.yml is deliberately NOT included. It redefines the app services
# with a stale hardcoded image (realtyna-erpnext-hrms:16, which does not
# exist). App operations use compose.yaml only (image via $CUSTOM_TAG);
# db/redis live in pwd.yml and are never touched by deploys.
CFILES="-f compose.yaml -f $OVERRIDE_FILE"
log "override written + compose config valid"

# ------------------------------------------------------- 8. execute ---------
OPS=""
BACKUP_ID=""
MIGRATE_RESULT="skipped"
NEW_TAG="$SNAP_TAG"

cx() {  # compose exec shortcut on server
	rssh "cd '$REMOTE_DIR' && sudo docker compose $CFILES $*"
}

if [ "$CLASS" = "full" ]; then
	# ---- full image build (base/deps/infra changes only) ----
	NEW_TAG="deploy-$(date -u +%Y%m%d)-$SHORT"
	BUST="deploy-$SHORT-$(date -u +%s)"
	OPS="$OPS|image-build:$NEW_TAG"
	log "building image $NEW_TAG (full path)"
	if rssh_read "ps aux | grep -q '[d]ocker build .*--tag realtyna-erpnext-hrms:$NEW_TAG '"; then
		fail "image build is still running; refusing to activate or start another build"
	else
		PROBE_STATUS=$?
		[ "$PROBE_STATUS" = "1" ] || fail "cannot verify build process state"
	fi
	if [ "$RESUME_BUILD" = "1" ]; then
		log "resuming completed image build (digest and completion proof required)"
	else
		rssh "cd '$REMOTE_DIR' && setsid nohup sudo docker build --progress=plain --secret id=apps_json,src=/tmp/apps-timer.json --build-arg FRAPPE_PATH=https://github.com/frappe/frappe --build-arg FRAPPE_BRANCH=v16.18.3 --build-arg CACHE_BUST=$BUST --tag realtyna-erpnext-hrms:$NEW_TAG -f images/custom/Containerfile . > '$REMOTE_DIR/$LOG_DIR/build-$NEW_TAG.log' 2>&1 < /dev/null & echo started" \
			|| fail "build launch failed"
		for _ in $(seq 1 120); do
			sleep 30
			if rssh_read "ps aux | grep -q '[C]ACHE_BUST=$BUST'" 2>/dev/null; then continue; else PROBE_STATUS=$?; fi
			[ "$PROBE_STATUS" = "1" ] && break
			log "build status unavailable; preserving the running build and retrying"
		done
	fi
	IMAGE_ID="$(rssh_read "sudo docker image inspect 'realtyna-erpnext-hrms:$NEW_TAG' --format '{{.Id}}'")" \
		|| fail "image build incomplete — see $LOG_DIR/build-$NEW_TAG.log on server"
	rssh_read "cat '$REMOTE_DIR/$LOG_DIR/build-$NEW_TAG.log'" \
		| python3 "$SCRIPT_DIR/verify_image_build.py" --image-id "$IMAGE_ID" --tag "realtyna-erpnext-hrms:$NEW_TAG" \
		|| fail "image build completion/digest proof failed — refusing activation"
	log "image built: $NEW_TAG"
	rssh "cp '$REMOTE_DIR/.env' '$REMOTE_DIR/.env.backup-deploy-$DEPLOY_ID' && sed -i 's/^CUSTOM_TAG=.*/CUSTOM_TAG=$NEW_TAG/' '$REMOTE_DIR/.env'"
	OPS="$OPS|tag-flip:$SNAP_TAG->$NEW_TAG"
fi

NEED_MIGRATE=0
[ "$HAS_SCHEMA" = "1" ] && NEED_MIGRATE=1

if [ "$NEED_MIGRATE" = "1" ]; then
	BACKUP_OUT="$(cx exec -T backend bench --site $SITE backup 2>&1)" \
		|| fail "pre-migration backup command failed — refusing to proceed"
	BACKUP_ID="$(printf '%s\n' "$BACKUP_OUT" | grep -o '[0-9_]*-frontend-database.sql.gz' | head -n 1)"
	[ -n "$BACKUP_ID" ] || fail "pre-migration backup produced no file — refusing to proceed"
	OPS="$OPS|backup:$BACKUP_ID"
	log "backup ok: $BACKUP_ID"
fi

log "activating release (recreate: $SERVICES)"
cx up -d --force-recreate --no-deps $SERVICES >/dev/null \
	|| fail "container recreate failed"
OPS="$OPS|recreate:$SERVICES"
rssh "cd '$REMOTE_DIR' && IDS=\$(sudo docker compose $CFILES ps -q $SERVICES) && test -n \"\$IDS\" && sudo docker inspect \$IDS" \
	| python3 "$SCRIPT_DIR/verify_release_mounts.py" --release "$RELEASES_DIR/$TARGET" \
	|| fail "active release mounts do not match the exact target — refusing migration/state advance"

if [ "$NEED_MIGRATE" = "1" ]; then
	if MIGRATE_OUT="$(cx exec -T backend bench --site $SITE migrate 2>&1)"; then
		MIGRATE_RESULT="ok"
	else
		# Automatic recovery: code back to previous release, state untouched.
		log "MIGRATE FAILED — recovering previous release $ACTIVE_SHA"
		rssh "cp '$OVERRIDE_BACKUP' '$REMOTE_DIR/$OVERRIDE_FILE' && sed -i 's/^CUSTOM_TAG=.*/CUSTOM_TAG=$SNAP_TAG/' '$REMOTE_DIR/.env'" \
			|| fail "migrate failed and previous release configuration could not be restored"
		cx up -d --force-recreate --no-deps $SERVICES >/dev/null || true
		printf '%s\n' "$MIGRATE_OUT" | tail -n 5 >&2
		fail "migrate failed; code rolled back to $ACTIVE_SHA (DB may be partially migrated — backup $BACKUP_ID recorded; inspect tabPatch Log)"
	fi
	OPS="$OPS|migrate:ok"
fi

cx exec -T backend bench --site $SITE clear-cache >/dev/null \
	|| fail "clear-cache failed"
OPS="$OPS|clear-cache"

# ------------------------------------------------------- 9. health gate -----
log "health verification (polling, no blind sleeps)"
HEALTH="pending"
for _ in $(seq 1 18); do
	sleep 10
	if rssh "cd '$REMOTE_DIR' && sudo docker compose $CFILES ps --format '{{.Name}} {{.State}}' 2>/dev/null | grep -E 'backend-1|frontend-1|websocket-1|scheduler-1|queue-short-1|queue-long-1' | grep -qv 'running'" 2>/dev/null; then
		continue
	fi
	UP="$(rssh "curl -s -o /dev/null -w '%{http_code}' --max-time 8 'http://127.0.0.1:8080/hrms'")"
	PONG="$(rssh "curl -s --max-time 8 'http://127.0.0.1:8080/api/method/frappe.ping'")"
	RD="$(rssh "sudo docker exec frappe_docker-redis-cache-1 redis-cli ping 2>/dev/null; sudo docker exec frappe_docker-redis-queue-1 redis-cli ping 2>/dev/null")"
	DBOK="$(rssh "RPW=\$(grep MARIADB_ROOT_PASSWORD '$REMOTE_DIR/pwd.yml' | head -n 1 | cut -d: -f2 | tr -d '[:space:]'); sudo docker exec frappe_docker-db-1 mariadb -uroot -p\$RPW -N -e 'SELECT 1' 2>/dev/null")"
	ASSET="$(rssh "REL='$RELEASES_DIR/$TARGET/hrms/public/frontend/index.html'; SRV=\$(sudo docker ps --format '{{.Names}}' | grep 'frontend-1' | head -n 1); WANT=\$(grep -o 'assets/index-[^\"]*\.js' \"\$REL\" | head -n 1); sudo docker exec \"\$SRV\" test -f \"/home/frappe/frappe-bench/sites/assets/hrms/frontend/\$WANT\" && echo ok")"
	if [ "$UP" = "200" ] && printf '%s' "$PONG" | grep -q pong \
		&& [ "$RD" = "$(printf 'PONG\nPONG')" ] && [ "$DBOK" = "1" ] && [ "$ASSET" = "ok" ]; then
		HEALTH="ok"
		break
	fi
done
[ "$HEALTH" = "ok" ] || fail "health verification failed — previous release preserved, state NOT advanced"
OPS="$OPS|health:ok"
log "healthy"

# ------------------------------------------------------- 10. state+history --
FINISH_EPOCH="$(date +%s)"
DUR=$(( FINISH_EPOCH - START_EPOCH ))
NOW_UTC="$(python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))')"
STARTED_UTC="$(python3 -c 'import datetime; print(datetime.datetime.fromtimestamp('"$START_EPOCH"', datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))')"
# Pre-escape once: json.dumps already includes the surrounding quotes.
REASON_JSON="$(printf '%s' "$REASON" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
NEW_STATE="$(python3 -c 'import json; print(json.dumps({"active_sha":"'"$TARGET"'","prev_sha":"'"$ACTIVE_SHA"'","class":"'"$CLASS"'","reason":'"$REASON_JSON"',"time_utc":"'"$NOW_UTC"'","image_tag":"'"$NEW_TAG"'","backup":"'"$BACKUP_ID"'","migrate":"'"$MIGRATE_RESULT"'","health":"ok","mode":"mount","deploy_id":"'"$DEPLOY_ID"'"}))')"
rssh "printf '%s' '$NEW_STATE' > '$REMOTE_DIR/$STATE_FILE.tmp' && mv '$REMOTE_DIR/$STATE_FILE.tmp' '$REMOTE_DIR/$STATE_FILE'"
REPORT="$(python3 -c 'import json,time; print(json.dumps({"deploy_id":"'"$DEPLOY_ID"'","target_sha":"'"$TARGET"'","previous_sha":"'"$ACTIVE_SHA"'","class":"'"$CLASS"'","reason":'"$REASON_JSON"',"started_utc":"'"$STARTED_UTC"'","finished_utc":"'"$NOW_UTC"'","operations":"'"$OPS"'","backup_id":"'"$BACKUP_ID"'","migration_result":"'"$MIGRATE_RESULT"'","health_result":"ok","rollback_actions":"none","final_sha":"'"$TARGET"'","duration_s":'"$DUR"'}))')"
rssh "printf '%s\n' '$REPORT' >> '$REMOTE_DIR/$HISTORY_DIR/deploys.jsonl'; tail -n 30 '$REMOTE_DIR/$HISTORY_DIR/deploys.jsonl' > '$REMOTE_DIR/$HISTORY_DIR/tmp' && mv '$REMOTE_DIR/$HISTORY_DIR/tmp' '$REMOTE_DIR/$HISTORY_DIR/deploys.jsonl'"
log "state advanced → $TARGET"

# ------------------------------------------------------- 11. retention ------
# Keep: active + previous releases (dirs), live + previous 2 image tags.
# Everything computed from explicit keep-sets; running images never touched.
rssh "cd '$RELEASES_DIR' && ls -1t | tail -n +4 | while read -r d; do if [ \"\$d\" != '$TARGET' ] && [ \"\$d\" != '$ACTIVE_SHA' ]; then chmod -R u+w \"\$d\" && rm -rf \"\$d\"; fi; done"
KEEP_TAGS="$NEW_TAG $SNAP_TAG $(rssh "sudo docker images 'realtyna-erpnext-hrms' --format '{{.Tag}}' | grep -v -E '^($NEW_TAG|$SNAP_TAG)$' | head -n 1")"
for t in $(rssh "sudo docker images 'realtyna-erpnext-hrms' --format '{{.Tag}}'"); do
	keep=0
	for k in $KEEP_TAGS; do [ "$t" = "$k" ] && keep=1; done
	if [ "$keep" = "0" ]; then
		rssh "sudo docker rmi 'realtyna-erpnext-hrms:$t' >/dev/null 2>&1" || true
	fi
done
# Builder cache only when disk is actually tight; bench backups keep newest 7;
# server build logs keep newest 5. .env backups are bytes — always kept.
rssh "if [ \$(df / | tail -n 1 | awk '{print \$5}' | tr -d %) -gt $DISK_PRUNE_THRESHOLD ]; then sudo docker builder prune -f >/dev/null 2>&1 || true; fi"
rssh "sudo docker exec frappe_docker-backend-1 sh -c 'ls -t /home/frappe/frappe-bench/sites/$SITE/private/backups/*-database.sql.gz 2>/dev/null' | tail -n +8 | while read -r b; do sudo docker exec frappe_docker-backend-1 rm -f \"\$b\"; done"
rssh "ls -t '$REMOTE_DIR/$LOG_DIR'/build-*.log 2>/dev/null | tail -n +6 | xargs -r rm -f"
log "retention applied"

# ------------------------------------------------------- 12. report ---------
DUR2=$(( $(date +%s) - START_EPOCH ))
log "DEPLOY OK class=$CLASS target=$TARGET duration=${DUR2}s ops=${OPS#|}"
