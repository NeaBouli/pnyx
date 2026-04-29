"""add vote correction fields (is_correction, corrected_at, original_vote)

Revision ID: k401a2b3c4d5
Revises: j301a2b3c4d5
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa

revision = "k401a2b3c4d5"
down_revision = "j301a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("citizen_votes", sa.Column("is_correction", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("citizen_votes", sa.Column("corrected_at", sa.DateTime(), nullable=True))
    op.add_column("citizen_votes", sa.Column("original_vote", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("citizen_votes", "original_vote")
    op.drop_column("citizen_votes", "corrected_at")
    op.drop_column("citizen_votes", "is_correction")
