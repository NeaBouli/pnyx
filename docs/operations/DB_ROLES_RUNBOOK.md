# PostgreSQL service roles — ADR-007 S4 / T-9142

This is an operator rollout procedure, not an automatic production change.
Rehearse against a restored, isolated database first. Keep the old credentials
available for rollback. Never change `POSTGRES_USER`/`POSTGRES_PASSWORD`: these
remain the bootstrap credentials for the existing volume, not the API login.

## Design and query inventory

| Login | Access | Configuration |
| --- | --- | --- |
| `ekklesia_api` | SELECT/INSERT/UPDATE/DELETE on application base tables, sequence USAGE/SELECT; no ownership, schema CREATE, TEMP, TRUNCATE or Alembic writes | `API_DATABASE_URL` |
| `ekklesia_migrator` | Owns application schema, tables, sequences, enum/domain types and reporting views; DDL | `MIGRATOR_DATABASE_URL`, one-shot Alembic service only |
| `ekklesia_monitor` | SELECT on the six aggregate views below; no base tables or sequences | `MONITOR_DATABASE_URL` |
| `ekklesia_dashboard` | CONNECT/USAGE only; no data grants | `DASHBOARD_DATABASE_URL` (reserved) |
| `ekklesia_backup` | SELECT on all application tables/views and sequences, including private data and `alembic_version`; no writes | `BACKUP_DATABASE_URL` (backup cron) |

All logins are NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION,
NOBYPASSRLS and NOINHERIT, with no role memberships. Default privileges for
migrator-created tables/sequences maintain API DML and backup reads. New views
are never automatically granted to monitor/dashboard. PUBLIC loses application
table/sequence/column grants, schema CREATE and database TEMP; the old bootstrap
superuser still works. The migrator owns application objects, not the database.
Use a bootstrap **superuser** for the ops script; it changes database ACLs,
ownership and logging settings. Application objects are expected in `public`.

The source audit was `rg -n 'execute|SELECT|FROM' apps/monitor/monitor.py` and
`rg -n 'DATABASE_URL|postgres|SELECT|fetch' apps/dashboard/src`:

| View | Monitor readers and exposed data |
| --- | --- |
| `monitor_bill_health` | `check_no_new_bills`, `_db_latest_parliament_activity`, `check_arweave_pending`, `check_db_consistency`: latest timestamps and counts |
| `monitor_lifecycle_stuck` | `check_lifecycle_stuck`: aggregate JSON list of overdue bill IDs, status and vote date, with the existing 30 minute update grace |
| `monitor_lifecycle_fast_forward` | `check_lifecycle_fast_forward`: MIN lifecycle timestamps per bill; caller keeps newest ten anomalies |
| `monitor_forum_missing` | `check_forum_missing`, `get_forum_missing_catalog` / `check_forum_completeness`: category counts; aggregate ID/title list only for public actionable bills; sensitive/hidden/demo/test categories expose counts only |
| `monitor_zk_pending` | `check_zk_canary_health`: counts grouped by scope, group size, completed age hours and Parliament eligibility; no receipts, nullifiers, commitments or proofs |
| `monitor_zk_health` | `check_zk_canary_health`: count of invalid root statuses |

The ZK hour bucket uses `pending_hours >= configured_hours`, preserving the
integer-hour threshold. Owner-rights, security-barrier views intentionally allow
aggregate reads without source-table grants. The monitor's API/Redis checks,
recovery actions and Telegram delivery still use their existing credentials.
The dashboard has **no PostgreSQL driver or SQL**: `src/lib/api.ts`,
`src/lib/overview.ts` and `src/app/api/proxy/[...path]/route.ts` use HTTP. There
are exactly zero dashboard views; its existing HTTP/admin authorization is
independent of the reserved database login.

## 1. Backup, restore check and preflight

Use the existing encrypted backup procedure in
[BACKUP_ENCRYPTION_RUNBOOK.md](BACKUP_ENCRYPTION_RUNBOOK.md). Before any role
changes, take a fresh custom-format dump with the old login. For example on the
DB host (paths below must be in an operator-only directory, `umask 077`):

