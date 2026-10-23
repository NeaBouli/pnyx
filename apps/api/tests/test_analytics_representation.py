"""Representation contract, one-query aggregation and bounded public-result cache."""
import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from database import get_db
from routers import analytics

CHOICES = ("YES", "NO", "ABSTAIN", "UNKNOWN")


class Cache:
    def __init__(self) -> None:
        self.now = 0
        self.values: dict[str, tuple[float, str]] = {}
        self.writes: list[tuple[str, int, str]] = []
        self.read_error = False
        self.write_error = False
        self.closed = 0

    async def __aenter__(self) -> "Cache":
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.closed += 1

    async def get(self, key: str) -> str | None:
        if self.read_error:
            raise RedisConnectionError("cache unavailable")
        expiry, value = self.values.get(key, (0, ""))
        return value if expiry > self.now else None

    async def setex(self, key: str, ttl: int, value: str) -> None:
        if self.write_error:
            raise RedisConnectionError("cache unavailable")
        self.writes.append((key, ttl, value))
        self.values[key] = (self.now + ttl, value)


@pytest.fixture
def cache(monkeypatch: pytest.MonkeyPatch) -> Cache:
    store = Cache()
    monkeypatch.setattr(analytics.aioredis, "from_url", lambda *_, **__: store)
    monkeypatch.delenv("PUBLIC_RESULTS_MIN_COUNT", raising=False)
    return store


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            for sql in (
                "CREATE TABLE parliament_bills (id TEXT PRIMARY KEY, title_el TEXT, source TEXT, status TEXT, admin_hidden BOOLEAN, summary_short_el TEXT, summary_long_el TEXT, party_votes_parliament TEXT)",
                "CREATE TABLE citizen_votes (bill_id TEXT, vote TEXT)",
                "CREATE INDEX idx_votes_bill ON citizen_votes (bill_id)",
                "CREATE TABLE zk_vote_receipts (vote_scope_id TEXT, vote_commitment TEXT)",
                "CREATE INDEX idx_zk_receipts_scope ON zk_vote_receipts (vote_scope_id)",
            ):
                await conn.execute(text(sql))
        async with AsyncSession(engine) as session:
            yield session
    finally:
        await engine.dispose()


async def bill(
    db: AsyncSession, bill_id: str, *, source: str = "PARLIAMENT",
    status: str = "OPEN_END", hidden: bool = False, title: str = "Δοκιμή",
    party: dict[str, str] | None = None, summary: str = "",
) -> None:
    await db.execute(text("""
        INSERT INTO parliament_bills
        (id, title_el, source, status, admin_hidden, summary_long_el, party_votes_parliament)
        VALUES (:id, :title, :source, :status, :hidden, :summary, :party)
    """), dict(id=bill_id, title=title, source=source, status=status,
               hidden=hidden, summary=summary, party=json.dumps(party) if party is not None else None))


async def votes(
    db: AsyncSession, bill_id: str, tier1: tuple[int, ...] = (0,)*4,
    zk: tuple[int, ...] = (0,)*4,
) -> None:
    for sql, counts in (
        ("INSERT INTO citizen_votes VALUES (:id, :vote)", tier1),
        ("INSERT INTO zk_vote_receipts VALUES ('bill:' || :id, :vote)", zk),
    ):
        rows = [dict(id=bill_id, vote=c) for c, n in zip(CHOICES, counts) for _ in range(n)]
        if rows:
            await db.execute(text(sql), rows)


@pytest.fixture
async def client(db: AsyncSession, cache: Cache) -> AsyncIterator[AsyncClient]:
    app = FastAPI()
    app.include_router(analytics.router)

    async def dependency() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = dependency
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def test_endpoint_contract_combines_sources_and_preserves_rounding(
    db: AsyncSession, client: AsyncClient, cache: Cache,
) -> None:
    await bill(db, "A", party={"A": "YES", "B": "NO"}, title="T" * 80)
    await votes(db, "A", (4, 2, 0, 0), (4, 0, 0, 0))
    await bill(db, "B", party={"A": "ΟΧΙ"}, status="PARLIAMENT_VOTED")
    await votes(db, "B", zk=(1, 2, 3, 7))
    # Publishable votes without party results still contribute to the total.
    await bill(db, "C")
    await votes(db, "C", (1, 0, 0, 0))
    response = await client.get("/api/v1/analytics/representation")
    assert response.status_code == 200
    result = response.json()
    assert result == {
        "cumulative_representation": 86.1, "cumulative_divergence": 13.9,
        "bills_analyzed": 2, "total_citizen_votes": 24,
        "label_el": "Υψηλή Αντιπροσωπευτικότητα", "label_en": "High Representation", "color": "#22c55e",
        "last_bill": {"bill_id": "B", "title_el": "Δοκιμή", "citizen_votes": 13,
                      "divergence": 7.7, "representation": 92.3},
        "bills": [
            {"bill_id": "A", "title_el": "T" * 60, "citizen_votes": 10,
             "divergence": 20.0, "representation": 80.0},
            {"bill_id": "B", "title_el": "Δοκιμή", "citizen_votes": 13,
             "divergence": 7.7, "representation": 92.3},
        ],
    }
    assert json.loads(cache.writes[0][2]) == result
    assert not any(term in cache.writes[0][2] for term in ("nullifier", "phone", "commitment", "identity"))


