#!/usr/bin/env bash
# Read-only GH#111 Nullifier v2 readiness/status helper.
#
# Intended to run on the production host. It does not edit env files, does not
# write DB state, does not rebuild containers, and does not trigger HLR.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ekklesia/app}"
ENV_FILE="${ENV_FILE:-/opt/ekklesia/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker/docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-}"

cd "$APP_DIR"

latest_backup_dir() {
  if [[ -n "$BACKUP_DIR" ]]; then
    printf '%s\n' "$BACKUP_DIR"
    return
  fi
  find /opt/ekklesia/backups -maxdepth 1 -type d -name 'pre_gh111_nullifier_v2_canary_*' \
    2>/dev/null | sort | tail -n 1
}

read_kdf_env() {
  python3 - "$ENV_FILE" <<'PY'
import sys
from pathlib import Path

env_file = Path(sys.argv[1])
value = "unset"
if env_file.exists():
    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        if key.strip() == "IDENTITY_NULLIFIER_KDF_VERSION":
            value = raw_value.strip().strip('"').strip("'") or "unset"
print(value)
PY
}

json_field() {
  local file_path="$1"
  local expression="$2"
  python3 - "$file_path" "$expression" <<'PY'
import json
import sys

path, expression = sys.argv[1:3]
payload = json.load(open(path))
if expression == "ok":
    print(str(payload.get("ok")).lower())
elif expression == "blockers":
    print(json.dumps(payload.get("blockers", []), sort_keys=True))
elif expression == "warnings":
    print(json.dumps(payload.get("warnings", []), sort_keys=True))
elif expression == "preflight_blockers":
    print(json.dumps(payload.get("preflight_blockers", []), sort_keys=True))
elif expression == "snapshot":
    snapshot = payload.get("snapshot", {})
    print(json.dumps(snapshot, sort_keys=True))
else:
    raise SystemExit(f"unknown expression: {expression}")
PY
}

safe_json_field() {
  local file_path="$1"
  local expression="$2"
  local fallback="$3"
  if [[ ! -s "$file_path" ]]; then
    printf '%s\n' "$fallback"
    return
  fi
  if ! json_field "$file_path" "$expression" 2>/dev/null; then
    printf '%s\n' "$fallback"
  fi
}

echo "GH111_STATUS_READ_ONLY=1"
echo "APP_HEAD=$(git rev-parse --short HEAD)"
KDF_ENV_VALUE="$(read_kdf_env)"
echo "KDF_ENV=$KDF_ENV_VALUE"

if curl -fsS --max-time 10 https://api.ekklesia.gr/health >/dev/null; then
  API_HEALTH_VALUE="ok"
  echo "API_HEALTH=ok"
else
  API_HEALTH_VALUE="failed"
  echo "API_HEALTH=failed"
fi

RESOLVED_BACKUP_DIR="$(latest_backup_dir || true)"
if [[ -z "$RESOLVED_BACKUP_DIR" ]]; then
  echo "PACKAGE_DIR=missing"
  PACKAGE_OK_VALUE="false"
  echo "PACKAGE_OK=false"
  echo "PACKAGE_BLOCKERS=[\"backup_dir_missing\"]"
  echo "PACKAGE_WARNINGS=[]"
else
  echo "PACKAGE_DIR=$RESOLVED_BACKUP_DIR"
  PACKAGE_JSON="$(mktemp)"
  if python3 apps/api/scripts/gh111_preflight_package_check.py \
    --backup-dir "$RESOLVED_BACKUP_DIR" >"$PACKAGE_JSON"; then
    PACKAGE_OK_VALUE="$(safe_json_field "$PACKAGE_JSON" ok false)"
  else
    PACKAGE_OK_VALUE="false"
  fi
  echo "PACKAGE_OK=$PACKAGE_OK_VALUE"
  echo "PACKAGE_BLOCKERS=$(safe_json_field "$PACKAGE_JSON" blockers '["package_check_unreadable"]')"
  echo "PACKAGE_WARNINGS=$(safe_json_field "$PACKAGE_JSON" warnings '[]')"
  rm -f "$PACKAGE_JSON"
fi

LIVE_JSON="$(mktemp)"
set +e
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api \
  python scripts/gh111_nullifier_v2_canary_check.py snapshot --preflight \
  >"$LIVE_JSON"
LIVE_EXIT=$?
set -e
if [[ "$LIVE_EXIT" == "0" ]]; then
  echo "LIVE_PREFLIGHT_OK=true"
else
  echo "LIVE_PREFLIGHT_OK=false"
fi
echo "LIVE_PREFLIGHT_BLOCKERS=$(safe_json_field "$LIVE_JSON" preflight_blockers '["live_snapshot_unreadable"]')"
echo "LIVE_SNAPSHOT=$(safe_json_field "$LIVE_JSON" snapshot '{}')"
rm -f "$LIVE_JSON"

if [[ "$KDF_ENV_VALUE" == "v1" && "$LIVE_EXIT" == "0" && "$PACKAGE_OK_VALUE" == "true" && "$API_HEALTH_VALUE" == "ok" ]]; then
  echo "GH111_NEXT_STEP=prepare-or-activate-only-when-Gio-ready-with-S10-and-real-HLR"
else
  echo "GH111_NEXT_STEP=review-status-before-any-action"
fi
