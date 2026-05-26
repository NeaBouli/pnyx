"""add polis_tickets and polis_votes tables

Revision ID: n701a2b3c4d5
Revises: m601a2b3c4d5
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "n701a2b3c4d5"
down_revision = "m601a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "polis_tickets",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("pk_polis", sa.Text(), nullable=False),
        sa.Column("ticket_nullifier", sa.Text(), unique=True, nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("up_votes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("down_votes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("category IN ('bug', 'proposal', 'vote')", name="ck_polis_tickets_category"),
        sa.CheckConstraint("status IN ('pending', 'open', 'claimed', 'resolved', 'spam')", name="ck_polis_tickets_status"),
    )

    op.create_table(
        "polis_votes",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("ticket_id", sa.Text(), sa.ForeignKey("polis_tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vote", sa.Text(), nullable=False),
        sa.Column("pk_polis", sa.Text(), nullable=False),
        sa.Column("vote_nullifier", sa.Text(), unique=True, nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("vote IN ('up', 'down')", name="ck_polis_votes_vote"),
        sa.UniqueConstraint("ticket_id", "pk_polis", name="uq_polis_votes_ticket_voter"),
    )


def downgrade() -> None:
    op.drop_table("polis_votes")
    op.drop_table("polis_tickets")
