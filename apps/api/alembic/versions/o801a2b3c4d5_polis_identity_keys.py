"""add polis_identity_keys table for pk_polis registration

Revision ID: o801a2b3c4d5
Revises: n701a2b3c4d5
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "o801a2b3c4d5"
down_revision = "n701a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "polis_identity_keys",
        sa.Column("nullifier_hash", sa.Text(), primary_key=True),
        sa.Column("pk_polis", sa.Text(), unique=True, nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("polis_identity_keys")
