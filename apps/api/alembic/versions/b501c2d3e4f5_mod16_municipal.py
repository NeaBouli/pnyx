"""mod16 municipal governance tables

Revision ID: b501c2d3e4f5
Revises: a408b698c25b
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'b501c2d3e4f5'
down_revision = 'a408b698c25b'
branch_labels = None
depends_on = None

def upgrade() -> None:
    governance_level = sa.Enum(
        'NATIONAL', 'REGIONAL', 'MUNICIPAL', 'COMMUNITY',
        name='governancelevel'
    )
    governance_level.create(op.get_bind(), checkfirst=True)

    op.create_table('periferia',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name_el', sa.String(100), nullable=False),
        sa.Column('name_en', sa.String(100)),
        sa.Column('code', sa.String(10), unique=True, nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
    )

    op.create_table('dimos',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name_el', sa.String(100), nullable=False),
        sa.Column('name_en', sa.String(100)),
        sa.Column('periferia_id', sa.Integer, sa.ForeignKey('periferia.id'), nullable=False),
        sa.Column('population', sa.Integer),
        sa.Column('is_active', sa.Boolean, default=True),
    )
    op.create_index('idx_dimos_periferia', 'dimos', ['periferia_id'])

    op.create_table('communities',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name_el', sa.String(100), nullable=False),
        sa.Column('name_en', sa.String(100)),
        sa.Column('dimos_id', sa.Integer, sa.ForeignKey('dimos.id'), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
    )

    op.create_table('decisions',
        sa.Column('id', sa.String(60), primary_key=True),
        sa.Column('title_el', sa.Text, nullable=False),
        sa.Column('title_en', sa.Text),
        sa.Column('pill_el', sa.String(200)),
        sa.Column('pill_en', sa.String(200)),
        sa.Column('summary_short_el', sa.Text),
        sa.Column('summary_short_en', sa.Text),
        sa.Column('level', governance_level, nullable=False, server_default='NATIONAL'),
        sa.Column('periferia_id', sa.Integer, sa.ForeignKey('periferia.id')),
        sa.Column('dimos_id', sa.Integer, sa.ForeignKey('dimos.id')),
        sa.Column('community_id', sa.Integer, sa.ForeignKey('communities.id')),
        sa.Column('categories', JSONB),
        sa.Column('authority_votes', JSONB),
        sa.Column('status', sa.String(30), nullable=False, server_default='ANNOUNCED'),
        sa.Column('vote_date', sa.DateTime),
        sa.Column('status_changed_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_decisions_level', 'decisions', ['level'])
    op.create_index('idx_decisions_status', 'decisions', ['status'])
    op.create_index('idx_decisions_periferia', 'decisions', ['periferia_id'])
    op.create_index('idx_decisions_dimos', 'decisions', ['dimos_id'])

def downgrade() -> None:
    op.drop_table('decisions')
    op.drop_table('communities')
    op.drop_table('dimos')
    op.drop_table('periferia')
    sa.Enum(name='governancelevel').drop(op.get_bind(), checkfirst=True)
