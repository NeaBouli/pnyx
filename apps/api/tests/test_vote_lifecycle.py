"""Citizen vote lifecycle: closed bills, one correction and immutable retries."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from nacl.signing import SigningKey

from models import (
    BillStatus, CitizenVote, GovernanceLevel, VoteChoice,
    ZkIdentityCommitment, ZkVoteReceipt, ZkVoteTierLock,
)
from routers import polis_qr, voting, zk
from services.zk_proof_binding import canonical_zk_message_value, canonical_zk_scope_value

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

    def scalars(self):
        return self

    def all(self):
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

    async def flush(self):
        for row_id, row in enumerate(self.added, start=1):
            if row.id is None:
                row.id = row_id

    async def refresh(self, row):
        await self.flush()


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
        id=7, public_key_hex=key.verify_key.encode().hex(), periferia_id=6, dimos_id=22,
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
    if closed or has_vote:
        with pytest.raises(HTTPException) as exc:
            await submit()
        assert exc.value.status_code == (400 if closed else 409)
        if closed:
            assert exc.value.detail.startswith("Η ψηφοφορία έχει κλείσει")
            assert len(db.executed) == 2  # no vote lookup or write
        elif bill_status == BillStatus.WINDOW_24H:
            assert "λειτουργία διόρθωσης" in exc.value.detail
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
    assert len(db.added) == 1
    assert db.added[0].vote == VoteChoice.NO
    if endpoint == "qr":
        assert redis.claims == 1
        assert redis.data["status"] == "used"


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["signed", "qr"])
@pytest.mark.parametrize("bill_status", [BillStatus.ACTIVE, BillStatus.WINDOW_24H])
@pytest.mark.parametrize("corrected", [False, True])
@pytest.mark.parametrize("level", LEVELS)
async def test_vote_identical_retry_never_mutates(
    monkeypatch, voter, endpoint, bill_status, corrected, level,
):
    key, identity = voter
    stored = _stored_vote()
    stored.is_correction = corrected
    stored.original_vote = "NO" if corrected else None
    stored.corrected_at = datetime(2026, 10, 16) if corrected else None
    # Even old Tier-1 metadata must survive a no-op with the flag disabled.
    stored.pk_eph = "1" * 64
    stored.vote_nullifier = "2" * 64
    stored.linkage_tag = "3" * 64
    stored.timestamp_ms = 1
    before = dict(vars(stored))
    db = _Db([identity, _bill(bill_status, level), stored])
    redis = await _install_redis(monkeypatch, identity)

    async def submit():
        if endpoint == "qr":
            return await polis_qr.qr_web_vote(polis_qr.QRVoteRequest(
                session_id=SESSION_ID, bill_id=BILL_ID, vote="YES",
            ), db)
        signature = key.sign(f"{BILL_ID}:YES:{NULLIFIER}".encode()).signature.hex()
        return await voting.submit_vote(voting.VoteRequest(
            nullifier_hash=NULLIFIER, bill_id=BILL_ID, vote="yes", signature_hex=signature,
        ), db)

    if bill_status == BillStatus.ACTIVE:
        with pytest.raises(HTTPException) as exc:
            await submit()
        assert exc.value.status_code == 409
        assert redis.claims == 0
    else:
        result = await submit()
        assert (result["vote"] if endpoint == "qr" else result.vote) == "YES"
        if endpoint == "qr":
            assert redis.claims == 1
            assert redis.data["status"] == "used"
    assert vars(stored) == before
    assert db.commits == 0
    assert db.added == []
    assert "FOR UPDATE" in str(db.executed[-1])


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["signed", "qr"])
@pytest.mark.parametrize("level", LEVELS)
async def test_post_cannot_overwrite_an_already_corrected_vote(monkeypatch, voter, endpoint, level):
    key, identity = voter
    stored = _stored_vote()
    stored.is_correction = True
    stored.original_vote = "NO"
    before = dict(vars(stored))
    db = _Db([identity, _bill(BillStatus.WINDOW_24H, level), stored])
    redis = await _install_redis(monkeypatch, identity)
    with pytest.raises(HTTPException) as exc:
        if endpoint == "qr":
            await polis_qr.qr_web_vote(polis_qr.QRVoteRequest(
                session_id=SESSION_ID, bill_id=BILL_ID, vote="NO",
            ), db)
        else:
            signature = key.sign(f"{BILL_ID}:NO:{NULLIFIER}".encode()).signature.hex()
            await voting.submit_vote(voting.VoteRequest(
                nullifier_hash=NULLIFIER, bill_id=BILL_ID, vote="NO", signature_hex=signature,
            ), db)
    assert exc.value.status_code == 409
    assert "λειτουργία διόρθωσης" in exc.value.detail
    assert vars(stored) == before
    assert db.commits == 0
    assert db.added == []
    assert redis.claims == 0
    assert redis.data["status"] == "authenticated"


@pytest.mark.asyncio
async def test_identical_signed_vote_retry_still_requires_valid_identity_signature(voter):
    key, identity = voter
    stored = _stored_vote()
    before = dict(vars(stored))
    db = _Db([identity, _bill(BillStatus.WINDOW_24H, GovernanceLevel.NATIONAL), stored])
    signature = key.sign(f"{BILL_ID}:NO:{NULLIFIER}".encode()).signature.hex()
    with pytest.raises(HTTPException) as exc:
        await voting.submit_vote(voting.VoteRequest(
            nullifier_hash=NULLIFIER, bill_id=BILL_ID, vote="YES", signature_hex=signature,
        ), db)
    assert exc.value.status_code == 401
    assert vars(stored) == before
    assert db.commits == 0
    assert db.added == []


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
        corrected = dict(vars(stored))
        # A retry of /correct is still a second correction, even with the same choice.
        for choice in ("NO", "YES"):
            signature = key.sign(f"{BILL_ID}:{choice}:{NULLIFIER}".encode()).signature.hex()
            retry = voting.CorrectionRequest(
                nullifier_hash=NULLIFIER, bill_id=BILL_ID, vote=choice, signature_hex=signature,
            )
            retry_db = _Db([_bill(bill_status, level), identity, stored])
            with pytest.raises(HTTPException) as exc:
                await voting.correct_vote(BILL_ID, retry, retry_db)
            assert exc.value.status_code == 409
            assert "μόνο μία διόρθωση" in exc.value.detail
            assert vars(stored) == corrected
            assert retry_db.commits == 0
            assert "FOR UPDATE" in str(retry_db.executed[-1])
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


@pytest.fixture(params=["allowlist", "global", "canary"])
def zk_mode(request, monkeypatch):
    for flag in ("ZK_VOTING_ENABLED", "ZK_OPT_IN_ENABLED", "ZK_TIER1_GUARD_ENABLED"):
        monkeypatch.setenv(flag, "true")
    monkeypatch.setenv("ZK_ROOT_PUBLICATION_ENABLED", "false")
    monkeypatch.setenv("ZK_CANARY_ENABLED", str(request.param == "canary").lower())
    monkeypatch.setenv("ZK_GLOBAL_ROLLOUT_ENABLED", str(request.param == "global").lower())
    monkeypatch.setenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", "" if request.param == "global" else f"bill:{BILL_ID}")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", f"bill:{BILL_ID}")
    return request.param


def _zk_bill(bill_status, mode):
    bill = _bill(bill_status, GovernanceLevel.NATIONAL)
    if mode == "canary":
        bill.source = "ZK_CANARY"
        bill.admin_hidden = True
        bill.forum_topic_id = None
        bill.arweave_tx_id = None
    return bill


def _zk_proof():
    scope = f"bill:{BILL_ID}"
    return {
        "merkleTreeDepth": 16,
        "merkleTreeRoot": "123456789",
        "message": canonical_zk_message_value(vote_scope_id=scope, vote_commitment="YES"),
        "nullifier": "987654321",
        "scope": canonical_zk_scope_value(scope),
        "points": [str(n) for n in range(1, 9)],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("bill_status", list(BillStatus))
async def test_zk_vote_write_lifecycle(monkeypatch, zk_mode, bill_status):
    verifier = Mock(return_value=True)
    monkeypatch.setattr(zk, "verify_semaphore_proof", verifier)
    monkeypatch.setattr(zk, "load_verification_key", Mock(return_value={}))
    proof = _zk_proof()
    db = _Db([_zk_bill(bill_status, zk_mode), SimpleNamespace(merkle_depth=16)])
    req = zk.ZkVoteRequest(vote_scope_id=f"bill:{BILL_ID}", vote_commitment="YES", proof=proof)

    if bill_status not in (BillStatus.ACTIVE, BillStatus.WINDOW_24H):
        with pytest.raises(HTTPException) as exc:
            await zk.accept_zk_vote(req, db)
        # Production scope visibility already excludes announced/parliament-voted bills.
        if zk_mode != "canary" and bill_status != BillStatus.OPEN_END:
            assert exc.value.status_code == 404
        else:
            assert exc.value.status_code == 400
            assert exc.value.detail == (
                f"Η ψηφοφορία έχει κλείσει ή δεν έχει ανοίξει ακόμα. Κατάσταση: {bill_status.value}. "
                "Επιτρέπεται: ACTIVE, WINDOW_24H."
            )
        assert len(db.executed) == 1  # no root lookup or write
        assert db.added == []
        assert db.commits == 0
        verifier.assert_not_called()
        return

    result = await zk.accept_zk_vote(req, db)
    assert result.accepted is True
    assert result.vote_scope_id == f"bill:{BILL_ID}"
    assert db.commits == 1
    assert len(db.added) == 1
    receipt = db.added[0]
    assert isinstance(receipt, ZkVoteReceipt)
    assert receipt.vote_commitment == "YES"
    assert receipt.proof_public_json == proof
    verifier.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("bill_status", list(BillStatus))
async def test_zk_opt_in_write_lifecycle(monkeypatch, voter, zk_mode, bill_status):
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    key, identity = voter
    signature = key.sign(f"zk_opt_in:{BILL_ID}:123456789:{NULLIFIER}".encode()).signature.hex()
    db = _Db([identity, _zk_bill(bill_status, zk_mode), None, None])
    req = zk.ZkOptInRequest(
        nullifier_hash=NULLIFIER, bill_id=BILL_ID, commitment="123456789", signature_hex=signature,
    )
    publish_root = Mock()
    monkeypatch.setattr(zk, "build_active_group_root_for_scope", publish_root)

    if bill_status not in (BillStatus.ACTIVE, BillStatus.WINDOW_24H):
        with pytest.raises(HTTPException) as exc:
            await zk.opt_in_zk(req, db)
        assert exc.value.status_code == 400
        assert exc.value.detail == (
            f"Η ψηφοφορία έχει κλείσει ή δεν έχει ανοίξει ακόμα. Κατάσταση: {bill_status.value}. "
            "Επιτρέπεται: ACTIVE, WINDOW_24H."
        )
        assert len(db.executed) == 2  # no enrollment, tier lock, or root write
        assert db.added == []
        assert db.commits == 0
        publish_root.assert_not_called()
        return

    result = await zk.opt_in_zk(req, db)
    assert result.status == "pending_root"
    assert result.tier_locked is True
    assert db.commits == 1
    assert [type(row) for row in db.added] == [ZkIdentityCommitment, ZkVoteTierLock]


@pytest.mark.asyncio
async def test_zk_open_end_receipts_remain_readable(zk_mode):
    receipt = ZkVoteReceipt(
        vote_scope_id=f"bill:{BILL_ID}", vote_commitment="YES",
        semaphore_nullifier="987654321", merkle_root="123456789", merkle_depth=16,
        signal_hash=_zk_proof()["message"], external_nullifier=_zk_proof()["scope"],
        proof_public_json=_zk_proof(), verifier_version="test-verifier", circuit_version="test-circuit",
        arweave_pending=True,
    )
    db = _Db([_zk_bill(BillStatus.OPEN_END, zk_mode), [receipt]])

    result = await zk.list_zk_receipts(f"bill:{BILL_ID}", limit=100, offset=0, db=db)

    assert len(result.receipts) == 1
    assert result.receipts[0]["vote_commitment"] == "YES"
    assert result.receipts[0]["proof_public"] == _zk_proof()
    assert db.added == []
    assert db.commits == 0


@pytest.mark.asyncio
async def test_zk_open_end_root_remains_readable(zk_mode):
    root = SimpleNamespace(
        id=8, vote_scope_id=f"bill:{BILL_ID}", merkle_root="123456789", merkle_depth=16,
        group_size=5, commitment_version="semaphore-v4", status="OPEN",
    )
    db = _Db([_zk_bill(BillStatus.OPEN_END, zk_mode), root])

    result = await zk.get_current_zk_root(f"bill:{BILL_ID}", db=db)

    assert result.merkle_root == root.merkle_root
    assert result.root_id == root.id
    assert db.added == []
    assert db.commits == 0
