"""Cover public bill metadata without re-reading imported text on every request.

Revision ID: z902a2b3c4d5
Revises: z901a2b3c4d5
"""
from alembic import op
import sqlalchemy as sa


revision = "z902a2b3c4d5"
down_revision = "z901a2b3c4d5"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_bills_public_metadata"
# Freeze the policy here: a later application change must not change old DDL.
PREDICATE = r"""admin_hidden IS NOT TRUE AND NOT (source = 'DIAVGEIA' AND (
lower(coalesce(title_el, '')) ~ 'αμκα|α\.μ\.κ\.α|amka|ασθεν|εοπυυ|eopyy'
OR lower(coalesce(summary_short_el, '')) ~ 'αμκα|α\.μ\.κ\.α|amka|ασθεν|εοπυυ|eopyy'
OR lower(coalesce(summary_long_el, '')) ~ 'αμκα|α\.μ\.κ\.α|amka|ασθεν|εοπυυ|eopyy'))"""


def _index_state(bind):
    return bind.execute(sa.text(
        "SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE c.relname = :name AND n.nspname = current_schema()"
    ), {"name": INDEX_NAME}).scalar_one_or_none()


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if _index_state(bind) is not None:
        raise RuntimeError(f"{INDEX_NAME} already exists; refusing to adopt an unknown index")
    with op.get_context().autocommit_block():
        try:
            op.execute(
                f"CREATE INDEX CONCURRENTLY {INDEX_NAME} ON parliament_bills (id) "
                "INCLUDE (source, status, results_visibility, governance_level, dimos_id, periferia_id) "
                f"WHERE {PREDICATE}"
            )
        except Exception:
            try:
                if _index_state(bind) is False:
                    op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
            except Exception:
                pass  # Preserve the original build failure.
            raise


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
