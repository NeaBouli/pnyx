"""ADR-022: Tier-1 vote schema — pk_eph, vote_nullifier, linkage_tag, timestamp_ms

Revision ID: h101a2b3c4d5
Revises: g001a2b3c4d5
Create Date: 2026-04-27

All new columns nullable — backward compatible with existing Tier-0 votes.
Deploy with v5 build on 01.05.2026 (Mobile + Server simultaneously).
"""
from alembic import op
import sqlalchemy as sa

revision = "h101a2b3c4d5"
down_revision = "g001a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("citizen_votes", sa.Column("pk_eph", sa.String(64), nullable=True))
    op.add_column("citizen_votes", sa.Column("vote_nullifier", sa.String(64), nullable=True))
    op.add_column("citizen_votes", sa.Column("linkage_tag", sa.String(64), nullable=True))
    op.add_column("citizen_votes", sa.Column("timestamp_ms", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("citizen_votes", "timestamp_ms")
    op.drop_column("citizen_votes", "linkage_tag")
    op.drop_column("citizen_votes", "vote_nullifier")
    op.drop_column("citizen_votes", "pk_eph")
