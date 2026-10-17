"""One ACTIVE identity per public key (EVA-001 v2 registration).

Revision ID: y803a2b3c4d5
Revises: y802a2b3c4d5

Partial unique index on identity_records.public_key_hex for status = 'ACTIVE'.
It backstops the per-key Redis lock of POST /api/v2/identity/verify: two
registrations that bind the same client key to different numbers can never
both commit. Revoked rows keep their old key and are not covered.

The upgrade aborts with a clear error if duplicate ACTIVE keys already exist
(production had 0 on 2026-10-16); it never modifies identity rows.
"""
import sqlalchemy as sa
from alembic import op

revision = "y803a2b3c4d5"
down_revision = "y802a2b3c4d5"
branch_labels = None
depends_on = None

INDEX = "uq_identity_records_active_public_key"


def upgrade() -> None:
    duplicates = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM (SELECT public_key_hex FROM identity_records "
        "WHERE status = 'ACTIVE' GROUP BY public_key_hex HAVING count(*) > 1) d"
    )).scalar()
    if duplicates:
        raise RuntimeError(f"y803: {duplicates} public keys are ACTIVE on several identities; resolve before upgrading")
    op.create_index(
        INDEX, "identity_records", ["public_key_hex"], unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name="identity_records")
