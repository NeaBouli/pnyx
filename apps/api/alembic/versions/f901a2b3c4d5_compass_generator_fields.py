"""add compass generator fields (source_bill_id, version, generated_by)

Revision ID: f901a2b3c4d5
Revises: e801f2a3b4c5
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = "f901a2b3c4d5"
down_revision = "e801f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("statements", sa.Column("source_bill_id", sa.String(50), nullable=True))
    op.add_column("statements", sa.Column("version", sa.Integer(), nullable=True, server_default="1"))
    op.add_column("statements", sa.Column("generated_by", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("statements", "generated_by")
    op.drop_column("statements", "version")
    op.drop_column("statements", "source_bill_id")
