"""add politician evaluation tables + enable flag on representative_tokens

Revision ID: l501a2b3c4d5
Revises: k401a2b3c4d5
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "l501a2b3c4d5"
down_revision = "k401a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. evaluation_questions — 8 Fragen zur Politiker-Bewertung
    op.create_table(
        "evaluation_questions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("question_el", sa.Text, nullable=False),
        sa.Column("question_en", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("active", sa.Boolean, server_default="true", nullable=False),
    )

    # 2. politician_evaluations — Bürgerbewertungen
    op.create_table(
        "politician_evaluations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ada_number", sa.String(50), nullable=False),
        sa.Column("nullifier_hash", sa.String(64), nullable=False),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.SmallInteger, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("nullifier_hash", "ada_number", "question_id", name="uq_one_eval_per_citizen_question"),
        sa.CheckConstraint("score BETWEEN -5 AND 5", name="ck_eval_score_range"),
    )
    op.create_index("idx_eval_ada", "politician_evaluations", ["ada_number"])
    op.create_index("idx_eval_nullifier", "politician_evaluations", ["nullifier_hash"])

    # 3. evaluation_enabled auf representative_tokens
    op.add_column("representative_tokens",
        sa.Column("evaluation_enabled", sa.Boolean, server_default="false", nullable=False),
    )

    # 4. Seed: 8 Evaluierungsfragen
    op.execute("""
        INSERT INTO evaluation_questions (question_el, question_en, category) VALUES
        ('Πόσο διαφανής είναι στις αποφάσεις του;', 'How transparent is this representative in their decisions?', 'transparency'),
        ('Πόσο καλά εκπροσωπεί την περιοχή του;', 'How well do they represent their region?', 'representation'),
        ('Πόσο συνεπής είναι με τις εκλογικές υποσχέσεις του;', 'How consistent are they with their election promises?', 'consistency'),
        ('Πόσο ανταποκρίνεται στα αιτήματα πολιτών;', 'How responsive are they to citizen requests?', 'responsiveness'),
        ('Πόσο έντιμος φαίνεται στη δημόσια ζωή;', 'How honest do they appear in public life?', 'integrity'),
        ('Πόσο αποτελεσματικός είναι στο ρόλο του;', 'How effective are they in their role?', 'effectiveness'),
        ('Πόσο καλά συνεργάζεται με άλλους;', 'How well do they cooperate with others?', 'cooperation'),
        ('Συνολική αξιολόγηση;', 'Overall evaluation?', 'overall')
    """)


def downgrade() -> None:
    op.drop_column("representative_tokens", "evaluation_enabled")
    op.drop_table("politician_evaluations")
    op.drop_table("evaluation_questions")
