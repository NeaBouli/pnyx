"""Tests für MOD-03 Parliament — Lifecycle Validator"""
import pytest
from models import BillStatus
from routers.parliament import VALID_TRANSITIONS


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
