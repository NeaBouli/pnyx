#!/bin/bash
# Off-Site Backup to Hetzner Storage Box (NEA-65)
# Cron: 0 4 * * * /opt/ekklesia/app/scripts/backup-offsite.sh >> /var/log/ekklesia-backup.log 2>&1
#
# Prerequisites:
#   1. Hetzner Storage Box ordered (BX11 = 1TB, ~3.81 EUR/mo)
#   2. SSH key uploaded: ssh-copy-id -p 23 -s uXXXXXX@uXXXXXX.your-storagebox.de
#   3. Export STORAGE_BOX_USER and STORAGE_BOX_HOST in the cron environment
#   4. Optional fallback target: set STORAGE_BOX_PORT, STORAGE_BOX_PATH, STORAGE_BOX_IDENTITY_FILE
#
# What gets backed up:
#   - PostgreSQL full dump (ekklesia_prod)
#   - Redis RDB snapshot
#   - Arweave wallet (encrypted)
#   - Uploaded assets
#   - Alembic migration state
#
# Retention: 30 daily, 12 weekly (Sunday), 6 monthly (1st)

set +x
set -euo pipefail
# Keep the optional secret URI out of every child process environment.
export -n BACKUP_DATABASE_URL
# shellcheck source=scripts/lib/backup-encrypt.sh
source "$(dirname "$0")/lib/backup-encrypt.sh"

# ─── Config ───────────────────────────────────────────────────────────────────
STORAGE_BOX_USER="${STORAGE_BOX_USER:-}"
STORAGE_BOX_HOST="${STORAGE_BOX_HOST:-}"
STORAGE_BOX_PORT="${STORAGE_BOX_PORT:-23}"
STORAGE_BOX_PATH="${STORAGE_BOX_PATH:-/backups/ekklesia}"
STORAGE_BOX_IDENTITY_FILE="${STORAGE_BOX_IDENTITY_FILE:-}"
REMOTE_DIR="${STORAGE_BOX_PATH}"

LOCAL_BACKUP_DIR="/opt/backups/ekklesia"
DB_NAME="${POSTGRES_DB:-ekklesia_prod}"
DB_USER="${POSTGRES_USER:-ekklesia}"
DB_CONTAINER="ekklesia-db"
# Empty/unset retains the existing local-socket user. The optional URI goes
# only to the parser's stdin; Docker/libpq receive separate PG* components.
export PGUSER="${DB_USER}" PGDATABASE="${DB_NAME}"
db_exec() {
  if [[ -n "${BACKUP_DATABASE_URL:-}" ]]; then
    printf '%s' "${BACKUP_DATABASE_URL}" | python3 "$(dirname "$0")/lib/backup-db.py" "${DB_CONTAINER}" "$@"
  else
    docker exec --env PGUSER --env PGDATABASE "${DB_CONTAINER}" "$@"
  fi
}
REDIS_CONTAINER="ekklesia-redis"

DATE=$(date +%Y-%m-%d)
DAY_OF_WEEK=$(date +%u)  # 7=Sunday
DAY_OF_MONTH=$(date +%d)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="ekklesia-backup-${TIMESTAMP}.tar.gz"

LOG_PREFIX="[BACKUP ${DATE}]"

echo "${LOG_PREFIX} Starting off-site backup..."

if [ -z "${STORAGE_BOX_USER}" ] || [ -z "${STORAGE_BOX_HOST}" ]; then
  echo "${LOG_PREFIX} ERROR: STORAGE_BOX_USER and STORAGE_BOX_HOST must be set" >&2
  exit 2
fi

# "-b -" (batch from stdin) makes sftp exit non-zero when a command such as
# "put" fails; "-mkdir" lines stay tolerant. Without it a failed upload looked
# successful (review of #605).
SFTP_OPTS=(-P "${STORAGE_BOX_PORT}" -o BatchMode=yes)
if [ -n "${STORAGE_BOX_IDENTITY_FILE}" ]; then
  SFTP_OPTS+=(-i "${STORAGE_BOX_IDENTITY_FILE}")
fi

# ─── 1. PostgreSQL Dump ──────────────────────────────────────────────────────
echo "${LOG_PREFIX} Dumping PostgreSQL..."
mkdir -p "${LOCAL_BACKUP_DIR}/daily"
db_exec pg_dump --no-password -Fc \
  > "${LOCAL_BACKUP_DIR}/daily/db-${TIMESTAMP}.dump"

