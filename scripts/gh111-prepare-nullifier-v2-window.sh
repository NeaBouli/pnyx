#!/usr/bin/env bash
# Prepare the GH#111 Nullifier v2 operator window without activating v2.
#
# This script is intended to run on the production host. It creates a fresh
# evidence/backup directory, captures read-only preflight artifacts, and runs
# the isolated v2 FastAPI lifespan probe. It does not edit .env.production.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ekklesia/app}"
ENV_FILE="${ENV_FILE:-/opt/ekklesia/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker/docker-compose.prod.yml}"
TS="${GH111_TS:-$(date -u +%Y%m%d_%H%M%S)}"
BACKUP_DIR="${BACKUP_DIR:-/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_${TS}}"

cd "$APP_DIR"
mkdir -p "$BACKUP_DIR"

echo "GH111_BACKUP_DIR=$BACKUP_DIR" | tee "$BACKUP_DIR/README.txt"
echo "GH111_STARTED_AT_UTC=$TS" | tee -a "$BACKUP_DIR/README.txt"
echo "GH111_APP_HEAD=$(git rev-parse --short HEAD)" | tee -a "$BACKUP_DIR/README.txt"

echo "[1/6] Monitor preflight"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T monitor \
  python /app/monitor.py --once | tee "$BACKUP_DIR/monitor_once.txt"

echo "[2/6] KDF env plan (read-only)"
python3 apps/api/scripts/gh111_kdf_env_guard.py plan \
  --env-file "$ENV_FILE" \
  --target v2 | tee "$BACKUP_DIR/kdf_env_plan_v2.json"

echo "[3/6] Identity KDF snapshot/preflight"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api \
  python scripts/gh111_nullifier_v2_canary_check.py snapshot --preflight \
  --output /tmp/gh111_before_snapshot.json \
  --report-output /tmp/gh111_preflight_report.json \
  | tee "$BACKUP_DIR/preflight_stdout.json"
docker cp ekklesia-api:/tmp/gh111_before_snapshot.json "$BACKUP_DIR/gh111_before_snapshot.json"
docker cp ekklesia-api:/tmp/gh111_preflight_report.json "$BACKUP_DIR/gh111_preflight_report.json"

echo "[4/6] identity_records/audit_log/alembic backup"
docker exec -i ekklesia-db sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" --table=identity_records --table=audit_log --table=alembic_version' \
  > "$BACKUP_DIR/identity_records_audit_alembic.sql"

echo "[5/6] Isolated v2 lifespan probe (read-only)"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api \
  env PYTHONPATH=/app:/packages/crypto IDENTITY_NULLIFIER_KDF_VERSION=v2 python - <<'PY' \
  | tee "$BACKUP_DIR/v2_lifespan_probe.txt"
from fastapi.testclient import TestClient
import main

with TestClient(main.app) as c:
    r = c.get("/health")
    r.raise_for_status()
    print(r.json()["status"])
PY

echo "[6/6] Checksums"
find "$BACKUP_DIR" -type f ! -name SHA256SUMS -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  > "$BACKUP_DIR/SHA256SUMS"

echo "GH111_PREPARED=1"
echo "GH111_BACKUP_DIR=$BACKUP_DIR"
echo "GH111_NEXT_STEP=Use GH111_NULLIFIER_V2_CANARY_RUNBOOK.md Activation Window only when Gio is ready with S10 and real HLR verification."
