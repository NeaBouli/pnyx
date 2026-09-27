"""Mock-only tests for EKA-04 subscribe rate limiting.

Covers both fixed-window limits (10/IP/hour, 3/normalized-email/24h),
boundaries, normalization, no side effects on 429, existing-confirmed and
validation ordering, privacy of Redis keys, and absence of raw email from
success logs. No real email, Redis service or network access.
"""
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routers import newsletter


def _request(ip: str = "203.0.113.10") -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=ip), headers={})


class _FakeRedis:
    """In-memory fixed-window stand-in; never touches a real Redis service."""

    def __init__(self, confirmed: dict[str, str] | None = None) -> None:
        self.confirmed = dict(confirmed or {})
        self.counts: dict[str, int] = {}
        self.pending: dict[str, str] = {}

    async def hget(self, key: str, field: str) -> str | None:
        assert key == "newsletter:confirmed"
        return self.confirmed.get(field)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.pending[key] = value

    async def eval(self, script: str, numkeys: int, *args: Any) -> int:
        key = args[0]
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


class _NoNetworkClient:
    """Raises if the provider HTTP client is ever instantiated."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("HTTP provider must not be instantiated")


@pytest.fixture
def redis_store(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    store = _FakeRedis()
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    monkeypatch.setattr(newsletter, "BREVO_API_KEY", "test-key")
    monkeypatch.setattr(newsletter.httpx, "AsyncClient", _NoNetworkClient)
    return store


async def _attempt(email: str, ip: str = "203.0.113.10") -> None:
    """Drive subscribe up to the provider boundary; counters are consumed."""
    with pytest.raises(AssertionError, match="must not be instantiated"):
        await newsletter.subscribe(newsletter.SubscribeRequest(email=email), _request(ip))


async def test_ip_limit_allows_ten_and_rejects_eleventh(redis_store: _FakeRedis) -> None:
    """10 attempted confirmation emails per IP per hour pass; the 11th is 429."""
    for i in range(newsletter.SUBSCRIBE_IP_LIMIT):
        await _attempt(f"citizen{i}@example.org")
    ip_keys = [k for k in redis_store.counts if ":ip:" in k]
    assert len(ip_keys) == 1
    assert redis_store.counts[ip_keys[0]] == newsletter.SUBSCRIBE_IP_LIMIT
    pending_pre = dict(redis_store.pending)

    with pytest.raises(HTTPException) as exc:
        await newsletter.subscribe(
            newsletter.SubscribeRequest(email="another@example.org"), _request()
        )
    assert exc.value.status_code == 429
    assert redis_store.pending == pending_pre


async def test_email_limit_allows_three_and_rejects_fourth(redis_store: _FakeRedis) -> None:
    """3 attempted confirmation emails per normalized address per 24h; 4th is 429."""
    variants = ["Citizen@Example.org", "citizen@example.org", "CITIZEN@example.ORG"]
    for variant in variants:
        await _attempt(variant)
    email_keys = [k for k in redis_store.counts if newsletter.EMAIL_RATE_NAMESPACE in k]
    assert len(email_keys) == 1
    assert redis_store.counts[email_keys[0]] == newsletter.SUBSCRIBE_EMAIL_LIMIT
    pending_pre = dict(redis_store.pending)

    with pytest.raises(HTTPException) as exc:
        await newsletter.subscribe(
            newsletter.SubscribeRequest(email="citizen@EXAMPLE.org"), _request()
        )
    assert exc.value.status_code == 429
    assert redis_store.pending == pending_pre


async def test_429_has_no_token_write_and_no_provider_call(redis_store: _FakeRedis) -> None:
    """A rejected attempt stores no pending token and never builds the HTTP client."""
    for _ in range(newsletter.SUBSCRIBE_EMAIL_LIMIT):
        await _attempt("limited@example.org")
    counts_pre = dict(redis_store.counts)
    pending_pre = dict(redis_store.pending)

    with pytest.raises(HTTPException) as exc:
        await newsletter.subscribe(
            newsletter.SubscribeRequest(email="limited@example.org"), _request()
        )
    assert exc.value.status_code == 429
    assert redis_store.pending == pending_pre
    # Fixed-window counts the rejected attempt itself, then blocks the send.
    email_bucket = {k: v for k, v in redis_store.counts.items()
                    if newsletter.EMAIL_RATE_NAMESPACE in k}
    email_pre = {k: v for k, v in counts_pre.items()
                 if newsletter.EMAIL_RATE_NAMESPACE in k}
    assert email_bucket == {k: v + 1 for k, v in email_pre.items()}


async def test_existing_confirmed_consumes_no_counters_and_resends_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeRedis(confirmed={"citizen@example.org": '{"frequency": "monthly"}'})
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    monkeypatch.setattr(newsletter, "BREVO_API_KEY", "test-key")
    monkeypatch.setattr(newsletter.httpx, "AsyncClient", _NoNetworkClient)

    result = await newsletter.subscribe(
        newsletter.SubscribeRequest(email="citizen@example.org"), _request()
    )
    assert result == {"success": True, "message": "Already subscribed."}
    assert store.counts == {}
    assert store.pending == {}


@pytest.mark.parametrize("field,value", [("frequency", "daily"), ("language", "xx"),
                                        ("subscriber_type", "unknown")])
async def test_invalid_preferences_consume_no_counters(
    redis_store: _FakeRedis, field: str, value: str,
) -> None:
    """Validation rejects before any rate-limit counter is consumed."""
    with pytest.raises(HTTPException) as exc:
        await newsletter.subscribe(
            newsletter.SubscribeRequest(email="citizen@example.org", **{field: value}), _request()
        )
    assert exc.value.status_code == 400
    assert redis_store.counts == {}
    assert redis_store.pending == {}


async def test_rate_limit_keys_contain_no_raw_ip_or_email(redis_store: _FakeRedis) -> None:
    """Keys hold only truncated HMAC identifiers — never raw IP or email."""
    await _attempt("private@example.org", ip="198.51.100.23")
    assert len(redis_store.counts) == 2
    for key in redis_store.counts:
        assert key.startswith("ratelimit:newsletter:subscribe:")
        assert "198.51.100.23" not in key
        assert "private@example.org" not in key.lower()
        assert "@" not in key


async def test_success_log_has_opaque_reference_and_no_raw_email(
    redis_store: _FakeRedis, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    posted: dict[str, Any] = {}

    class _Resp:
        status_code = 201
        text = "{}"

    class _Client:
        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *args: Any) -> bool:
            return False

        async def post(self, url: str, headers: Any = None, json: Any = None) -> _Resp:
            posted["url"] = url
            posted["json"] = json
            return _Resp()

    monkeypatch.setattr(newsletter.httpx, "AsyncClient", lambda *a, **k: _Client())
    with caplog.at_level(logging.INFO, logger="routers.newsletter"):
        out = await newsletter.subscribe(
            newsletter.SubscribeRequest(email="secret@example.org"), _request()
        )
    assert out["success"] is True
    assert posted["json"]["to"] == [{"email": "secret@example.org"}]
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "secret@example.org" not in messages
    assert "emailref:" in messages
