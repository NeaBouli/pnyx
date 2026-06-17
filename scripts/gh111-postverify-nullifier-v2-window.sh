#!/usr/bin/env bash
# Read-only post-verification helper for GH#111 Nullifier v2.
#
# Run this only after:
#   1. the guarded activate-v2 helper succeeded, and
#   2. Gio completed the real S10 VerifyScreen HLR verification.
#
# The helper does not edit env, does not write DB state, and does not trigger
# HLR. It gathers the compare verdict, monitor output, and checksums into the
# active BACKUP_DIR so the operator can decide keep-v2 vs rollback-v1.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ekklesia/app}"
ENV_FILE="${ENV_FILE:-/opt/ekklesia/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker/docker-compose.prod.yml}"
MODE="${1:-}"

usage() {
  cat <<'EOF'
Usage:
  BACKUP_DIR=/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_... \
  scripts/gh111-postverify-nullifier-v2-window.sh existing-reregistration

  BACKUP_DIR=/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_... \
  scripts/gh111-postverify-nullifier-v2-window.sh new-registration

Safety:
  - read-only helper; does not edit env, DB, or trigger HLR
  - requires package_check.json with ok=true
  - writes compare/monitor/checksum artifacts into BACKUP_DIR
EOF
}

require_backup_dir() {
  if [[ -z "${BACKUP_DIR:-}" ]]; then
    echo "ERROR: set BACKUP_DIR to the active GH#111 evidence directory" >&2
    exit 2
  fi
  if [[ ! -d "$BACKUP_DIR" ]]; then
    echo "ERROR: BACKUP_DIR does not exist: $BACKUP_DIR" >&2
    exit 2
  fi
}

require_mode() {
  case "$MODE" in
    existing-reregistration|new-registration)
      ;;
    *)
      echo "ERROR: mode must be existing-reregistration or new-registration" >&2
      exit 2
      ;;
  esac
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

require_before_snapshot() {
  if [[ ! -s "$BACKUP_DIR/gh111_before_snapshot.json" ]]; then
    echo "ERROR: missing gh111_before_snapshot.json in $BACKUP_DIR" >&2
    exit 2
  fi
}

run_compare() {
  cd "$APP_DIR"
  docker cp "$BACKUP_DIR/gh111_before_snapshot.json" ekklesia-api:/tmp/gh111_before_snapshot.json
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api \
    python scripts/gh111_nullifier_v2_canary_check.py compare \
      --before /tmp/gh111_before_snapshot.json \
      --mode "$MODE" \
      --report-output /tmp/gh111_compare_report.json \
    | tee "$BACKUP_DIR/gh111_compare_stdout_${MODE}.json"
  docker cp ekklesia-api:/tmp/gh111_compare_report.json "$BACKUP_DIR/gh111_compare_report_${MODE}.json"
}

run_monitor_once() {
  cd "$APP_DIR"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T monitor \
    python /app/monitor.py --once 2>&1 \
    | tee "$BACKUP_DIR/monitor_after_postverify_${MODE}.txt"
}

write_checksums() {
  find "$BACKUP_DIR" -type f ! -name SHA256SUMS -print0 \
    | sort -z \
    | xargs -0 sha256sum \
    > "$BACKUP_DIR/SHA256SUMS"
}

case "$MODE" in
  -h|--help|help|"")
    usage
    ;;
  *)
    require_backup_dir
    require_mode
    require_package_ok
    require_before_snapshot
    run_compare
    run_monitor_once
    write_checksums
    echo "GH111_POSTVERIFY_CHECK_COMPLETE=1"
    echo "GH111_POSTVERIFY_MODE=$MODE"
    echo "NEXT: If compare ok=true and monitor is clean, decide keep v2 or run rollback-v1 helper."
    ;;
esac
