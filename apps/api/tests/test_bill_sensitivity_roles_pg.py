"""z904 permission boundary using z901's disposable split-role bootstrap."""
import json

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.pg_public_bill_schema import public_metadata_revision, sensitivity_revision
from tests.pg_vote_schema import requires_postgres
from tests.test_db_roles_pg import bootstrap, cli, connect, db, url_for  # noqa: F401
from tests.test_public_bill_snapshot_pg import migrate

pytestmark = requires_postgres


@pytest.fixture
async def sensitivity_roles(db):
    url, bootstrap_engine, passwords = db
    bootstrap(url, passwords)
    # The shared fixture installs this predecessor function as the bootstrap
    # superuser; model the ownership it has when z903 runs as the migrator.
    async with bootstrap_engine.begin() as connection:
        await connection.exec_driver_sql("""ALTER FUNCTION public_bill_sensitive(text, text, text, text)
            OWNER TO ekklesia_migrator""")
    owner_url = url_for(url, "migrator", passwords["migrator"])
    cli(url, "upgrade", "z901a2b3c4d5", migrator_url=owner_url)
    engine = create_async_engine(owner_url, poolclass=NullPool)
    try:
        async with engine.connect() as owner:
            owner = await owner.execution_options(isolation_level="AUTOCOMMIT")
            await owner.exec_driver_sql("""ALTER TABLE parliament_bills
                DROP COLUMN sensitive_public_block, DROP COLUMN sensitive_override,
                DROP COLUMN sensitive_override_reason""")
            await owner.exec_driver_sql("""INSERT INTO parliament_bills
                (id, source, title_el, status, governance_level)
                VALUES ('S', 'DIAVGEIA', 'Synthetic AMKA marker', 'OPEN_END', 'NATIONAL')""")
            await migrate(owner, public_metadata_revision(), "upgrade")
            await migrate(owner, sensitivity_revision(), "upgrade")
            runtime = await connect(url_for(url, "api", passwords["api"]))
            try:
                yield owner, runtime
            finally:
                await runtime.close()
    finally:
        await engine.dispose()


async def test_runtime_cannot_override_clear_or_spoof_owner_with_settings(sensitivity_roles):
    _owner, runtime = sensitivity_roles
    assert await runtime.fetchval("SELECT current_user") == "ekklesia_api"
    assert await runtime.fetchval("SELECT sensitive_public_block FROM parliament_bills WHERE id = 'S'") is True
    # These fail because of the trigger, despite the runtime role's table DML grants.
    writes = (
        "UPDATE parliament_bills SET sensitive_override = false WHERE id = 'S'",
        "UPDATE parliament_bills SET sensitive_override = true WHERE id = 'S'",
        "UPDATE parliament_bills SET sensitive_override_reason = 'unaudited' WHERE id = 'S'",
        "UPDATE parliament_bills SET sensitive_public_block = false WHERE id = 'S'",
        "UPDATE parliament_bills SET title_el = 'ordinary', sensitive_public_block = false WHERE id = 'S'",
        "INSERT INTO parliament_bills (id, title_el, sensitive_override) VALUES ('BAD', 'ordinary', false)",
        "INSERT INTO parliament_bills (id, title_el, sensitive_override) VALUES ('BAD', 'ordinary', true)",
    )
    for setting in (None, "pnyx.allow_sensitive_public_block_clear", "pnyx.admin", "app.is_admin"):
        if setting:
            await runtime.execute(f"SET {setting} = 'on'")
        for sql in writes:
            with pytest.raises(asyncpg.InsufficientPrivilegeError, match="Only the table owner"):
                await runtime.execute(sql)
    assert await runtime.fetchval("SELECT count(*) FROM audit_log") == 0
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await runtime.execute("SET ROLE ekklesia_migrator")

    # Normal runtime writes can latch new markers, but never remove an old latch.
    await runtime.execute("""INSERT INTO parliament_bills (id, source, title_el, status, governance_level)
        VALUES ('TEXT', 'DIAVGEIA', 'ordinary', 'OPEN_END', 'NATIONAL')""")
    assert await runtime.fetchval("SELECT sensitive_public_block FROM parliament_bills WHERE id = 'TEXT'") is False
    for title in ("AMKA", "regenerated ordinary text", ""):
        await runtime.execute("UPDATE parliament_bills SET title_el = $1 WHERE id = 'TEXT'", title)
        assert await runtime.fetchval("SELECT sensitive_public_block FROM parliament_bills WHERE id = 'TEXT'") is True


