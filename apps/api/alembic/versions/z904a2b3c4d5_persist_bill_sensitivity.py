"""Persist public sensitivity independently of generated prose.

Revision ID: z904a2b3c4d5
Revises: z903a2b3c4d5

Only the table owner may override or clear sensitivity. The API reaches that
owner through a reasoned, audited SECURITY DEFINER function.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "z904a2b3c4d5"
down_revision = "z903a2b3c4d5"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_bills_public_metadata_v3"
LEGACY_INDEX_NAME = "idx_bills_public_metadata_v2"
BATCH_SIZE = 1000
# Historical DDL must not import application policy.
PREDICATE = (
    "admin_hidden IS NOT TRUE AND "
    "coalesce(sensitive_override, sensitive_public_block) IS NOT TRUE"
)
LEGACY_PREDICATE = (
    "admin_hidden IS NOT TRUE AND NOT "
    "public_bill_sensitive(source, title_el, summary_short_el, summary_long_el)"
)
TRIGGER_FUNCTION_DDL = """DO $install$ BEGIN
EXECUTE format($ddl$CREATE OR REPLACE FUNCTION maintain_bill_sensitivity()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, %1$I AS $$
DECLARE
    table_owner name;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF ROW(NEW.sensitive_override, NEW.sensitive_override_reason)
               IS DISTINCT FROM ROW(OLD.sensitive_override, OLD.sensitive_override_reason)
           OR (OLD.sensitive_public_block AND NOT NEW.sensitive_public_block) THEN
            SELECT pg_catalog.pg_get_userbyid(relowner) INTO table_owner
                FROM pg_catalog.pg_class WHERE oid = TG_RELID;
            IF current_user <> table_owner THEN
                RAISE EXCEPTION 'Only the table owner may override or clear bill sensitivity'
                    USING ERRCODE = '42501';
            END IF;
        END IF;
        IF ROW(NEW.source, NEW.title_el, NEW.summary_short_el, NEW.summary_long_el)
            IS NOT DISTINCT FROM
            ROW(OLD.source, OLD.title_el, OLD.summary_short_el, OLD.summary_long_el) THEN
            RETURN NEW;
        END IF;
        NEW.sensitive_public_block := OLD.sensitive_public_block
            OR NEW.sensitive_public_block
            OR (public_bill_sensitive(NEW.source, NEW.title_el,
                NEW.summary_short_el, NEW.summary_long_el) IS NOT FALSE);
    ELSE
        IF NEW.sensitive_override IS NOT NULL THEN
            SELECT pg_catalog.pg_get_userbyid(relowner) INTO table_owner
                FROM pg_catalog.pg_class WHERE oid = TG_RELID;
            IF current_user <> table_owner THEN
                RAISE EXCEPTION 'Only the table owner may insert a bill sensitivity override'
                    USING ERRCODE = '42501';
            END IF;
        END IF;
        NEW.sensitive_public_block := NEW.sensitive_public_block
            OR (public_bill_sensitive(NEW.source, NEW.title_el,
                NEW.summary_short_el, NEW.summary_long_el) IS NOT FALSE);
    END IF;
    RETURN NEW;
END;
$$ $ddl$, current_schema());
END $install$"""
# Until every row is backfilled, capture removed OLD markers too. Afterwards an
# explicitly cleared latch follows only NEW text; removing an old marker must
# not undo the admin's clear. Replacing the function preserves the trigger.
BACKFILL_TRIGGER_FUNCTION_DDL = TRIGGER_FUNCTION_DDL.replace(
    "OR NEW.sensitive_public_block",
    """OR NEW.sensitive_public_block
            OR (public_bill_sensitive(OLD.source, OLD.title_el,
                OLD.summary_short_el, OLD.summary_long_el) IS NOT FALSE)""",
)
# Deleting or re-keying a protected row would let a fresh INSERT under the same
# id start unflagged (and drop a hide override) without the audited function.
IDENTITY_GUARD_FUNCTION_DDL = """DO $install$ BEGIN
EXECUTE format($ddl$CREATE OR REPLACE FUNCTION guard_bill_sensitivity_identity()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, %1$I AS $$
DECLARE
    table_owner name;
BEGIN
    IF OLD.sensitive_public_block OR OLD.sensitive_override IS NOT NULL THEN
        SELECT pg_catalog.pg_get_userbyid(relowner) INTO table_owner
            FROM pg_catalog.pg_class WHERE oid = TG_RELID;
        IF current_user <> table_owner THEN
            RAISE EXCEPTION 'Only the table owner may delete or re-key a sensitivity-protected bill'
                USING ERRCODE = '42501';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ $ddl$, current_schema());
