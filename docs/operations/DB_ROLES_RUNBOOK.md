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
| `ekklesia_monitor` | SELECT on the six aggregate views below and EXECUTE on their aggregate functions; no base tables or sequences | `MONITOR_DATABASE_URL` |
| `ekklesia_monitor_owner` | NOLOGIN owner of the six definer functions; SELECT only on their five source tables; no schema CREATE after migration | No password or connection URL |
| `ekklesia_dashboard` | CONNECT/USAGE only; no data grants | Reserved login; no credential delivered to dashboard |
| `ekklesia_backup` | SELECT on application base tables/sequences, including private data and `alembic_version`; pg_dump includes view/function definitions; no aggregate function EXECUTE or writes | `BACKUP_DATABASE_URL` (backup cron) |

All logins are NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION,
NOBYPASSRLS and NOINHERIT. Only migrator has a membership: it may explicitly
`SET ROLE ekklesia_monitor_owner` to install/update/drop the functions. Runtime
roles have no memberships and cannot assume that owner. Default privileges for
migrator-created tables/sequences maintain API DML and backup reads. New views
are never automatically granted to monitor/dashboard. PUBLIC loses application
table/sequence/column grants, schema CREATE and database TEMP; the old bootstrap
superuser still works. The migrator owns application objects, not the database.
Bootstrap explicitly revokes both global and `public` schema defaults for
PUBLIC and all runtime roles, for every existing table/sequence creator plus
the legacy and migrator creators. The migration repeats both revokes for its
creators, then adds API/backup grants only within `public`. It fails explicitly
if another creator still has unsafe global defaults; rerun bootstrap as the
superuser before retrying. A schema-scoped revoke cannot cancel a global grant.
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
| `monitor_zk_pending` | `check_zk_canary_health`: release-guarded counts grouped by public Parliament scope, root size and fixed UTC receipt hour; no receipts, nullifiers, commitments or proofs |
| `monitor_zk_health` | `check_zk_canary_health`: count of invalid root statuses |

The ZK view enforces the `services.small_cell.publishable_set` choice/source
rule inside PostgreSQL, including zero choices in each present Tier-1/ZK
source. With suppression enabled, every observed UTC-hour/source/root-size/
pending-state partition must also have all four choices at or above k. Any
unsafe partition withholds the entire scope, including otherwise safe buckets;
published/nonpending complements cannot be recovered by subtraction. Hidden,
demo, canary, non-Parliament and unknown scopes are withheld. Invalid choices,
missing roots/timestamps and root sizes below k also withhold a scope.

The threshold is embedded in owner-controlled function SQL from the migrator's
`PUBLIC_RESULTS_MIN_COUNT` at upgrade/reconciliation; readers cannot weaken it
with `SET` or a connection option. Keep the API and migrator setting identical.
Before **raising/enabling** the API threshold, reconcile this revision's
`upgrade()` with the new setting in an Alembic transaction (use the reapply
procedure below); a restart alone does not update the database rule. Lower the
API threshold before lowering the database threshold. Unset/0 disables the
small-cell checks, as in the API. This is suppression, not a privacy budget
against observations as votes arrive.

`pending_hours >= configured_hours` counts completed hours since the end of
the fixed receipt hour. Alerts can be delayed by up to one additional hour,
avoiding moving time boundaries that split an unchanged bucket. All six views
select only from `public.<view_name>_aggregate()` functions. Each is
`SECURITY DEFINER`, owned by `ekklesia_monitor_owner`, with
`SET search_path = pg_catalog, public` and schema-qualified source tables.
PUBLIC, API, dashboard and backup have no function EXECUTE grant; only monitor
does. Dashboard still has no database views or functions to read.
The owner reads only `parliament_bills`, `bill_status_logs`, `citizen_votes`,
`zk_vote_receipts` and `zk_merkle_roots` and owns no application tables.
The functions return the final aggregates, including the complete ZK suppression
rule. Their execution cannot be inlined: caller `EXPLAIN (ANALYZE, FORMAT JSON)`
sees a Function Scan with only released row counts, never a source-table scan
or pre-suppression cardinalities. A security-barrier view alone does **not**
provide this plan boundary. The monitor's API/Redis checks,
recovery actions and Telegram delivery still use their existing credentials.
The dashboard has **no PostgreSQL driver or SQL**: `src/lib/api.ts`,
`src/lib/overview.ts` and `src/app/api/proxy/[...path]/route.ts` use HTTP. There
are exactly zero dashboard views; its existing HTTP/admin authorization is
independent of the reserved database login.
The pre-PR Compose dashboard had no `DATABASE_URL` or database env file; that
exact credential-free configuration is retained. `DASHBOARD_DATABASE_URL` is
reserved and is not passed to the container, even when populated.

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
 WHERE n.nspname='public' AND p.prosecdef;
-- Initial rollout: expected 0. Reconciliation: exactly the six *_aggregate()
-- functions above, owned by ekklesia_monitor_owner; review anything else.
SELECT r.rolname, parent.rolname AS member_of FROM pg_auth_members m
 JOIN pg_roles r ON r.oid=m.member JOIN pg_roles parent ON parent.oid=m.roleid
 WHERE r.rolname LIKE 'ekklesia_%';
-- Only expected membership after bootstrap: migrator -> monitor_owner.
SELECT owner.rolname AS creator, d.defaclnamespace::regnamespace AS schema,
       d.defaclobjtype, d.defaclacl
 FROM pg_default_acl d JOIN pg_roles owner ON owner.oid=d.defaclrole
 WHERE d.defaclobjtype IN ('r','S');
