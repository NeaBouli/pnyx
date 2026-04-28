"""add knowledge_base table for RAG Agent

Revision ID: j301a2b3c4d5
Revises: i201a2b3c4d5
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "j301a2b3c4d5"
down_revision = "i201a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("title_el", sa.Text(), nullable=False),
        sa.Column("title_en", sa.Text()),
        sa.Column("content_el", sa.Text(), nullable=False),
        sa.Column("content_en", sa.Text()),
        sa.Column("keywords", JSONB()),
        sa.Column("priority", sa.Integer(), server_default="2"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_kb_category", "knowledge_base", ["category"])


def downgrade() -> None:
    op.drop_table("knowledge_base")
