"""EKA-11: gov.gr OAuth state is TTL-bound, shared across workers, single-use.

No gov.gr access: the provider is replaced by an in-test fake. The flow stays
default OFF; tests only force ``is_active`` inside a monkeypatched scope.
"""
import asyncio
import os
import urllib.parse
from typing import Any
from uuid import uuid4

import pytest
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient

from main import app
from routers import govgr


class _Clock:
    def __init__(self) -> None:
        self.t = 1_900_000_000.0

    def __call__(self) -> float:
        return self.t


class _SharedRedisBackend:
    """Stands in for the single Redis server shared by all API workers."""

    def __init__(self, clock: _Clock) -> None:
        self.clock = clock
        self.data: dict[str, tuple[str, float]] = {}

    def _live(self, key: str) -> str | None:
        item = self.data.get(key)
        if item is None:
            return None
        value, expires_at = item
        if self.clock() >= expires_at:
            del self.data[key]
            return None
        return value


class _WorkerRedisClient:
    """One worker's client connection; no await between read and delete, like GETDEL."""

    def __init__(self, backend: _SharedRedisBackend) -> None:
        self.backend = backend

    async def set(self, key: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool | None:
        await asyncio.sleep(0)
        if nx and self.backend._live(key) is not None:
            return None
        assert ex is not None and ex > 0, "state must always carry a TTL"
        self.backend.data[key] = (value, self.backend.clock() + ex)
        return True

    async def getdel(self, key: str) -> str | None:
        await asyncio.sleep(0)
        value = self.backend._live(key)
        self.backend.data.pop(key, None)
        return value


class _BrokenRedisClient:
    async def set(self, *args: Any, **kwargs: Any) -> None:
        raise aioredis.ConnectionError("down")

    async def getdel(self, *args: Any, **kwargs: Any) -> None:
        raise aioredis.ConnectionError("down")


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    c = _Clock()
    monkeypatch.setattr(govgr, "_now", c)
    return c


@pytest.fixture
def backend(clock: _Clock) -> _SharedRedisBackend:
    return _SharedRedisBackend(clock)


@pytest.fixture
def oauth_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(govgr, "GOVGR_CLIENT_ID", "test-client")
    monkeypatch.setattr(govgr, "GOVGR_REDIRECT_URI", "https://ekklesia.test/auth/govgr/callback")
    monkeypatch.setattr(govgr, "_state_redis", None)


def _use_worker(monkeypatch: pytest.MonkeyPatch, client: Any) -> None:
    monkeypatch.setattr(govgr, "_state_redis", client)


# ── Defaults stay OFF ────────────────────────────────────────────────────────

def test_flow_remains_default_off() -> None:
    assert govgr.GOVGR_FLOW_ENABLED is False
    assert govgr.is_active() is False
    assert not all(govgr.ACTIVATION_GATES.values())
    assert not hasattr(govgr, "_oauth_states"), "no process-local state store may exist"


# ── Store-level properties ───────────────────────────────────────────────────

async def test_state_has_entropy_ttl_and_bound_context(
    monkeypatch: pytest.MonkeyPatch, backend: _SharedRedisBackend, oauth_config: None
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    states = {await govgr._issue_oauth_state("/el") for _ in range(20)}
    assert len(states) == 20
    for state in states:
        assert len(state) >= 43  # 32 random bytes, url-safe base64
        assert state not in "".join(backend.data), "raw state must not be stored"
    key, (raw, expires_at) = next(iter(backend.data.items()))
    assert key.startswith("govgr:oauth_state:v1:")
    assert expires_at - backend.clock() == govgr.GOVGR_STATE_TTL_SECONDS
    assert '"purpose": "govgr_oauth_login:v1"' in raw
    assert '"redirect_uri": "https://ekklesia.test/auth/govgr/callback"' in raw


async def test_state_issued_on_one_worker_consumed_on_another(
    monkeypatch: pytest.MonkeyPatch, backend: _SharedRedisBackend, oauth_config: None
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    state = await govgr._issue_oauth_state("/el/bills")

    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    record = await govgr._consume_oauth_state(state)
    assert record["redirect_after"] == "/el/bills"


async def test_state_survives_process_restart(
    monkeypatch: pytest.MonkeyPatch, backend: _SharedRedisBackend, oauth_config: None
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    state = await govgr._issue_oauth_state("/")

    # Restart: the module-level client cache is gone; only the shared store remains.
    monkeypatch.setattr(govgr, "_state_redis", None)
    monkeypatch.setattr(govgr.aioredis, "from_url", lambda *a, **k: _WorkerRedisClient(backend))
    record = await govgr._consume_oauth_state(state)
    assert record["purpose"] == govgr.GOVGR_STATE_PURPOSE


async def test_parallel_consume_exactly_one_wins(
    monkeypatch: pytest.MonkeyPatch, backend: _SharedRedisBackend, oauth_config: None
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    state = await govgr._issue_oauth_state("/")

    async def attempt() -> bool:
        try:
            await govgr._consume_oauth_state(state)
            return True
        except govgr.OAuthStateInvalid:
            return False

    results = await asyncio.gather(*(attempt() for _ in range(16)))
    assert results.count(True) == 1


async def test_replay_is_rejected(
    monkeypatch: pytest.MonkeyPatch, backend: _SharedRedisBackend, oauth_config: None
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    state = await govgr._issue_oauth_state("/")
    await govgr._consume_oauth_state(state)
    with pytest.raises(govgr.OAuthStateInvalid):
        await govgr._consume_oauth_state(state)
    assert backend.data == {}


async def test_expired_state_is_rejected(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock, backend: _SharedRedisBackend, oauth_config: None
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    state = await govgr._issue_oauth_state("/")
    clock.t += govgr.GOVGR_STATE_TTL_SECONDS
    with pytest.raises(govgr.OAuthStateInvalid):
        await govgr._consume_oauth_state(state)


async def test_embedded_expiry_enforced_even_if_store_ttl_is_lost(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock, backend: _SharedRedisBackend, oauth_config: None
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    state = await govgr._issue_oauth_state("/")
    key, (raw, _) = next(iter(backend.data.items()))
    backend.data[key] = (raw, float("inf"))  # e.g. PERSIST applied by mistake
    clock.t += govgr.GOVGR_STATE_TTL_SECONDS + 1
    with pytest.raises(govgr.OAuthStateInvalid):
        await govgr._consume_oauth_state(state)


@pytest.mark.parametrize(
    "bad_state",
    [None, "", "short", "x" * 43 + "!", "a" * 200, "../" + "a" * 50],
)
async def test_malformed_state_rejected_without_store_access(
    monkeypatch: pytest.MonkeyPatch, oauth_config: None, bad_state: str | None
) -> None:
    _use_worker(monkeypatch, _BrokenRedisClient())
    with pytest.raises(govgr.OAuthStateInvalid):
        await govgr._consume_oauth_state(bad_state)


async def test_unknown_state_rejected(
    monkeypatch: pytest.MonkeyPatch, backend: _SharedRedisBackend, oauth_config: None
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    await govgr._issue_oauth_state("/")
    with pytest.raises(govgr.OAuthStateInvalid):
        await govgr._consume_oauth_state("A" * 43)


@pytest.mark.parametrize(
    "attr, value",
    [
        ("GOVGR_REDIRECT_URI", "https://evil.test/callback"),
        ("GOVGR_CLIENT_ID", "other-client"),
        ("GOVGR_STATE_PURPOSE", "family_verify:v1"),
    ],
)
async def test_state_bound_to_context(
    monkeypatch: pytest.MonkeyPatch,
    backend: _SharedRedisBackend,
    oauth_config: None,
    attr: str,
    value: str,
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    state = await govgr._issue_oauth_state("/")
    monkeypatch.setattr(govgr, attr, value)
    with pytest.raises(govgr.OAuthStateInvalid):
        await govgr._consume_oauth_state(state)
    # A context mismatch still burns the state: no second try with fixed context.
    assert backend.data == {}


@pytest.mark.parametrize("raw", ["not-json", "[]", '{"purpose": "govgr_oauth_login:v1"}', '{"exp": "x"}'])
async def test_corrupt_record_rejected(
    monkeypatch: pytest.MonkeyPatch, backend: _SharedRedisBackend, oauth_config: None, raw: str
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    state = "B" * 43
    backend.data[govgr._state_key(state)] = (raw, float("inf"))
    with pytest.raises(govgr.OAuthStateInvalid):
        await govgr._consume_oauth_state(state)


async def test_store_outage_fails_closed(monkeypatch: pytest.MonkeyPatch, oauth_config: None) -> None:
    _use_worker(monkeypatch, _BrokenRedisClient())
    with pytest.raises(govgr.OAuthStateStoreUnavailable):
        await govgr._issue_oauth_state("/")
    with pytest.raises(govgr.OAuthStateStoreUnavailable):
        await govgr._consume_oauth_state("C" * 43)


async def test_nx_collision_is_refused(
    monkeypatch: pytest.MonkeyPatch, backend: _SharedRedisBackend, oauth_config: None
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    monkeypatch.setattr(govgr.secrets, "token_urlsafe", lambda n: "D" * 43)
    await govgr._issue_oauth_state("/")
    with pytest.raises(govgr.OAuthStateStoreUnavailable):
        await govgr._issue_oauth_state("/other")


# ── Endpoint behaviour (flow forced active only within the test) ─────────────

class _FakeResp:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeProvider:
    calls = 0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "_FakeProvider":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def post(self, *args: Any, **kwargs: Any) -> _FakeResp:
        type(self).calls += 1
        return _FakeResp({"access_token": "fake-token"})

    async def get(self, *args: Any, **kwargs: Any) -> _FakeResp:
        return _FakeResp({"sub": "synthetic-subject"})


@pytest.fixture
def active_flow(monkeypatch: pytest.MonkeyPatch, oauth_config: None) -> type[_FakeProvider]:
    monkeypatch.setattr(govgr, "is_active", lambda: True)
    monkeypatch.setattr(govgr, "REGISTRATION_SALT", "t" * 32)
    provider = type("_Provider", (_FakeProvider,), {"calls": 0})
    monkeypatch.setattr(govgr.httpx, "AsyncClient", provider)
    return provider


async def _login(c: AsyncClient) -> str:
    r = await c.get("/api/v1/auth/govgr/login", params={"redirect_after": "/el"})
    assert r.status_code == 307
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(r.headers["location"]).query)
    return query["state"][0]


async def test_endpoint_login_callback_replay(
    monkeypatch: pytest.MonkeyPatch,
    backend: _SharedRedisBackend,
    active_flow: type[_FakeProvider],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        _use_worker(monkeypatch, _WorkerRedisClient(backend))
        state = await _login(c)

        _use_worker(monkeypatch, _WorkerRedisClient(backend))  # callback lands on another worker
        ok = await c.get("/api/v1/auth/govgr/callback", params={"code": "c1", "state": state})
        assert ok.status_code == 200
        assert ok.json()["redirect"] == "/el"

        replay = await c.get("/api/v1/auth/govgr/callback", params={"code": "c1", "state": state})
        assert replay.status_code == 400
    assert active_flow.calls == 1, "replayed state must never reach the token endpoint"


async def test_endpoint_wrong_state_never_reaches_provider(
    monkeypatch: pytest.MonkeyPatch,
    backend: _SharedRedisBackend,
    active_flow: type[_FakeProvider],
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _login(c)
        r = await c.get("/api/v1/auth/govgr/callback", params={"code": "c", "state": "E" * 43})
    assert r.status_code == 400
    assert active_flow.calls == 0


async def test_endpoint_store_outage_fails_closed(
    monkeypatch: pytest.MonkeyPatch, active_flow: type[_FakeProvider]
) -> None:
    _use_worker(monkeypatch, _BrokenRedisClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        login = await c.get("/api/v1/auth/govgr/login")
        callback = await c.get("/api/v1/auth/govgr/callback", params={"code": "c", "state": "F" * 43})
    assert login.status_code == 503
    assert "location" not in login.headers
    assert callback.status_code == 503
    assert active_flow.calls == 0


async def test_endpoints_stay_closed_when_flow_off(
    monkeypatch: pytest.MonkeyPatch, backend: _SharedRedisBackend, oauth_config: None
) -> None:
    _use_worker(monkeypatch, _WorkerRedisClient(backend))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        login = await c.get("/api/v1/auth/govgr/login")
        callback = await c.get("/api/v1/auth/govgr/callback", params={"code": "c", "state": "G" * 43})
    assert login.status_code == 503
    assert callback.status_code == 503
    assert backend.data == {}


# ── Real Redis wire shape (skipped without REDIS_URL) ────────────────────────

async def test_real_redis_state_roundtrip(monkeypatch: pytest.MonkeyPatch, oauth_config: None) -> None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL is required for the wire compatibility test")
    monkeypatch.setattr(govgr, "_STATE_KEY_PREFIX", f"test:govgr-state:{uuid4().hex}:")
    worker_a = aioredis.from_url(redis_url, decode_responses=True)
    worker_b = aioredis.from_url(redis_url, decode_responses=True)
    try:
        _use_worker(monkeypatch, worker_a)
        state = await govgr._issue_oauth_state("/")
        ttl = await worker_a.ttl(govgr._state_key(state))
        assert 0 < ttl <= govgr.GOVGR_STATE_TTL_SECONDS

        async def consume_on(worker: aioredis.Redis) -> bool:
            return await worker.getdel(govgr._state_key(state)) is not None

        results = await asyncio.gather(*(consume_on(w) for w in (worker_a, worker_b) * 4))
        assert results.count(True) == 1
    finally:
        await worker_a.aclose()
        await worker_b.aclose()
