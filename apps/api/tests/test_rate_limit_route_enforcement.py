"""Exercise EVA-011 limits on real included routes, without lifespan or I/O."""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from nacl.signing import SigningKey

import main
from database import get_db
from models import BillStatus
from rate_limit import limiter
from routers import export, polis_qr, public_api
from services.citizen_action_integrity import build_vote_status_read_payload


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
    ("GET", "/api/v1/export/bills.csv", None, 20, 200),
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
def test_heavy_public_reads_bound_shared_ssr_traffic(limited_app, monkeypatch, path, status):
    client, session, storage = limited_app
    monkeypatch.setattr(export, "get_all_results", AsyncMock(return_value=[]))
    for _ in range(20):
        assert client.get(path).status_code == status
    calls = session.execute.await_count
    assert client.get(path).status_code == 429
    assert session.execute.await_count == calls
    assert storage.storage


@pytest.mark.parametrize("method,path,quota", [
    ("GET", "/api/v1/rep/my-scores", 10),
    ("GET", "/api/v1/rep/results/{target}", 30),
    ("GET", "/api/v1/rep/divergence/{target}", 30),
    ("POST", "/api/v1/rep/enable-evaluation", 20),
])
@pytest.mark.parametrize("credentials", ["invalid", "malformed", "missing"])
def test_representative_rate_limits_reject_before_authentication(
    limited_app, method, path, quota, credentials,
):
    client, session, storage = limited_app

    def headers(index):
        result = {"X-Forwarded-For": "203.0.113.101"}
        if credentials != "missing":
            scheme = "Bearer" if credentials == "invalid" else "Basic"
            result["Authorization"] = f"{scheme} rejected-token-{index}"
        return result

    status = 422 if credentials == "missing" else 401
    for index in range(quota):
        response = client.request(method, path.format(target=f"missing-{index}"), headers=headers(index))
        assert response.status_code == status, response.text
    queries = quota if credentials == "invalid" else 0
    assert session.execute.await_count == queries
    assert client.request(method, path.format(target="rotated"), headers=headers(quota)).status_code == 429
    assert session.execute.await_count == queries
    assert storage.storage
    assert all("ratelimit:slowapi:" in key for key in storage.storage)
    assert all("rejected-token" not in key and "203.0.113." not in key for key in storage.storage)
    other_ip = {**headers(quota), "X-Forwarded-For": "203.0.113.102"}
    assert client.request(method, path.format(target="fresh"), headers=other_ip).status_code == status


def test_representative_rate_limit_counts_authenticated_requests_once(limited_app):
    client, session, storage = limited_app

    async def query(statement, *args):
        if "representative_tokens" in str(statement):
            return SimpleNamespace(fetchone=lambda: ("ADA-fixture", "MP", None, None, None, None, None, None, None))
        return EmptyResult()

    session.execute.side_effect = query
    headers = {"Authorization": "Bearer local-valid-token"}
    for _ in range(10):
        response = client.get("/api/v1/rep/my-scores", headers=headers)
        assert response.status_code == 200, response.text
    assert list(storage.storage.values()) == [10]
    assert session.execute.await_count == 20  # Auth lookup and score query.
    assert client.get("/api/v1/rep/my-scores", headers=headers).status_code == 429
    assert session.execute.await_count == 20


def test_vote_preflight_rate_limit_allows_eleven_shared_ip_identities_and_full_vote_budget(limited_app):
    client, session, _ = limited_app
    keys = {f"{index:064x}": SigningKey(bytes([index]) * 32) for index in range(1, 12)}
    timestamp = int(time.time() * 1000)

    async def query(statement, *args):
        sql = str(statement)
        if "identity_records" in sql:
            nullifier = statement.compile().params["nullifier_hash_1"]
            key = keys[nullifier]
            return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(
                public_key_hex=key.verify_key.encode().hex(),
            ))
        if "parliament_bills" in sql:
            return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(
                status=BillStatus.ACTIVE, source="PARLIAMENT", admin_hidden=False,
            ))
        assert "citizen_votes" in sql
        return EmptyResult()

    session.execute.side_effect = query
    identities = list(keys)
    for index in range(120):
        bill_id = f"GR-preflight-{index}"
        nullifier = identities[index % len(identities)]
        payload = build_vote_status_read_payload(bill_id, nullifier, timestamp)
        body = {
            "nullifier_hash": nullifier, "timestamp_ms": timestamp,
            "signature_hex": keys[nullifier].sign(payload.encode()).signature.hex(),
        }
        response = client.post(f"/api/v1/vote/{bill_id}/status", json=body)
        assert response.status_code == 200, response.text
        assert response.headers["x-vote-read-integrity"] == "signed"
    assert session.execute.await_count == 360
    assert client.post("/api/v1/vote/rotated/status", json=body).status_code == 429
    assert session.execute.await_count == 360


