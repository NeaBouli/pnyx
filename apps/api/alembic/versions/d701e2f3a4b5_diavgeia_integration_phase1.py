"""diavgeia_integration_phase1

Revision ID: d701e2f3a4b5
Revises: c601d2e3f4a5
Create Date: 2026-04-24

New tables:
- diavgeia_decisions (raw Diavgeia snapshot)
- dimos_diavgeia_orgs (1:N mapping dimos <-> Diavgeia organizations)
- decisions.diavgeia_ada FK column
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'd701e2f3a4b5'
down_revision = 'c601d2e3f4a5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Table: diavgeia_decisions ────────────────────────────────────────────
    op.create_table(
        'diavgeia_decisions',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('ada', sa.String(32), unique=True, nullable=False),
        sa.Column('subject', sa.Text, nullable=False),
        sa.Column('decision_type_uid', sa.String(16), nullable=False),
        sa.Column('decision_type_label', sa.Text),
        sa.Column('organization_uid', sa.String(16), nullable=False),
        sa.Column('organization_label', sa.Text, nullable=False),
        sa.Column('document_url', sa.Text, nullable=False),
        sa.Column('submission_timestamp', sa.DateTime(timezone=True)),
        sa.Column('publish_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('raw_payload', JSONB, nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('dimos_id', sa.Integer, sa.ForeignKey('dimos.id', ondelete='SET NULL'), nullable=True),
        sa.Column('periferia_id', sa.Integer, sa.ForeignKey('periferia.id', ondelete='SET NULL'), nullable=True),
        sa.CheckConstraint("length(ada) BETWEEN 10 AND 32", name='diavgeia_decisions_ada_chk'),
    )
    op.create_index('ix_diavgeia_decisions_org_published', 'diavgeia_decisions',
                     ['organization_uid', sa.text('publish_timestamp DESC')])
    op.create_index('ix_diavgeia_decisions_dimos_published', 'diavgeia_decisions',
                     ['dimos_id', sa.text('publish_timestamp DESC')])
    op.create_index('ix_diavgeia_decisions_type_published', 'diavgeia_decisions',
                     ['decision_type_uid', sa.text('publish_timestamp DESC')])

    # ── Table: dimos_diavgeia_orgs ──────────────────────────────────────────
    op.create_table(
        'dimos_diavgeia_orgs',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('dimos_id', sa.Integer, sa.ForeignKey('dimos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('diavgeia_uid', sa.String(16), nullable=False),
        sa.Column('org_label', sa.Text, nullable=False),
        sa.Column('org_category', sa.String(32)),
        sa.Column('is_primary', sa.Boolean, nullable=False, server_default=sa.text('false')),
        sa.Column('match_confidence', sa.Numeric(4, 3)),
        sa.Column('verified_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('dimos_id', 'diavgeia_uid', name='uq_dimos_diavgeia_org'),
    )
    op.create_index('ix_dimos_diavgeia_orgs_uid', 'dimos_diavgeia_orgs', ['diavgeia_uid'])

    # ── ALTER decisions: add diavgeia_ada FK ────────────────────────────────
    op.add_column('decisions', sa.Column('diavgeia_ada', sa.String(32), nullable=True))
    op.create_foreign_key(
        'fk_decisions_diavgeia_ada', 'decisions', 'diavgeia_decisions',
        ['diavgeia_ada'], ['ada'], ondelete='SET NULL',
    )
    op.create_index('ix_decisions_diavgeia_ada', 'decisions', ['diavgeia_ada'])


def downgrade() -> None:
    # ── Reverse decisions column ────────────────────────────────────────────
    op.drop_index('ix_decisions_diavgeia_ada', 'decisions')
    op.drop_constraint('fk_decisions_diavgeia_ada', 'decisions', type_='foreignkey')
    op.drop_column('decisions', 'diavgeia_ada')

    # ── Drop dimos_diavgeia_orgs ────────────────────────────────────────────
    op.drop_index('ix_dimos_diavgeia_orgs_uid', 'dimos_diavgeia_orgs')
    op.drop_table('dimos_diavgeia_orgs')

    # ── Drop diavgeia_decisions ─────────────────────────────────────────────
    op.drop_index('ix_diavgeia_decisions_type_published', 'diavgeia_decisions')
    op.drop_index('ix_diavgeia_decisions_dimos_published', 'diavgeia_decisions')
    op.drop_index('ix_diavgeia_decisions_org_published', 'diavgeia_decisions')
    op.drop_table('diavgeia_decisions')
