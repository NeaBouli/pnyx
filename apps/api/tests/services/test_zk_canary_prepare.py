"""Tests for the hidden GH#112 ZK canary scope prepare script."""
from types import SimpleNamespace

import pytest

from models import BillStatus, GovernanceLevel
from scripts.prepare_zk_canary_scope import canary_bill_values, validate_existing_canary_row


def test_canary_bill_values_are_hidden_and_non_public_source() -> None:
    values = canary_bill_values()
    assert values.id == "ZK-CANARY-001"
    assert values.status == BillStatus.ACTIVE
    assert values.governance_level == GovernanceLevel.NATIONAL
    assert values.source == "ZK_CANARY"
    assert values.admin_hidden is True
    assert values.results_visibility == "HIDDEN"


def test_existing_canary_row_must_be_hidden() -> None:
    row = SimpleNamespace(id="ZK-CANARY-001", admin_hidden=False)
    with pytest.raises(RuntimeError, match="not admin_hidden"):
        validate_existing_canary_row(row)


def test_existing_canary_row_must_not_have_forum_topic() -> None:
    row = SimpleNamespace(id="ZK-CANARY-001", admin_hidden=True, forum_topic_id=123)
    with pytest.raises(RuntimeError, match="forum_topic_id"):
        validate_existing_canary_row(row)


def test_existing_canary_row_must_not_have_arweave_tx() -> None:
    row = SimpleNamespace(id="ZK-CANARY-001", admin_hidden=True, arweave_tx_id="tx")
    with pytest.raises(RuntimeError, match="arweave_tx_id"):
        validate_existing_canary_row(row)
