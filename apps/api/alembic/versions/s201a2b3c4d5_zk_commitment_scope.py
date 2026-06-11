"""add vote scope to ZK identity commitments

Revision ID: s201a2b3c4d5
Revises: r101a2b3c4d5
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = "s201a2b3c4d5"
down_revision = "r101a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "zk_identity_commitments",
        sa.Column("vote_scope_id", sa.String(128), nullable=True),
    )
    op.create_index(
        "idx_zk_commitments_scope",
        "zk_identity_commitments",
        ["vote_scope_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_zk_commitments_scope", table_name="zk_identity_commitments")
    op.drop_column("zk_identity_commitments", "vote_scope_id")
