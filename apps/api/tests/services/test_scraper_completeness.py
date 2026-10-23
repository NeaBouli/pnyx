"""Run the scheduled function with real SQL against an in-memory SQLite table."""
import ast
import logging
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import respx
from sqlalchemy.dialects import sqlite

from models import ParliamentBill
from services import parliament_fetcher, scraper_state


def load_job(monkeypatch, bills):
    connection = sqlite3.connect(":memory:")
    columns = ", ".join(f'"{column.name}" TEXT' for column in ParliamentBill.__table__.columns)
    connection.execute(f"CREATE TABLE parliament_bills ({columns})")
    for bill in bills:
        connection.execute(
            "INSERT INTO parliament_bills (id, source, status, parliament_url, summary_long_el) VALUES (?, ?, ?, ?, ?)",
            (bill.id, bill.source, bill.status, bill.parliament_url, bill.summary_long_el),
        )

    class DB:
        commit = AsyncMock()

        async def execute(self, statement):
            sql = str(statement.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
            ids = {row[0] for row in connection.execute(sql).fetchall()}
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [b for b in bills if b.id in ids]))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            connection.close()

    db = DB()
    monkeypatch.setitem(sys.modules, "database", SimpleNamespace(AsyncSessionLocal=lambda: db))
    for name in ("record_run", "record_success", "record_failure"):
        monkeypatch.setattr(scraper_state, name, AsyncMock())
    path = Path(__file__).resolve().parents[2] / "main.py"
    node = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.AsyncFunctionDef) and n.name == "scheduled_completeness_check")
    namespace = {"logger": logging.getLogger("test.completeness")}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["scheduled_completeness_check"], db


def bill(bid, source, status="OPEN_END", text=None):
    return SimpleNamespace(
        id=bid, source=source, status=status, summary_long_el=text,
        parliament_url=f"https://example.org/{bid}", party_votes_parliament=None,
    )


@pytest.mark.parametrize("status", ["OPEN_END", "PARLIAMENT_VOTED"])
async def test_completeness_and_party_vote_checks_only_include_parliament(monkeypatch, caplog, status):
    caplog.set_level(logging.INFO)
    parliament = bill("parliament-private-id", "PARLIAMENT", status)
    diavgeia = bill("diavgeia-private-id", "DIAVGEIA", status)
    other = bill("other-private-id", "COMMUNITY", status)
    announced = bill("announced-private-id", "PARLIAMENT", "ANNOUNCED")
    job, db = load_job(monkeypatch, [parliament, diavgeia, other, announced])
    fetch = AsyncMock(return_value=("Κείμενο απόφασης με επαρκές ουσιαστικό περιεχόμενο. " * 12, "fetched"))
    monkeypatch.setattr(parliament_fetcher, "_fetch_bill_text_result", fetch)

    await job()

    fetch.assert_awaited_once_with(parliament.id, parliament.parliament_url, source="PARLIAMENT")
    assert parliament.summary_long_el is not None
    assert diavgeia.summary_long_el is None and other.summary_long_el is None
    assert announced.summary_long_el is None
    assert caplog.text.count("Parliament party votes missing") == 1
    assert "fetched=1 skipped=0 failed=0" in caplog.text
    assert "private-id" not in caplog.text
    db.commit.assert_awaited_once()
    scraper_state.record_success.assert_awaited_once_with("completeness_check", outcome="clean", reason="none", count=0)


async def test_diavgeia_only_run_is_empty_and_logs_zero_counts(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    job, db = load_job(monkeypatch, [bill("private-id", "DIAVGEIA")])
    fetch = AsyncMock()
    monkeypatch.setattr(parliament_fetcher, "_fetch_bill_text_result", fetch)
    await job()
    fetch.assert_not_awaited()
    db.commit.assert_not_awaited()
    assert "party votes missing" not in caplog.text
    assert "fetched=0 skipped=0 failed=0" in caplog.text


@pytest.mark.parametrize("text", [None, "", "short text"])
async def test_empty_or_rejected_text_is_degraded(monkeypatch, caplog, text):
    caplog.set_level(logging.INFO)
    job, _ = load_job(monkeypatch, [bill("private-id", "PARLIAMENT")])
    monkeypatch.setattr(parliament_fetcher, "_fetch_bill_text_result", AsyncMock(return_value=(text, "fetched")))
    await job()
    scraper_state.record_success.assert_awaited_once_with(
        "completeness_check", outcome="degraded", reason="scrape_errors", count=1,
    )
    assert "fetched=0 skipped=0 failed=1" in caplog.text


async def test_completeness_exception_logs_only_error_type(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    job, _ = load_job(monkeypatch, [bill("private-id", "PARLIAMENT")])
    monkeypatch.setattr(parliament_fetcher, "_fetch_bill_text_result", AsyncMock(side_effect=RuntimeError("private-person https://private-url/?secret=value")))
    await job()
    assert "fetched=0 skipped=0 failed=1" in caplog.text
    assert "private-" not in caplog.text and "secret=value" not in caplog.text


@pytest.mark.parametrize("outcome", ["skipped", "failed"])
async def test_completeness_preserves_fetch_outcome(monkeypatch, caplog, outcome):
    caplog.set_level(logging.INFO)
    candidate = bill("private-id", "PARLIAMENT")
    job, db = load_job(monkeypatch, [candidate])
    monkeypatch.setattr(parliament_fetcher, "_fetch_bill_text_result", AsyncMock(return_value=("", outcome)))
    await job()
    assert candidate.summary_long_el is None
    db.commit.assert_awaited_once()
    skipped = outcome == "skipped"
    assert f"fetched=0 skipped={int(skipped)} failed={int(not skipped)}" in caplog.text
    scraper_state.record_success.assert_awaited_once_with(
        "completeness_check", outcome="clean" if skipped else "degraded",
        reason="none" if skipped else "scrape_errors", count=0 if skipped else 1,
    )


@pytest.mark.parametrize("deferred", ["cooldown", "redis_down", "lease_busy"])
@respx.mock
async def test_completeness_deferral_keeps_scheduler_running(monkeypatch, caplog, scraper_clock, scraper_redis, deferred):
    caplog.set_level(logging.INFO)
    candidate = bill("private-id", "PARLIAMENT")
    job, _ = load_job(monkeypatch, [candidate])
    if deferred == "cooldown":
        await scraper_clock.limiter.record(candidate.parliament_url, 403, {})
    elif deferred == "redis_down":
        scraper_redis.down = True
    else:
        await scraper_clock.limiter.reserve(candidate.parliament_url)
    await job()
    assert candidate.summary_long_el is None
    assert "[COMPLETENESS] fetched=0 skipped=1 failed=0" in caplog.text
    scraper_state.record_success.assert_awaited_once_with(
        "completeness_check", outcome="clean", reason="none", count=0,
    )
    assert len(respx.calls) == 0
