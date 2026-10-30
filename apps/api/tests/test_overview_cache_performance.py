"""The overview owner computes immediately; hits only authorize cached inputs."""
import asyncio
import logging
import threading
from time import monotonic
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event, text

from models import BillStatus
from routers import analytics
from services.request_work import WaitingWorkSlots
from tests.test_public_bill_snapshot import snapshot_db, seventeen_votes
from tests.test_released_mobile_client_flow import Rows


@pytest.mark.parametrize("k", [0, 10])
async def test_cold_overview_owner_never_waits_for_admission_or_moves_db_off_loop(monkeypatch, caplog, k):
    cache = analytics.analytics_overview.public_cache
    # Any attempt to enter this full queue costs the entire wait timeout.
    pool = WaitingWorkSlots(capacity=1, queue_capacity=0, wait_timeout=4)
    monkeypatch.setattr(cache, "workers", pool)
    monkeypatch.setattr(cache, "wait_timeout", 4)
    monkeypatch.setattr(cache.flights, "wait_timeout", 4)
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", str(k))
    monkeypatch.setenv("PUBLIC_OVERVIEW_TIMING", "1")
    owner = asyncio.current_task()
    loop, thread = asyncio.get_running_loop(), threading.get_ident()
    queries = 0

    async def execute(_statement):
        nonlocal queries
        assert asyncio.current_task() is owner
        assert asyncio.get_running_loop() is loop and threading.get_ident() == thread
        queries += 1
        if queries == 1:
            await asyncio.sleep(2)  # Slow async DB, independent of admission.
        return Rows([])

    async def scalar(_statement):
        assert asyncio.current_task() is owner
        assert asyncio.get_running_loop() is loop and threading.get_ident() == thread
        return 0

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute), scalar=AsyncMock(side_effect=scalar))
    with caplog.at_level(logging.INFO, logger="services.overview_timing"):
        started = monotonic()
        cold = await analytics.analytics_overview(db=db)
        elapsed = monotonic() - started
        assert 2 <= elapsed < cache.wait_timeout
        assert cold["bills"]["total"] == 0
        assert bool(cache.entries) is (k == 0)
        assert not pool._loops  # Foreground never even enters slot admission.
        if not k:
            before, counts_before = db.execute.await_count, db.scalar.await_count
            started = monotonic()
            assert await analytics.analytics_overview(db=db) == cold
            warm_elapsed = monotonic() - started
            assert db.execute.await_count == before + 1
            assert db.scalar.await_count == counts_before
            assert warm_elapsed < .1
    assert "phase=singleflight.owner" in caplog.text
    assert "phase=body.revalidate" in caplog.text
    assert "phase=slots.admission" not in caplog.text
    assert not cache.flights._pending()
    print(f"overview owner k={k} slow-DB=2s saturated-admission=4s: cold={elapsed:.3f}s")


async def test_overview_timings_are_off_by_default(monkeypatch, caplog):
    monkeypatch.delenv("PUBLIC_OVERVIEW_TIMING", raising=False)
    db = SimpleNamespace(execute=AsyncMock(return_value=Rows([])), scalar=AsyncMock(return_value=0))
    with caplog.at_level(logging.INFO, logger="services.overview_timing"):
        await analytics.analytics_overview(db=db)
    assert "overview_timing" not in caplog.text


async def test_overview_large_population_keeps_unvoted_counts_and_has_one_warm_check(snapshot_db):
    db = snapshot_db
    bill = await seventeen_votes(db, status=BillStatus.PARLIAMENT_VOTED)
    bill.party_votes_parliament = {"ND": "YES"}
    await db.execute(text("""
        WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i < 11431)
        INSERT INTO parliament_bills (id,title_el,source,status,governance_level,admin_hidden,summary_long_el)
        SELECT 'B'||i, 'Unvoted bill', 'PARLIAMENT', 'PARLIAMENT_VOTED', 'NATIONAL', FALSE,
               'Unrelated large bill text' FROM n
    """))
    await db.commit()
    statements = []

    def record(_conn, _cursor, sql, _params, *_):
        statements.append(sql)

    event.listen(db.bind.sync_engine, "before_cursor_execute", record)
    try:
        started = monotonic()
        cold = await analytics.analytics_overview(db=db)
        cold_elapsed = monotonic() - started
        cold_queries = len(statements)
        assert cold["bills"] == {"total": 11432, "voted": 11432, "active": 0}
        assert cold["votes"]["total"] == 17
        assert cold["divergence"]["bills_analyzed"] == 1
        # One vote-bearing bill: 3 counts + 6 vote windows + 1 bill query +
        # 2 source totals + capture + serve check, regardless of unvoted bills.
        assert cold_queries == 14
        statements.clear()
        started = monotonic()
        assert await analytics.analytics_overview(db=db) == cold
        warm_elapsed = monotonic() - started
        assert len(statements) == 1
        assert "summary_long_el" not in statements[0].split("FROM")[0]
        print(f"overview SQLite 11432 voted bills/1 contributor: cold={cold_elapsed:.3f}s/{cold_queries} SQL "
              f"warm={warm_elapsed:.3f}s/1 SQL")
    finally:
        event.remove(db.bind.sync_engine, "before_cursor_execute", record)
