#!/usr/bin/env bash
set -euo pipefail
# Run on the deployment host. This stack never shares production data,
# networks, host ports, credentials, or application container names.
ROOT=${1:?Pass a dedicated QA directory containing the candidate app}
IMAGE=${2:?Pass the verified installed application image}
PREFIX=hrms-qa-20261002
case "$ROOT" in /home/ubuntu/hrms-qa-20261002) ;; *) echo "Unexpected QA directory" >&2; exit 1;; esac
test -f "$ROOT/app/hrms/hooks.py"
sudo docker network inspect "$PREFIX" >/dev/null 2>&1 || sudo docker network create --internal "$PREFIX" >/dev/null
start() {
  local name=$1; shift
  sudo docker inspect "$name" >/dev/null 2>&1 || sudo docker run -d --name "$name" --network "$PREFIX" "$@" >/dev/null
}
start "$PREFIX-db" --network-alias qa-db -e MARIADB_ROOT_PASSWORD=isolated-qa-only-20261002 -e MARIADB_ROOT_HOST=% mariadb:11.8
start "$PREFIX-redis" --network-alias qa-redis redis:6.2-alpine
start "$PREFIX-app" -v "$PREFIX-sites:/home/frappe/frappe-bench/sites" -v "$PREFIX-logs:/home/frappe/frappe-bench/logs" -v "$ROOT/app:/home/frappe/frappe-bench/apps/hrms:ro" --entrypoint bash "$IMAGE" -c 'sleep infinity'
for _ in $(seq 1 60); do
  if sudo docker exec "$PREFIX-db" mariadb-admin ping -p'isolated-qa-only-20261002' --silent >/dev/null 2>&1; then break; fi
  sleep 2
done
sudo docker exec "$PREFIX-app" bench set-config -g db_host qa-db
sudo docker exec "$PREFIX-app" bench set-config -g redis_cache redis://qa-redis:6379/0
sudo docker exec "$PREFIX-app" bench set-config -g redis_queue redis://qa-redis:6379/1
sudo docker exec "$PREFIX-app" bench set-config -g redis_socketio redis://qa-redis:6379/2
if ! sudo docker exec "$PREFIX-app" test -f sites/qa.local/site_config.json; then
  sudo docker exec "$PREFIX-app" bench new-site qa.local --db-root-password isolated-qa-only-20261002 --admin-password isolated-qa-only-20261002 --mariadb-user-host-login-scope %
fi
sudo docker exec "$PREFIX-app" bench --site qa.local install-app erpnext
sudo docker exec "$PREFIX-app" bench --site qa.local install-app hrms --force
sudo docker exec "$PREFIX-app" bench --site qa.local set-config allow_tests true
sudo docker exec "$PREFIX-app" bench --site qa.local set-config mute_emails true
sudo docker exec "$PREFIX-app" bench --site qa.local set-config pause_scheduler true
sudo docker exec "$PREFIX-app" bench --site qa.local migrate
echo "Isolated QA ready; no host ports were exposed."