END $install$"""
IDENTITY_GUARD_TRIGGERS_DDL = (
    """CREATE OR REPLACE TRIGGER trg_bill_sensitivity_delete
BEFORE DELETE ON parliament_bills
FOR EACH ROW EXECUTE FUNCTION guard_bill_sensitivity_identity()""",
    """CREATE OR REPLACE TRIGGER trg_bill_sensitivity_rekey
BEFORE UPDATE OF id ON parliament_bills
FOR EACH ROW WHEN (OLD.id IS DISTINCT FROM NEW.id)
EXECUTE FUNCTION guard_bill_sensitivity_identity()""",
)
TRIGGER_DDL = """CREATE OR REPLACE TRIGGER trg_bill_sensitivity
BEFORE INSERT OR UPDATE OF source, title_el, summary_short_el, summary_long_el,
    sensitive_public_block, sensitive_override, sensitive_override_reason ON parliament_bills
FOR EACH ROW EXECUTE FUNCTION maintain_bill_sensitivity()"""
ADMIN_FUNCTION_SIGNATURE = "admin_set_bill_sensitivity(text, boolean, boolean, text, text)"
# Bind table names to the migration's schema, independently of the caller's
# search_path (also supports the disposable schemas used by PostgreSQL tests).
ADMIN_FUNCTION_DDL = """DO $install$ BEGIN
EXECUTE format($ddl$CREATE OR REPLACE FUNCTION admin_set_bill_sensitivity(
    p_bill_id text, p_override boolean, p_clear_flag boolean, p_reason text, p_actor text
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
DECLARE
    previous %1$I.parliament_bills%%ROWTYPE;
    updated %1$I.parliament_bills%%ROWTYPE;
BEGIN
    IF p_reason IS NULL OR p_reason !~ '[^[:space:]]' THEN
        RAISE EXCEPTION 'A non-empty reason is required' USING ERRCODE = '22023';
    END IF;
    IF p_actor IS NULL OR p_actor !~ '[^[:space:]]' THEN
        RAISE EXCEPTION 'A non-empty actor is required' USING ERRCODE = '22023';
    END IF;
    SELECT * INTO STRICT previous FROM %1$I.parliament_bills
        WHERE id = p_bill_id FOR UPDATE;
    UPDATE %1$I.parliament_bills SET sensitive_override = p_override,
        sensitive_override_reason = p_reason,
        sensitive_public_block = CASE WHEN p_clear_flag THEN false ELSE sensitive_public_block END
        WHERE id = p_bill_id RETURNING * INTO updated;
    INSERT INTO %1$I.audit_log (action, actor, target_type, target_id, metadata)
        VALUES ('bill.sensitivity_override', p_actor, 'parliament_bill', p_bill_id,
            jsonb_build_object('reason', p_reason,
                'before', jsonb_build_object(
                    'sensitive_public_block', previous.sensitive_public_block,
                    'sensitive_override', previous.sensitive_override,
                    'sensitive_override_reason', previous.sensitive_override_reason),
                'after', jsonb_build_object(
                    'sensitive_public_block', updated.sensitive_public_block,
                    'sensitive_override', updated.sensitive_override,
                    'sensitive_override_reason', updated.sensitive_override_reason)));
END;
$$ $ddl$, current_schema());
END $install$"""
ADMIN_FUNCTION_GRANT_DDL = f"""DO $$ BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'ekklesia_api') THEN
        GRANT EXECUTE ON FUNCTION {ADMIN_FUNCTION_SIGNATURE} TO ekklesia_api;
    END IF;
