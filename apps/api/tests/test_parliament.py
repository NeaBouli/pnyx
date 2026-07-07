"""Tests für MOD-03 Parliament — Lifecycle Validator"""
import pytest
from models import BillStatus
from fastapi import HTTPException
from routers.parliament import VALID_TRANSITIONS, _parse_status_any, _region_filter_conditions


def _compiled_conditions(conditions):
    return " ".join(
        str(condition.compile(compile_kwargs={"literal_binds": True}))
        for condition in conditions
    )


class TestLifecycle:
    def test_announced_to_active_allowed(self):
        assert BillStatus.ACTIVE in VALID_TRANSITIONS[BillStatus.ANNOUNCED]

    def test_active_to_window_allowed(self):
        assert BillStatus.WINDOW_24H in VALID_TRANSITIONS[BillStatus.ACTIVE]

    def test_window_to_parliament_voted_allowed(self):
        assert BillStatus.PARLIAMENT_VOTED in VALID_TRANSITIONS[BillStatus.WINDOW_24H]

    def test_parliament_voted_to_open_end_allowed(self):
        assert BillStatus.OPEN_END in VALID_TRANSITIONS[BillStatus.PARLIAMENT_VOTED]

    def test_open_end_has_no_transitions(self):
        assert VALID_TRANSITIONS[BillStatus.OPEN_END] == []

    def test_no_backwards_transition(self):
        # ACTIVE → ANNOUNCED nicht erlaubt
        assert BillStatus.ANNOUNCED not in VALID_TRANSITIONS[BillStatus.ACTIVE]

    def test_no_skip_transition(self):
        # ANNOUNCED → PARLIAMENT_VOTED nicht erlaubt (Sprung)
        assert BillStatus.PARLIAMENT_VOTED not in VALID_TRANSITIONS[BillStatus.ANNOUNCED]

    def test_all_states_have_entry(self):
        for status in BillStatus:
            assert status in VALID_TRANSITIONS, f"{status} fehlt in VALID_TRANSITIONS"


class TestStatusAny:
    def test_parse_status_any_keeps_active_and_window_24h(self):
        assert _parse_status_any("ACTIVE,WINDOW_24H") == [
            BillStatus.ACTIVE,
            BillStatus.WINDOW_24H,
        ]

    def test_parse_status_any_ignores_empty_and_duplicate_values(self):
        assert _parse_status_any("ACTIVE,, active ") == [BillStatus.ACTIVE]

    def test_parse_status_any_rejects_invalid_values(self):
        with pytest.raises(HTTPException) as exc:
            _parse_status_any("ACTIVE,NOT_A_STATUS")

        assert exc.value.status_code == 400


class TestRegionFilterConditions:
    def test_region_filter_includes_institutional_by_default_when_requested(self):
        conditions = _region_filter_conditions(
            periferia_id=1,
            dimos_id=2,
            include_institutional=True,
        )
        sql = _compiled_conditions(conditions)

        assert len(conditions) == 4
        assert "INSTITUTIONAL" in sql
        assert "REGIONAL" in sql
        assert "MUNICIPAL" in sql

    def test_region_filter_can_exclude_institutional_for_mixed_all_feed(self):
        conditions = _region_filter_conditions(
            periferia_id=1,
            dimos_id=2,
            include_institutional=False,
        )
        sql = _compiled_conditions(conditions)

        assert len(conditions) == 3
        assert "INSTITUTIONAL" not in sql
        assert "REGIONAL" in sql
        assert "MUNICIPAL" in sql


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Braucht laufende PostgreSQL — läuft in Docker CI")
async def test_bills_endpoint_health():
    """Bills Endpoint ist erreichbar (benötigt DB)"""
    from httpx import AsyncClient, ASGITransport
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/bills")
    assert r.status_code != 404

@pytest.mark.asyncio
@pytest.mark.xfail(reason="Braucht laufende PostgreSQL — läuft in Docker CI")
async def test_bill_not_found():
    """Unbekannte Bill-ID gibt 404 oder 500 (benötigt DB)"""
    from httpx import AsyncClient, ASGITransport
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/bills/GR-NONEXISTENT-9999")
    assert r.status_code in [404, 500]
