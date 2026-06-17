# GH#111 Nullifier v2 Canary Runbook

Status: prepared, not activated.
Last updated: 2026-06-17.

## Purpose

GH#111 activates the server-side identity nullifier v2 path from ADR-004:

- v1 compatibility anchor remains `identity_records.nullifier_hash`.
- v2 adds `identity_records.nullifier_hash_v2` with Argon2id and prefix `v2:`.
- Existing v1 identities must migrate in the **same DB row** during real HLR re-verification.
- Existing active identities are re-registered atomically: no intermediate `REVOKED`
  commit is allowed before the replacement key/v2 fields are written.
- Existing identity rows are selected with a DB row lock (`FOR UPDATE`) during
  verification so parallel re-registration requests cannot issue two private
  keys while only the last public key remains stored.
- A short Redis in-flight lock (`identity:verify:lock:{nullifier}`) rejects
  concurrent verification requests for the same identity with HTTP 409, before
  any second keypair can be issued.
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
- Latest no-mutation production preflight package: `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_064644`.
- Preflight on 2026-06-17 06:46 UTC:
  - `identity_records`: 17 total, 17 active.
  - `nullifier_hash_v2`: 0 rows.
  - `nullifier_version='v2'`: 0 rows.
  - `preflight_blockers=[]`.
  - Monitor: PASS, 17 checks, no alerts.
  - Isolated v2 lifespan probe: PASS with scheduler no-op in the test process.

## Preferred Pre-Window Preparation

Use the guarded host-side preparation script immediately before any real
operator window. It creates a fresh evidence/backup directory, runs the monitor,
captures the KDF env rewrite plan, stores the read-only identity snapshot and
preflight report, dumps the identity/audit/alembic tables, runs the isolated v2
lifespan probe, writes SHA-256 checksums, and validates the evidence package.

This script does **not** edit `/opt/ekklesia/.env.production`, does **not** set
`IDENTITY_NULLIFIER_KDF_VERSION=v2`, and does **not** trigger HLR.

```bash
cd /opt/ekklesia/app
scripts/gh111-prepare-nullifier-v2-window.sh
```

Expected final lines:

```text
GH111_PREPARED=1
GH111_BACKUP_DIR=/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_...
GH111_NEXT_STEP=Use GH111_NULLIFIER_V2_CANARY_RUNBOOK.md Activation Window only when Gio is ready with S10 and real HLR verification.
```

Use the printed `GH111_BACKUP_DIR` as `BACKUP_DIR` in the activation window.
If this preparation script fails at any step, abort before the flag flip and
document the failed artifact.

The preparation script writes `package_check.json`. It must contain `"ok": true`
before the activation window starts. To re-check the package manually:

```bash
cd /opt/ekklesia/app
python3 apps/api/scripts/gh111_preflight_package_check.py --backup-dir "$BACKUP_DIR"
```

## Pre-Window Checks

The script above is the preferred path. The commands below are the manual
fallback/reference checks to run before changing any env flag:

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

Structured read-only preflight helper:

```bash
cd /opt/ekklesia/app/infra/docker
docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml exec -T api \
  python scripts/gh111_nullifier_v2_canary_check.py snapshot --preflight \
  --output /tmp/gh111_before_snapshot.json \
  --report-output /tmp/gh111_preflight_report.json
: "${BACKUP_DIR:?Set BACKUP_DIR from the fresh backup step before copying artifacts}"
docker cp ekklesia-api:/tmp/gh111_before_snapshot.json "$BACKUP_DIR/gh111_before_snapshot.json"
docker cp ekklesia-api:/tmp/gh111_preflight_report.json "$BACKUP_DIR/gh111_preflight_report.json"
```

`gh111_before_snapshot.json` is the machine-readable input for `compare`.
`gh111_preflight_report.json` is the operator/audit artifact and includes
`preflight_blockers`.

The preflight report also records aggregate v2 safety counters:

- `active_with_v2`
- `v2_without_version`
- `version_without_v2`
- `malformed_v2`

All four must be `0` before the first activation.

## Fresh Backup

The preferred preparation script already creates the fresh backup. If the script
cannot be used, create a fresh backup manually immediately before the real
canary, even though an older preflight backup exists:

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
2. Prefer the guarded activation helper. It validates `package_check.json`,
   re-runs the isolated v2 lifespan probe, writes only the KDF env key through
   `gh111_kdf_env_guard.py`, rebuilds only the API, waits for external health,
   and runs monitor once. If activation fails after the KDF env write, it
   attempts an automatic emergency rollback to v1 and writes
   `emergency_rollback_after_failed_activation.txt` into `BACKUP_DIR`. It does
   **not** trigger HLR.

```bash
cd /opt/ekklesia/app
: "${BACKUP_DIR:?Set BACKUP_DIR from the fresh preparation script}"
GH111_OPERATOR_CONFIRM=GH111-ACTIVATE-V2 \
  scripts/gh111-activate-nullifier-v2-window.sh activate-v2
```

