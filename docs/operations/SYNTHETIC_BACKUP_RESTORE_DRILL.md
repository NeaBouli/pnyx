# Synthetic Postgres 15 Backup/Restore Drill (T-9065)

Local, synthetic-only drill for the `pg_dump -Fc` / `pg_restore` path and the
repo Alembic version marker. **Not** a production backup, backup policy,
RPO/RTO, full-schema, migration or recovery proof.

## Commands

```bash
python3 scripts/synthetic_restore_drill.py        # default: offline plan, no Docker/DB/subprocess
python3 scripts/synthetic_restore_drill.py --run  # opt-in synthetic local drill
python3 -m unittest test_synthetic_restore_drill  # from scripts/redesign, offline mocks
```

`--run` prerequisites: local Unix-socket Docker endpoint, the cached
`postgres:15` image ID pinned in the script (`--pull=never`, no implicit pull),
and the API Python deps (`alembic`, `sqlalchemy` 2.x, `asyncpg`, `pydantic-settings`).
Nothing is installed by the script. There are no DSN, dump, SQL or container
arguments.

Before any Docker command, temp dir or container, `--run` checks these imports
in a child of the same interpreter (`PATH`-only env, cwd `/`, fixed import-only
code; no app config/database/models/`env.py`, no `.env`, no DB connection).
A missing or incompatible dependency (e.g. SQLAlchemy 1.4 without
`async_sessionmaker`), a timeout or a missing interpreter exits 1 with a fixed
dependency message and no raw child output; nothing is created. Install the
`apps/api` requirements yourself and retry.

## Flow

```text
dependency import preflight (fail closed) -> repo heads -> local Docker/image checks
  -> synthetic fixtures -> NEW PG15 source (--network none)
  -> pg_dump -Fc (in container) -> PGDMP magic check -> pg_restore -l (TOC kept private)
  -> NEW PG15 target (127.0.0.1 ephemeral port) -> pg_restore --exit-on-error --no-owner --no-acl
  -> SQL sample counts/aggregates source == target
  -> repo `alembic current` against target (empty scratch CWD, sanitized env,
     absolute ini/script_location, ENVIRONMENT=test) == ScriptDirectory heads
```

Distinguish the receipts: PGDMP magic and a readable TOC prove only an archive
format; restore exit 0 proves the archive loads into an empty cluster; matching
counts prove synthetic data equality; `alembic current` proves only that the
synthetic `alembic_version` marker (seeded with the offline repo heads)
survived. No repo migrations are applied, no stamp/upgrade is run.

## Safety

- Refuses remote `DOCKER_HOST` and non-`unix://` contexts before creating anything.
- Refuses explicit `DOCKER_CONTEXT` overrides and pins every Docker action to the validated Unix endpoint with `--host`.
- Server major 15 and the `127.0.0.1` port binding are verified before fixtures/Alembic.
- Containers get UUID names and label `ekklesia.drill=t9065-synthetic`; no `--rm`,
  no stop/delete/prune/drop/`--clean`. No env/`.env`/production config is read.
- The dump, TOC and scratch dir live in a fresh `mkdtemp` (umask 077). Retained
  containers and the temp dir are listed in the private receipt; cleanup needs
  owner approval and is never automatic. Never commit dumps, TOCs or logs.

## Failure interpretation

Any dependency preflight failure, readiness timeout, wrong major, non-loopback binding, non-PGDMP archive,
TOC/restore non-zero exit, count mismatch or Alembic head mismatch exits 1.
Investigate locally; do not extrapolate to production.

A preflight/Docker-check failure prints a fixed message and creates nothing (no
receipt). Any failure after the private temp dir is allocated prints `FAIL: <type>`
plus a private partial receipt on stderr: fixed `code`/`stage`
(`create_source|create_target|restore`), the private `workdir` and only
acknowledged full-hex `acknowledged_container_ids`. No password, DSN, SQL,
command, stdout/stderr or raw exception text is printed. A failed or malformed
create sets `creation_uncertain`: an unacknowledged container may exist, so check
label `ekklesia.drill=t9065-synthetic` before owner-approved cleanup. The workdir
path is local and private; never paste it into public docs or tickets.

## Related

Production backup, `y801` migration and rollback stay Gio-gated in the separate
[follow-up API/Web deploy runbook](FOLLOWUP_API_WEB_DEPLOY_RUNBOOK_2026-10-10.md).
