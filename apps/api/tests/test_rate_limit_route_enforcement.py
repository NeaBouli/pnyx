"""Exercise EVA-011 limits on real included routes, without lifespan or I/O."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

import main
from database import get_db
from rate_limit import limiter
from routers import export, polis_qr, public_api


class EmptyResult:
    def scalar_one_or_none(self):
        return None

    def fetchone(self):
        return None

    def scalars(self):
        return self

    def all(self):
        return []

    def fetchall(self):
        return []


@pytest.fixture
def limited_app(monkeypatch):
    # Decorators close over the original singleton, so enable that instance.
    storage = MemoryStorage()
    monkeypatch.setattr(limiter, "enabled", True)
    monkeypatch.setattr(limiter, "_storage", storage)
    monkeypatch.setattr(limiter, "_limiter", FixedWindowRateLimiter(storage))
    monkeypatch.setattr(limiter, "_storage_dead", False)
    monkeypatch.setattr(limiter, "_in_memory_fallback_enabled", False)
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    monkeypatch.setenv("EVALUATION_REQUIRE_V2", "false")
    session = SimpleNamespace(execute=AsyncMock(return_value=EmptyResult()),
                              get=AsyncMock(return_value=None))
    monkeypatch.setitem(main.app.dependency_overrides, get_db, lambda: session)
    client = TestClient(main.app, client=("127.0.0.1", 50000))
    try:
        yield client, session, storage
    finally:
        client.close()
        storage.reset()


NULLIFIER = "a" * 64
SIGNATURE = "0" * 128


@pytest.mark.parametrize("method,path,body,quota,status", [
    ("PUT", "/api/v1/vote/{target}/correct", {
        "bill_id": "missing", "vote": "NO", "nullifier_hash": NULLIFIER,
        "signature_hex": SIGNATURE,
    }, 20, 404),
    ("POST", "/api/v1/vote/{target}/relevance", {
        "signal": 1, "nullifier_hash": NULLIFIER, "signature_hex": SIGNATURE,
    }, 30, 403),
    ("POST", "/api/v1/vote/{target}/consensus", {
        "score": 1, "nullifier_hash": NULLIFIER, "signature_hex": SIGNATURE,
    }, 20, 404),
    ("POST", "/api/v1/identity/status", {"nullifier_hash": NULLIFIER}, 10, 404),
    ("PATCH", "/api/v1/identity/profile/location", {
        "nullifier_hash": NULLIFIER, "signature_hex": SIGNATURE,
    }, 20, 403),
    ("POST", "/api/v1/municipal/vote", {
        "ada": "missing", "vote": "YES", "nullifier_hash": NULLIFIER,
        "signature_hex": SIGNATURE,
    }, 20, 404),
    ("POST", "/api/v1/politicians/{target}/evaluate", {
        "nullifier_hash": NULLIFIER, "signature_hex": SIGNATURE,
        "scores": [{"question_id": 1, "score": 1}],
    }, 20, 404),
    ("GET", f"/api/v1/politicians/{{target}}/my-evaluation?nullifier_hash={NULLIFIER}", None, 10, 200),
    ("GET", f"/api/v1/politicians/my-evaluations/bulk?nullifier_hash={NULLIFIER}", None, 10, 200),
    ("GET", "/api/v1/export/bills.csv", None, 30, 200),
])
def test_new_rate_limits_reject_before_handler_work_and_cannot_rotate_targets(
    limited_app, method, path, body, quota, status,
):
    client, session, storage = limited_app
    headers = {"X-Forwarded-For": "203.0.113.101"}
    for index in range(quota):
        response = client.request(method, path.format(target=f"missing-{index}"),
                                  json=body, headers=headers)
        assert response.status_code == status, response.text
    calls = (session.execute.await_count, session.get.await_count)
    assert client.request(method, path.format(target="another"), json=body,
                          headers=headers).status_code == 429
    assert (session.execute.await_count, session.get.await_count) == calls
    # The IP budget does not block a different trusted client IP.
    assert client.request(method, path.format(target="fresh"), json=body,
                          headers={"X-Forwarded-For": "203.0.113.102"}).status_code == status
    # New scopes still use the existing daily HMAC-IP key function.
    assert storage.storage
    assert all("ratelimit:slowapi:" in key for key in storage.storage)
    assert all("203.0.113." not in key and NULLIFIER not in key for key in storage.storage)


def test_api_key_status_rate_limit_cannot_be_reset_by_changing_keys(limited_app, monkeypatch):
    client, _, _ = limited_app
    redis = SimpleNamespace(hget=AsyncMock(return_value=None))
    monkeypatch.setattr(public_api, "get_redis", AsyncMock(return_value=redis))
    for index in range(10):
        response = client.get("/api/v1/public/keys/status", headers={"X-API-Key": f"invalid-{index}"})
        assert response.status_code == 401
    assert client.get("/api/v1/public/keys/status", headers={"X-API-Key": "fresh"}).status_code == 429
    assert redis.hget.await_count == 10


@pytest.mark.parametrize("path,status", [
    ("/api/v1/bills", 200),
    ("/api/v1/export/results.json?min_votes=1", 200),
    ("/api/v1/vote/missing/results", 404),
])
def test_public_reads_allow_ssr_traffic_from_one_ip(limited_app, monkeypatch, path, status):
    client, _, storage = limited_app
    monkeypatch.setattr(export, "get_all_results", AsyncMock(return_value=[]))
    # Above the old 10/30/120 quotas and the configured 60/min default. These
    # requests represent different visitors rendered by the same web server.
    for _ in range(150):
        response = client.get(path, headers={"X-Forwarded-For": "203.0.113.101"})
        assert response.status_code == status, response.text
    assert not storage.storage


def test_qr_status_rate_limit_allows_normal_concurrent_polling(limited_app, monkeypatch):
    client, _, _ = limited_app
    redis = SimpleNamespace(hgetall=AsyncMock(return_value={}))
    monkeypatch.setattr(polis_qr, "_redis", AsyncMock(return_value=redis))
    # Four concurrent QR flows, each 24 polls/minute plus one conservative
    # initial request: 4 * 25 = 100, below the 120/minute IP quota.
    for index in range(100):
        response = client.get(f"/api/v1/polis/qr-session/session-{index % 4}")
        assert response.status_code == 200
    for index in range(20):
        assert client.get(f"/api/v1/polis/qr-session/rotated-{index}").status_code == 200
    assert client.get("/api/v1/polis/qr-session/another").status_code == 429
    assert redis.hgetall.await_count == 120
