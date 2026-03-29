"""initial schema — all v7 tables

Revision ID: a408b698c25b
Revises:
Create Date: 2026-03-29 22:14:07.549756

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a408b698c25b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === Enums ===
    billstatus = sa.Enum('ANNOUNCED', 'ACTIVE', 'WINDOW_24H', 'PARLIAMENT_VOTED', 'OPEN_END', name='billstatus')
    votechoice = sa.Enum('YES', 'NO', 'ABSTAIN', 'UNKNOWN', name='votechoice')
    keystatus = sa.Enum('ACTIVE', 'REVOKED', name='keystatus')
    billstatus.create(op.get_bind(), checkfirst=True)
    votechoice.create(op.get_bind(), checkfirst=True)
    keystatus.create(op.get_bind(), checkfirst=True)

    # === MOD-01: Identity ===
    op.create_table('identity_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nullifier_hash', sa.String(64), nullable=False),
        sa.Column('public_key_hex', sa.String(128), nullable=False),
        sa.Column('demographic_hash', sa.String(64), nullable=True),
        sa.Column('age_group', sa.String(20), nullable=True),
        sa.Column('region', sa.String(30), nullable=True),
        sa.Column('gender_code', sa.String(20), nullable=True),
        sa.Column('status', keystatus, nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('nullifier_hash'),
    )
    op.create_index('idx_identity_nullifier', 'identity_records', ['nullifier_hash'])
    op.create_index('idx_identity_status', 'identity_records', ['status'])

    # === MOD-02: VAA — Parties ===
    op.create_table('parties',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name_el', sa.String(100), nullable=False),
        sa.Column('name_en', sa.String(100), nullable=True),
        sa.Column('abbreviation', sa.String(20), nullable=True),
        sa.Column('logo_url', sa.Text(), nullable=True),
        sa.Column('color_hex', sa.String(7), nullable=True),
        sa.Column('description_el', sa.Text(), nullable=True),
        sa.Column('description_en', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # === MOD-02: VAA — Statements ===
    op.create_table('statements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('text_el', sa.Text(), nullable=False),
        sa.Column('text_en', sa.Text(), nullable=True),
        sa.Column('explanation_el', sa.Text(), nullable=True),
        sa.Column('explanation_en', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('display_order', sa.Integer(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # === MOD-02: VAA — Party Positions ===
    op.create_table('party_positions',
        sa.Column('party_id', sa.Integer(), sa.ForeignKey('parties.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('statement_id', sa.Integer(), sa.ForeignKey('statements.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('position', sa.SmallInteger(), nullable=False),
        sa.CheckConstraint('position IN (-1, 0, 1)', name='ck_position_valid'),
    )

    # === MOD-03: Parliament — Bills ===
    op.create_table('parliament_bills',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('title_el', sa.Text(), nullable=False),
        sa.Column('title_en', sa.Text(), nullable=True),
        sa.Column('pill_el', sa.String(200), nullable=True),
        sa.Column('pill_en', sa.String(200), nullable=True),
        sa.Column('summary_short_el', sa.Text(), nullable=True),
        sa.Column('summary_short_en', sa.Text(), nullable=True),
        sa.Column('summary_long_el', sa.Text(), nullable=True),
        sa.Column('summary_long_en', sa.Text(), nullable=True),
        sa.Column('categories', postgresql.JSONB(), nullable=True),
        sa.Column('party_votes_parliament', postgresql.JSONB(), nullable=True),
        sa.Column('status', billstatus, nullable=False, server_default='ANNOUNCED'),
        sa.Column('parliament_vote_date', sa.DateTime(), nullable=True),
        sa.Column('status_changed_at', sa.DateTime(), nullable=True),
        sa.Column('ai_summary_reviewed', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_bills_status', 'parliament_bills', ['status'])
    op.create_index('idx_bills_vote_date', 'parliament_bills', ['parliament_vote_date'])

    # === MOD-03: Parliament — Status Log ===
    op.create_table('bill_status_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('bill_id', sa.String(50), sa.ForeignKey('parliament_bills.id'), nullable=False),
        sa.Column('from_status', sa.String(30), nullable=True),
        sa.Column('to_status', sa.String(30), nullable=False),
        sa.Column('changed_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_statuslog_bill', 'bill_status_logs', ['bill_id'])

    # === MOD-04: CitizenVote ===
    op.create_table('citizen_votes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nullifier_hash', sa.String(64), nullable=False),
        sa.Column('bill_id', sa.String(50), sa.ForeignKey('parliament_bills.id'), nullable=False),
        sa.Column('vote', votechoice, nullable=False),
        sa.Column('signature_hex', sa.String(128), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('nullifier_hash', 'bill_id', name='uq_one_vote_per_citizen'),
    )
    op.create_index('idx_votes_bill', 'citizen_votes', ['bill_id'])
    op.create_index('idx_votes_nullifier', 'citizen_votes', ['nullifier_hash'])

    # === MOD-14: Bill Relevance Votes ===
    op.create_table('bill_relevance_votes',
        sa.Column('nullifier_hash', sa.String(64), primary_key=True),
        sa.Column('bill_id', sa.String(50), sa.ForeignKey('parliament_bills.id'), primary_key=True),
        sa.Column('signal', sa.SmallInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint('signal IN (1, -1)', name='ck_relevance_signal'),
    )

    # === MOD-02: VAA — Survey Responses ===
    op.create_table('survey_responses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_hash', sa.String(64), nullable=False),
        sa.Column('age_group', sa.String(20), nullable=True),
        sa.Column('region', sa.String(30), nullable=True),
        sa.Column('gender_code', sa.String(20), nullable=True),
        sa.Column('answers', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_survey_hash', 'survey_responses', ['user_hash'])
    op.create_index('idx_survey_demographics', 'survey_responses', ['age_group', 'region'])


def downgrade() -> None:
    op.drop_table('survey_responses')
    op.drop_table('bill_relevance_votes')
    op.drop_table('citizen_votes')
    op.drop_table('bill_status_logs')
    op.drop_table('parliament_bills')
    op.drop_table('party_positions')
    op.drop_table('statements')
    op.drop_table('parties')
    op.drop_table('identity_records')
    sa.Enum(name='billstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='votechoice').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='keystatus').drop(op.get_bind(), checkfirst=True)
