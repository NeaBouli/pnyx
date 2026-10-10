"""Signed POLIS and bill-flag writes share the explicit 120/min HMAC-IP limiter.

Exercises the real included route wrappers on main.app with the original
limiter singleton enabled against an isolated memory store. No lifespan,
provider or network work runs; the database is a local fail-closed stub.
"""

import time
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

import main
from database import get_db
from rate_limit import limiter
from routers import parliament, polis_tickets


HEX64 = "a" * 64
HEX128 = "0" * 128
IP_ONE = {"X-Forwarded-For": "203.0.113.91"}
IP_TWO = {"X-Forwarded-For": "203.0.113.92"}


class EmptyResult:
    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list[Any]:
        return []

    def scalar_one_or_none(self) -> None:
        return None

    def scalar(self) -> int:
        return 0

    def scalars(self) -> "EmptyResult":
        return self

    def all(self) -> list[Any]:
        return []


class LocalSession:
    """Every lookup misses, so each write stops at its unchanged identity guard."""

    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, statement: Any, params: Any = None) -> EmptyResult:
        self.calls += 1
        sql = str(statement)
        if any(table in sql for table in (
            "identity_records", "polis_identity_keys", "polis_tickets", "parliament_bills",
        )):
            return EmptyResult()
        raise AssertionError(f"Unexpected database access: {sql}")

    async def get(self, model: Any, key: Any) -> None:
        self.calls += 1
        return None


def _register_body() -> dict[str, Any]:
    return {"nullifier_hash": HEX64, "pk_polis": HEX64,
            "identity_signature": HEX128, "timestamp_ms": int(time.time() * 1000)}


def _ticket_body() -> dict[str, Any]:
    return {"title": "Local fixture", "content": "Local fixture content", "category": "bug",
            "pk_polis": HEX64, "ticket_nullifier": HEX64, "signature": HEX128,
            "timestamp_ms": int(time.time() * 1000), "nullifier_hash": HEX64}


def _vote_body() -> dict[str, Any]:
    return {"vote": "up", "pk_polis": HEX64, "vote_nullifier": HEX64, "signature": HEX128,
            "timestamp_ms": int(time.time() * 1000), "nullifier_hash": HEX64}


def _flag_body() -> dict[str, Any]:
    return {"nullifier_hash": HEX64, "timestamp_ms": int(time.time() * 1000),
            "signature_hex": HEX128}


# (path factory, body factory, expected guard status). Path IDs rotate per call
# to prove dynamic ticket/bill IDs cannot mint fresh buckets.
ROUTES = {
    "register": (lambda i: "/api/v1/polis/register-key", _register_body, 403),
    "ticket": (lambda i: "/api/v1/polis/tickets", _ticket_body, 403),
    "vote": (lambda i: f"/api/v1/polis/tickets/t{i}/votes", _vote_body, 403),
    "flag": (lambda i: f"/api/v1/bills/GR-fixture-{i}/flag", _flag_body, 401),
}


@pytest.fixture
def http(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[TestClient, LocalSession], None, None]:
    # Decorators close over this singleton; replacing app.state.limiter would
    # leave the wrappers disabled and give a false-positive test.
    assert main.app.state.limiter is main.limiter is limiter
    assert polis_tickets.limiter is limiter
    assert parliament.limiter is limiter
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


@pytest.mark.parametrize("name", list(ROUTES))
def test_signed_write_limit_keeps_guard_and_separates_ips(
    http: tuple[TestClient, LocalSession], name: str,
) -> None:
    client, session = http
    path, body, guard = ROUTES[name]
    for index in range(120):
        assert client.post(path(index), headers=IP_ONE, json=body()).status_code == guard
    calls = session.calls
    assert calls >= 120
    assert client.post(path(999), headers=IP_ONE, json=body()).status_code == 429
    assert session.calls == calls  # Rejected before any further database work.
    assert client.post(path(999), headers=IP_TWO, json=body()).status_code == guard


def test_signed_write_buckets_are_per_route(http: tuple[TestClient, LocalSession]) -> None:
    client, _ = http
    path, body, _guard = ROUTES["ticket"]
    for index in range(120):
        client.post(path(index), headers=IP_ONE, json=body())
    assert client.post(path(0), headers=IP_ONE, json=body()).status_code == 429
    for other in ("register", "vote", "flag"):
        other_path, other_body, other_guard = ROUTES[other]
        assert client.post(other_path(0), headers=IP_ONE, json=other_body()).status_code == other_guard


@pytest.mark.parametrize("name", list(ROUTES))
def test_untrusted_forwarded_headers_cannot_reset_signed_write_bucket(
    http: tuple[TestClient, LocalSession], monkeypatch: pytest.MonkeyPatch, name: str,
) -> None:
    client, _ = http
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "192.0.2.0/24")
    path, body, guard = ROUTES[name]
    for index in range(120):
        headers = {"X-Forwarded-For": f"203.0.113.{index + 1}"}
        assert client.post(path(index), headers=headers, json=body()).status_code == guard
    assert client.post(path(0), headers=IP_TWO, json=body()).status_code == 429


def test_public_reads_stay_unlimited_after_signed_writes_exhausted(
    http: tuple[TestClient, LocalSession],
) -> None:
    client, _ = http
    for name, (path, body, _guard) in ROUTES.items():
        for index in range(121):
            client.post(path(index), headers=IP_ONE, json=body())
    for _ in range(61):
        assert client.get("/api/v1/app/version", headers=IP_ONE).status_code == 200
        assert client.get("/api/v1/bills", headers=IP_ONE).status_code == 200
        assert client.get("/api/v1/polis/tickets", headers=IP_ONE).status_code == 200
        assert client.get("/api/v1/vote/GR-missing/results", headers=IP_ONE).status_code == 404
