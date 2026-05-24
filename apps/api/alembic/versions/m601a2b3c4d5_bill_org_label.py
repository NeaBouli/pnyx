"""add org_label to parliament_bills for INSTITUTIONAL forum titles

Revision ID: m601a2b3c4d5
Revises: l501a2b3c4d5
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa

revision = "m601a2b3c4d5"
down_revision = "l501a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parliament_bills",
        sa.Column("org_label", sa.Text(), nullable=True),
    )

    # Backfill from diavgeia_decisions where source is DIAVGEIA
    # Exclude unknown/blank labels
    op.execute("""
        UPDATE parliament_bills pb
        SET org_label = TRIM(dd.organization_label)
        FROM diavgeia_decisions dd
        WHERE pb.diavgeia_ada = dd.ada
          AND pb.source = 'DIAVGEIA'
          AND pb.org_label IS NULL
          AND dd.organization_label IS NOT NULL
          AND TRIM(dd.organization_label) != ''
          AND dd.organization_label NOT LIKE '[unknown:%'
          AND LOWER(TRIM(dd.organization_label)) != 'unknown'
    """)


def downgrade() -> None:
    op.drop_column("parliament_bills", "org_label")