@pytest.mark.parametrize("clear", [False, True])
async def test_definer_validates_audits_and_grants_only_runtime(sensitivity_roles, clear):
    owner, runtime = sensitivity_roles
    identity = (await owner.exec_driver_sql("""SELECT p.proowner = c.relowner,
        p.prosecdef, p.proconfig,
        has_function_privilege('ekklesia_api', p.oid, 'EXECUTE'),
        has_function_privilege('ekklesia_monitor', p.oid, 'EXECUTE'),
        has_function_privilege('ekklesia_dashboard', p.oid, 'EXECUTE'),
        has_function_privilege('ekklesia_backup', p.oid, 'EXECUTE')
        FROM pg_proc p CROSS JOIN pg_class c
        WHERE p.oid = 'admin_set_bill_sensitivity(text,boolean,boolean,text,text)'::regprocedure
          AND c.oid = 'parliament_bills'::regclass""")).one()
    assert tuple(identity) == (True, True, ["search_path=pg_catalog, public"], True, False, False, False)
    call = "SELECT admin_set_bill_sensitivity('S', $1, $2, $3, $4)"
    for reason, actor in ((None, "admin"), ("", "admin"), (" \n\t", "admin"),
                          ("review", None), ("review", ""), ("review", " \n\t")):
        with pytest.raises(asyncpg.InvalidParameterValueError):
            await runtime.execute(call, False, clear, reason, actor)
    assert await runtime.fetchval("SELECT count(*) FROM audit_log") == 0
    assert await runtime.fetchval("SELECT sensitive_override FROM parliament_bills WHERE id = 'S'") is None

    await runtime.execute(call, False, clear, "Synthetic review", "test_admin")
    bill = await runtime.fetchrow("SELECT sensitive_override, sensitive_override_reason, sensitive_public_block FROM parliament_bills WHERE id = 'S'")
    assert tuple(bill) == (False, "Synthetic review", not clear)
    audits = await runtime.fetch("SELECT action, actor, target_type, target_id, metadata FROM audit_log")
    assert len(audits) == 1
    audit = audits[0]
    assert tuple(audit)[:4] == ("bill.sensitivity_override", "test_admin", "parliament_bill", "S")
    assert json.loads(audit["metadata"]) == {"reason": "Synthetic review", "before": {
        "sensitive_public_block": True, "sensitive_override": None, "sensitive_override_reason": None,
    }, "after": {"sensitive_public_block": not clear, "sensitive_override": False,
                  "sensitive_override_reason": "Synthetic review"}}
    # Runtime cannot erase an existing decision or its justification either.
    for assignment in ("sensitive_override = NULL", "sensitive_override_reason = NULL"):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await runtime.execute(f"UPDATE parliament_bills SET {assignment} WHERE id = 'S'")


@pytest.mark.asyncio
async def test_runtime_cannot_delete_or_rekey_protected_bills(sensitivity_roles):
    _owner, runtime = sensitivity_roles
    assert await runtime.fetchval("SELECT sensitive_public_block FROM parliament_bills WHERE id = 'S'") is True
    # DELETE + re-INSERT under the same id would start unflagged without the audited function.
    for sql in ("DELETE FROM parliament_bills WHERE id = 'S'",
                "UPDATE parliament_bills SET id = 'S-renamed' WHERE id = 'S'"):
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="delete or re-key"):
            await runtime.execute(sql)
    assert await runtime.fetchval("SELECT count(*) FROM parliament_bills WHERE id = 'S'") == 1
    # Unprotected rows keep ordinary runtime DML.
    await runtime.execute("""INSERT INTO parliament_bills (id, source, title_el, status, governance_level)
        VALUES ('PLAIN', 'DIAVGEIA', 'Ordinary procurement', 'OPEN_END', 'NATIONAL')""")
    await runtime.execute("UPDATE parliament_bills SET id = 'PLAIN-2' WHERE id = 'PLAIN'")
    await runtime.execute("DELETE FROM parliament_bills WHERE id = 'PLAIN-2'")
    assert await runtime.fetchval("SELECT count(*) FROM parliament_bills WHERE id LIKE 'PLAIN%'") == 0
