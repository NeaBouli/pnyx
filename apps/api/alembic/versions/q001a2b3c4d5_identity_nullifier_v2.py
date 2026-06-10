"""add versioned identity nullifier v2 fields

Revision ID: q001a2b3c4d5
Revises: p901a2b3c4d5
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision = "q001a2b3c4d5"
down_revision = "p901a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("identity_records", sa.Column("nullifier_hash_v2", sa.String(128), nullable=True))
    op.add_column("identity_records", sa.Column("nullifier_version", sa.String(8), server_default="v1", nullable=False))
    op.add_column("identity_records", sa.Column("nullifier_migrated_at", sa.DateTime(), nullable=True))
    op.create_index("idx_identity_nullifier_v2", "identity_records", ["nullifier_hash_v2"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_identity_nullifier_v2", table_name="identity_records")
    op.drop_column("identity_records", "nullifier_migrated_at")
    op.drop_column("identity_records", "nullifier_version")
    op.drop_column("identity_records", "nullifier_hash_v2")