After this command succeeds, Gio performs the real S10 verification in the app.

Manual fallback:

2. Before changing production flags, prove the current API image can boot its
   app lifespan under `IDENTITY_NULLIFIER_KDF_VERSION=v2` in an isolated
   process. This does **not** mutate `/opt/ekklesia/.env.production`:

```bash
cd /opt/ekklesia/app/infra/docker
docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml exec -T api \
  env PYTHONPATH=/app:/packages/crypto IDENTITY_NULLIFIER_KDF_VERSION=v2 python - <<'PY'
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
```

Abort before the flag flip if this probe fails.

3. Set the production env flag:

```bash
cd /opt/ekklesia/app
: "${BACKUP_DIR:?Set BACKUP_DIR from the fresh backup step before activation}"
python3 apps/api/scripts/gh111_kdf_env_guard.py plan \
  --env-file /opt/ekklesia/.env.production \
  --target v2
python3 apps/api/scripts/gh111_kdf_env_guard.py write \
  --env-file /opt/ekklesia/.env.production \
  --backup-dir "$BACKUP_DIR" \
  --target v2 \
  --confirm GH111-KDF-WRITE
cd /opt/ekklesia/app/infra/docker
docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml up -d --build api
```

4. Verify API startup with retry. Do not treat a single immediate 500 during
   container replacement as success or failure; wait for a stable external
   health response:

```bash
for i in $(seq 1 45); do
  if curl -fsS https://api.ekklesia.gr/health >/dev/null; then
    echo "health-ok"
    break
  fi
  sleep 2
done

curl -fsS https://api.ekklesia.gr/health >/dev/null
docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml logs --tail=80 api | grep -iE 'IDENTITY_NULLIFIER|argon2|error|traceback' || true
```

If the final health check still fails, run the rollback section immediately.
Do not ask Gio to perform HLR verification while health is unstable.

5. On S10, open the app and run real phone verification through `VerifyScreen`.
6. Record whether this is:
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
- the row was not left `REVOKED` during a partial failure,
- no duplicate active identity was created for the same phone.

For new-phone registration:

- new identity row contains both v1 and v2 anchors,
- response to the app still returns the v1 compatibility `nullifier_hash`,
- regular Tier-1 vote/status paths still use the returned v1 anchor.
- `active_with_v2` increased by exactly one.
- `v2_without_version`, `version_without_v2`, and `malformed_v2` remain `0`.

Always run:

```bash
docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml exec -T monitor python /app/monitor.py --once
```

Then run the structured post-check. Choose exactly one mode:

```bash
# Existing-phone re-registration:
: "${BACKUP_DIR:?Set BACKUP_DIR from the fresh backup step before compare}"
docker cp "$BACKUP_DIR/gh111_before_snapshot.json" ekklesia-api:/tmp/gh111_before_snapshot.json
docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml exec -T api \
  python scripts/gh111_nullifier_v2_canary_check.py compare \
  --before /tmp/gh111_before_snapshot.json \
  --mode existing-reregistration \
  --report-output /tmp/gh111_compare_report.json
docker cp ekklesia-api:/tmp/gh111_compare_report.json "$BACKUP_DIR/gh111_compare_report.json"

# New-phone registration:
: "${BACKUP_DIR:?Set BACKUP_DIR from the fresh backup step before compare}"
docker cp "$BACKUP_DIR/gh111_before_snapshot.json" ekklesia-api:/tmp/gh111_before_snapshot.json
docker compose --env-file /opt/ekklesia/.env.production -f docker-compose.prod.yml exec -T api \
  python scripts/gh111_nullifier_v2_canary_check.py compare \
  --before /tmp/gh111_before_snapshot.json \
  --mode new-registration \
  --report-output /tmp/gh111_compare_report.json
docker cp ekklesia-api:/tmp/gh111_compare_report.json "$BACKUP_DIR/gh111_compare_report.json"
```

## Rollback

Rollback is env-only unless the operator explicitly chooses to restore the backup.

Preferred rollback helper:

```bash
cd /opt/ekklesia/app
: "${BACKUP_DIR:?Set BACKUP_DIR from the fresh preparation script}"
GH111_OPERATOR_CONFIRM=GH111-ROLLBACK-V1 \
  scripts/gh111-activate-nullifier-v2-window.sh rollback-v1
```

Manual fallback:

```bash
cd /opt/ekklesia/app
python3 apps/api/scripts/gh111_kdf_env_guard.py plan \
  --env-file /opt/ekklesia/.env.production \
  --target v1
python3 apps/api/scripts/gh111_kdf_env_guard.py write \
  --env-file /opt/ekklesia/.env.production \
  --backup-dir "${BACKUP_DIR:-/opt/ekklesia/backups}" \
  --target v1 \
  --confirm GH111-KDF-WRITE
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
