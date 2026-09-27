"""
EKA-01 — Tier-1 (ADR-022) vote validation must actually run and fail closed.

Before the fix `submit_vote` called `validate_vote(pk_eph=..., ...)` against the
real signature `validate_vote(payload, used_nullifiers, *, now_ms=None)`; every
call raised TypeError, which was swallowed as a "non-blocking" warning, and the
unauthenticated Tier-1 fields were persisted.
"""
from __future__ import annotations

import inspect
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from nacl.signing import SigningKey
from sqlalchemy.exc import IntegrityError

from crypto import nullifier
from crypto.nullifier import (
    Tier1CryptoBackendError,
    VotePayload,
    build_signed_payload,
    validate_vote,
)
from models import CITIZEN_VOTE_NULLIFIER_UNIQUE_INDEX, BillStatus, GovernanceLevel, VoteChoice
from routers import voting

BILL_ID = "GR-TIER1-001"
NULLIFIER_HASH = "a" * 64


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDb:
    """Serves queued results in order; records writes."""

    def __init__(self, values):
        self.values = list(values)
        self.executed = []
        self.added = []
        self.commits = 0

    async def execute(self, statement):
        self.executed.append(statement)
        return _Result(self.values.pop(0))

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass


def _identity():
    return SimpleNamespace(public_key_hex="c" * 64, periferia_id=None, dimos_id=None)


def _bill(bill_id: str = BILL_ID):
    return SimpleNamespace(
        id=bill_id,
        status=BillStatus.ACTIVE,
        governance_level=GovernanceLevel.NATIONAL,
        admin_hidden=False,
    )


def _tier1_fields(
    *,
    sign_bill_id: str = BILL_ID,
    sign_choice: str = "YES",
    signer: SigningKey | None = None,
    claimed_pk: bytes | None = None,
    timestamp_ms: int | None = None,
) -> dict:
    signer = signer or SigningKey.generate()
    pk_eph = bytes(signer.verify_key)
    vote_nullifier = bytes.fromhex("11" * 32)
    linkage_tag = bytes.fromhex("22" * 32)
    ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    message = build_signed_payload(
        bill_id=sign_bill_id,
        choice=sign_choice,
        pk_eph=pk_eph,
        vote_nullifier=vote_nullifier,
        linkage_tag=linkage_tag,
        timestamp_ms=ts,
    )
    return {
        "pk_eph": (claimed_pk or pk_eph).hex(),
        "vote_nullifier": vote_nullifier.hex(),
        "linkage_tag": linkage_tag.hex(),
        "timestamp_ms": ts,
        "tier1_signature_hex": signer.sign(message).signature.hex(),
    }


def _request(vote: str = "YES", **tier1) -> voting.VoteRequest:
    return voting.VoteRequest(
        nullifier_hash=NULLIFIER_HASH,
        bill_id=BILL_ID,
        vote=vote,
        signature_hex="b" * 128,
        **tier1,
    )


@pytest.fixture(autouse=True)
def _identity_signature_ok(monkeypatch):
    monkeypatch.delenv("ZK_TIER1_GUARD_ENABLED", raising=False)
    monkeypatch.setattr(voting, "verify_signature", lambda *_args: True)


async def _submit(req, *, nullifier_used: bool = False):
    # identity, bill, tier-1 nullifier lookup, existing vote lookup
    used_row = 99 if nullifier_used else None
    db = _FakeDb([_identity(), _bill(), used_row, None])
    try:
        return await voting.submit_vote(req, db), db
    except HTTPException as exc:
        exc.db = db
        raise


async def _expect_reject(req, status_code: int, **kwargs) -> _FakeDb:
    with pytest.raises(HTTPException) as exc:
        await _submit(req, **kwargs)
    assert exc.value.status_code == status_code
    db = exc.value.db
    assert db.added == []
    assert db.commits == 0
    return db


# ── Root cause evidence ───────────────────────────────────────────────────────

