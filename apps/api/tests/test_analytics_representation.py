"""Representation contract, one-query aggregation and bounded public-result cache."""
import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from database import get_db
from models import BillStatus
from routers import admin, analytics, notifications, parliament
from services import bill_lifecycle

CHOICES = ("YES", "NO", "ABSTAIN", "UNKNOWN")


class Cache:
    def __init__(self) -> None:
        self.now = 0.0
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

    async def scan_iter(self, *, match: str) -> AsyncIterator[str]:
        if self.read_error:
            raise RedisConnectionError("cache unavailable")
        for key in list(self.values):
            if fnmatchcase(key, match):
                yield key

    async def delete(self, key: str) -> None:
        if self.write_error:
            raise RedisConnectionError("cache unavailable")
        self.values.pop(key, None)


@pytest.fixture
def cache(monkeypatch: pytest.MonkeyPatch) -> Cache:
    store = Cache()
    monkeypatch.setattr(analytics.aioredis, "from_url", lambda *_, **__: store)
    monkeypatch.setattr(analytics, "monotonic", lambda: store.now)
    monkeypatch.delenv("PUBLIC_RESULTS_MIN_COUNT", raising=False)
    return store


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            for sql in (
                "CREATE TABLE parliament_bills (id TEXT PRIMARY KEY, title_el TEXT, parliament_url TEXT, created_at TEXT, source TEXT, status TEXT, admin_hidden BOOLEAN, summary_short_el TEXT, summary_long_el TEXT, party_votes_parliament TEXT)",
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
    assert json.loads(cache.writes[0][2]) == result
    for projected in result["bills"] + [result["last_bill"]]:
        assert projected.pop("source") == "PARLIAMENT"
        assert projected.pop("parliament_url") is None
        assert projected.pop("official_source_url") is None
        assert projected.pop("created_at") is None
    assert result == {
        "cumulative_representation": 86.1, "cumulative_divergence": 13.9,
        "bills_analyzed": 2, "total_citizen_votes": 24,
        "label_el": "Υψηλή Αντιπροσωπευτικότητα", "label_en": "High Representation", "color": "#22c55e",
        "last_bill": {"bill_id": "B", "title_el": "Δοκιμή", "citizen_votes": 13,
                      "divergence": 7.7, "representation": 92.3},
        "bills": [
            {"bill_id": "A", "title_el": "T" * 80, "citizen_votes": 10,
             "divergence": 20.0, "representation": 80.0},
            {"bill_id": "B", "title_el": "Δοκιμή", "citizen_votes": 13,
             "divergence": 7.7, "representation": 92.3},
        ],
    }
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


@pytest.mark.parametrize("delay", [5, 5.25, 29.5, 30, 35])
@pytest.mark.parametrize("empty", [False, True])
async def test_delayed_fill_expires_from_snapshot_start(
    db: AsyncSession, client: AsyncClient, cache: Cache,
    monkeypatch: pytest.MonkeyPatch, delay: float, empty: bool,
) -> None:
    if not empty:
        await bill(db, "A", party={"A": "YES"})
        await votes(db, "A", (10, 0, 0, 0))
    compute = analytics.compute_cumulative_representation

    async def delayed_compute(db: AsyncSession) -> dict:
        snapshot = await compute(db)  # Snapshot at t=0; hidden at t=1.
        cache.now = 1
        await db.execute(text("UPDATE parliament_bills SET admin_hidden = TRUE"))
        cache.now = delay
        return snapshot

    monkeypatch.setattr(analytics, "compute_cumulative_representation", delayed_compute)
    response = await client.get("/api/v1/analytics/representation")
    assert response.status_code == 200
    assert response.json()["bills_analyzed"] == (0 if empty else 1)
    remaining = int(30 - delay)
    if remaining > 0:
        assert len(cache.writes) == 1
        key, ttl, _ = cache.writes[0]
        assert ttl == remaining
        assert cache.values[key][0] <= 30
    else:
        assert cache.writes == []

    # A completed snapshot must never stay cached until t=delay+30.
    monkeypatch.setattr(analytics, "compute_cumulative_representation", compute)
    cache.now = max(30, delay)
    assert (await client.get("/api/v1/analytics/representation")).json()["bills"] == []
    assert len(cache.writes) == (2 if remaining > 0 else 1)


@pytest.mark.parametrize("field", ["results_visibility", "title_el", "summary_short_el", "summary_long_el"])
async def test_admin_visibility_edit_invalidates_all_policies_after_commit(
    db: AsyncSession, client: AsyncClient, cache: Cache,
    monkeypatch: pytest.MonkeyPatch, field: str,
) -> None:
    await bill(db, "A", source="DIAVGEIA", party={"A": "YES"})
    await votes(db, "A", (10,)*4)
    for policy in ("0", "10"):
        monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", policy)
        assert (await client.get("/api/v1/analytics/representation")).json()["bills_analyzed"] == 1
    keys = set(cache.values)
    cache.values["unrelated"] = (30, "keep")
    value = "HIDDEN" if field == "results_visibility" else "AMKA"
    writer = AsyncMock(spec=AsyncSession)
    writer.get.return_value = SimpleNamespace(generated_content_provenance=None)

    async def commit() -> None:
        assert keys <= cache.values.keys()  # Invalidation must follow commit.
        if field != "results_visibility":
            await db.execute(text(f"UPDATE parliament_bills SET {field} = :value"), {"value": value})
        await db.commit()

    writer.commit.side_effect = commit
    result = await admin.admin_update_bill(
        "A", admin.BillUpdateRequest(**{field: value}), _key=True, db=writer,
    )
    assert result["success"] is True
    writer.commit.assert_awaited_once()
    assert cache.values == {"unrelated": (30, "keep")}
    if field != "results_visibility":
        assert (await client.get("/api/v1/analytics/representation")).json()["bills"] == []


@pytest.mark.parametrize("failure", ["scan", "delete", "timeout"])
async def test_invalidation_failure_does_not_fail_committed_visibility_edit(
    cache: Cache, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    cache.values["analytics:representation:v1:k0"] = (30, "stale")
    cache.read_error = failure == "scan"
    cache.write_error = failure == "delete"
    if failure == "timeout":
        async def timed_out_scan(**_: Any) -> AsyncIterator[str]:
            raise TimeoutError("cache deadline")
            yield  # Make this an async iterator, like Redis scan_iter.
        monkeypatch.setattr(cache, "scan_iter", timed_out_scan)
    writer = AsyncMock(spec=AsyncSession)
    writer.get.return_value = SimpleNamespace(results_visibility="ALWAYS")
    result = await admin.admin_update_bill(
        "A", admin.BillUpdateRequest(results_visibility="HIDDEN"), _key=True, db=writer,
    )
    assert result["success"] is True
    writer.commit.assert_awaited_once()
    assert cache.closed == 1


@pytest.mark.parametrize("scheduled", [False, True])
async def test_status_transition_invalidates_representation_after_commit(
    cache: Cache, monkeypatch: pytest.MonkeyPatch, scheduled: bool,
) -> None:
    cache.values["analytics:representation:v1:k0"] = (30, "stale")
    record = SimpleNamespace(
        id="A", status=BillStatus.WINDOW_24H, arweave_tx_id=None,
        parliament_vote_date=datetime.now(timezone.utc) - timedelta(days=1),
        status_changed_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    writer = AsyncMock(spec=AsyncSession)

    async def commit() -> None:
        assert record.status == BillStatus.PARLIAMENT_VOTED
        assert cache.values  # Still present until the transition commits.

    writer.commit.side_effect = commit
    monkeypatch.setattr(bill_lifecycle, "_hook_arweave_snapshot", AsyncMock())
    monkeypatch.setattr(bill_lifecycle, "_hook_telegram_community", AsyncMock())
    monkeypatch.setattr(notifications, "publish_bill_event", AsyncMock())
    if scheduled:
        writer.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [record]))
        monkeypatch.setattr(bill_lifecycle, "_catchup_arweave", AsyncMock(return_value=0))
        result = await bill_lifecycle.run_bill_lifecycle(writer)
        assert result["transitioned"] == 1
        assert result["errors"] == 0
    else:
        writer.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: record)
        result = await parliament.transition_bill(
            "A", parliament.TransitionRequest(new_status="PARLIAMENT_VOTED"), _auth=True, db=writer,
        )
        assert result["success"] is True
    writer.commit.assert_awaited_once()
    assert cache.values == {}
    assert cache.closed == 1


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


