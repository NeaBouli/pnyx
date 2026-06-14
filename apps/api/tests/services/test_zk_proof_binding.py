"""Tests for canonical GH#112 ZK proof binding helpers."""
import json
from pathlib import Path

import pytest

from services.zk_proof_binding import (
    canonical_zk_message_text,
    canonical_zk_message_value,
    canonical_zk_scope_text,
    canonical_zk_scope_value,
    proof_matches_canonical_binding,
    semaphore_text_to_bigint_string,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "gh112_s10_fixture.json"


def test_semaphore_text_to_bigint_matches_s10_fixture_message_and_scope() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text())
    proof = json.loads(fixture["proof"])

    assert semaphore_text_to_bigint_string(fixture["message"]) == proof["message"]
    assert semaphore_text_to_bigint_string(fixture["scope"]) == proof["scope"]


def test_semaphore_text_to_bigint_rejects_long_text() -> None:
    with pytest.raises(ValueError):
        semaphore_text_to_bigint_string("x" * 33)


def test_canonical_zk_binding_is_stable_and_distinct_per_scope_and_vote() -> None:
    scope_text = canonical_zk_scope_text("bill:ZK-CANARY-001")
    yes_text = canonical_zk_message_text(
        vote_scope_id="bill:ZK-CANARY-001",
        vote_commitment="YES",
    )
    yes = canonical_zk_message_value(
        vote_scope_id="bill:ZK-CANARY-001",
        vote_commitment="YES",
    )
    no = canonical_zk_message_value(
        vote_scope_id="bill:ZK-CANARY-001",
        vote_commitment="NO",
    )
    other_scope_yes = canonical_zk_message_value(
        vote_scope_id="bill:GR-0490a766",
        vote_commitment="YES",
    )

    assert len(scope_text.encode("utf-8")) <= 32
    assert len(yes_text.encode("utf-8")) <= 32
    assert scope_text.startswith("zks:")
    assert yes_text.startswith("zkm:")
    assert canonical_zk_scope_value("bill:ZK-CANARY-001").isdigit()
    assert yes.isdigit()
    assert yes != no
    assert yes != other_scope_yes


def test_canonical_zk_binding_matches_cross_platform_golden_vector() -> None:
    assert canonical_zk_scope_text("bill:ZK-CANARY-001") == "zks:0e4NG-4g8ttGB4S3oNnvrvmirLeN"
    assert (
        canonical_zk_message_text(
            vote_scope_id="bill:ZK-CANARY-001",
            vote_commitment="YES",
        )
        == "zkm:5mTOk-0X_3vcqb8k_khYt92TxVfV"
    )
    assert (
        canonical_zk_scope_value("bill:ZK-CANARY-001")
        == "55372015432693197156684210389612366682933503607061176685521685831438937384270"
    )
    assert (
        canonical_zk_message_value(
            vote_scope_id="bill:ZK-CANARY-001",
            vote_commitment="YES",
        )
        == "55371974022745020309936148062986343275232691383944616415973239990294343476822"
    )


def test_proof_matches_canonical_binding_rejects_wrong_scope_or_vote() -> None:
    scope = "bill:ZK-CANARY-001"
    commitment = "YES"
    message_value = canonical_zk_message_value(
        vote_scope_id=scope,
        vote_commitment=commitment,
    )
    scope_value = canonical_zk_scope_value(scope)

    assert proof_matches_canonical_binding(
        proof_message=message_value,
        proof_scope=scope_value,
        vote_scope_id=scope,
        vote_commitment=commitment,
    )
    assert not proof_matches_canonical_binding(
        proof_message=message_value,
        proof_scope=scope_value,
        vote_scope_id=scope,
        vote_commitment="NO",
    )
    assert not proof_matches_canonical_binding(
        proof_message=message_value,
        proof_scope=scope_value,
        vote_scope_id="bill:GR-0490a766",
        vote_commitment=commitment,
    )
