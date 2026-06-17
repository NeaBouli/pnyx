# GH#111 Nullifier v2 Canary Runbook

Status: prepared, not activated.
Last updated: 2026-06-17.

## Purpose

GH#111 activates the server-side identity nullifier v2 path from ADR-004:

- v1 compatibility anchor remains `identity_records.nullifier_hash`.
- v2 adds `identity_records.nullifier_hash_v2` with Argon2id and prefix `v2:`.
- Existing v1 identities must migrate in the **same DB row** during real HLR re-verification.
- No phone number is stored.

This is separate from GH#112 ZK voting. Do not mix both rollout windows.

## Non-Negotiable Boundary

Do not activate `IDENTITY_NULLIFIER_KDF_VERSION=v2` based only on DB inspection or admin-test accounts.

Reason: admin-test identities use random nullifiers and do not exercise the real phone/HLR path. GH#111 is only proven if a real `/api/v1/identity/verify` request with a real Greek mobile number either:

- migrates an existing v1 row to v2 in the same row, or
- creates a new row with both v1 and v2 anchors.

## Current Prepared State

- Code scaffold: deployed.
- DB columns: present.
- Production default: v1.
- Identity backup: `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_004847`.
- Preflight on 2026-06-17:
  - `identity_records`: 17 total, 17 active.
  - `nullifier_hash_v2`: 0 rows.
  - `nullifier_version='v2'`: 0 rows.
  - Argon2id helper in API container: about 131 ms per derivation.

## Pre-Window Checks

Run before changing any env flag:

```bash
cd /opt/ekklesia/app/infra/docker

docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml exec -T monitor python /app/monitor.py --once

grep -E '^IDENTITY_NULLIFIER_KDF_VERSION=' /opt/ekklesia/.env.production || true

docker exec -i ekklesia-db sh -lc 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"' <<'SQL'
SELECT COUNT(*) AS total,
       COUNT(*) FILTER (WHERE nullifier_hash_v2 IS NOT NULL) AS with_v2,
       COUNT(*) FILTER (WHERE nullifier_version = 'v2') AS version_v2,
       COUNT(*) FILTER (WHERE status = 'ACTIVE') AS active,
       COUNT(*) FILTER (WHERE status = 'REVOKED') AS revoked
FROM identity_records;
SQL
```

Expected before first activation: KDF v1/unset, monitor clean, `with_v2=0`, `version_v2=0`.

## Fresh Backup

Use a fresh backup immediately before the real canary, even though an older preflight backup exists:

```bash
TS=$(date -u +%Y%m%d_%H%M%S)
BACKUP_DIR=/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_$TS
mkdir -p "$BACKUP_DIR"

docker exec -i ekklesia-db sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" --table=identity_records --table=audit_log --table=alembic_version' \
  > "$BACKUP_DIR/identity_records_audit_alembic.sql"

sha256sum "$BACKUP_DIR/identity_records_audit_alembic.sql"
```

## Activation Window

1. Make sure Gio has the S10, the app is installed, and a real Greek mobile number can be entered in `VerifyScreen`.
2. Set the production env flag:

```bash
cd /opt/ekklesia/app
cp /opt/ekklesia/.env.production "/opt/ekklesia/backups/env_pre_gh111_$(date -u +%Y%m%d_%H%M%S).production"
python3 - <<'PY'
from pathlib import Path
path = Path("/opt/ekklesia/.env.production")
lines = path.read_text().splitlines()
out = []
seen = False
for line in lines:
    if line.startswith("IDENTITY_NULLIFIER_KDF_VERSION="):
        out.append("IDENTITY_NULLIFIER_KDF_VERSION=v2")
        seen = True
    else:
        out.append(line)
if not seen:
    out.append("IDENTITY_NULLIFIER_KDF_VERSION=v2")
path.write_text("\n".join(out) + "\n")
PY
cd /opt/ekklesia/app/infra/docker
docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml up -d --build api
```

3. Verify API startup:

```bash
curl -fsS https://api.ekklesia.gr/health >/dev/null
docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml logs --tail=80 api | grep -iE 'IDENTITY_NULLIFIER|argon2|error|traceback' || true
```

4. On S10, open the app and run real phone verification through `VerifyScreen`.
5. Record whether this is:
   - existing-phone re-registration, or
   - new-phone registration.

## Success Checks

For existing-phone re-registration:

```sql
SELECT id, nullifier_hash_v2 IS NOT NULL AS has_v2, nullifier_version, status, revoked_at
FROM identity_records
WHERE nullifier_hash_v2 IS NOT NULL
ORDER BY nullifier_migrated_at DESC NULLS LAST
LIMIT 5;
```

Expected:

- exactly the existing identity row was updated,
- `nullifier_hash` remains populated,
- `nullifier_hash_v2` is populated and starts with `v2:`,
- `nullifier_version='v2'`,
- row is `ACTIVE`,
- no duplicate active identity was created for the same phone.

For new-phone registration:

- new identity row contains both v1 and v2 anchors,
- response to the app still returns the v1 compatibility `nullifier_hash`,
- regular Tier-1 vote/status paths still use the returned v1 anchor.

Always run:

```bash
docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml exec -T monitor python /app/monitor.py --once
```

## Rollback

Rollback is env-only unless the operator explicitly chooses to restore the backup.

```bash
python3 - <<'PY'
from pathlib import Path
path = Path("/opt/ekklesia/.env.production")
lines = path.read_text().splitlines()
out = []
seen = False
for line in lines:
    if line.startswith("IDENTITY_NULLIFIER_KDF_VERSION="):
        out.append("IDENTITY_NULLIFIER_KDF_VERSION=v1")
        seen = True
    else:
        out.append(line)
if not seen:
    out.append("IDENTITY_NULLIFIER_KDF_VERSION=v1")
path.write_text("\n".join(out) + "\n")
PY
cd /opt/ekklesia/app/infra/docker
docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml up -d --build api
curl -fsS https://api.ekklesia.gr/health >/dev/null
```

Do not drop v2 columns. They are additive and harmless while v1 is active.

## Abort Conditions

Abort and rollback to v1 if any of these occur:

- API fails startup or health check.
- HLR verification errors spike.
- `/identity/verify` creates duplicate active rows for one phone.
- returned app nullifier differs from the v1 compatibility anchor for an existing row.
- vote/status/Polis/Diavgeia/evaluation paths fail for the re-verified account.
- monitor reports any new T2/T3 alert.

## Completion Criteria

GH#111 can only be called complete when:

- fresh backup exists,
- v2 activation window completed,
- at least one real HLR `/identity/verify` path succeeded with v2 active,
- same-row migration or new-row dual-anchor behavior is verified,
- downstream identity consumers still work,
- monitor passes,
- rollback to v1 has been tested or intentionally left available,
- bridge, GitHub, and Linear are updated.