async def test_empty_contract_is_cached(db: AsyncSession, client: AsyncClient, cache: Cache) -> None:
    await bill(db, "LOW", party={"A": "YES"})
    await votes(db, "LOW", (9, 0, 0, 0))
    result = (await client.get("/api/v1/analytics/representation")).json()
    assert result == dict(cumulative_representation=None, cumulative_divergence=None,
                         bills_analyzed=0, total_citizen_votes=0,
                         message_el="Δεν υπάρχουν αρκετά δεδομένα ακόμη.",
                         message_en="Not enough data yet.", last_bill=None, bills=[])
    assert (await client.get("/api/v1/analytics/representation")).json() == result
    assert len(cache.writes) == 1


async def test_visibility_sources_and_invalid_receipts(db: AsyncSession, client: AsyncClient) -> None:
    for bill_id, options in (
        ("VISIBLE", {}), ("HIDDEN", {"hidden": True}),
        ("ACTIVE", {"status": "ACTIVE"}), ("ANNOUNCED", {"status": "ANNOUNCED"}),
        ("SENSITIVE_TITLE", {"source": "DIAVGEIA", "title": "AMKA"}),
        ("SENSITIVE_SUMMARY", {"source": "DIAVGEIA", "summary": "eopyy"}),
        ("DIAVGEIA", {"source": "DIAVGEIA"}),
        ("PARLIAMENT", {"title": "AMKA"}),
    ):
        await bill(db, bill_id, party={"A": "YES"}, **options)
        await votes(db, bill_id, (8, 2, 0, 0), (10, 0, 0, 0))
    await db.execute(text("INSERT INTO zk_vote_receipts VALUES ('bill:VISIBLE', 'invalid'), ('poll:VISIBLE', 'YES')"))
    result = (await client.get("/api/v1/analytics/representation")).json()
    assert {b["bill_id"]: b["citizen_votes"] for b in result["bills"]} == {
        "VISIBLE": 20, "DIAVGEIA": 10, "PARLIAMENT": 20,
    }
    assert result["total_citizen_votes"] == 50


async def test_source_suppression_and_policy_invalidation(
    db: AsyncSession, client: AsyncClient, cache: Cache, monkeypatch: pytest.MonkeyPatch,
) -> None:
    await bill(db, "SAFE", party={"A": "YES"})
    await votes(db, "SAFE", (10,)*4)
    await bill(db, "SMALL_SOURCE", party={"A": "YES"})
    await votes(db, "SMALL_SOURCE", (1, 0, 0, 0), (10,)*4)
    before = (await client.get("/api/v1/analytics/representation")).json()
    assert before["total_citizen_votes"] == 81
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    after = (await client.get("/api/v1/analytics/representation")).json()
    assert after["total_citizen_votes"] == 40
    assert [b["bill_id"] for b in after["bills"]] == ["SAFE"]
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "11")
    assert (await client.get("/api/v1/analytics/representation")).json()["bills"] == []
    assert len({key for key, _, _ in cache.writes}) == 3


async def test_hit_skips_db_and_expiry_refreshes_votes_and_visibility(
    db: AsyncSession, client: AsyncClient, cache: Cache, monkeypatch: pytest.MonkeyPatch,
) -> None:
    await bill(db, "A", party={"A": "YES"})
    await votes(db, "A", (10, 0, 0, 0))
    before = (await client.get("/api/v1/analytics/representation")).json()
    compute = AsyncMock(wraps=analytics.compute_cumulative_representation)
    monkeypatch.setattr(analytics, "compute_cumulative_representation", compute)
    await votes(db, "A", (0, 10, 0, 0))
    cache.now = 29
    assert (await client.get("/api/v1/analytics/representation")).json() == before
    compute.assert_not_awaited()
    assert len(cache.writes) == 1  # Hits must not extend expiry.
    cache.now = 30
    after = (await client.get("/api/v1/analytics/representation")).json()
    assert after["total_citizen_votes"] == 20
    assert after["cumulative_representation"] == 50
    compute.assert_awaited_once()
    await db.execute(text("UPDATE parliament_bills SET admin_hidden = TRUE"))
    cache.now = 60
    assert (await client.get("/api/v1/analytics/representation")).json()["bills"] == []
    assert all(ttl == 30 for _, ttl, _ in cache.writes)
    assert cache.closed == 4


@pytest.mark.parametrize("failure", ["read", "write", "json", "shape"])
async def test_cache_failure_still_returns_query_result(
    db: AsyncSession, client: AsyncClient, cache: Cache, failure: str,
) -> None:
    cache.read_error = failure == "read"
    cache.write_error = failure == "write"
    if failure in ("json", "shape"):
        cache.values["analytics:representation:v1:k0"] = (30, "broken" if failure == "json" else "[]")
    response = await client.get("/api/v1/analytics/representation")
    assert response.status_code == 200
    assert response.json()["bills"] == []
    assert cache.closed == 1


async def test_database_errors_propagate_and_are_not_cached(client: AsyncClient, cache: Cache, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analytics, "compute_cumulative_representation", AsyncMock(side_effect=RuntimeError("database unavailable")))
    with pytest.raises(RuntimeError, match="database unavailable"):
        await client.get("/api/v1/analytics/representation")
    assert cache.writes == []
    assert cache.closed == 1


async def test_query_count_is_constant_for_many_bills(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PUBLIC_RESULTS_MIN_COUNT", raising=False)
    for index in range(100):
        await bill(db, str(index), party={"A": "YES"})
        await votes(db, str(index), (6, 4, 0, 0), (2, 3, 0, 0))
    statements: list[str] = []
    def record(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        statements.append(statement)
    event.listen(db.bind.sync_engine, "before_cursor_execute", record)
    try:
        result = await analytics.compute_cumulative_representation(db)
    finally:
        event.remove(db.bind.sync_engine, "before_cursor_execute", record)
    assert len(statements) == 1
    assert result["bills_analyzed"] == 100
    assert result["total_citizen_votes"] == 1500
