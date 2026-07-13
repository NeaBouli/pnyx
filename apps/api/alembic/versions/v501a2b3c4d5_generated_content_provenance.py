"""Add forward-only generated-content provenance.

Revision ID: v501a2b3c4d5
Revises: u401a2b3c4d5
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v501a2b3c4d5"
down_revision = "u401a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parliament_bills",
        sa.Column("generated_content_provenance", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("parliament_bills", "generated_content_provenance")
