"""Enforce global, case-insensitive uniqueness of Tier-1 vote_nullifier.

A read-only preflight aborts before any DDL if existing rows already share a
vote_nullifier (exact or case-variant). Nothing is logged, deleted or rewritten;
the operator must resolve the duplicates manually. Legacy/Tier-0 rows with NULL
stay outside the partial index.

Revision ID: x701a2b3c4d5
Revises: v501a2b3c4d5
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "x701a2b3c4d5"
down_revision = "v501a2b3c4d5"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_citizen_votes_vote_nullifier_ci_not_null"
TABLE_NAME = "citizen_votes"

_DUPLICATE_GROUPS_SQL = sa.text(
    "SELECT count(*) FROM ("
    " SELECT 1 FROM citizen_votes"
    " WHERE vote_nullifier IS NOT NULL"
    " GROUP BY lower(vote_nullifier)"
    " HAVING count(*) > 1"
    ") AS duplicate_groups"
)
_INDEX_STATE_SQL = sa.text(
    "SELECT i.indisvalid FROM pg_index i"
    " JOIN pg_class c ON c.oid = i.indexrelid"
    " JOIN pg_namespace n ON n.oid = c.relnamespace"
    " WHERE c.relname = :name AND n.nspname = current_schema()"
)


class VoteNullifierPreflightError(RuntimeError):
    """Existing data violates the new invariant; migration refuses to proceed."""


def _duplicate_group_count(bind: Connection) -> int:
    return int(bind.execute(_DUPLICATE_GROUPS_SQL).scalar_one())


def _index_state(bind: Connection) -> bool | None:
    """None if absent, otherwise pg_index.indisvalid."""
    return bind.execute(_INDEX_STATE_SQL, {"name": INDEX_NAME}).scalar_one_or_none()


def preflight(bind: Connection) -> None:
    """Read-only check; raises without exposing any vote_nullifier value."""
    groups = _duplicate_group_count(bind)
    if groups:
        raise VoteNullifierPreflightError(
            f"{TABLE_NAME}.vote_nullifier has {groups} case-insensitive duplicate "
            f"group(s); refusing to create {INDEX_NAME}. Resolve manually — this "
            "migration never deletes or rewrites vote rows."
        )


def upgrade() -> None:
    bind = op.get_bind()
    preflight(bind)

    if bind.dialect.name != "postgresql":
        op.create_index(
            INDEX_NAME,
            TABLE_NAME,
            [sa.text("lower(vote_nullifier)")],
            unique=True,
            sqlite_where=sa.text("vote_nullifier IS NOT NULL"),
        )
        return

    if _index_state(bind) is not None:
        raise RuntimeError(
            f"{INDEX_NAME} already exists before upgrade; refusing to adopt an "
            "index this migration did not create."
        )

    with op.get_context().autocommit_block():
        try:
            op.execute(
                f"CREATE UNIQUE INDEX CONCURRENTLY {INDEX_NAME} "
                f"ON {TABLE_NAME} (lower(vote_nullifier)) "
                "WHERE vote_nullifier IS NOT NULL"
            )
        except Exception:
            # A failed concurrent build leaves an INVALID index behind. It did
            # not exist before this attempt, so it is ours to remove.
            try:
                if _index_state(bind) is False:
                    op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
            except Exception:  # noqa: BLE001 - best effort; keep the original error
                pass
            raise


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
        return
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
