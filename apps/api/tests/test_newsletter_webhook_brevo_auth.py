"""Mock-only tests for EKA-09 Brevo webhook bearer authentication.

Covers unconfigured token (503), missing/malformed/wrong credentials (401
with Bearer challenge) and valid auth for single and batched payloads.
Proves rejected requests perform zero Redis mutations and never parse the
JSON body, and that accepted requests retain the existing counter/cache
behavior. No real Redis, network or token material is used.
"""
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routers import newsletter

TEST_TOKEN = "test-only-webhook-token-not-a-secret"


class _FakeRedis:
    """In-memory stand-in recording every mutation; never touches Redis."""

    def __init__(self) -> None:
        self.events: dict[str, int] = {}
        self.deleted: list[str] = []
        self.mutations: list[tuple[str, tuple[Any, ...]]] = []

    async def hincrby(self, key: str, field: str, amount: int) -> int:
        self.mutations.append(("hincrby", (key, field, amount)))
        assert key == "newsletter:events"
        self.events[field] = self.events.get(field, 0) + amount
        return self.events[field]

    async def delete(self, *keys: str) -> int:
        self.mutations.append(("delete", keys))
        self.deleted.extend(keys)
        return len(keys)


class _BodyGuardRequest:
    """Request stub whose JSON body raises if parsed before auth."""

    def __init__(self, authorization: str | None) -> None:
        self.headers = {}
        if authorization is not None:
            self.headers["authorization"] = authorization

    async def json(self) -> Any:
        raise AssertionError("JSON body must not be parsed before authentication")


class _JsonRequest:
    """Request stub returning a fixed JSON payload."""

    def __init__(self, authorization: str, payload: Any) -> None:
        self.headers = {"authorization": authorization}
        self._payload = payload
        self.parsed = False

    async def json(self) -> Any:
        self.parsed = True
        return self._payload


@pytest.fixture
def redis_store(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    store = _FakeRedis()
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    monkeypatch.setattr(newsletter, "BREVO_WEBHOOK_TOKEN", TEST_TOKEN)
    return store


async def test_unconfigured_token_returns_503_before_any_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeRedis()
    get_redis = AsyncMock(return_value=store)
    monkeypatch.setattr(newsletter, "_get_redis", get_redis)
    monkeypatch.setattr(newsletter, "BREVO_WEBHOOK_TOKEN", "")

    with pytest.raises(HTTPException) as exc:
        await newsletter.brevo_webhook(_BodyGuardRequest(f"Bearer {TEST_TOKEN}"))
    assert exc.value.status_code == 503
    get_redis.assert_not_called()
    assert store.mutations == []


@pytest.mark.parametrize("authorization", [
    None,
    "",
    "Bearer",
    "Bearer  ",
    f"Token {TEST_TOKEN}",
    f"basic {TEST_TOKEN}",
    f"BEARERER {TEST_TOKEN}",
])
async def test_missing_or_malformed_credentials_return_401_challenge(
    redis_store: _FakeRedis, authorization: str | None,
) -> None:
    with pytest.raises(HTTPException) as exc:
        await newsletter.brevo_webhook(_BodyGuardRequest(authorization))
    assert exc.value.status_code == 401
    assert exc.value.headers == {"WWW-Authenticate": "Bearer"}
    assert redis_store.mutations == []


@pytest.mark.parametrize("presented", [
    "wrong-token",
    TEST_TOKEN + "x",
    TEST_TOKEN[:-1],
    f"{TEST_TOKEN} extra",
    "tést-non-ascii",
])
async def test_wrong_credentials_return_401_challenge(
    redis_store: _FakeRedis, presented: str,
) -> None:
    with pytest.raises(HTTPException) as exc:
        await newsletter.brevo_webhook(_BodyGuardRequest(f"Bearer {presented}"))
    assert exc.value.status_code == 401
    assert exc.value.headers == {"WWW-Authenticate": "Bearer"}
    assert redis_store.mutations == []


async def test_rejections_never_log_token_material(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=_FakeRedis()))
    monkeypatch.setattr(newsletter, "BREVO_WEBHOOK_TOKEN", TEST_TOKEN)
    with caplog.at_level(logging.DEBUG, logger="routers.newsletter"):
        for authorization in (None, "wrong-token", TEST_TOKEN + "x"):
            with pytest.raises(HTTPException):
                await newsletter.brevo_webhook(_BodyGuardRequest(authorization))
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert TEST_TOKEN not in messages


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
async def test_valid_single_event_retains_counter_behavior(
    redis_store: _FakeRedis, scheme: str,
) -> None:
    payload = {"event": "delivered", "email": "citizen@example.org"}
    request = _JsonRequest(f"{scheme} {TEST_TOKEN}", payload)

    result = await newsletter.brevo_webhook(request)

    assert result == {"received": True, "events": 1}
    assert request.parsed is True
    assert redis_store.events == {"delivered": 1}
    assert redis_store.deleted == ["newsletter:stats_cache"]


async def test_valid_batched_events_retain_counter_behavior(
    redis_store: _FakeRedis,
) -> None:
    payload = [
        {"event": "sent"},
        {"event": "opened"},
        {"event": "opened"},
        {"event": "hardBounce"},
        {"event": "notARealEvent"},
        {"no_event_key": True},
    ]
    request = _JsonRequest(f"Bearer {TEST_TOKEN}", payload)

    result = await newsletter.brevo_webhook(request)

    assert result == {"received": True, "events": 6}
    assert redis_store.events == {"sent": 1, "opened": 2, "hardBounce": 1}
    assert redis_store.deleted == ["newsletter:stats_cache"]


async def test_authenticated_processing_error_is_not_disclosed(
    redis_store: _FakeRedis,
) -> None:
    internal_detail = "redis://user:private-value@example.invalid:6379"
    redis_store.hincrby = AsyncMock(side_effect=RuntimeError(internal_detail))
    request = _JsonRequest(
        f"Bearer {TEST_TOKEN}",
        {"event": "delivered"},
    )

    result = await newsletter.brevo_webhook(request)

    assert result == {"received": False, "error": "Webhook processing failed"}
    assert internal_detail not in str(result)
