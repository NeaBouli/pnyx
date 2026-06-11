"""add additive ZK gate 1 storage

Revision ID: r101a2b3c4d5
Revises: q001a2b3c4d5
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r101a2b3c4d5"
down_revision = "q001a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zk_identity_commitments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("identity_record_id", sa.Integer(), nullable=True),
        sa.Column("commitment", sa.String(160), nullable=False),
        sa.Column("commitment_version", sa.String(32), server_default="semaphore-v4", nullable=False),
        sa.Column("merkle_depth", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["identity_record_id"], ["identity_records.id"], ondelete="SET NULL"),
        sa.CheckConstraint("merkle_depth > 0", name="ck_zk_commitment_depth_positive"),
        sa.CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="ck_zk_commitment_status"),
        sa.UniqueConstraint("commitment", name="uq_zk_identity_commitment"),
    )
    op.create_index("idx_zk_commitments_identity", "zk_identity_commitments", ["identity_record_id"])

    op.create_table(
        "zk_merkle_roots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vote_scope_id", sa.String(128), nullable=False),
        sa.Column("scope_type", sa.String(32), server_default="BILL", nullable=False),
        sa.Column("merkle_root", sa.String(160), nullable=False),
        sa.Column("merkle_depth", sa.Integer(), nullable=False),
        sa.Column("group_size", sa.Integer(), nullable=False),
        sa.Column("commitment_version", sa.String(32), server_default="semaphore-v4", nullable=False),
        sa.Column("status", sa.String(20), server_default="OPEN", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("merkle_depth > 0", name="ck_zk_root_depth_positive"),
        sa.CheckConstraint("group_size >= 0", name="ck_zk_root_group_size_nonnegative"),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED', 'ARCHIVED')", name="ck_zk_root_status"),
        sa.UniqueConstraint("vote_scope_id", "merkle_root", name="uq_zk_scope_merkle_root"),
    )
    op.create_index("idx_zk_roots_scope", "zk_merkle_roots", ["vote_scope_id"])

    op.create_table(
        "zk_vote_tier_locks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vote_scope_id", sa.String(128), nullable=False),
        sa.Column("tier_guard_hash", sa.String(128), nullable=False),
        sa.Column("lock_version", sa.String(32), server_default="tier-guard-v1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("vote_scope_id", "tier_guard_hash", name="uq_zk_tier_lock_scope_guard"),
    )
    op.create_index("idx_zk_tier_locks_scope", "zk_vote_tier_locks", ["vote_scope_id"])

    op.create_table(
        "zk_vote_receipts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vote_scope_id", sa.String(128), nullable=False),
        sa.Column("semaphore_nullifier", sa.String(160), nullable=False),
        sa.Column("merkle_root", sa.String(160), nullable=False),
        sa.Column("merkle_depth", sa.Integer(), nullable=False),
        sa.Column("signal_hash", sa.String(128), nullable=False),
        sa.Column("external_nullifier", sa.String(160), nullable=False),
        sa.Column("proof_public_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("verifier_version", sa.String(64), nullable=False),
        sa.Column("circuit_version", sa.String(64), nullable=False),
        sa.Column("arweave_tx_id", sa.String(100), nullable=True),
        sa.Column("arweave_pending", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("publication_bucket", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("merkle_depth > 0", name="ck_zk_receipt_depth_positive"),
        sa.UniqueConstraint("vote_scope_id", "semaphore_nullifier", name="uq_zk_scope_semaphore_nullifier"),
    )
    op.create_index("idx_zk_receipts_scope", "zk_vote_receipts", ["vote_scope_id"])
    op.create_index("idx_zk_receipts_arweave_pending", "zk_vote_receipts", ["arweave_pending"])


def downgrade() -> None:
    op.drop_index("idx_zk_receipts_arweave_pending", table_name="zk_vote_receipts")
    op.drop_index("idx_zk_receipts_scope", table_name="zk_vote_receipts")
    op.drop_table("zk_vote_receipts")
    op.drop_index("idx_zk_tier_locks_scope", table_name="zk_vote_tier_locks")
    op.drop_table("zk_vote_tier_locks")
    op.drop_index("idx_zk_roots_scope", table_name="zk_merkle_roots")
    op.drop_table("zk_merkle_roots")
    op.drop_index("idx_zk_commitments_identity", table_name="zk_identity_commitments")
    op.drop_table("zk_identity_commitments")