-- Bootstrap removes PUBLIC/runtime global grants, including reused creator roles.
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
# Dashboard uses HTTP only; leave its reserved URL empty (Compose does not pass it).
DASHBOARD_DATABASE_URL=
BACKUP_DATABASE_URL=postgresql://ekklesia_backup:<encoded-password>@127.0.0.1:5432/<database>
```

Encode with `urllib.parse.quote(password, safe='')` inside secret provisioning;
never paste passwords into command arguments or git. `db` is Compose DNS;
`127.0.0.1` in the backup URL is inside `ekklesia-db`, where the script invokes
pg_dump. The optional URL path requires Python 3.9+ on the backup host (stdlib
only). The script unexports the URL immediately and sends it only through the
parser's stdin. The parser percent-decodes separate `PGHOST`, `PGPORT`, `PGUSER`,
`PGPASSWORD` and `PGDATABASE` values; Docker receives environment **names**,
with no URL or password in argv/logs. `PGDATABASE` is always a literal database
name: libpq does not interpret a URI supplied through that environment variable.
Absent/empty URLs keep the original `POSTGRES_USER`/`POSTGRES_DB` socket path.
The optional URI accepts `postgresql://` or `postgres://`, IPv6 and common
libpq TLS options (`sslmode`, `sslcert`, `sslkey`, `sslrootcert`, `sslcrl`,
`sslcrldir`, `ssl_min_protocol_version`, `ssl_max_protocol_version`), plus
`connect_timeout`, `application_name`, `target_session_attrs`, `channel_binding`
and `gssencmode`. Duplicate/unknown options, credential/host overrides,
fragments and malformed URLs fail with a generic error that omits the input.

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
Bootstrap is required before applying/reconciling this revision, including on
legacy single-login deployments: migration fails if the dedicated non-login
owner is absent or has unsafe role attributes. No additional secret is needed.
Existing installations must rerun the updated bootstrap to provision the owner,
then reconcile this revision before switching service credentials.

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
transaction instead. The migration creates no roles or passwords. It must run before
the new monitor code; unset/empty API, migrator, monitor and backup URLs retain
their existing single-user paths. Dashboard always keeps its HTTP-only setup.

For a threshold change or an already-applied revision, reconcile without
changing the Alembic version (after updating the protected environment):

```bash
dc --profile ops run --rm -T migrator python - <<'PY'
import asyncio
import importlib.util
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import create_async_engine
from config import settings

def reconcile(connection):
    spec = importlib.util.spec_from_file_location(
        'db_roles', 'alembic/versions/z901a2b3c4d5_separate_database_roles.py')
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    with Operations.context(MigrationContext.configure(connection)):
        revision.upgrade()

async def main():
    engine = create_async_engine(settings.migrator_database_url or settings.database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(reconcile)
    finally:
        await engine.dispose()

asyncio.run(main())
PY
```

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
   unchanged and its container receives no database credential. Probe the
   reserved DB login separately; it must fail every base-table/view probe.
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
EXPLAIN (ANALYZE, FORMAT JSON) SELECT * FROM public.citizen_votes;
EXPLAIN (ANALYZE, FORMAT JSON) SELECT * FROM public.zk_vote_receipts;
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

As monitor, inspect each of the six plans (substitute each view name):

```sql
EXPLAIN (ANALYZE, VERBOSE, FORMAT JSON) SELECT * FROM public.monitor_zk_pending;
-- Function Scan, optionally inside Subquery Scan/Result wrappers;
-- no source relation nodes or raw row counts anywhere in the plan tree.
SELECT * FROM public.monitor_zk_pending_aggregate(); -- same suppressed output
SELECT p.oid::regprocedure, r.rolname, p.prosecdef, p.proconfig,
       EXISTS (SELECT FROM aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) acl
               WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE') AS public_execute
 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 JOIN pg_roles r ON r.oid=p.proowner
 WHERE n.nspname='public' AND p.proname LIKE 'monitor_%_aggregate';
-- Six rows: owner=ekklesia_monitor_owner, prosecdef=true,
-- proconfig={"search_path=pg_catalog, public"}, public_execute=false.
SET ROLE ekklesia_monitor_owner; -- must fail for both monitor and dashboard
```

Monitor can SELECT all six named views and execute the corresponding functions;
dashboard can access none. API can DML
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
# Optional socket-only disposable cluster: real SQL/view/backup regression tests.
# Set PGHOST/PGPORT/PGUSER/PGDATABASE and use psql >=15 on PATH.
PNYX_TEST_POSTGRES_SOCKET="$PGHOST" python3 -m unittest discover -s scripts/tests -p test_db_roles_sql.py
```

## Rollback

Restore each affected API/migrator/monitor/backup URL to its saved old URL, or
unset/empty those four new variables; keep the original POSTGRES bootstrap
values. The dashboard receives no database credential in either direction;
leave its reserved URL empty. Recreate API,
monitor and dashboard individually with the same commands and reload the backup
cron environment. For direct Python/Alembic processes, also restore `DATABASE_URL`
to the saved legacy value. Verify health and a backup restore again.

Keep the new views during an env-only rollback: the updated monitor needs them
with either login. Do not drop roles or reverse ownership during an incident.
A schema downgrade is optional only when also reverting monitor code; it drops
the six views and their functions and leaves ownership, API/backup DML/read grants and PUBLIC
revocations in place. Reopening PUBLIC access is not part of rollback.
