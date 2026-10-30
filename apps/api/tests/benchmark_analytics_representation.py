"""Manual SQLite benchmark of the original function versus the new aggregate.

From apps/api (using the project's Python environment):
  PR_BASE=abf433abfac97fdf6dae714c5eba68e5acba1a94
  git show "${PR_BASE}:apps/api/routers/analytics.py" > /tmp/representation-before.py
  PYTHONPATH=. python tests/benchmark_analytics_representation.py /tmp/representation-before.py

Synthetic: 20,000 eligible bills, 1,000 with 400 Tier-1 + 200 ZK votes each.
PR_BASE pins PR #681's base commit, before the aggregate implementation.
SQLite and a memory cache measure local cost, not PostgreSQL/Redis network latency.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any
from unittest.mock import patch

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Keep tests/services from shadowing the application services package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import ParliamentBill
from routers import analytics


class MemoryCache:
    value: str | None = None

    async def __aenter__(self) -> MemoryCache:
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    async def get(self, _key: str) -> str | None:
        from services.public_visibility_cache import PUBLIC_VISIBILITY_GENERATION_KEY
        if _key == PUBLIC_VISIBILITY_GENERATION_KEY:
            return None
        return self.value

    async def setex(self, _key: str, _ttl: int, value: str) -> None:
        self.value = value


async def run(baseline_path: str) -> None:
    os.environ["PUBLIC_RESULTS_MIN_COUNT"] = "0"
    spec = importlib.util.spec_from_file_location("representation_before", baseline_path)
    assert spec and spec.loader
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    query_count = 0

    def record(*_: Any) -> None:
        nonlocal query_count
        query_count += 1

    try:
        async with engine.begin() as conn:
            # Raw DDL includes every column hydrated by the original function.
            columns = []
            for col in ParliamentBill.__table__.columns:
                kind = ("JSON" if isinstance(col.type, JSON) else
                        "BOOLEAN" if isinstance(col.type, Boolean) else
                        "TIMESTAMP" if isinstance(col.type, DateTime) else
                        "INTEGER" if isinstance(col.type, Integer) else
                        "REAL" if isinstance(col.type, Float) else "TEXT")
                columns.append(f'"{col.name}" {kind}' + (" PRIMARY KEY" if col.name == "id" else ""))
            for sql in (
                "CREATE TABLE parliament_bills (" + ", ".join(columns) + ")",
                "CREATE TABLE citizen_votes (id INTEGER PRIMARY KEY, bill_id TEXT, vote TEXT)",
                "CREATE INDEX idx_votes_bill ON citizen_votes (bill_id)",
                "CREATE TABLE zk_vote_receipts (id INTEGER PRIMARY KEY, vote_scope_id TEXT, vote_commitment TEXT)",
                "CREATE INDEX idx_zk_receipts_scope ON zk_vote_receipts (vote_scope_id)",
                "CREATE INDEX idx_bills_status ON parliament_bills (status)",
            ):
                await conn.execute(text(sql))
            await conn.execute(text("""
                WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i < :bills)
                INSERT INTO parliament_bills (id, title_el, summary_short_el, summary_long_el,
                    source, status, admin_hidden, party_votes_parliament)
                SELECT printf('B%06d', i), 'Public bill', 'Summary', :summary,
                       CASE WHEN i <= :voted THEN 'PARLIAMENT' ELSE 'DIAVGEIA' END,
                       'OPEN_END', FALSE, :party FROM n
            """), dict(bills=20_000, voted=1_000, summary="Public summary " * 80,
                       party=json.dumps({"A": "YES", "B": "NO"})))
            for table, id_column, prefix, count in (
                ("citizen_votes", "bill_id", "", 400),
                ("zk_vote_receipts", "vote_scope_id", "bill:", 200),
            ):
                choice_column = "vote" if table == "citizen_votes" else "vote_commitment"
                await conn.execute(text(f"""
                    WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i < :count)
                    INSERT INTO {table} ({id_column}, {choice_column})
                    SELECT :prefix || b.id,
                           CASE i % 4 WHEN 0 THEN 'YES' WHEN 1 THEN 'NO'
                                      WHEN 2 THEN 'ABSTAIN' ELSE 'UNKNOWN' END
                    FROM parliament_bills b CROSS JOIN n WHERE b.source = 'PARLIAMENT'
                """), dict(count=count, prefix=prefix))
            await conn.execute(text("ANALYZE"))
        event.listen(engine.sync_engine, "before_cursor_execute", record)
        async with AsyncSession(engine) as db:
            query_count = 0
            started = perf_counter()
            before = await baseline.compute_cumulative_representation(db)
            before_ms, before_queries = (perf_counter() - started) * 1000, query_count
            assert before_queries > 1, "Baseline must be the original function from PR #681's base commit"
            cold = []
            for _ in range(3):
                query_count = 0
                started = perf_counter()
                after = await analytics.compute_cumulative_representation(db)
                cold.append((perf_counter() - started) * 1000)
                assert query_count == 1
                assert before == after
            store = MemoryCache()
            with patch.object(analytics.aioredis, "from_url", return_value=store):
                await analytics.cumulative_representation(db)
                warm = []
                query_count = 0
                for _ in range(20):
                    started = perf_counter()
                    assert await analytics.cumulative_representation(db) == before
                    warm.append((perf_counter() - started) * 1000)
                assert query_count == 20  # One indexed current-visibility check per response.
            warm_queries = query_count
            sql, params = analytics.representation_query()
            plan = (await db.execute(text("EXPLAIN QUERY PLAN " + sql), params)).all()
            print(json.dumps(dict(
                database="SQLite in-memory; original baseline function",
                bills=20_000, voted_bills=1_000, tier1_votes=400_000, zk_votes=200_000,
                before_ms=round(before_ms, 2), before_queries=before_queries,
                after_uncached_ms=[round(v, 2) for v in cold],
                after_uncached_median_ms=round(median(cold), 2), after_queries=1,
                warm_serialization_median_ms=round(median(warm), 2), warm_queries=warm_queries,
                note="Warm cache uses a memory double; network latency is not measured.",
            ), indent=2))
            print("EXPLAIN QUERY PLAN:")
            for row in plan:
                print(tuple(row))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1]))
