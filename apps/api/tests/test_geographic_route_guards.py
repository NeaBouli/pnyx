"""Route-level regression tests for the shared geographic authorization policy."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models import BillStatus, GovernanceLevel
from routers import polis_qr, voting, zk


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Db:
    def __init__(self, values):
        self.values = list(values)
        self.executed = []
        self.added = []
        self.committed = False

    async def execute(self, statement):
        self.executed.append(statement)
        return _ScalarResult(self.values.pop(0))

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.committed = True


class _RedisSession:
    def __init__(self, data):
        self.data = data

    async def hgetall(self, _key):
        return self.data


def _identity(*, periferia_id: int = 7, dimos_id: int | None = None):
    return SimpleNamespace(
        public_key_hex="c" * 64,
        periferia_id=periferia_id,
        dimos_id=dimos_id,
    )


def _regional_bill(*, status: BillStatus):
    return SimpleNamespace(
        id="REGIONAL-1",
        status=status,
        governance_level=GovernanceLevel.REGIONAL,
        periferia_id=6,
        dimos_id=None,
        source="PARLIAMENT",
        admin_hidden=False,
    )


@pytest.mark.asyncio
async def test_normal_vote_rejects_foreign_region_before_signature(monkeypatch):
    signature_checked = False

    def verify_signature(*_args):
        nonlocal signature_checked
        signature_checked = True
        return True

    monkeypatch.setattr(voting, "verify_signature", verify_signature)
    monkeypatch.delenv("ZK_TIER1_GUARD_ENABLED", raising=False)
    request = voting.VoteRequest(
        nullifier_hash="a" * 64,
        bill_id="REGIONAL-1",
        vote="YES",
        signature_hex="b" * 128,
    )
    db = _Db([_identity(), _regional_bill(status=BillStatus.ACTIVE)])

    with pytest.raises(HTTPException) as exc:
        await voting.submit_vote(request, db)

    assert exc.value.status_code == 403
    assert signature_checked is False
    assert db.added == []
    assert db.committed is False


@pytest.mark.asyncio
async def test_consensus_rejects_foreign_region_before_signature(monkeypatch):
    signature_checked = False

    def verify_signature(*_args):
        nonlocal signature_checked
        signature_checked = True
        return True

    monkeypatch.setattr(voting, "verify_signature", verify_signature)
    request = voting.ConsensusRequest(
        score=2,
        nullifier_hash="a" * 64,
        signature_hex="b" * 128,
    )
    db = _Db([_regional_bill(status=BillStatus.OPEN_END), _identity()])

    with pytest.raises(HTTPException) as exc:
        await voting.submit_consensus("REGIONAL-1", request, db)

    assert exc.value.status_code == 403
    assert signature_checked is False
    assert len(db.executed) == 2
    assert db.committed is False


@pytest.mark.asyncio
async def test_polis_qr_vote_rejects_foreign_region_without_consuming_session(monkeypatch):
    redis = _RedisSession({
        "status": "authenticated",
        "purpose": "vote",
        "bill_id": "REGIONAL-1",
        "nullifier_hash": "a" * 64,
    })

    async def get_redis():
        return redis

    claimed = False

    async def claim(*_args):
        nonlocal claimed
        claimed = True

    monkeypatch.setattr(polis_qr, "_redis", get_redis)
    monkeypatch.setattr(polis_qr, "_claim_authenticated_session", claim)
    request = polis_qr.QRVoteRequest(
        session_id="session-12345",
        bill_id="REGIONAL-1",
        vote="YES",
    )
    db = _Db([_identity(), _regional_bill(status=BillStatus.ACTIVE)])

    with pytest.raises(HTTPException) as exc:
        await polis_qr.qr_web_vote(request, db)

    assert exc.value.status_code == 403
    assert claimed is False
    assert db.committed is False


@pytest.mark.asyncio
async def test_polis_qr_consensus_rejects_foreign_region_without_consuming_session(monkeypatch):
    redis = _RedisSession({
        "status": "authenticated",
        "purpose": "consensus",
        "bill_id": "REGIONAL-1",
        "nullifier_hash": "a" * 64,
    })

    async def get_redis():
        return redis

    claimed = False

    async def claim(*_args):
        nonlocal claimed
        claimed = True

    monkeypatch.setattr(polis_qr, "_redis", get_redis)
    monkeypatch.setattr(polis_qr, "_claim_authenticated_session", claim)
    request = polis_qr.QRConsensusRequest(
        session_id="session-12345",
        bill_id="REGIONAL-1",
        score=2,
    )
    db = _Db([_identity(), _regional_bill(status=BillStatus.OPEN_END)])

    with pytest.raises(HTTPException) as exc:
        await polis_qr.qr_web_consensus(request, db)

    assert exc.value.status_code == 403
    assert claimed is False
    assert db.committed is False


@pytest.mark.asyncio
async def test_zk_opt_in_rejects_foreign_region_before_signature_or_mutation(monkeypatch):
    monkeypatch.setattr(zk, "_ensure_zk_opt_in_enabled", lambda: None)
    signature_checked = False

    def verify_signature(*_args):
        nonlocal signature_checked
        signature_checked = True
        return True

    monkeypatch.setattr(zk, "verify_signature", verify_signature)
    request = zk.ZkOptInRequest(
        nullifier_hash="a" * 64,
        bill_id="REGIONAL-1",
        commitment="123456789",
        signature_hex="b" * 128,
    )
    db = _Db([_identity(), _regional_bill(status=BillStatus.ACTIVE)])

    with pytest.raises(HTTPException) as exc:
        await zk.opt_in_zk(request, db)

    assert exc.value.status_code == 403
    assert signature_checked is False
    assert db.added == []
    assert db.committed is False