def test_previous_router_kwargs_never_matched_validate_vote():
    """The pre-fix call shape raised TypeError on every Tier-1 vote."""
    params = inspect.signature(validate_vote).parameters
    assert list(params)[:2] == ["payload", "used_nullifiers"]
    with pytest.raises(TypeError):
        validate_vote(
            pk_eph="00" * 32,
            vote_nullifier="11" * 32,
            linkage_tag="22" * 32,
            bill_id=BILL_ID,
            choice="YES",
            signature="33" * 64,
            timestamp_ms=0,
        )


def test_router_no_longer_swallows_tier1_exceptions():
    source = inspect.getsource(voting.submit_vote) + inspect.getsource(voting._enforce_tier1_vote)
    assert "non-blocking" not in source
    assert "except Exception" not in source


# ── Router behaviour ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_tier1_vote_is_stored():
    fields = _tier1_fields()
    resp, db = await _submit(_request(**fields))
    assert resp.success is True
    assert db.commits == 1
    (row,) = db.added
    assert row.pk_eph == fields["pk_eph"]
    assert row.vote_nullifier == fields["vote_nullifier"]
    assert row.linkage_tag == fields["linkage_tag"]
    assert row.timestamp_ms == fields["timestamp_ms"]
    assert "vote_nullifier" in str(db.executed[2])


@pytest.mark.asyncio
async def test_legacy_vote_without_tier1_fields_is_unchanged():
    db = _FakeDb([_identity(), _bill(), None])
    resp = await voting.submit_vote(_request(), db)
    assert resp.success is True
    assert len(db.executed) == 3  # no Tier-1 nullifier lookup
    assert db.added[0].pk_eph is None


@pytest.mark.asyncio
async def test_identity_signature_still_required_for_tier1(monkeypatch):
    monkeypatch.setattr(voting, "verify_signature", lambda *_args: False)
    db = _FakeDb([_identity(), _bill()])
    with pytest.raises(HTTPException) as exc:
        await voting.submit_vote(_request(**_tier1_fields()), db)
    assert exc.value.status_code == 401
    assert db.added == []


@pytest.mark.asyncio
async def test_tampered_tier1_signature_rejected():
    fields = _tier1_fields()
    sig = bytearray.fromhex(fields["tier1_signature_hex"])
    sig[0] ^= 0x01
    fields["tier1_signature_hex"] = sig.hex()
    await _expect_reject(_request(**fields), 401)


@pytest.mark.asyncio
async def test_wrong_public_key_rejected():
    fields = _tier1_fields(claimed_pk=bytes(SigningKey.generate().verify_key))
    await _expect_reject(_request(**fields), 401)


@pytest.mark.asyncio
async def test_signature_for_other_bill_rejected():
    await _expect_reject(_request(**_tier1_fields(sign_bill_id="GR-OTHER")), 401)


@pytest.mark.asyncio
async def test_signature_for_other_choice_rejected():
    await _expect_reject(_request(vote="NO", **_tier1_fields(sign_choice="YES")), 401)


@pytest.mark.asyncio
async def test_expired_timestamp_rejected():
    stale = int(time.time() * 1000) - nullifier.TIMESTAMP_WINDOW_MS - 1_000
    await _expect_reject(_request(**_tier1_fields(timestamp_ms=stale)), 400)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field, value",
    [
        ("pk_eph", "zz" * 32),
        ("pk_eph", "00" * 31),
        ("vote_nullifier", "11" * 33),
        ("linkage_tag", ""),
        ("tier1_signature_hex", "33" * 63),
    ],
)
async def test_malformed_tier1_material_rejected(field, value):
    fields = _tier1_fields()
    fields[field] = value
    await _expect_reject(_request(**fields), 400)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["pk_eph", "vote_nullifier", "linkage_tag", "timestamp_ms", "tier1_signature_hex"])
async def test_incomplete_tier1_fields_rejected(missing):
    fields = _tier1_fields()
    fields.pop(missing)
    with pytest.raises(HTTPException) as exc:
        await voting.submit_vote(_request(**fields), _FakeDb([_identity(), _bill()]))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_unknown_choice_not_valid_for_tier1():
    await _expect_reject(_request(vote="UNKNOWN", **_tier1_fields(sign_choice="UNKNOWN")), 400)


