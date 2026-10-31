"""Persist public sensitivity independently of generated prose.

Revision ID: z904a2b3c4d5
Revises: z903a2b3c4d5

The admin endpoint uses the transaction-local pnyx.allow_sensitive_public_block_clear
setting for an explicit flag-only clear. Text writes always remain monotonic.
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
TRIGGER_FUNCTION_DDL = """CREATE OR REPLACE FUNCTION maintain_bill_sensitivity()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF current_setting('pnyx.allow_sensitive_public_block_clear', true) = 'on'
           AND ROW(NEW.source, NEW.title_el, NEW.summary_short_el, NEW.summary_long_el)
               IS NOT DISTINCT FROM
               ROW(OLD.source, OLD.title_el, OLD.summary_short_el, OLD.summary_long_el)
        THEN
            RETURN NEW;
        END IF;
        NEW.sensitive_public_block := OLD.sensitive_public_block
            OR NEW.sensitive_public_block
            OR (public_bill_sensitive(NEW.source, NEW.title_el,
                NEW.summary_short_el, NEW.summary_long_el) IS NOT FALSE);
    ELSE
        NEW.sensitive_public_block := NEW.sensitive_public_block
            OR (public_bill_sensitive(NEW.source, NEW.title_el,
                NEW.summary_short_el, NEW.summary_long_el) IS NOT FALSE);
    END IF;
    RETURN NEW;
END;
$$"""
# Until every row is backfilled, capture removed OLD markers too. Afterwards an
# explicitly cleared latch follows only NEW text; removing an old marker must
# not undo the admin's clear. Replacing the function preserves the trigger.
BACKFILL_TRIGGER_FUNCTION_DDL = TRIGGER_FUNCTION_DDL.replace(
    "OR NEW.sensitive_public_block",
    """OR NEW.sensitive_public_block
            OR (public_bill_sensitive(OLD.source, OLD.title_el,
                OLD.summary_short_el, OLD.summary_long_el) IS NOT FALSE)""",
)
TRIGGER_DDL = """CREATE OR REPLACE TRIGGER trg_bill_sensitivity
BEFORE INSERT OR UPDATE OF source, title_el, summary_short_el, summary_long_el,
    sensitive_public_block ON parliament_bills
FOR EACH ROW EXECUTE FUNCTION maintain_bill_sensitivity()"""


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
    op.execute("DROP TRIGGER trg_bill_sensitivity ON parliament_bills")
    op.execute("DROP FUNCTION maintain_bill_sensitivity()")
    op.execute("""ALTER TABLE parliament_bills
        DROP COLUMN sensitive_public_block,
        DROP COLUMN sensitive_override,
        DROP COLUMN sensitive_override_reason""")
