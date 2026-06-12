"""add vote commitment to ZK receipts

Revision ID: t301a2b3c4d5
Revises: s201a2b3c4d5
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = "t301a2b3c4d5"
down_revision = "s201a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "zk_vote_receipts",
        sa.Column("vote_commitment", sa.String(160), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("zk_vote_receipts", "vote_commitment")