@pytest.mark.asyncio
async def test_duplicate_vote_nullifier_rejected():
    await _expect_reject(_request(**_tier1_fields()), 409, nullifier_used=True)


@pytest.mark.asyncio
async def test_duplicate_vote_nullifier_lookup_is_case_insensitive():
    db = _FakeDb([None])
    await voting._tier1_vote_nullifier_used(
        db,
        vote_nullifier="AB" * 32,
        nullifier_hash=NULLIFIER_HASH,
        bill_id=BILL_ID,
    )
    statement = db.executed[0]
    assert "lower(" in str(statement).lower()
    assert ("ab" * 32) in statement.compile().params.values()


@pytest.mark.asyncio
async def test_verifier_backend_failure_is_503_not_invalid_signature(monkeypatch, caplog):
    class _BrokenVerifyKey:
        def __init__(self, *_args):
            raise RuntimeError("libsodium unavailable")

    monkeypatch.setattr(nullifier, "VerifyKey", _BrokenVerifyKey)
    fields = _tier1_fields()
    with caplog.at_level("ERROR"):
        db = await _expect_reject(_request(**fields), 503)
    assert len(db.executed) == 3  # never reached the vote write path
    assert "RuntimeError" in caplog.text
    assert fields["pk_eph"] not in caplog.text
    assert fields["tier1_signature_hex"] not in caplog.text


# ── Validator contract ───────────────────────────────────────────────────────

def _payload(**fields) -> VotePayload:
    return VotePayload(
        bill_id=BILL_ID,
        choice="YES",
        pk_eph=fields["pk_eph"],
        vote_nullifier=fields["vote_nullifier"],
        linkage_tag=fields["linkage_tag"],
        signature=fields["tier1_signature_hex"],
        timestamp_ms=fields["timestamp_ms"],
        version=nullifier.PROTO_VERSION,
    )


def test_validator_backend_error_is_typed_not_validation_error(monkeypatch):
    def _boom(*_args):
        raise RuntimeError("backend")

    monkeypatch.setattr(nullifier, "VerifyKey", _boom)
    with pytest.raises(Tier1CryptoBackendError):
        validate_vote(_payload(**_tier1_fields()), set())


def test_validator_bad_signature_is_validation_error():
    fields = _tier1_fields(claimed_pk=bytes(SigningKey.generate().verify_key))
    err = validate_vote(_payload(**fields), set())
    assert err is not None and err.code == "INVALID_SIGNATURE"


# ── T-410: canonical storage and exact conflict mapping ──────────────────────

@pytest.mark.asyncio
async def test_tier1_hex_stored_lowercase():
    signer = SigningKey.generate()
    fields = _tier1_fields(signer=signer)
    upper = {
        key: (value.upper() if key in {"pk_eph", "vote_nullifier", "linkage_tag"} else value)
        for key, value in fields.items()
    }
    _resp, db = await _submit(_request(**upper))
    (row,) = db.added
    assert row.pk_eph == fields["pk_eph"].lower()
    assert row.vote_nullifier == fields["vote_nullifier"].lower()
    assert row.linkage_tag == fields["linkage_tag"].lower()


@pytest.mark.asyncio
async def test_whitespace_hex_rejected_before_lookup():
    fields = _tier1_fields()
    fields["vote_nullifier"] = "11 " * 21 + "1"  # 64 chars, bytes.fromhex() would accept
    assert len(fields["vote_nullifier"]) == 64
    db = await _expect_reject(_request(**fields), 400)
    assert len(db.executed) == 2  # identity + bill, no nullifier lookup


class _PgError(Exception):
    def __init__(self, sqlstate: str, constraint_name: str | None):
        super().__init__("pg")
        self.sqlstate = sqlstate
        self.constraint_name = constraint_name


def _integrity_error(sqlstate: str, constraint_name: str | None) -> IntegrityError:
    adapted = Exception("adapted")
    adapted.__cause__ = _PgError(sqlstate, constraint_name)
    return IntegrityError("INSERT", {}, adapted)


