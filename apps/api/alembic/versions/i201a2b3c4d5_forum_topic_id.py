"""add forum_topic_id to parliament_bills

Revision ID: i201a2b3c4d5
Revises: h101a2b3c4d5
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = "i201a2b3c4d5"
down_revision = "h101a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parliament_bills", sa.Column("forum_topic_id", sa.Integer(), nullable=True))
    op.create_index("idx_bills_forum_topic_id", "parliament_bills", ["forum_topic_id"])


def downgrade() -> None:
    op.drop_index("idx_bills_forum_topic_id", "parliament_bills")
    op.drop_column("parliament_bills", "forum_topic_id")
