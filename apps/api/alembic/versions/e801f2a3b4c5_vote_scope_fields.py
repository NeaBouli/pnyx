"""add vote scope fields (governance_level, dimos_id, periferia_id)

Revision ID: e801f2a3b4c5
Revises: d701e2f3a4b5
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = "e801f2a3b4c5"
down_revision = "d701e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GovernanceLevel enum already exists from decisions table
    governance_enum = sa.Enum("NATIONAL", "REGIONAL", "MUNICIPAL", "COMMUNITY", name="governancelevel")

    # parliament_bills: add governance_level + location FKs
    op.add_column("parliament_bills", sa.Column(
        "governance_level", governance_enum,
        nullable=False, server_default="NATIONAL"
    ))
    op.add_column("parliament_bills", sa.Column(
        "periferia_id", sa.Integer(), nullable=True
    ))
    op.add_column("parliament_bills", sa.Column(
        "dimos_id", sa.Integer(), nullable=True
    ))
    op.create_foreign_key(
        "fk_bills_periferia", "parliament_bills", "periferia",
        ["periferia_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_bills_dimos", "parliament_bills", "dimos",
        ["dimos_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("idx_bills_governance", "parliament_bills", ["governance_level"])

    # identity_records: add location FKs
    op.add_column("identity_records", sa.Column(
        "periferia_id", sa.Integer(), nullable=True
    ))
    op.add_column("identity_records", sa.Column(
        "dimos_id", sa.Integer(), nullable=True
    ))
    op.create_foreign_key(
        "fk_identity_periferia", "identity_records", "periferia",
        ["periferia_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_identity_dimos", "identity_records", "dimos",
        ["dimos_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_identity_dimos", "identity_records", type_="foreignkey")
    op.drop_constraint("fk_identity_periferia", "identity_records", type_="foreignkey")
    op.drop_column("identity_records", "dimos_id")
    op.drop_column("identity_records", "periferia_id")

    op.drop_index("idx_bills_governance", "parliament_bills")
    op.drop_constraint("fk_bills_dimos", "parliament_bills", type_="foreignkey")
    op.drop_constraint("fk_bills_periferia", "parliament_bills", type_="foreignkey")
    op.drop_column("parliament_bills", "dimos_id")
    op.drop_column("parliament_bills", "periferia_id")
    op.drop_column("parliament_bills", "governance_level")