END $$"""


def _index_state(bind: Connection, name: str) -> bool | None:
    return bind.execute(sa.text(
        "SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE c.relname = :name AND n.nspname = current_schema()"
    ), {"name": name}).scalar_one_or_none()


def _refuse_existing(bind: Connection, name: str) -> None:
    if _index_state(bind, name) is not None:
        raise RuntimeError(f"{name} already exists; refusing to adopt an unknown index")


def _create_index(bind: Connection, name: str, predicate: str) -> None:
    try:
        op.execute(
            f"CREATE INDEX CONCURRENTLY {name} ON parliament_bills (id) "
            "INCLUDE (source, status, results_visibility, governance_level, dimos_id, periferia_id) "
            f"WHERE {predicate}"
        )
    except Exception:
        try:
            if _index_state(bind, name) is False:
                op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
        except Exception:
            pass  # Preserve the original build failure.
        raise


def _backfill(bind: Connection) -> None:
    after: str | None = None
    while True:
        where = "" if after is None else "WHERE id > :after"
        boundary = bind.execute(sa.text(f"""
            WITH batch AS (
                SELECT id FROM parliament_bills {where} ORDER BY id LIMIT :size
            ), updated AS (
            UPDATE parliament_bills b
            SET sensitive_public_block = b.sensitive_public_block OR
                (public_bill_sensitive(b.source, b.title_el,
                    b.summary_short_el, b.summary_long_el) IS NOT FALSE)
            FROM batch WHERE b.id = batch.id RETURNING b.id
            ) SELECT max(id) FROM batch
        """), {"after": after, "size": BATCH_SIZE}).scalar_one()
        if boundary is None:
            return
        # Use database collation and selected IDs, even if a concurrent delete
        # removes every UPDATE target in this batch.
        after = boundary


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    _refuse_existing(bind, INDEX_NAME)
    # Fast constant defaults; install the trigger in the same short DDL transaction.
    # IF NOT EXISTS permits a retry after a failed concurrent index build. Backfill
    # only ORs flags, preserving any intervening writes or admin overrides.
    op.execute("""ALTER TABLE parliament_bills
        ADD COLUMN IF NOT EXISTS sensitive_public_block boolean NOT NULL DEFAULT false,
        ADD COLUMN IF NOT EXISTS sensitive_override boolean NULL,
        ADD COLUMN IF NOT EXISTS sensitive_override_reason text NULL""")
    op.execute(BACKFILL_TRIGGER_FUNCTION_DDL)
    op.execute(TRIGGER_DDL)
    op.execute(IDENTITY_GUARD_FUNCTION_DDL)
    for ddl in IDENTITY_GUARD_TRIGGERS_DDL:
        op.execute(ddl)
    op.execute(ADMIN_FUNCTION_DDL)
    op.execute(f"REVOKE ALL ON FUNCTION {ADMIN_FUNCTION_SIGNATURE} FROM PUBLIC")
    op.execute(ADMIN_FUNCTION_GRANT_DDL)
    with op.get_context().autocommit_block():
        # Each statement commits <= 1000 rows; the DDL lock is already released.
        # IS NOT FALSE retains NULL sensitivity outcomes that NOT(...) used to hide.
        _backfill(bind)
        op.execute(TRIGGER_FUNCTION_DDL)
        _create_index(bind, INDEX_NAME, PREDICATE)
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {LEGACY_INDEX_NAME}")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    _refuse_existing(bind, LEGACY_INDEX_NAME)
    with op.get_context().autocommit_block():
        _create_index(bind, LEGACY_INDEX_NAME, LEGACY_PREDICATE)
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
    op.execute("DROP TRIGGER IF EXISTS trg_bill_sensitivity_rekey ON parliament_bills")
    op.execute("DROP TRIGGER IF EXISTS trg_bill_sensitivity_delete ON parliament_bills")
    op.execute("DROP FUNCTION IF EXISTS guard_bill_sensitivity_identity()")
    op.execute("DROP TRIGGER trg_bill_sensitivity ON parliament_bills")
    op.execute("DROP FUNCTION maintain_bill_sensitivity()")
    op.execute(f"DROP FUNCTION {ADMIN_FUNCTION_SIGNATURE}")
    op.execute("""ALTER TABLE parliament_bills
        DROP COLUMN sensitive_public_block,
        DROP COLUMN sensitive_override,
        DROP COLUMN sensitive_override_reason""")
