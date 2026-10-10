"""Accept nine-character Diavgeia ADAs without changing stored identifiers.

Revision ID: y801a2b3c4d5
Revises: x701a2b3c4d5

Both directions replace only the named length check. PostgreSQL length() counts
characters, not UTF-8 bytes; the existing upper bound remains unchanged.

Downgrade restores the old 10..32 rule as NOT VALID: existing nine-character
rows remain untouched, while PostgreSQL enforces the old rule for subsequent
inserts and updates. The downgraded constraint intentionally remains unvalidated;
validating historical rows is a separate operator decision, not data cleanup.
"""

from alembic import op


revision = "y801a2b3c4d5"
down_revision = "x701a2b3c4d5"
branch_labels = None
depends_on = None

TABLE_NAME = "diavgeia_decisions"
CONSTRAINT_NAME = "diavgeia_decisions_ada_chk"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="check")
    op.create_check_constraint(CONSTRAINT_NAME, TABLE_NAME, "length(ada) BETWEEN 9 AND 32")


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="check")
    op.create_check_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        "length(ada) BETWEEN 10 AND 32",
        postgresql_not_valid=True,
    )
