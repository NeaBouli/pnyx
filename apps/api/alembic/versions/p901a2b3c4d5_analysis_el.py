"""add analysis_el to parliament_bills

Revision ID: p901a2b3c4d5
Revises: o801a2b3c4d5
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "p901a2b3c4d5"
down_revision = "o801a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parliament_bills", sa.Column("analysis_el", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("parliament_bills", "analysis_el")
