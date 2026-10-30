"""Cost the public visibility text check so cold queries use the metadata index.

Revision ID: z903a2b3c4d5
Revises: z902a2b3c4d5
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "z903a2b3c4d5"
down_revision = "z902a2b3c4d5"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_bills_public_metadata_v2"
LEGACY_INDEX_NAME = "idx_bills_public_metadata"
# Freeze both policies here; historical DDL must not import application policy.
SENSITIVE_PATTERN = r"αμκα|α\.μ\.κ\.α|amka|ασθεν|εοπυυ|eopyy"
FUNCTION_DDL = f"""CREATE OR REPLACE FUNCTION public_bill_sensitive(
    source text, title text, short text, long text
) RETURNS boolean LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE COST 10000 AS $$
BEGIN
    RETURN coalesce(source = 'DIAVGEIA' AND (
        lower(coalesce(title, '')) ~ '{SENSITIVE_PATTERN}'
        OR lower(coalesce(short, '')) ~ '{SENSITIVE_PATTERN}'
        OR lower(coalesce(long, '')) ~ '{SENSITIVE_PATTERN}'
    ), FALSE);
END;
$$"""
PREDICATE = (
    "admin_hidden IS NOT TRUE AND NOT "
    "public_bill_sensitive(source, title_el, summary_short_el, summary_long_el)"
)
LEGACY_PREDICATE = r"""admin_hidden IS NOT TRUE AND NOT (source = 'DIAVGEIA' AND (
lower(coalesce(title_el, '')) ~ 'αμκα|α\.μ\.κ\.α|amka|ασθεν|εοπυυ|eopyy'
OR lower(coalesce(summary_short_el, '')) ~ 'αμκα|α\.μ\.κ\.α|amka|ασθεν|εοπυυ|eopyy'
OR lower(coalesce(summary_long_el, '')) ~ 'αμκα|α\.μ\.κ\.α|amka|ασθεν|εοπυυ|eopyy'))"""


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


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    _refuse_existing(bind, INDEX_NAME)
    with op.get_context().autocommit_block():
        # PL/pgSQL prevents inlining from discarding the declared evaluation cost.
        op.execute(FUNCTION_DDL)
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
        op.execute("DROP FUNCTION public_bill_sensitive(text, text, text, text)")
