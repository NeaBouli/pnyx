"""Tests for GH#112 public ZK scope preflight."""
from scripts.preflight_zk_public_scope import (
    ZkScopeCounts,
    evaluate_public_scope_candidate,
)


EMPTY_COUNTS = ZkScopeCounts(commitments=0, roots=0, receipts=0, tier_locks=0)


def _bill(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "GR-5294",
        "title_el": "Test bill",
        "status": "OPEN_END",
        "source": "PARLIAMENT",
        "admin_hidden": False,
        "results_visibility": "HIDDEN",
        "governance_level": "NATIONAL",
        "forum_topic_id": 132,
        "arweave_tx_id": None,
    }
    data.update(overrides)
    return data


def test_real_open_end_parliament_bill_is_eligible_with_arweave_warning() -> None:
    result = evaluate_public_scope_candidate(_bill(), bill_id="GR-5294", counts=EMPTY_COUNTS)
    assert result.eligible is True
    assert result.blockers == []
    assert "bill_not_archived_to_arweave" in result.warnings


def test_announced_bill_is_blocked() -> None:
    result = evaluate_public_scope_candidate(
        _bill(status="ANNOUNCED"),
        bill_id="GR-056b74d6",
        counts=EMPTY_COUNTS,
    )
    assert result.eligible is False
    assert "bill_status_not_votable" in result.blockers


def test_demo_bill_is_blocked_for_first_public_rollout() -> None:
    result = evaluate_public_scope_candidate(_bill(), bill_id="DEMO-001", counts=EMPTY_COUNTS)
    assert result.eligible is False
    assert "demo_bill_not_allowed_for_first_public_rollout" in result.blockers


def test_hidden_canary_scope_is_blocked() -> None:
    result = evaluate_public_scope_candidate(
        _bill(source="ZK_CANARY", admin_hidden=True),
        bill_id="ZK-CANARY-001",
        counts=EMPTY_COUNTS,
    )
    assert result.eligible is False
    assert "admin_hidden_bill" in result.blockers
    assert "hidden_canary_scope_not_public_rollout" in result.blockers


def test_existing_zk_state_is_warning_not_blocker() -> None:
    counts = ZkScopeCounts(commitments=1, roots=1, receipts=0, tier_locks=1)
    result = evaluate_public_scope_candidate(_bill(), bill_id="GR-5294", counts=counts)
    assert result.eligible is True
    assert "existing_zk_scope_state_present" in result.warnings
