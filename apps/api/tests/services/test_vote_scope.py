from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models import GovernanceLevel
from services.vote_scope import ScopeAction, ensure_bill_scope_allowed, evaluate_bill_scope


def identity(*, periferia_id=None, dimos_id=None):
    return SimpleNamespace(periferia_id=periferia_id, dimos_id=dimos_id)


def bill(level, *, periferia_id=None, dimos_id=None):
    return SimpleNamespace(
        governance_level=level,
        periferia_id=periferia_id,
        dimos_id=dimos_id,
    )


@pytest.mark.parametrize("level", [None, GovernanceLevel.NATIONAL, GovernanceLevel.INSTITUTIONAL])
def test_country_wide_levels_preserve_existing_access(level):
    assert evaluate_bill_scope(identity(), bill(level)).allowed is True


def test_regional_scope_requires_matching_server_identity():
    target = bill(GovernanceLevel.REGIONAL, periferia_id=6)
    assert evaluate_bill_scope(identity(periferia_id=6), target).allowed is True
    denied = evaluate_bill_scope(identity(periferia_id=7), target)
    assert denied.allowed is False
    assert denied.reason == "regional_scope_mismatch"


def test_municipal_scope_requires_matching_server_identity():
    target = bill(GovernanceLevel.MUNICIPAL, dimos_id=22)
    assert evaluate_bill_scope(identity(dimos_id=22), target).allowed is True
    denied = evaluate_bill_scope(identity(dimos_id=23), target)
    assert denied.allowed is False
    assert denied.reason == "municipal_scope_mismatch"


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        (bill(GovernanceLevel.REGIONAL), "regional_scope_missing"),
        (bill(GovernanceLevel.MUNICIPAL), "municipal_scope_missing"),
        (bill(GovernanceLevel.COMMUNITY), "unsupported_scope"),
        (bill("UNKNOWN"), "unsupported_scope"),
    ],
)
def test_malformed_or_unsupported_scope_fails_closed(target, reason):
    decision = evaluate_bill_scope(identity(periferia_id=6, dimos_id=22), target)
    assert decision.allowed is False
    assert decision.reason == reason


def test_consensus_uses_action_specific_greek_message():
    target = bill(GovernanceLevel.REGIONAL, periferia_id=6)
    decision = evaluate_bill_scope(identity(periferia_id=7), target, action=ScopeAction.CONSENSUS)
    assert "αξιολόγηση" in decision.detail_el


def test_enforcement_raises_403():
    with pytest.raises(HTTPException) as exc:
        ensure_bill_scope_allowed(
            identity(dimos_id=23),
            bill(GovernanceLevel.MUNICIPAL, dimos_id=22),
        )
    assert exc.value.status_code == 403