```bash
umask 077
# Load the existing protected environment; do not enable shell tracing.
set +x
set -a
source /opt/ekklesia/.env.production
set +a
export PGUSER="$POSTGRES_USER" PGDATABASE="$POSTGRES_DB"
# Save under the existing encrypted-backup workflow; this file contains private data.
docker exec --env PGUSER --env PGDATABASE ekklesia-db pg_dump --no-password -Fc > before-db-roles.dump
pg_restore --list before-db-roles.dump > before-db-roles.list
```

Restore the dump to an **isolated disposable PostgreSQL instance**, not a new
schema in the live database. On that isolated instance only:

```bash
# PGHOST/PGPORT/PGUSER/PGPASSWORD here belong to the isolated instance.
createdb pnyx_test_roles_restore
pg_restore --exit-on-error --no-owner --no-acl -d pnyx_test_roles_restore before-db-roles.dump
psql -X -v ON_ERROR_STOP=1 -d pnyx_test_roles_restore -c 'SELECT version_num FROM public.alembic_version'
psql -X -v ON_ERROR_STOP=1 -d pnyx_test_roles_restore -c 'SELECT count(*) FROM public.identity_records; SELECT count(*) FROM public.citizen_votes; SELECT count(*) FROM public.parliament_bills;'
```

Compare those counts and Alembic revision with the source, run the API's health
and representative read checks against the restored instance, and record the
restore result before proceeding. Encrypt/remove the temporary plaintext dump
under the existing retention policy. Do not put dumps or passwords in git.

Preflight on the target with the old superuser (stop if the assumptions differ):

```sql
SELECT current_user, current_database(), version();
SELECT version_num FROM public.alembic_version; -- y803a2b3c4d5 or z901a2b3c4d5
SELECT rolname, rolsuper FROM pg_roles WHERE rolname = current_user; -- superuser
SELECT schemaname, tablename FROM pg_tables
 WHERE schemaname NOT IN ('pg_catalog', 'information_schema', 'public'); -- no app tables elsewhere
SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relrowsecurity; -- no RLS tables: backup is NOBYPASSRLS
SELECT count(*) FROM pg_largeobject_metadata; -- expected 0 (app does not use large objects)
SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='public' AND p.prosecdef; -- expected 0, review any privileged functions
SELECT r.rolname, parent.rolname AS member_of FROM pg_auth_members m
 JOIN pg_roles r ON r.oid=m.member JOIN pg_roles parent ON parent.oid=m.roleid
 WHERE r.rolname LIKE 'ekklesia_%'; -- new logins must have no memberships
```

Check the existing app schema against the ORM as usual: older migration history
has known drift (`apps/api/alembic/SCHEMA_DRIFT_NOTES.md`); this revision does not
repair it. If the single legacy user is not a superuser, establish its rollback
access explicitly before transferring ownership. Do not use that unsupported
configuration with the commands below unchanged.

## 2. Create roles — requires six secrets

Required: the current bootstrap password plus five independent new passwords.
Inject these through the operator's secret manager into environment variables:

- `PGPASSWORD`: existing bootstrap secret.
- `EKKLESIA_API_PASSWORD`, `EKKLESIA_MIGRATOR_PASSWORD`,
  `EKKLESIA_MONITOR_PASSWORD`, `EKKLESIA_DASHBOARD_PASSWORD`,
  `EKKLESIA_BACKUP_PASSWORD`: new role secrets.

Alternatively, read them without shell-history arguments:

```bash
set +x
for role in API MIGRATOR MONITOR DASHBOARD BACKUP; do
  read -r -s -p "Password for ekklesia_${role}: " "EKKLESIA_${role}_PASSWORD"
  printf '\n'
  export "EKKLESIA_${role}_PASSWORD"
done
export PGHOST=127.0.0.1 PGPORT=5432 PGDATABASE="$POSTGRES_DB" PGUSER="$POSTGRES_USER"
export PGPASSWORD="$POSTGRES_PASSWORD"
# Uses psql >=15 inside the existing PostgreSQL container. No secret in argv.
scripts/ops/db-roles.sh --docker ekklesia-db
```

For a directly reachable staging database with psql >=15 installed, set the
appropriate libpq connection environment and use `scripts/ops/db-roles.sh`.
The wrapper refuses missing role secrets and disables tracing. SQL reads secrets
via `\getenv`, runs in one transaction, and suppresses ordinary statement/error
logging for password statements. Re-running rotates passwords and reconciles
ownership. Keep any independent SQL audit pipeline configured to redact password
statements. Do not save the five bootstrap-only password variables in the API's
runtime env file.