class QRRedis:
    """Server-created sessions and expiring counters with a controllable clock."""

    def __init__(self):
        self.now = 1_788_000_000.0
        self.sessions = {}
        self.counts = {}
        self.expirations = {}
        self.hgetall = AsyncMock(side_effect=lambda key: self.sessions.get(key, {}))

    async def hset(self, key, *, mapping):
        self.sessions[key] = mapping

    async def expire(self, key, seconds):
        assert key in self.sessions and seconds == polis_qr.SESSION_TTL

    async def eval(self, script, numkeys, key, seconds):
        assert numkeys == 1 and seconds == 60
        assert "redis.call('INCR', KEYS[1])" in script
        assert "redis.call('EXPIRE', KEYS[1], ARGV[1])" in script
        if self.expirations.get(key, 0) <= self.now:
            self.counts[key] = 0
            self.expirations[key] = self.now + seconds
        self.counts[key] += 1
        return self.counts[key]


@pytest.fixture
def qr_redis(limited_app, monkeypatch):
    redis = QRRedis()
    monkeypatch.setattr(polis_qr, "_redis", AsyncMock(return_value=redis))
    monkeypatch.setattr("limits.storage.memory.time.time", lambda: redis.now)
    return redis


def create_qr_sessions(client, count):
    sessions = []
    for _ in range(count):
        response = client.get("/api/v1/polis/qr-session")
        assert response.status_code == 200, response.text
        sessions.append(response.json()["session_id"])
    return sessions


def test_qr_status_rate_limit_allows_six_concurrent_sessions_at_client_interval(limited_app, qr_redis):
    client, _, _ = limited_app
    sessions = create_qr_sessions(client, 6)
    # Six real sessions at t=0, 2.5, ..., 60s, including an initial poll.
    for _ in range(25):
        for session_id in sessions:
            response = client.get(f"/api/v1/polis/qr-session/{session_id}")
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "pending"
        qr_redis.now += 2.5
    assert qr_redis.hgetall.await_count == 150


def test_qr_poll_session_rate_limit_is_shared_across_ips_and_recovers(limited_app, qr_redis):
    client, _, _ = limited_app
    first, second = create_qr_sessions(client, 2)
    for index in range(30):
        response = client.get(f"/api/v1/polis/qr-session/{first}", headers={
            "X-Forwarded-For": f"203.0.113.{index + 1}",
        })
        assert response.status_code == 200
    assert client.get(f"/api/v1/polis/qr-session/{first}").status_code == 429
    assert client.get(f"/api/v1/polis/qr-session/{second}").status_code == 200
    assert len(qr_redis.counts) == 2
    assert all(first not in key and second not in key for key in qr_redis.counts)
    assert all("203.0.113." not in key for key in qr_redis.counts)
    qr_redis.now += 60
    assert client.get(f"/api/v1/polis/qr-session/{first}").status_code == 200


def test_qr_poll_ip_ceiling_bounds_unknown_session_rotation_before_redis(limited_app, qr_redis):
    client, _, _ = limited_app
    for index in range(600):
        response = client.get(f"/api/v1/polis/qr-session/unknown-{index}")
        assert response.status_code == 200
        assert response.json()["status"] == "expired"
    assert client.get("/api/v1/polis/qr-session/another").status_code == 429
    assert qr_redis.hgetall.await_count == 600
    assert not qr_redis.counts  # Unknown IDs cannot allocate session counters.
    assert client.get("/api/v1/polis/qr-session/another", headers={
        "X-Forwarded-For": "203.0.113.102",
    }).status_code == 200


def test_qr_poll_ip_ceiling_also_bounds_valid_session_rotation(limited_app, qr_redis):
    client, _, _ = limited_app
    # Sessions can be created on several networks before polling behind one NAT.
    sessions = [f"existing-{index}" for index in range(25)]
    for session_id in sessions:
        qr_redis.sessions[f"polis_qr:{session_id}"] = {"status": "pending"}
    for _ in range(24):
        for session_id in sessions:
            assert client.get(f"/api/v1/polis/qr-session/{session_id}").status_code == 200
    assert client.get(f"/api/v1/polis/qr-session/{sessions[0]}").status_code == 429
    assert qr_redis.hgetall.await_count == 600
    assert set(qr_redis.counts.values()) == {24}
