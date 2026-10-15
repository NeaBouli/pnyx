"""Store representative invite codes only as a keyed hash (EVA-033).

Revision ID: y802a2b3c4d5
Revises: y801a2b3c4d5

rep_invitations was created outside Alembic in production (see
SCHEMA_DRIFT_NOTES.md). On such databases this revision adds
invite_code_hash (HMAC-SHA256, namespace "rep-invite:v1:", key SERVER_SALT,
identical to services/invite_codes.py) and invite_code_hint, backfills both
from the existing plaintext, makes invite_code nullable and empties it.
On a fresh database the table is created directly in its final form.

The backfill needs the runtime SERVER_SALT; without it the migration aborts
before changing anything (fail closed). Downgrade is only possible while no
plaintext has been erased; afterwards HMAC digests cannot be reversed.
"""
from __future__ import annotations

import hashlib
import hmac
import os

import sqlalchemy as sa
from alembic import op

revision = "y802a2b3c4d5"
down_revision = "y801a2b3c4d5"
branch_labels = None
depends_on = None

TABLE = "rep_invitations"
NAMESPACE = b"rep-invite:v1:"


def _key() -> bytes:
    salt = (os.getenv("SERVER_SALT") or "").strip()
    if not salt:
        raise RuntimeError("y802: SERVER_SALT is required to hash existing invite codes")
    return salt.encode("utf-8")


def _hash(key: bytes, code: str) -> str:
    return hmac.new(key, NAMESPACE + code.encode("utf-8"), hashlib.sha256).hexdigest()


def _hint(code: str) -> str:
    return code[:2] + "**-****" if len(code) == 9 else "****-****"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("invite_code", sa.String(9), nullable=True),
            sa.Column("invite_code_hash", sa.String(64), nullable=False),
            sa.Column("invite_code_hint", sa.String(9), nullable=True),
            sa.Column("ada_number", sa.String(50), nullable=True),
            sa.Column("role", sa.String(30), nullable=False),
            sa.Column("region", sa.String(100), nullable=True),
            sa.Column("municipality", sa.String(100), nullable=True),
            sa.Column("created_by_admin", sa.Boolean, server_default=sa.true()),
            sa.Column("used", sa.Boolean, server_default=sa.false()),
            sa.Column("used_at", sa.DateTime, nullable=True),
            sa.Column("expires_at", sa.DateTime, nullable=False),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("periferia_id", sa.Integer, sa.ForeignKey("periferia.id", ondelete="SET NULL"), nullable=True),
            sa.Column("dimos_id", sa.Integer, sa.ForeignKey("dimos.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("uq_rep_invitations_code_hash", TABLE, ["invite_code_hash"], unique=True)
        return

    rows = bind.execute(sa.text(f"SELECT id, invite_code FROM {TABLE}")).fetchall()
    key = _key() if rows else b""
    missing = [row[0] for row in rows if not row[1]]
    if missing:
        raise RuntimeError(f"y802: invites without a code cannot be hashed (ids {missing})")

    op.add_column(TABLE, sa.Column("invite_code_hash", sa.String(64), nullable=True))
    op.add_column(TABLE, sa.Column("invite_code_hint", sa.String(9), nullable=True))
    for invite_id, code in rows:
        bind.execute(
            sa.text(f"UPDATE {TABLE} SET invite_code_hash = :h, invite_code_hint = :hint WHERE id = :id"),
            {"h": _hash(key, code), "hint": _hint(code), "id": invite_id},
        )
    op.alter_column(TABLE, "invite_code_hash", nullable=False)
    op.create_index("uq_rep_invitations_code_hash", TABLE, ["invite_code_hash"], unique=True)
    op.alter_column(TABLE, "invite_code", nullable=True)
    bind.execute(sa.text(f"UPDATE {TABLE} SET invite_code = NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    erased = bind.execute(
        sa.text(f"SELECT count(*) FROM {TABLE} WHERE invite_code IS NULL")
    ).scalar()
    if erased:
        raise RuntimeError(
            "y802 downgrade refused: invite codes are stored only as HMAC digests and cannot be "
            "restored; reissue the affected invites or restore a pre-migration snapshot."
        )
    op.drop_index("uq_rep_invitations_code_hash", table_name=TABLE)
    op.drop_column(TABLE, "invite_code_hint")
    op.drop_column(TABLE, "invite_code_hash")
    op.alter_column(TABLE, "invite_code", nullable=False)
