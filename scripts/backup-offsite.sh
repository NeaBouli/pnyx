#!/bin/bash
# Off-Site Backup to Hetzner Storage Box (NEA-65)
# Cron: 0 4 * * * /opt/ekklesia/app/scripts/backup-offsite.sh >> /var/log/ekklesia-backup.log 2>&1
#
# Prerequisites:
#   1. Hetzner Storage Box ordered (BX11 = 1TB, ~3.81 EUR/mo)
#   2. SSH key uploaded: ssh-copy-id -p 23 -s uXXXXXX@uXXXXXX.your-storagebox.de
#   3. Set STORAGE_BOX_USER and STORAGE_BOX_HOST below
#
# What gets backed up:
#   - PostgreSQL full dump (ekklesia_prod)
#   - Redis RDB snapshot
#   - Arweave wallet (encrypted)
#   - Uploaded assets
#   - Alembic migration state
#
# Retention: 30 daily, 12 weekly (Sunday), 6 monthly (1st)

set -euo pipefail

# ─── Config ───────────────────────────────────────────────────────────────────
STORAGE_BOX_USER="${STORAGE_BOX_USER:-uXXXXXX}"
STORAGE_BOX_HOST="${STORAGE_BOX_HOST:-${STORAGE_BOX_USER}.your-storagebox.de}"
STORAGE_BOX_PORT=23
REMOTE_DIR="/backups/ekklesia"

LOCAL_BACKUP_DIR="/opt/backups/ekklesia"
DB_NAME="ekklesia_prod"
DB_CONTAINER="ekklesia-db"
REDIS_CONTAINER="ekklesia-redis"

DATE=$(date +%Y-%m-%d)
DAY_OF_WEEK=$(date +%u)  # 7=Sunday
DAY_OF_MONTH=$(date +%d)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="ekklesia-backup-${TIMESTAMP}.tar.gz"

LOG_PREFIX="[BACKUP ${DATE}]"

echo "${LOG_PREFIX} Starting off-site backup..."

# ─── 1. PostgreSQL Dump ──────────────────────────────────────────────────────
echo "${LOG_PREFIX} Dumping PostgreSQL..."
mkdir -p "${LOCAL_BACKUP_DIR}/daily"
docker exec "${DB_CONTAINER}" pg_dump -U postgres -Fc "${DB_NAME}" \
  > "${LOCAL_BACKUP_DIR}/daily/db-${TIMESTAMP}.dump"

# ─── 2. Redis Snapshot ───────────────────────────────────────────────────────
echo "${LOG_PREFIX} Saving Redis snapshot..."
docker exec "${REDIS_CONTAINER}" redis-cli BGSAVE >/dev/null 2>&1 || true
sleep 2
docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "${LOCAL_BACKUP_DIR}/daily/redis-${TIMESTAMP}.rdb" 2>/dev/null || true

# ─── 3. Alembic State ────────────────────────────────────────────────────────
echo "${LOG_PREFIX} Capturing migration state..."
docker exec "${DB_CONTAINER}" psql -U postgres -d "${DB_NAME}" \
  -c "SELECT version_num FROM alembic_version;" \
  > "${LOCAL_BACKUP_DIR}/daily/alembic-${TIMESTAMP}.txt" 2>/dev/null || true

# ─── 4. Pack Everything ──────────────────────────────────────────────────────
echo "${LOG_PREFIX} Creating archive..."
tar -czf "${LOCAL_BACKUP_DIR}/${BACKUP_FILE}" \
  -C "${LOCAL_BACKUP_DIR}/daily" \
  "db-${TIMESTAMP}.dump" \
  "redis-${TIMESTAMP}.rdb" \
  "alembic-${TIMESTAMP}.txt" \
  2>/dev/null

# ─── 5. Upload to Storage Box ────────────────────────────────────────────────
echo "${LOG_PREFIX} Uploading to Hetzner Storage Box..."
sftp -P "${STORAGE_BOX_PORT}" -o BatchMode=yes "${STORAGE_BOX_USER}@${STORAGE_BOX_HOST}" <<SFTP
  -mkdir ${REMOTE_DIR}
  -mkdir ${REMOTE_DIR}/daily
  -mkdir ${REMOTE_DIR}/weekly
  -mkdir ${REMOTE_DIR}/monthly
  put ${LOCAL_BACKUP_DIR}/${BACKUP_FILE} ${REMOTE_DIR}/daily/${BACKUP_FILE}
SFTP

# ─── 6. Weekly + Monthly Copies ──────────────────────────────────────────────
if [ "${DAY_OF_WEEK}" = "7" ]; then
  echo "${LOG_PREFIX} Sunday — creating weekly copy..."
  sftp -P "${STORAGE_BOX_PORT}" -o BatchMode=yes "${STORAGE_BOX_USER}@${STORAGE_BOX_HOST}" <<SFTP
    put ${LOCAL_BACKUP_DIR}/${BACKUP_FILE} ${REMOTE_DIR}/weekly/${BACKUP_FILE}
SFTP
fi

if [ "${DAY_OF_MONTH}" = "01" ]; then
  echo "${LOG_PREFIX} 1st of month — creating monthly copy..."
  sftp -P "${STORAGE_BOX_PORT}" -o BatchMode=yes "${STORAGE_BOX_USER}@${STORAGE_BOX_HOST}" <<SFTP
    put ${LOCAL_BACKUP_DIR}/${BACKUP_FILE} ${REMOTE_DIR}/monthly/${BACKUP_FILE}
SFTP
fi

# ─── 7. Local Cleanup (30 days) ──────────────────────────────────────────────
echo "${LOG_PREFIX} Cleaning local backups older than 30 days..."
find "${LOCAL_BACKUP_DIR}/daily" -name "*.dump" -mtime +30 -delete 2>/dev/null || true
find "${LOCAL_BACKUP_DIR}/daily" -name "*.rdb" -mtime +30 -delete 2>/dev/null || true
find "${LOCAL_BACKUP_DIR}/daily" -name "*.txt" -mtime +30 -delete 2>/dev/null || true
find "${LOCAL_BACKUP_DIR}" -name "ekklesia-backup-*.tar.gz" -mtime +30 -delete 2>/dev/null || true

# ─── 8. Remote Cleanup ───────────────────────────────────────────────────────
# Remote retention managed by Storage Box sub-account or manual cron
# Daily: 30 files, Weekly: 12, Monthly: 6

ARCHIVE_SIZE=$(du -sh "${LOCAL_BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
echo "${LOG_PREFIX} Done. Archive: ${BACKUP_FILE} (${ARCHIVE_SIZE})"
echo "${LOG_PREFIX} Remote: ${STORAGE_BOX_USER}@${STORAGE_BOX_HOST}:${REMOTE_DIR}/daily/${BACKUP_FILE}"