# ─── 2. Redis Snapshot ───────────────────────────────────────────────────────
echo "${LOG_PREFIX} Saving Redis snapshot..."
docker exec "${REDIS_CONTAINER}" redis-cli BGSAVE >/dev/null 2>&1 || true
sleep 2
if ! docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "${LOCAL_BACKUP_DIR}/daily/redis-${TIMESTAMP}.rdb" 2>/dev/null; then
  echo "${LOG_PREFIX} Redis dump unavailable; writing empty marker"
  : > "${LOCAL_BACKUP_DIR}/daily/redis-${TIMESTAMP}.rdb"
fi

# ─── 3. Alembic State ────────────────────────────────────────────────────────
echo "${LOG_PREFIX} Capturing migration state..."
db_exec psql --no-psqlrc --no-password \
  -c "SELECT version_num FROM alembic_version;" \
  > "${LOCAL_BACKUP_DIR}/daily/alembic-${TIMESTAMP}.txt" 2>/dev/null || \
  echo "alembic_version unavailable" > "${LOCAL_BACKUP_DIR}/daily/alembic-${TIMESTAMP}.txt"

# ─── 4. Pack Everything ──────────────────────────────────────────────────────
echo "${LOG_PREFIX} Creating archive..."
tar -czf "${LOCAL_BACKUP_DIR}/${BACKUP_FILE}" \
  -C "${LOCAL_BACKUP_DIR}/daily" \
  "db-${TIMESTAMP}.dump" \
  "redis-${TIMESTAMP}.rdb" \
  "alembic-${TIMESTAMP}.txt" \
  2>/dev/null

# ─── 4b. Encrypt (ADR-007 S3; active once BACKUP_AGE_RECIPIENT is set) ───────
UPLOAD_PATH=$(select_upload_file "${LOCAL_BACKUP_DIR}/${BACKUP_FILE}")
UPLOAD_FILE=$(basename "${UPLOAD_PATH}")

# ─── 5. Upload to off-site target ────────────────────────────────────────────
echo "${LOG_PREFIX} Uploading ${UPLOAD_FILE} to off-site target..."
sftp -b - "${SFTP_OPTS[@]}" "${STORAGE_BOX_USER}@${STORAGE_BOX_HOST}" <<SFTP
  -mkdir ${REMOTE_DIR}
  -mkdir ${REMOTE_DIR}/daily
  -mkdir ${REMOTE_DIR}/weekly
  -mkdir ${REMOTE_DIR}/monthly
  put ${UPLOAD_PATH} ${REMOTE_DIR}/daily/${UPLOAD_FILE}
SFTP

# ─── 6. Weekly + Monthly Copies ──────────────────────────────────────────────
if [ "${DAY_OF_WEEK}" = "7" ]; then
  echo "${LOG_PREFIX} Sunday — creating weekly copy..."
  sftp -b - "${SFTP_OPTS[@]}" "${STORAGE_BOX_USER}@${STORAGE_BOX_HOST}" <<SFTP
    put ${UPLOAD_PATH} ${REMOTE_DIR}/weekly/${UPLOAD_FILE}
SFTP
fi

if [ "${DAY_OF_MONTH}" = "01" ]; then
  echo "${LOG_PREFIX} 1st of month — creating monthly copy..."
  sftp -b - "${SFTP_OPTS[@]}" "${STORAGE_BOX_USER}@${STORAGE_BOX_HOST}" <<SFTP
    put ${UPLOAD_PATH} ${REMOTE_DIR}/monthly/${UPLOAD_FILE}
SFTP
fi

# ─── 7. Local Cleanup (30 days) ──────────────────────────────────────────────
echo "${LOG_PREFIX} Cleaning local backups older than 30 days..."
find "${LOCAL_BACKUP_DIR}/daily" -name "*.dump" -mtime +30 -delete 2>/dev/null || true
find "${LOCAL_BACKUP_DIR}/daily" -name "*.rdb" -mtime +30 -delete 2>/dev/null || true
find "${LOCAL_BACKUP_DIR}/daily" -name "*.txt" -mtime +30 -delete 2>/dev/null || true
find "${LOCAL_BACKUP_DIR}" -name "ekklesia-backup-*.tar.gz" -mtime +30 -delete 2>/dev/null || true
find "${LOCAL_BACKUP_DIR}" -name "ekklesia-backup-*.tar.gz.age" -mtime +30 -delete 2>/dev/null || true

# ─── 8. Remote Cleanup ───────────────────────────────────────────────────────
# Remote retention managed by Storage Box sub-account or manual cron
# Daily: 30 files, Weekly: 12, Monthly: 6

ARCHIVE_SIZE=$(du -sh "${LOCAL_BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
echo "${LOG_PREFIX} Done. Archive: ${BACKUP_FILE} (${ARCHIVE_SIZE})"
echo "${LOG_PREFIX} Remote: ${STORAGE_BOX_USER}@${STORAGE_BOX_HOST}:${REMOTE_DIR}/daily/${UPLOAD_FILE}"
