"""add diavgeia_votes table

Revision ID: g001a2b3c4d5
Revises: f901a2b3c4d5
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = "g001a2b3c4d5"
down_revision = "f901a2b3c4d5"
branch_labels = None
depends_on = None

vote_enum = sa.Enum("YES", "NO", "ABSTAIN", "UNKNOWN", name="votechoice", create_type=False)


def upgrade() -> None:
    op.create_table(
        "diavgeia_votes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ada", sa.String(20), nullable=False, index=True),
        sa.Column("nullifier_hash", sa.String(64), nullable=False),
        sa.Column("vote", vote_enum, nullable=False),
        sa.Column("voted_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("ada", "nullifier_hash", name="uq_diavgeia_vote"),
    )
    op.create_index("idx_diavgeia_votes_ada", "diavgeia_votes", ["ada"])


def downgrade() -> None:
    op.drop_table("diavgeia_votes")
