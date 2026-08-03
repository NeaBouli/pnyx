from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routers.polis_qr import (
    _authenticate_session_once,
    _claim_authenticated_session,
    _mark_session_used,
    _restore_authenticated_session,
)


@pytest.mark.asyncio
async def test_authentication_is_an_atomic_one_time_transition() -> None:
    redis_client = AsyncMock()
    redis_client.eval.return_value = 1

    await _authenticate_session_once(redis_client, "polis_qr:one", "nullifier", "public-key")

    redis_client.eval.assert_awaited_once()
    assert redis_client.eval.await_args.args[-3:] == (
        "polis_qr:one",
        "nullifier",
        "public-key",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("redis_result", "expected_status"),
    [(-1, 410), (0, 409)],
)
async def test_authentication_rejects_expired_or_consumed_session(
    redis_result: int,
    expected_status: int,
) -> None:
    redis_client = AsyncMock()
    redis_client.eval.return_value = redis_result

    with pytest.raises(HTTPException) as exc_info:
        await _authenticate_session_once(redis_client, "polis_qr:one", "nullifier", "public-key")

    assert exc_info.value.status_code == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("redis_result", "expected_status"),
    [(-1, 410), (0, 409)],
)
async def test_vote_claim_rejects_expired_or_concurrently_used_session(
    redis_result: int,
    expected_status: int,
) -> None:
    redis_client = AsyncMock()
    redis_client.eval.return_value = redis_result

    with pytest.raises(HTTPException) as exc_info:
        await _claim_authenticated_session(redis_client, "polis_qr:one")

    assert exc_info.value.status_code == expected_status


@pytest.mark.asyncio
async def test_failed_transaction_can_restore_only_processing_session() -> None:
    redis_client = AsyncMock()

    await _restore_authenticated_session(redis_client, "polis_qr:one")

    redis_client.eval.assert_awaited_once()
    assert redis_client.eval.await_args.args[-1] == "polis_qr:one"


@pytest.mark.asyncio
async def test_committed_vote_is_marked_used_and_identity_is_removed() -> None:
    redis_client = AsyncMock()

    await _mark_session_used(redis_client, "polis_qr:one")

    redis_client.hset.assert_awaited_once_with(
        "polis_qr:one",
        mapping={"status": "used"},
    )
    redis_client.hdel.assert_awaited_once_with(
        "polis_qr:one",
        "nullifier_hash",
        "public_key_hex",
    )
    redis_client.expire.assert_awaited_once_with("polis_qr:one", 60)


@pytest.mark.asyncio
async def test_post_commit_redis_failure_does_not_report_vote_as_failed() -> None:
    redis_client = AsyncMock()
    redis_client.hset.side_effect = ConnectionError("redis unavailable")

    await _mark_session_used(redis_client, "polis_qr:one")

    redis_client.hdel.assert_not_awaited()
