"""add arweave_tx_id to parliament_bills

Revision ID: c601d2e3f4a5
Revises: b501c2d3e4f5
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = 'c601d2e3f4a5'
down_revision = 'b501c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('parliament_bills',
        sa.Column('arweave_tx_id', sa.String(100), nullable=True)
    )
    op.create_index('idx_bills_arweave', 'parliament_bills', ['arweave_tx_id'])


def downgrade() -> None:
    op.drop_index('idx_bills_arweave', 'parliament_bills')
    op.drop_column('parliament_bills', 'arweave_tx_id')
