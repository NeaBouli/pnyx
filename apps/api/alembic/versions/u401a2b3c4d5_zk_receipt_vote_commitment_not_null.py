"""require vote commitment on ZK receipts

Revision ID: u401a2b3c4d5
Revises: t301a2b3c4d5
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = "u401a2b3c4d5"
down_revision = "t301a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE zk_vote_receipts SET vote_commitment = 'LEGACY_UNKNOWN' "
        "WHERE vote_commitment IS NULL"
    )
    op.alter_column(
        "zk_vote_receipts",
        "vote_commitment",
        existing_type=sa.String(160),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "zk_vote_receipts",
        "vote_commitment",
        existing_type=sa.String(160),
        nullable=True,
    )
