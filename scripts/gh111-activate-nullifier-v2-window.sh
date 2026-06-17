#!/usr/bin/env bash
# Guarded GH#111 Nullifier v2 activation/rollback helper.
#
# This script is intended for the explicit real operator window only. It never
# runs HLR itself; Gio must still perform the real S10 VerifyScreen step after
# a successful activate-v2 action. The script exists to make the env flip,
# rebuild, health retry, and rollback path consistent and auditable.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ekklesia/app}"
ENV_FILE="${ENV_FILE:-/opt/ekklesia/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker/docker-compose.prod.yml}"
ACTION="${1:-}"
ACTIVATE_CONFIRM_TOKEN="GH111-ACTIVATE-V2"
ROLLBACK_CONFIRM_TOKEN="GH111-ROLLBACK-V1"
KDF_WRITE_CONFIRM_TOKEN="GH111-KDF-WRITE"
KDF_MUTATED=0

usage() {
  cat <<'EOF'
Usage:
  BACKUP_DIR=/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_... \
  GH111_OPERATOR_CONFIRM=GH111-ACTIVATE-V2 \
  scripts/gh111-activate-nullifier-v2-window.sh activate-v2

  BACKUP_DIR=/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_... \
  GH111_OPERATOR_CONFIRM=GH111-ROLLBACK-V1 \
  scripts/gh111-activate-nullifier-v2-window.sh rollback-v1

Safety:
  - activate-v2 requires package_check.json with ok=true.
  - both actions require an exact confirmation token.
  - HLR/S10 verification is never triggered by this script.
EOF
}

require_backup_dir() {
  if [[ -z "${BACKUP_DIR:-}" ]]; then
    echo "ERROR: set BACKUP_DIR to the fresh GH#111 preflight package directory" >&2
    exit 2
  fi
  if [[ ! -d "$BACKUP_DIR" ]]; then
    echo "ERROR: BACKUP_DIR does not exist: $BACKUP_DIR" >&2
    exit 2
  fi
}

require_confirm() {
  local expected="$1"
  if [[ "${GH111_OPERATOR_CONFIRM:-}" != "$expected" ]]; then
    echo "ERROR: set GH111_OPERATOR_CONFIRM=$expected" >&2
    exit 2
  fi
}

require_package_ok() {
  local check_json="$BACKUP_DIR/package_check.json"
  if [[ ! -s "$check_json" ]]; then
    echo "ERROR: missing package_check.json in $BACKUP_DIR" >&2
    exit 2
  fi
  python3 - "$check_json" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1]).read())
if payload.get("ok") is not True:
    print("ERROR: package_check.json ok is not true", file=sys.stderr)
    sys.exit(2)
if payload.get("blockers"):
    print("ERROR: package_check.json has blockers", file=sys.stderr)
    sys.exit(2)
PY
}

run_v2_lifespan_probe() {
  cd "$APP_DIR"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api \
    env PYTHONPATH=/app:/packages/crypto IDENTITY_NULLIFIER_KDF_VERSION=v2 python - <<'PY' 2>&1 \
    | tee "$BACKUP_DIR/v2_lifespan_probe_before_activation.txt"
from fastapi.testclient import TestClient
import main

class NoopScheduler:
    def add_job(self, *args, **kwargs):
        return None

    def start(self):
        return None

    def shutdown(self):
        return None

main.scheduler = NoopScheduler()

with TestClient(main.app) as c:
    r = c.get("/health")
    r.raise_for_status()
    print(r.json()["status"])
PY
}

write_kdf_target() {
  local target="$1"
  cd "$APP_DIR"
  python3 apps/api/scripts/gh111_kdf_env_guard.py plan \
    --env-file "$ENV_FILE" \
    --target "$target" \
    | tee "$BACKUP_DIR/kdf_env_plan_${target}_$(date -u +%Y%m%d_%H%M%S).json"
  python3 apps/api/scripts/gh111_kdf_env_guard.py write \
    --env-file "$ENV_FILE" \
    --backup-dir "$BACKUP_DIR" \
    --target "$target" \
    --confirm "$KDF_WRITE_CONFIRM_TOKEN" \
    | tee "$BACKUP_DIR/kdf_env_write_${target}_$(date -u +%Y%m%d_%H%M%S).json"
}

rebuild_api_and_wait() {
  cd "$APP_DIR"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build api

  local ok=0
  for _ in $(seq 1 45); do
    if curl -fsS https://api.ekklesia.gr/health >/dev/null; then
      ok=1
      echo "health-ok" | tee "$BACKUP_DIR/health_after_${ACTION}.txt"
      break
    fi
    sleep 2
  done
  if [[ "$ok" != "1" ]]; then
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=120 api \
      > "$BACKUP_DIR/api_logs_after_failed_${ACTION}.txt" || true
    echo "ERROR: API health did not recover after $ACTION" >&2
    exit 1
  fi
}

emergency_rollback_to_v1() {
  local exit_code=$?
  trap - ERR
  if [[ "$ACTION" == "activate-v2" && "$KDF_MUTATED" == "1" ]]; then
    echo "ERROR: activation failed after KDF mutation; attempting emergency rollback to v1" >&2
    {
      echo "GH111_EMERGENCY_ROLLBACK_STARTED_AT_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      write_kdf_target v1
      cd "$APP_DIR"
      docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build api
      for _ in $(seq 1 45); do
        if curl -fsS https://api.ekklesia.gr/health >/dev/null; then
          echo "GH111_EMERGENCY_ROLLBACK_HEALTH=ok"
          exit "$exit_code"
        fi
        sleep 2
      done
      echo "GH111_EMERGENCY_ROLLBACK_HEALTH=failed"
    } 2>&1 | tee "$BACKUP_DIR/emergency_rollback_after_failed_activation.txt" || true
  fi
  exit "$exit_code"
}

run_monitor_once() {
  cd "$APP_DIR"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T monitor \
    python /app/monitor.py --once 2>&1 \
    | tee "$BACKUP_DIR/monitor_after_${ACTION}.txt"
}

case "$ACTION" in
  activate-v2)
    require_backup_dir
    require_confirm "$ACTIVATE_CONFIRM_TOKEN"
    require_package_ok
    trap emergency_rollback_to_v1 ERR
    run_v2_lifespan_probe
    write_kdf_target v2
    KDF_MUTATED=1
    rebuild_api_and_wait
    run_monitor_once
    trap - ERR
    echo "GH111_ACTIVATED_V2=1"
    echo "NEXT: Gio must perform real S10 VerifyScreen HLR verification, then run compare from the runbook."
    ;;
  rollback-v1)
    require_backup_dir
    require_confirm "$ROLLBACK_CONFIRM_TOKEN"
    write_kdf_target v1
    rebuild_api_and_wait
    run_monitor_once
    echo "GH111_ROLLED_BACK_V1=1"
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    echo "ERROR: unknown action: $ACTION" >&2
    usage >&2
    exit 2
    ;;
esac
