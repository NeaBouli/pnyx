from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from database import get_db
from models import ParliamentBill, BillStatus
from routers import parliament
from services import source_freshness as freshness

NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize("age,stale", [(47, False), (48, False), (49, True)])
def test_freshness_uses_last_success_and_48_hour_threshold(age, stale):
    success = (NOW - timedelta(hours=age)).isoformat()
    assert freshness.source_status(success, now=NOW) == {
        "last_success": success, "source_blocked": False, "stale": stale,
    }


@pytest.mark.parametrize("value", [None, "bad", "2026-10-18T12:00:00", b"private"])
def test_unknown_update_is_stale(value):
    assert freshness.source_status(value, now=NOW)["stale"] is True


def test_new_failure_does_not_advance_success_and_later_success_recovers():
    success = (NOW - timedelta(minutes=2)).isoformat()
    blocked = (NOW - timedelta(minutes=1)).isoformat()
    state = freshness.source_status(success, blocked, now=NOW)
    assert state == {
        "last_success": success, "source_blocked": True, "stale": True,
    }
    assert freshness.source_status(NOW.isoformat(), blocked, now=NOW) == {
        "last_success": NOW.isoformat(), "source_blocked": False, "stale": False,
    }


@pytest.mark.asyncio
async def test_bill_list_detail_and_public_source_freshness_serialize_real_state(monkeypatch):
    success = datetime.now(timezone.utc).isoformat()
    store = {"scraper:parliament:last_success": success,
             "scraper:diavgeia_municipal:last_success": "2026-01-01T00:00:00+00:00"}
    redis = SimpleNamespace(mget=AsyncMock(side_effect=lambda *keys: [store.get(k) for k in keys]),
                            set=AsyncMock(side_effect=lambda k, v: store.update({k: v})), aclose=AsyncMock())
    monkeypatch.setattr(freshness.scraper_state, "_redis", AsyncMock(return_value=redis))
    monkeypatch.setattr(freshness, "_blocked_at", None)
    await freshness.record_source_blocked()
    assert "scraper:parliament:source_blocked" in store
    bill = ParliamentBill(id="GR-actual", title_el="Δημόσιο νομοσχέδιο", status=BillStatus.ACTIVE,
                          source="PARLIAMENT", ai_summary_reviewed=False,
                          created_at=datetime(2026, 1, 1, 23, 30))
    async def execute(statement):
        values = [bill.id] if list(statement.selected_columns.keys()) == ["id"] else [bill]
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: values), scalar_one_or_none=lambda: bill,
            all=lambda: [(bill, 5)])

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    app = FastAPI()
    app.include_router(parliament.router)
    app.dependency_overrides[get_db] = lambda: db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        sources = (await client.get("/api/v1/bills/sources/freshness")).json()
        assert sources["PARLIAMENT"]["last_success"] == success
        assert sources["PARLIAMENT"]["source_blocked"] is True
        assert sources["PARLIAMENT"]["stale"] is True
        assert sources["DIAVGEIA"]["stale"] is True
        for path in ("/api/v1/bills", "/api/v1/bills/trending", "/api/v1/bills/GR-actual"):
            response = await client.get(path)
            assert response.status_code == 200, response.text
            payload = response.json()
            if isinstance(payload, list):
                payload = payload[0]
            assert payload["source_last_success"] == success
            assert payload["source_blocked"] is True
            assert payload["source_stale"] is True
            assert payload["created_at"] == "2026-01-01T23:30:00"


@pytest.mark.asyncio
async def test_missing_redis_reports_unknown_stale_instead_of_fabricating_a_date(monkeypatch):
    monkeypatch.setattr(freshness.scraper_state, "_redis", AsyncMock(side_effect=ConnectionError))
    monkeypatch.setattr(freshness, "_blocked_at", None)
    states = await freshness.get_source_freshness()
    assert all(state["last_success"] is None and state["stale"] for state in states.values())
