"""Regression checks for GH#112 Gate 1 additive ZK storage."""
import importlib.util
from pathlib import Path

from models import Base


def _unique_constraints(table_name: str) -> set[tuple[str, tuple[str, ...]]]:
    table = Base.metadata.tables[table_name]
    return {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }


def test_zk_gate1_tables_are_additive_only() -> None:
    expected = {
        "zk_identity_commitments",
        "zk_merkle_roots",
        "zk_vote_receipts",
        "zk_vote_tier_locks",
    }
    assert expected.issubset(Base.metadata.tables.keys())

    citizen_vote = Base.metadata.tables["citizen_votes"]
    assert "zk_identity_commitment_id" not in citizen_vote.columns
    assert "semaphore_nullifier" not in citizen_vote.columns
    assert "tier_guard_hash" not in citizen_vote.columns


def test_zk_gate1_uniqueness_guards() -> None:
    assert ("uq_zk_identity_commitment", ("commitment",)) in _unique_constraints(
        "zk_identity_commitments"
    )
    assert ("uq_zk_scope_merkle_root", ("vote_scope_id", "merkle_root")) in _unique_constraints(
        "zk_merkle_roots"
    )
    assert (
        "uq_zk_scope_semaphore_nullifier",
        ("vote_scope_id", "semaphore_nullifier"),
    ) in _unique_constraints("zk_vote_receipts")
    assert ("uq_zk_tier_lock_scope_guard", ("vote_scope_id", "tier_guard_hash")) in _unique_constraints(
        "zk_vote_tier_locks"
    )


def test_zk_public_receipts_exclude_identity_bridge_fields() -> None:
    receipt_columns = set(Base.metadata.tables["zk_vote_receipts"].columns.keys())
    forbidden = {
        "tier_guard_hash",
        "identity_record_id",
        "nullifier_hash",
        "phone_number",
        "public_key_hex",
        "semaphore_identity_secret",
    }
    assert receipt_columns.isdisjoint(forbidden)


def test_zk_gate1_migration_chains_after_nullifier_v2() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "r101a2b3c4d5_zk_gate1_storage.py"
    )
    spec = importlib.util.spec_from_file_location("zk_gate1_migration", migration_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "r101a2b3c4d5"
    assert migration.down_revision == "q001a2b3c4d5"
