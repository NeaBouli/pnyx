"""T-9127: archived bills retain results/consensus but accept no citizen votes."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from nacl.signing import SigningKey

from models import BillStatus, CitizenVote, GovernanceLevel, VoteChoice
from routers import polis_qr, voting

BILL_ID = "GR-T9127"
NULLIFIER = "a" * 64
SESSION_ID = "t9127-session"
LEVELS = [GovernanceLevel.NATIONAL, GovernanceLevel.REGIONAL, GovernanceLevel.MUNICIPAL]


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def fetchone(self):
        return self.value


class _Db:
    def __init__(self, values):
        self.values = list(values)
        self.executed = []
        self.added = []
        self.commits = 0

    async def execute(self, statement, *_args):
        self.executed.append(statement)
        return _Result(self.values.pop(0))

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1


class _Redis:
    def __init__(self, public_key, purpose="vote"):
        self.data = {
            "status": "authenticated", "purpose": purpose, "bill_id": BILL_ID,
            "nullifier_hash": NULLIFIER, "public_key_hex": public_key,
        }
        self.claims = 0

    async def hgetall(self, _key):
        return dict(self.data)

    async def eval(self, *_args):
        self.claims += 1
        self.data["status"] = "processing"
        return 1

    async def hset(self, _key, *, mapping):
        self.data.update(mapping)

    async def hdel(self, _key, *fields):
        for field in fields:
            self.data.pop(field, None)

    async def expire(self, *_args):
        return True


@pytest.fixture
def voter(monkeypatch):
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "false")
    monkeypatch.setenv("TIER1_METADATA_ACCEPTED", "false")
    key = SigningKey.generate()
    identity = SimpleNamespace(
        public_key_hex=key.verify_key.encode().hex(), periferia_id=6, dimos_id=22,
    )
    return key, identity


def _bill(status, level):
    return SimpleNamespace(
        id=BILL_ID, status=status, governance_level=level, source="PARLIAMENT",
        periferia_id=6, dimos_id=22, admin_hidden=False,
    )


def _stored_vote():
    return CitizenVote(
        nullifier_hash=NULLIFIER, bill_id=BILL_ID, vote=VoteChoice.YES,
        signature_hex="original", is_correction=False,
    )


async def _install_redis(monkeypatch, identity, purpose="vote"):
    redis = _Redis(identity.public_key_hex, purpose)

    async def get_redis():
        return redis

    monkeypatch.setattr(polis_qr, "_redis", get_redis)
    return redis


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["signed", "qr"])
@pytest.mark.parametrize("bill_status", list(BillStatus))
@pytest.mark.parametrize("has_vote", [False, True], ids=["new", "change"])
@pytest.mark.parametrize("level", LEVELS)
async def test_citizen_vote_write_lifecycle(
    monkeypatch, voter, endpoint, bill_status, has_vote, level,
):
    key, identity = voter
    bill = _bill(bill_status, level)
    stored = _stored_vote() if has_vote else None
    before = dict(vars(stored)) if stored is not None else None
    db = _Db([identity, bill, stored])
    redis = await _install_redis(monkeypatch, identity)

    async def submit():
        if endpoint == "qr":
            return await polis_qr.qr_web_vote(polis_qr.QRVoteRequest(
                session_id=SESSION_ID, bill_id=BILL_ID, vote="NO",
            ), db)
        signature = key.sign(f"{BILL_ID}:NO:{NULLIFIER}".encode()).signature.hex()
        return await voting.submit_vote(voting.VoteRequest(
            nullifier_hash=NULLIFIER, bill_id=BILL_ID, vote="NO", signature_hex=signature,
        ), db)

    closed = bill_status not in (BillStatus.ACTIVE, BillStatus.WINDOW_24H)
    if closed or (has_vote and bill_status == BillStatus.ACTIVE):
        with pytest.raises(HTTPException) as exc:
            await submit()
        assert exc.value.status_code == (400 if closed else 409)
        if closed:
            assert exc.value.detail.startswith("Η ψηφοφορία έχει κλείσει")
            assert len(db.executed) == 2  # no vote lookup or write
        assert db.added == []
        assert db.commits == 0
        assert redis.claims == 0
        assert redis.data["status"] == "authenticated"
        if stored is not None:
            assert vars(stored) == before
        return

    result = await submit()
    assert (result["success"] if endpoint == "qr" else result.success) is True
    assert db.commits == 1
    if stored is not None:
        assert db.added == []
        assert stored.vote == VoteChoice.NO
        assert stored.signature_hex != "original"
    else:
        assert len(db.added) == 1
        assert db.added[0].vote == VoteChoice.NO
    if endpoint == "qr":
        assert redis.claims == 1
        assert redis.data["status"] == "used"


@pytest.mark.asyncio
@pytest.mark.parametrize("bill_status", list(BillStatus))
@pytest.mark.parametrize("level", LEVELS)
async def test_vote_correction_remains_window_only(voter, bill_status, level):
    key, identity = voter
    stored = _stored_vote()
    before = dict(vars(stored))
    db = _Db([_bill(bill_status, level), identity, stored])
    signature = key.sign(f"{BILL_ID}:NO:{NULLIFIER}".encode()).signature.hex()
    req = voting.CorrectionRequest(
        nullifier_hash=NULLIFIER, bill_id=BILL_ID, vote="NO", signature_hex=signature,
    )
    if bill_status != BillStatus.WINDOW_24H:
        with pytest.raises(HTTPException) as exc:
            await voting.correct_vote(BILL_ID, req, db)
        assert exc.value.status_code == 403
        assert len(db.executed) == 1
        assert vars(stored) == before
        assert db.commits == 0
    else:
        result = await voting.correct_vote(BILL_ID, req, db)
        assert result["status"] == "corrected"
        assert stored.vote == VoteChoice.NO
        assert stored.is_correction is True
        assert stored.original_vote == "YES"
        assert db.commits == 1
    assert db.added == []


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["signed", "qr"])
async def test_open_end_consensus_still_accepted(monkeypatch, voter, endpoint):
    key, identity = voter
    bill = _bill(BillStatus.OPEN_END, GovernanceLevel.NATIONAL)
    first_reads = [identity, bill] if endpoint == "qr" else [bill, identity]
    db = _Db([*first_reads, None, (2.0, 1), None])
    redis = await _install_redis(monkeypatch, identity, "consensus")
    if endpoint == "qr":
        result = await polis_qr.qr_web_consensus(polis_qr.QRConsensusRequest(
            session_id=SESSION_ID, bill_id=BILL_ID, score=2,
        ), db)
        assert redis.data["status"] == "used"
    else:
        signature = key.sign(f"{BILL_ID}:2:{NULLIFIER}".encode()).signature.hex()
        result = await voting.submit_consensus(BILL_ID, voting.ConsensusRequest(
            score=2, nullifier_hash=NULLIFIER, signature_hex=signature,
        ), db)
    assert result["your_score"] == 2
    assert result["consensus_score"] == 2.0
    assert result["consensus_count"] == 1
    assert db.commits == 1
    assert db.added == []
    assert any("INSERT INTO consensus_votes" in str(stmt) for stmt in db.executed)
    assert all("citizen_votes" not in str(stmt) for stmt in db.executed)