## 3. Apply migration — uses migrator secret

Prepare percent-encoded URLs in the protected environment/secret manager:

```text
API_DATABASE_URL=postgresql+asyncpg://ekklesia_api:<encoded-password>@db:5432/<database>
MIGRATOR_DATABASE_URL=postgresql+asyncpg://ekklesia_migrator:<encoded-password>@db:5432/<database>
MONITOR_DATABASE_URL=postgresql://ekklesia_monitor:<encoded-password>@db:5432/<database>
DASHBOARD_DATABASE_URL=postgresql://ekklesia_dashboard:<encoded-password>@db:5432/<database>
BACKUP_DATABASE_URL=postgresql://ekklesia_backup:<encoded-password>@127.0.0.1:5432/<database>
```

Encode with `urllib.parse.quote(password, safe='')` inside secret provisioning;
never paste passwords into command arguments or git. `db` is Compose DNS;
`127.0.0.1` in the backup URL is inside `ekklesia-db`, where the script invokes
pg_dump. The backup script forwards its URL as the `PGDATABASE` environment,
not in the Docker or pg_dump command arguments, and uses TCP password auth.

Persist the URLs in `/opt/ekklesia/.env.production` with operator-only access,
but do not recreate long-lived services until the migration has succeeded.
Ensure the backup cron sources its protected environment as well. Define:

```bash
dc() (
  # Let the protected file supply these values, even if this shell sourced an
  # older version before the role rollout (shell env wins over --env-file).
  unset API_DATABASE_URL MIGRATOR_DATABASE_URL MONITOR_DATABASE_URL DASHBOARD_DATABASE_URL BACKUP_DATABASE_URL
  docker compose --env-file /opt/ekklesia/.env.production \
    -f infra/docker/docker-compose.prod.yml "$@"
)
dc build migrator
dc --profile ops run --rm migrator
```

The one-shot service runs `alembic upgrade head`. Alembic selects
`MIGRATOR_DATABASE_URL or DATABASE_URL`, independently of `API_DATABASE_URL`.
Use this service for **all future migrations**, never `exec api alembic`.
The long-lived API has `MIGRATOR_DATABASE_URL` and `POSTGRES_PASSWORD` cleared.

If `z901a2b3c4d5` was already applied with the legacy URL **before** the ops step,
reconcile grants before switching any service (all services still use the old
URL):

```bash
dc --profile ops run --rm migrator alembic downgrade y803a2b3c4d5
dc --profile ops run --rm migrator alembic upgrade z901a2b3c4d5
```

This briefly removes the monitor views; schedule it between monitor checks.
If needed, stop monitor during this reconciliation and restart after upgrade.
Do not downgrade an installation containing later revisions just to reconcile
ACLs; have its operator run this revision's idempotent `upgrade()` in an Alembic
transaction instead. The migration creates no roles or passwords and is safe
when roles are absent, so deployment may precede bootstrap. It must run before
the new monitor code; unset/empty role URLs retain the existing single user.

## 4. Switch and verify services one at a time

Do not run a bulk `compose up`. Verify the preceding stage before each switch.

1. **Monitor:** `dc up -d --no-deps --build monitor`. Query its views using its
   new login and run its DB check functions in an isolated rehearsal. On the live
   host observe one normal scheduled cycle in `dc logs --tail=100 monitor`:
   no permission/undefined-view errors, expected forum/lifecycle/ZK counts.
   The normal full cycle includes HTTP checks and recovery, so a rehearsal must
   disable external delivery/recovery. Do not run ad-hoc full cycles as a SQL probe.
2. **Dashboard:** `dc up -d --no-deps --build dashboard`. Check authenticated
   overview, bills, statistics, monitor and proxy routes. Its HTTP behavior is
   unchanged; its reserved DB login must fail every base-table/view probe.
3. **API:** `dc stop api`, then `dc up -d --no-deps --build api` (existing deploy
   guard). Check `/health`, `/api/v1/health/modules`, bill listing and admin
   stats. Complete a synthetic identity/vote/correction flow in staging to
   verify DML and sequence usage; do not create live identity/vote fixtures.
   Confirm the authenticated `current_user` is `ekklesia_api` using that URL.
