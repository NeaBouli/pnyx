"""Exercise targeted write limits through the actual app and route wrappers.

All storage is local and disposable. TestClient is deliberately not entered as
a context manager, so production startup tasks and provider clients never run.
"""

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from nacl.signing import SigningKey

import main
from database import get_db
from models import BillStatus, GovernanceLevel
from rate_limit import limiter
from routers import agent, contact, newsletter, voting


VOTE_BODY = {
    "nullifier_hash": "a" * 64,
    "bill_id": "GR-targeted-limit",
    "vote": "YES",
    "signature_hex": "00" * 64,
}
IP_ONE = {"X-Forwarded-For": "203.0.113.81"}
IP_TWO = {"X-Forwarded-For": "203.0.113.82"}


class EmptyResult:
    def __init__(self, value: Any = None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Any:
        return self.value

    def scalars(self) -> "EmptyResult":
        return self

    def all(self) -> list[Any]:
        return []


class LocalSession:
    """Fail closed on identity by default; support empty public read results."""

    def __init__(self, *, identity: Any = None, bill: Any = None) -> None:
        self.identity = identity
        self.bill = bill
        self.calls = 0

    async def execute(self, statement: Any, params: Any = None) -> EmptyResult:
        self.calls += 1
        sql = str(statement)
        if "identity_records" in sql:
            return EmptyResult(self.identity)
        if "parliament_bills" in sql:
            return EmptyResult(self.bill)
        raise AssertionError(f"Unexpected database access: {sql}")


class LocalRedis:
    """Run the actual fixed-window helper against recorded INCR/EXPIRE calls."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.windows: dict[str, int] = {}
        self.pending: dict[str, str] = {}

    async def hget(self, key: str, field: str) -> None:
        assert key == "newsletter:confirmed"
        return None

    async def setex(self, key: str, seconds: int, value: str) -> None:
        assert key.startswith("newsletter:pending:") and seconds == 86400
        self.pending[key] = value

    async def eval(self, script: str, numkeys: int, key: str, seconds: int) -> int:
        assert numkeys == 1
        assert "redis.call('INCR', KEYS[1])" in script
        assert "redis.call('EXPIRE', KEYS[1], ARGV[1])" in script
        self.counts[key] = self.counts.get(key, 0) + 1
        self.windows.setdefault(key, seconds)
        return self.counts[key]


@pytest.fixture
def http(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[TestClient, LocalSession], None, None]:
    # Decorators close over this singleton: replacing app.state.limiter would
    # leave those wrappers disabled by conftest and give a false-positive test.
    assert main.app.state.limiter is main.limiter is limiter
    assert agent.limiter is limiter
    assert voting.limiter is limiter
    storage = MemoryStorage()
    monkeypatch.setattr(limiter, "enabled", True)
    monkeypatch.setattr(limiter, "_storage", storage)
    monkeypatch.setattr(limiter, "_limiter", FixedWindowRateLimiter(storage))
    monkeypatch.setattr(limiter, "_storage_dead", False)
    monkeypatch.setattr(limiter, "_in_memory_fallback_enabled", False)
    monkeypatch.setattr(limiter, "_headers_enabled", False)
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    session = LocalSession()
    monkeypatch.setitem(main.app.dependency_overrides, get_db, lambda: session)
    client = TestClient(main.app, client=("127.0.0.1", 50000))
    try:
        yield client, session
    finally:
        client.close()
        storage.reset()


@pytest.fixture
def redis_store(monkeypatch: pytest.MonkeyPatch) -> LocalRedis:
    store = LocalRedis()
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    monkeypatch.setattr(contact, "_get_redis", AsyncMock(return_value=store))
    monkeypatch.setattr(newsletter, "BREVO_API_KEY", "")
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    return store


def test_real_agent_wrapper_limits_each_ip_to_five(
    http: tuple[TestClient, LocalSession], monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = http
    monkeypatch.setattr(agent, "_safety_response", lambda question, lang: {
        "question": question, "answer": "Local fixture", "sources": [], "lang": lang,
    })
    for headers in (IP_ONE, IP_TWO):
        for _ in range(5):
            assert client.post("/api/v1/agent/ask", headers=headers,
                               json={"question": "How does voting work?"}).status_code == 200
        assert client.post("/api/v1/agent/ask", headers=headers,
                           json={"question": "How does voting work?"}).status_code == 429
    assert session.calls == 0


def test_vote_limit_preserves_identity_guard_and_leaves_get_reads_available(
    http: tuple[TestClient, LocalSession],
) -> None:
    client, session = http
    for _ in range(120):
        assert client.post("/api/v1/vote", headers=IP_ONE, json=VOTE_BODY).status_code == 403
    assert session.calls == 120
    assert client.post("/api/v1/vote", headers=IP_ONE, json=VOTE_BODY).status_code == 429
    assert session.calls == 120  # Rejected before database/authentication work.
    assert client.post("/api/v1/vote", headers=IP_TWO, json=VOTE_BODY).status_code == 403

    # Public SSR reads stay available beyond the generic 60/minute threshold,
    # even from the IP whose vote-write bucket has already been exhausted.
    for _ in range(61):
        assert client.get("/api/v1/app/version", headers=IP_ONE).status_code == 200
        assert client.get("/api/v1/bills", headers=IP_ONE).status_code == 200
        assert client.get("/api/v1/vote/results/latest", headers=IP_ONE).status_code == 200
        assert client.get("/api/v1/vote/GR-missing/results", headers=IP_ONE).status_code == 404


def test_vote_write_limit_does_not_bypass_signature_validation(
    http: tuple[TestClient, LocalSession],
) -> None:
    client, session = http
    key = SigningKey(bytes([7]) * 32)
    session.identity = SimpleNamespace(public_key_hex=key.verify_key.encode().hex())
    session.bill = SimpleNamespace(
        id=VOTE_BODY["bill_id"], status=BillStatus.ACTIVE,
        governance_level=GovernanceLevel.NATIONAL, source="PARLIAMENT", admin_hidden=False,
    )
    response = client.post("/api/v1/vote", headers=IP_ONE, json=VOTE_BODY)
    assert response.status_code == 401
    assert session.calls == 2


def test_untrusted_forwarded_headers_cannot_reset_vote_bucket(
    http: tuple[TestClient, LocalSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = http
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "192.0.2.0/24")
    for index in range(120):
        headers = {"X-Forwarded-For": f"203.0.113.{index + 1}"}
        assert client.post("/api/v1/vote", headers=headers, json=VOTE_BODY).status_code == 403
    blocked = client.post("/api/v1/vote", headers=IP_TWO, json=VOTE_BODY)
    assert blocked.status_code == 429
    assert session.calls == 120


def test_newsletter_http_ip_limit_is_ten_without_double_counting(
    http: tuple[TestClient, LocalSession], redis_store: LocalRedis,
) -> None:
    client, _ = http
    for index in range(10):
        response = client.post("/api/v1/newsletter/subscribe", headers=IP_ONE,
                               json={"email": f"citizen{index}@example.org"})
        assert response.status_code == 503
        ip_counts = {key: value for key, value in redis_store.counts.items() if ":ip:" in key}
        email_counts = {key: value for key, value in redis_store.counts.items() if ":email:" in key}
        assert list(ip_counts.values()) == [index + 1]
        assert len(email_counts) == index + 1
        assert set(email_counts.values()) == {1}
    pending = dict(redis_store.pending)
    assert client.post("/api/v1/newsletter/subscribe", headers=IP_ONE,
                       json={"email": "eleventh@example.org"}).status_code == 429
    assert redis_store.pending == pending
    assert sorted(redis_store.counts.values()) == [1] * 10 + [11]
    assert sorted(redis_store.windows.values()) == [3600] + [86400] * 10


def test_newsletter_http_normalized_email_limit_is_three(
    http: tuple[TestClient, LocalSession], redis_store: LocalRedis,
) -> None:
    client, _ = http
    for index, email in enumerate(("Citizen@example.org", "citizen@example.org", "CITIZEN@example.org"), 1):
        assert client.post("/api/v1/newsletter/subscribe", headers=IP_ONE,
                           json={"email": email}).status_code == 503
        assert sorted(redis_store.counts.values()) == [index, index]
    pending = dict(redis_store.pending)
    assert client.post("/api/v1/newsletter/subscribe", headers=IP_TWO,
                       json={"email": "citizen@example.org"}).status_code == 429
    assert redis_store.pending == pending
    assert sorted(redis_store.counts.values()) == [1, 3, 4]


def test_contact_http_limit_is_three_without_double_counting(
    http: tuple[TestClient, LocalSession], redis_store: LocalRedis,
) -> None:
    client, _ = http
    body = {"first_name": "Test", "last_name": "Citizen", "email": "citizen@example.org",
            "message": "A local fixture message", "consent": True}
    for attempt in range(1, 4):
        assert client.post("/api/v1/contact/ngo", headers=IP_ONE, json=body).status_code == 503
        assert list(redis_store.counts.values()) == [attempt]
    assert client.post("/api/v1/contact/ngo", headers=IP_ONE, json=body).status_code == 429
    assert list(redis_store.counts.values()) == [4]
    assert list(redis_store.windows.values()) == [3600]
    assert client.post("/api/v1/contact/ngo", headers=IP_TWO, json=body).status_code == 503
    assert sorted(redis_store.counts.values()) == [1, 4]
