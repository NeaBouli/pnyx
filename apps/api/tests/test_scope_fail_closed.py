"""Regression tests for scope paths that previously failed open."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models import GovernanceLevel
from routers import municipal, representative


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _SequenceDb:
    def __init__(self, values):
        self._values = list(values)
        self.added = []
        self.committed = False

    async def execute(self, _statement):
        return _ScalarResult(self._values.pop(0))

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_legacy_municipal_vote_rejects_unmapped_decision_before_signature(monkeypatch):
    signature_checked = False

    def verify_signature(*_args):
        nonlocal signature_checked
        signature_checked = True
        return True

    monkeypatch.setattr("keypair.verify_signature", verify_signature)
    identity = SimpleNamespace(public_key_hex="a" * 64, periferia_id=6, dimos_id=22)
    decision = SimpleNamespace(
        governance_level=GovernanceLevel.MUNICIPAL,
        periferia_id=None,
        dimos_id=None,
    )
    db = _SequenceDb([identity, decision])
    request = municipal.DecisionVoteRequest(
        ada="ADA-UNMAPPED-1",
        nullifier_hash="b" * 64,
        vote="YES",
        signature_hex="c" * 128,
    )

    with pytest.raises(HTTPException) as exc:
        await municipal.vote_on_decision(request, db)

    assert exc.value.status_code == 403
    assert signature_checked is False
    assert db.added == []
    assert db.committed is False


@pytest.mark.asyncio
async def test_legacy_municipal_vote_infers_missing_level_before_signature(monkeypatch):
    signature_checked = False

    def verify_signature(*_args):
        nonlocal signature_checked
        signature_checked = True
        return True

    monkeypatch.setattr("keypair.verify_signature", verify_signature)
    identity = SimpleNamespace(public_key_hex="a" * 64, periferia_id=6, dimos_id=23)
    decision = SimpleNamespace(
        ada="ADA-LEGACY-2",
        governance_level=None,
        periferia_id=6,
        dimos_id=22,
    )
    db = _SequenceDb([identity, decision])
    request = municipal.DecisionVoteRequest(
        ada="ADA-LEGACY-2",
        nullifier_hash="b" * 64,
        vote="YES",
        signature_hex="c" * 128,
    )

    with pytest.raises(HTTPException) as exc:
        await municipal.vote_on_decision(request, db)

    assert exc.value.status_code == 403
    assert signature_checked is False
    assert db.added == []
    assert db.committed is False


@pytest.mark.asyncio
async def test_legacy_municipal_vote_hides_sensitive_decision_before_signature(monkeypatch):
    signature_checked = False

    def verify_signature(*_args):
        nonlocal signature_checked
        signature_checked = True
        return True

    monkeypatch.setattr("keypair.verify_signature", verify_signature)
    identity = SimpleNamespace(public_key_hex="a" * 64, periferia_id=6, dimos_id=22)
    decision = SimpleNamespace(
        ada="ADA-SENSITIVE-1",
        subject="Δαπάνη ασθενή με ΑΜΚΑ 123",
        governance_level="MUNICIPAL",
        periferia_id=6,
        dimos_id=22,
    )
    db = _SequenceDb([identity, decision])
    request = municipal.DecisionVoteRequest(
        ada="ADA-SENSITIVE-1",
        nullifier_hash="b" * 64,
        vote="YES",
        signature_hex="c" * 128,
    )

    with pytest.raises(HTTPException) as exc:
        await municipal.vote_on_decision(request, db)

    assert exc.value.status_code == 404
    assert signature_checked is False
    assert db.added == []


def test_municipal_representative_only_sees_own_dimos():
    own = SimpleNamespace(
        source="DIAVGEIA",
        governance_level=GovernanceLevel.MUNICIPAL,
        dimos_id=22,
        admin_hidden=False,
        id="DIAV-OWN",
    )
    foreign = SimpleNamespace(
        source="DIAVGEIA",
        governance_level=GovernanceLevel.MUNICIPAL,
        dimos_id=23,
        admin_hidden=False,
        id="DIAV-FOREIGN",
    )
    rep = {"role": "Δήμαρχος", "dimos_id": 22}

    assert representative.is_bill_visible_for_token(own, rep) is True
    assert representative.is_bill_visible_for_token(foreign, rep) is False
    assert representative.is_bill_visible_for_token(own, {"role": "Δήμαρχος", "dimos_id": None}) is False