4. **Backup:** load `BACKUP_DATABASE_URL` in the protected cron environment.
   Run the normal backup procedure, verify its dump/Alembic capture, and repeat
   the isolated restore check from step 1. Confirm login `ekklesia_backup`.

When invoking libpq probes, use `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGHOST`
and `PGPORT` for each role, with secrets sourced from the secret manager. For a
container, pass names with `docker exec --env PGUSER --env PGPASSWORD ...`.
Use TCP (`PGHOST=127.0.0.1` inside the DB container) so the login's password is
actually tested. Do not test against a trusted Unix socket and mistake that for
password authentication. `psql -X -v ON_ERROR_STOP=1` makes failed probes visible.

## 5. Permission verification

Run as each login, never as the superuser with `SET ROLE` for authentication
checks. As monitor/dashboard, this query must return **zero** readable tables:

```sql
SELECT current_user;
SELECT tablename FROM pg_tables WHERE schemaname='public'
 AND has_table_privilege(current_user, format('public.%I', tablename), 'SELECT');
-- Expected zero for both logins (stronger than a denylist).
```

Each following direct probe must fail with SQLSTATE 42501 for **both** monitor
and dashboard. Execute separately when ON_ERROR_STOP is on:

```sql
SELECT * FROM public.identity_records LIMIT 0;
SELECT * FROM public.citizen_votes LIMIT 0;
SELECT * FROM public.consensus_votes LIMIT 0;
SELECT * FROM public.cplm_history LIMIT 0;
SELECT * FROM public.politician_evaluations LIMIT 0;
SELECT * FROM public.bill_relevance_votes LIMIT 0;
SELECT * FROM public.diavgeia_votes LIMIT 0;
SELECT * FROM public.bill_flags LIMIT 0;
SELECT * FROM public.zk_vote_receipts LIMIT 0;
SELECT * FROM public.parliament_bills LIMIT 0;
-- Enumerate every deployed polis_* table, then attempt SELECT * ... LIMIT 0:
SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'polis\_%' ESCAPE '\';
```

A missing optional table reports 42P01 instead; verify all deployed tables via
the catalog query. Also check column-level permissions (all results false):

```sql
SELECT c.table_name, c.column_name FROM information_schema.columns c
 WHERE c.table_schema='public' AND c.table_name IN ('identity_records','citizen_votes')
 AND has_column_privilege(current_user, format('public.%I', c.table_name), c.column_name, 'SELECT');
SELECT has_schema_privilege(current_user, 'public', 'CREATE'),
       has_database_privilege(current_user, current_database(), 'TEMP'); -- false for runtime roles
```

Monitor can SELECT all six named views; dashboard can SELECT none. API can DML
base tables and use sequences but cannot update `alembic_version`, CREATE/ALTER
objects, TRUNCATE, or `SET ROLE ekklesia_migrator`. Backup can SELECT all base
tables and sequence values and produce a full pg_dump, but cannot DELETE, use
`nextval`, or CREATE/ALTER objects. Migrator can ALTER its tables and upgrade/
downgrade. Use the local test suite for destructive permission probes:

```bash
# Disposable cluster only: role names are global; the suite rejects existing roles.
export PNYX_TEST_POSTGRES_URL=postgresql+asyncpg://<test-superuser>:<encoded-secret>@127.0.0.1:<port>/pnyx_test_roles
cd apps/api
python -m pytest -q tests/test_db_roles_pg.py tests/test_db_role_configuration.py \
  tests/test_monitor_hidden_bills.py tests/test_monitor_zk_canary_health.py
# Repository root: stdlib wrapper/backup credential tests (no network).
python3 -m unittest discover -s scripts/tests -p test_db_roles.py
```

## Rollback

Restore each affected role URL to its saved old URL, or unset/empty the five
new URL variables; keep the original POSTGRES bootstrap values. Recreate API,
monitor and dashboard individually with the same commands and reload the backup
cron environment. For direct Python/Alembic processes, also restore `DATABASE_URL`
to the saved legacy value. Verify health and a backup restore again.

Keep the new views during an env-only rollback: the updated monitor needs them
with either login. Do not drop roles or reverse ownership during an incident.
A schema downgrade is optional only when also reverting monitor code; it drops
the six views and leaves ownership, API/backup DML/read grants and PUBLIC
revocations in place. Reopening PUBLIC access is not part of rollback.
