"""EVA-001 PR2: QR sessions authenticated with a rotated-away key must not act."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers import polis_qr
from routers.polis_qr import QRConsensusRequest, QRVoteRequest

OLD_PK = "a" * 64
NEW_PK = "b" * 64
NULLIFIER = "1" * 64


class _Redis:
    def __init__(self, purpose: str, session_pk: str) -> None:
        self.data = {"status": "authenticated", "purpose": purpose, "bill_id": "GR-1",
                     "nullifier_hash": NULLIFIER, "public_key_hex": session_pk}
        self.claimed = False

    async def hgetall(self, _key: str) -> dict:
        return dict(self.data)

    async def eval(self, *_args, **_kwargs):
        self.claimed = True
        return 1


class _Result:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _DB:
    """First query: identity (current key NEW_PK); second: bill (absent)."""

    def __init__(self) -> None:
        self.calls = 0
        self.writes = 0

    async def execute(self, statement, *_a, **_k):
        self.calls += 1
        if "INSERT" in str(statement) or "UPDATE" in str(statement):
            self.writes += 1
        if self.calls == 1:
            return _Result(SimpleNamespace(public_key_hex=NEW_PK, nullifier_hash=NULLIFIER))
        return _Result(None)


async def _run(endpoint: str, session_pk: str):
    purpose = "vote" if endpoint == "vote" else "consensus"
    redis = _Redis(purpose, session_pk)
    db = _DB()

    async def fake_redis():
        return redis

    polis_qr_redis = polis_qr._redis
    polis_qr._redis = fake_redis
    try:
        if endpoint == "vote":
            await polis_qr.qr_web_vote(QRVoteRequest(session_id="s" * 12, bill_id="GR-1", vote="YES"), db=db)
        else:
            await polis_qr.qr_web_consensus(QRConsensusRequest(session_id="s" * 12, bill_id="GR-1", score=1), db=db)
    except HTTPException as exc:
        return exc, redis, db
    finally:
        polis_qr._redis = polis_qr_redis
    return None, redis, db


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["vote", "consensus"])
async def test_session_with_rotated_key_is_rejected(endpoint) -> None:
    exc, redis, db = await _run(endpoint, OLD_PK)
    assert exc is not None and exc.status_code == 403
    assert redis.claimed is False and db.writes == 0
    assert db.calls == 1  # stopped before the bill lookup


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["vote", "consensus"])
async def test_session_with_current_key_passes_the_check(endpoint) -> None:
    exc, _redis, db = await _run(endpoint, NEW_PK)
    assert exc is not None and exc.status_code == 404  # reached the bill lookup
    assert db.calls == 2
