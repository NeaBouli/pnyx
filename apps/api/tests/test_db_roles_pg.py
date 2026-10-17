"""ADR-007 S4: real role bootstrap, Alembic up/down and permission boundaries.

PNYX_TEST_POSTGRES_URL must be a superuser connection to an isolated local
pnyx_test_* database in a DISPOSABLE CLUSTER: this test creates cluster roles.
psql >= 15 must be on PATH. Never point this suite at a shared cluster.
The historical schema chain has drift, so use the current ORM schema and stamp
its predecessor, matching the existing *_pg.py migration test pattern.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import types

import asyncpg
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from database import Base
import models  # noqa: F401
from tests.pg_vote_schema import disposable_postgres_url, requires_postgres

pytestmark = requires_postgres
ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "apps/api"
TARGET = "z901a2b3c4d5"
PREVIOUS = "y803a2b3c4d5"
ROLES = ("api", "migrator", "monitor", "dashboard", "backup")
# Also exercise SQL-created opinion tables that are not in models.py.
EXTRA_PRIVATE = ("consensus_votes", "cplm_history", "bill_flags", "polis_tickets", "polis_identity_keys", "polis_votes")
FORBIDDEN = ("identity_records", "citizen_votes", "politician_evaluations", "bill_relevance_votes", "diavgeia_votes", "zk_vote_receipts", "zk_identity_commitments", "zk_vote_tier_locks", *EXTRA_PRIVATE)


def url_for(url, role, password):
    return make_url(url).set(username=f"ekklesia_{role}", password=password).render_as_string(hide_password=False)


def cli(url, *args, migrator_url=""):
    env = {**os.environ, "DATABASE_URL": url, "API_DATABASE_URL": "", "MIGRATOR_DATABASE_URL": migrator_url}
    result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=API, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return result


def bootstrap(url, passwords):
    parsed = make_url(url)
    env = {**os.environ, "PGHOST": parsed.host, "PGPORT": str(parsed.port or 5432), "PGDATABASE": parsed.database,
           "PGUSER": parsed.username, "PGPASSWORD": parsed.password or "",
           **{f"EKKLESIA_{role.upper()}_PASSWORD": password for role, password in passwords.items()}}
    result = subprocess.run([str(ROOT / "scripts/ops/db-roles.sh")], env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert not any(password in result.stdout + result.stderr for password in passwords.values())


@pytest.fixture
async def db():
    url = disposable_postgres_url()
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        existing = await conn.exec_driver_sql("SELECT rolname FROM pg_roles WHERE rolname = ANY(ARRAY['ekklesia_api','ekklesia_migrator','ekklesia_monitor','ekklesia_dashboard','ekklesia_backup'])")
        assert not existing.all(), "Use a disposable cluster without existing ekklesia_* roles"
        await conn.exec_driver_sql("DROP SCHEMA public CASCADE")
        await conn.exec_driver_sql("CREATE SCHEMA public")
        await conn.run_sync(Base.metadata.create_all)
        for table in EXTRA_PRIVATE:
            await conn.exec_driver_sql(f"CREATE TABLE IF NOT EXISTS public.{table} (id serial PRIMARY KEY, private_value text)")
        await conn.exec_driver_sql("CREATE TABLE public.db_roles_fixture (id serial PRIMARY KEY, private_value text)")
    cli(url, "stamp", PREVIOUS)
    passwords = {role: secrets.token_urlsafe(24) + "'\\$@:" for role in ROLES}
    try:
        yield url, engine, passwords
    finally:
        async with engine.begin() as conn:
            await conn.exec_driver_sql("DROP SCHEMA public CASCADE")
            await conn.exec_driver_sql("CREATE SCHEMA public")
            for role in ROLES:
                exists = await conn.exec_driver_sql(f"SELECT FROM pg_roles WHERE rolname = 'ekklesia_{role}'")
                if exists.all():
                    await conn.exec_driver_sql(f"DROP OWNED BY ekklesia_{role}")
                    await conn.exec_driver_sql(f"DROP ROLE ekklesia_{role}")
        await engine.dispose()


@contextmanager
def migration_module():
    spec = importlib.util.spec_from_file_location("db_roles_revision", API / f"alembic/versions/{TARGET}_separate_database_roles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module


async def reapply(engine):
    async with engine.begin() as conn:
        def run(sync_conn):
            with migration_module() as revision, Operations.context(MigrationContext.configure(sync_conn)):
                revision.upgrade()
        await conn.run_sync(run)


async def connect(url):
    return await asyncpg.connect(make_url(url).set(drivername="postgresql").render_as_string(hide_password=False))


async def test_pre_ops_fallback_then_bootstrap_migrator_up_down(db):
    url, engine, passwords = db
    # Deploy migration before the roles exist: current credentials still work.
    cli(url, "upgrade", TARGET)
    await reapply(engine)
    async with engine.connect() as conn:
        assert len((await conn.exec_driver_sql("SELECT viewname FROM pg_views WHERE schemaname='public' AND viewname LIKE 'monitor_%'")).all()) == 6
    bootstrap(url, passwords)
    bootstrap(url, passwords)  # idempotent ownership transfer/password rotation
    migrator = url_for(url, "migrator", passwords["migrator"])
    # MIGRATOR_DATABASE_URL overrides an unusable legacy URL, never API URL.
    bogus = make_url(url).set(database="pnyx_test_no_such_db").render_as_string(hide_password=False)
    cli(bogus, "downgrade", PREVIOUS, migrator_url=migrator)
    cli(bogus, "upgrade", TARGET, migrator_url=migrator)
    migrator_engine = create_async_engine(migrator, poolclass=NullPool)
    try:
        await reapply(migrator_engine)
        cli(url, "downgrade", PREVIOUS, migrator_url=migrator)
        async with engine.connect() as conn:
            assert not (await conn.exec_driver_sql("SELECT FROM pg_views WHERE schemaname='public' AND viewname LIKE 'monitor_%'")).all()
        cli(url, "upgrade", TARGET, migrator_url=migrator)
    finally:
        await migrator_engine.dispose()


async def test_permissions_defaults_and_dump_restore(db, tmp_path):
    url, engine, passwords = db
    bootstrap(url, passwords)
    migrator = url_for(url, "migrator", passwords["migrator"])
    async with engine.begin() as conn:
        # Reconciliation must remove column ACLs as well as table ACLs.
        await conn.exec_driver_sql("GRANT SELECT(private_value) ON public.db_roles_fixture TO PUBLIC, ekklesia_monitor, ekklesia_dashboard")
    cli(url, "upgrade", TARGET, migrator_url=migrator)
    for role in ROLES:
        conn = await connect(url_for(url, role, passwords[role]))
        try:
            assert await conn.fetchval("SELECT current_user") == f"ekklesia_{role}"
            tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            checked_tables = set(FORBIDDEN) | {row[0] for row in tables}
            if role == "api":
                checked_tables.discard("alembic_version")
            for table in checked_tables:
                if role in ("monitor", "dashboard"):
                    with pytest.raises(asyncpg.InsufficientPrivilegeError):
                        await conn.fetch(f"SELECT * FROM public.{table} LIMIT 0")
                else:
                    await conn.fetch(f"SELECT * FROM public.{table} LIMIT 0")
            if role != "migrator":
                for ddl in ("CREATE TABLE public.must_fail(id int)", "CREATE TEMP TABLE must_fail(id int)",
                            "ALTER TABLE public.identity_records ADD COLUMN must_fail int", "CREATE SCHEMA must_fail",
                            "TRUNCATE public.citizen_votes"):
                    with pytest.raises(asyncpg.InsufficientPrivilegeError):
                        await conn.execute(ddl)
            if role in ("monitor", "dashboard", "backup"):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute("DELETE FROM public.identity_records WHERE false")
            if role in ("monitor", "dashboard"):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.fetch("SELECT private_value FROM public.db_roles_fixture")
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.fetch("SELECT * FROM public.parliament_bills LIMIT 0")
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute("SET ROLE ekklesia_migrator")
            if role == "api":
                await conn.execute("INSERT INTO public.db_roles_fixture(private_value) VALUES ('synthetic')")
                await conn.execute("UPDATE public.db_roles_fixture SET private_value='updated'")
                await conn.execute("DELETE FROM public.db_roles_fixture")
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.execute("UPDATE public.alembic_version SET version_num='bad'")
            if role == "backup":
                await conn.fetchval("SELECT last_value FROM public.db_roles_fixture_id_seq")
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.fetchval("SELECT nextval('public.db_roles_fixture_id_seq')")
            if role == "migrator":
                await conn.execute("CREATE TABLE public.future_app_table(id serial, value text)")
                await conn.execute("CREATE VIEW public.future_report AS SELECT count(*) FROM public.future_app_table")
        finally:
            await conn.close()
    for role in ("api", "monitor", "dashboard", "backup"):
        conn = await connect(url_for(url, role, passwords[role]))
        try:
            if role in ("api", "backup"):
                await conn.fetch("SELECT * FROM public.future_app_table")
            else:
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.fetch("SELECT * FROM public.future_app_table")
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.fetch("SELECT * FROM public.future_report")
        finally:
            await conn.close()
    # Dump as the authenticated backup login over TCP; restore locally into an
    # empty database owned by the bootstrap user (no role secrets in argv).
    parsed = make_url(url)
    env = {**os.environ, "PGHOST": parsed.host, "PGPORT": str(parsed.port or 5432), "PGDATABASE": parsed.database,
           "PGUSER": "ekklesia_backup", "PGPASSWORD": passwords["backup"]}
    dump = tmp_path / "roles.dump"
    subprocess.run(["pg_dump", "--no-password", "-Fc", "-f", str(dump)], env=env, check=True, capture_output=True)
    env.update(PGUSER=parsed.username, PGPASSWORD=parsed.password or "")
    async with engine.connect() as conn:
        autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await autocommit.exec_driver_sql("CREATE DATABASE pnyx_test_t9142_restore")
    try:
        subprocess.run(["pg_restore", "--exit-on-error", "--no-owner", "--no-acl", "-d", "pnyx_test_t9142_restore", str(dump)], env=env, check=True, capture_output=True)
        restored = await connect(make_url(url).set(database="pnyx_test_t9142_restore").render_as_string(hide_password=False))
        try:
            assert await restored.fetchval("SELECT version_num FROM public.alembic_version") == TARGET
            assert await restored.fetchval("SELECT COUNT(*) FROM public.monitor_bill_health") == 1
        finally:
            await restored.close()
    finally:
        async with engine.connect() as conn:
            autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await autocommit.exec_driver_sql("DROP DATABASE pnyx_test_t9142_restore")


class MonitorConnection:
    """Run unchanged psycopg-style monitor functions through real asyncpg SQL."""
    def __init__(self, connection):
        self.connection = connection
        self.loop = asyncio.get_running_loop()

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql, params=()):
        counter = iter(range(1, len(params) + 1))
        sql = re.sub(r"%s", lambda _: f"${next(counter)}", sql)
        self.rows = asyncio.run_coroutine_threadsafe(self.connection.fetch(sql, *params), self.loop).result(timeout=10)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0]


async def test_every_monitor_db_check_runs_with_read_only_role(db, monkeypatch):
    url, engine, passwords = db
    bootstrap(url, passwords)
    cli(url, "upgrade", TARGET, migrator_url=url_for(url, "migrator", passwords["migrator"]))
    async with engine.begin() as conn:
        await conn.exec_driver_sql("""INSERT INTO parliament_bills(id,title_el,status,governance_level,source,created_at,updated_at,parliament_vote_date)
            VALUES ('GR-TEST', 'Public bill', 'ACTIVE', 'NATIONAL', 'PARLIAMENT', NOW()-INTERVAL '2 days', NOW()-INTERVAL '1 hour', NOW()-INTERVAL '2 days'),
                   ('GR-SENSITIVE', 'AMKA patient', 'ACTIVE', 'NATIONAL', 'DIAVGEIA', NOW()-INTERVAL '2 days', NOW(), NULL)""")
        await conn.exec_driver_sql("INSERT INTO bill_status_logs(bill_id,from_status,to_status,changed_at) VALUES ('GR-TEST','ANNOUNCED','ACTIVE',NOW()-INTERVAL '3 hours'),('GR-TEST','ACTIVE','WINDOW_24H',NOW()-INTERVAL '2 hours'),('GR-TEST','WINDOW_24H','PARLIAMENT_VOTED',NOW()-INTERVAL '1 hour')")
    sys.modules.setdefault("psycopg2", types.SimpleNamespace())
    sys.path.insert(0, str(ROOT / "apps/monitor"))
    import monitor
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_PUBLICATION_ENABLED", True)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_SCOPE_ALLOWLIST", {"bill:GR-TEST"})
    conn = await connect(url_for(url, "monitor", passwords["monitor"]))
    try:
        adapter = MonitorConnection(conn)
        for check in (monitor.check_no_new_bills, monitor._db_latest_parliament_activity,
                      monitor.check_lifecycle_stuck, monitor.check_lifecycle_fast_forward,
                      monitor.check_forum_missing, monitor.get_forum_missing_catalog,
                      monitor.check_arweave_pending, monitor.check_db_consistency, monitor.check_zk_canary_health):
            result = await asyncio.to_thread(check, adapter)
            if check in (monitor.check_lifecycle_stuck, monitor.check_lifecycle_fast_forward, monitor.check_forum_missing):
                assert len(result) == 1
            if check is monitor.get_forum_missing_catalog:
                assert result["public_actionable"] == 1
                assert result["sensitive_diavgeia"] == 1
        payload = await conn.fetchval("SELECT actionable_bills::text FROM public.monitor_forum_missing WHERE category='sensitive_diavgeia'")
        assert payload == "[]"
    finally:
        await conn.close()