@pytest.mark.parametrize("route", ["set-text", "fetch-text", "party-votes", "patch-party-votes"])
@pytest.mark.parametrize("cache_failure", [False, True])
async def test_admin_text_and_party_vote_routes_remove_cached_rows(
    db: AsyncSession, cache: Cache, monkeypatch: pytest.MonkeyPatch,
    route: str, cache_failure: bool,
) -> None:
    from fastapi import Request
    from services import parliament_fetcher

    await bill(db, "A", source="DIAVGEIA", party={"A": "YES"})
    await votes(db, "A", (10,)*4)
    record = SimpleNamespace(
        id="A", source="DIAVGEIA", parliament_url="https://example.test/bill.pdf",
        summary_long_el="", party_votes_parliament={"A": "YES"},
        generated_content_provenance=None,
    )
    writer = AsyncMock(spec=AsyncSession)
    writer.get.return_value = record
    writer.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: record)
    keys = set()

    async def commit() -> None:
        assert keys <= cache.values.keys()  # Cache deletion follows the DB commit.
        await db.execute(text("""UPDATE parliament_bills
            SET summary_long_el = :summary, party_votes_parliament = :party WHERE id = 'A'
        """), dict(summary=record.summary_long_el, party=json.dumps(record.party_votes_parliament)))
        await db.commit()

    writer.commit.side_effect = commit
    monkeypatch.setattr(parliament_fetcher, "_fetch_bill_text_result",
                        AsyncMock(return_value=("AMKA " + "official text " * 25, "fetched")))
    # The routes also close their summary-cache connection.
    monkeypatch.setattr(cache, "aclose", AsyncMock(), raising=False)
    if cache_failure:
        # Fail only representation deletion; summary-cache deletion still works.
        async def unavailable_scan(**_: Any) -> AsyncIterator[str]:
            raise RuntimeError("cache adapter failed")
            yield
        monkeypatch.setattr(cache, "scan_iter", unavailable_scan)

    app = FastAPI()
    app.include_router(analytics.router)
    app.include_router(admin.router)

    async def dependency(request: Request) -> AsyncIterator[AsyncSession]:
        yield writer if "/admin/" in request.url.path else db

    app.dependency_overrides[get_db] = dependency
    app.dependency_overrides[admin.verify_admin] = lambda: True
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        for policy in ("0", "10"):
            monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", policy)
            assert (await http.get("/api/v1/analytics/representation")).json()["bills_analyzed"] == 1
        keys.update(cache.values)
        cache.values["unrelated"] = (30, "keep")
        if route == "patch-party-votes":
            response = await http.patch("/api/v1/admin/bills/A", json={"party_votes_parliament": {}})
        else:
            payload = {"text": "AMKA " + "official text " * 25} if route == "set-text" else {}
            response = await http.post(f"/api/v1/admin/bills/A/{route}", json=payload)
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True
        writer.commit.assert_awaited_once()
        if cache_failure:
            assert keys <= cache.values.keys()
            # The existing anchored expiry remains the outage backstop.
            cache.now = 30
        else:
            assert cache.values == {"unrelated": (30, "keep")}
        assert (await http.get("/api/v1/analytics/representation")).json()["bills"] == []


async def test_failed_commit_never_invalidates(cache: Cache) -> None:
    from services.representation_cache import commit_and_invalidate_representation

    cache.values["analytics:representation:v1:k0"] = (30, "keep")
    writer = AsyncMock(spec=AsyncSession)
    writer.commit.side_effect = RuntimeError("database rejected write")
    with pytest.raises(RuntimeError, match="database rejected write"):
        await commit_and_invalidate_representation(writer)
    assert cache.values == {"analytics:representation:v1:k0": (30, "keep")}
    assert cache.closed == 0


async def test_invalidation_client_setup_failure_does_not_fail_write(
    cache: Cache, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services.representation_cache import commit_and_invalidate_representation

    def broken_client(*_: Any, **__: Any) -> None:
        raise ValueError("invalid Redis configuration")

    monkeypatch.setattr(analytics.aioredis, "from_url", broken_client)
    writer = AsyncMock(spec=AsyncSession)
    await commit_and_invalidate_representation(writer)
    writer.commit.assert_awaited_once()