class _FailingCommitDb:
    def __init__(self, exc: BaseException):
        self.exc = exc
        self.rollbacks = 0

    async def commit(self):
        raise self.exc

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "constraint, detail",
    [
        (CITIZEN_VOTE_NULLIFIER_UNIQUE_INDEX, voting.TIER1_DUPLICATE_DETAIL),
        ("uq_one_vote_per_citizen", "Η ψήφος έχει ήδη καταχωρηθεί."),
    ],
)
async def test_expected_unique_conflicts_map_to_409(constraint, detail):
    db = _FailingCommitDb(_integrity_error("23505", constraint))
    with pytest.raises(HTTPException) as exc:
        await voting._commit_vote_write(db)
    assert exc.value.status_code == 409
    assert exc.value.detail == detail
    assert db.rollbacks == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sqlstate, constraint",
    [
        ("23505", "uq_some_other_index"),
        ("23505", None),
        ("23503", CITIZEN_VOTE_NULLIFIER_UNIQUE_INDEX),  # FK, same name must not match
        ("23514", "ck_votes"),
    ],
)
async def test_foreign_integrity_errors_are_reraised(sqlstate, constraint):
    error = _integrity_error(sqlstate, constraint)
    db = _FailingCommitDb(error)
    with pytest.raises(IntegrityError) as exc:
        await voting._commit_vote_write(db)
    assert exc.value is error
    assert db.rollbacks == 1


@pytest.mark.asyncio
async def test_non_integrity_commit_failure_rolls_back_and_reraises():
    db = _FailingCommitDb(RuntimeError("connection lost"))
    with pytest.raises(RuntimeError):
        await voting._commit_vote_write(db)
    assert db.rollbacks == 1


def _window_bill():
    bill = _bill()
    bill.status = BillStatus.WINDOW_24H
    return bill


def _stored_vote(*, tier1: bool, timestamp_ms: int | None = None):
    return SimpleNamespace(
        vote=VoteChoice.YES,
        signature_hex="0" * 128,
        pk_eph="01" * 32 if tier1 else None,
        vote_nullifier="11" * 32 if tier1 else None,
        linkage_tag="02" * 32 if tier1 else None,
        timestamp_ms=timestamp_ms if tier1 else None,
        is_correction=False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_tier1", [True, False])
async def test_resubmit_refuses_tier_switch(stored_tier1):
    stored = _stored_vote(tier1=stored_tier1, timestamp_ms=1)
    snapshot = dict(vars(stored))
    if stored_tier1:
        req, values = _request(vote="NO"), [_identity(), _window_bill(), stored]
    else:
        req = _request(vote="NO", **_tier1_fields(sign_choice="NO"))
        values = [_identity(), _window_bill(), None, stored]
    db = _FakeDb(values)
    with pytest.raises(HTTPException) as exc:
        await voting.submit_vote(req, db)
    assert exc.value.status_code == 409
    assert db.commits == 0
    assert vars(stored) == snapshot
    assert "FOR UPDATE" in str(db.executed[-1])


@pytest.mark.asyncio
async def test_correction_requires_fresh_tier1_payload_and_locks_row():
    stored = _stored_vote(tier1=True, timestamp_ms=int(time.time() * 1000) + 60_000)
    snapshot = dict(vars(stored))
    fields = _tier1_fields(sign_bill_id=BILL_ID, sign_choice="NO")
    req = voting.CorrectionRequest(
        nullifier_hash=NULLIFIER_HASH, bill_id=BILL_ID, vote="NO",
        signature_hex="b" * 128, **fields,
    )
    db = _FakeDb([_window_bill(), _identity(), stored, None])
    with pytest.raises(HTTPException) as exc:
        await voting.correct_vote(BILL_ID, req, db)
    assert exc.value.status_code == 400
    assert "STALE_PAYLOAD" in exc.value.detail
    assert db.commits == 0
    assert vars(stored) == snapshot
    assert "FOR UPDATE" in str(db.executed[2])
