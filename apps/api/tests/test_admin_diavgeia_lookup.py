import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers import diavgeia
from main import app


class _FakeResult:
    def __init__(self, decision):
        self.decision = decision

    def scalar_one_or_none(self):
        return self.decision


class _FakeDB:
    def __init__(self, decision=None):
        self.decision = decision
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _FakeResult(self.decision)


@pytest.mark.asyncio
async def test_admin_diavgeia_lookup_requires_admin_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/diavgeia/decision/ABC-123")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_diavgeia_lookup_rejects_wrong_admin_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/admin/diavgeia/decision/ABC-123",
            headers={"Authorization": "Bearer wrong-key"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_diavgeia_lookup_returns_catalogued_decision():
    published = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    db = _FakeDB(SimpleNamespace(
        ada="ABC-123",
        subject="Δοκιμαστική απόφαση",
        decision_type_label="Α.2",
        decision_type_uid="A2",
        organization_label="ΔΗΜΟΣ ΔΟΚΙΜΗΣ",
        publish_timestamp=published,
        document_url="https://diavgeia.gov.gr/doc/ABC-123",
        periferia_id=6,
        dimos_id=22,
    ))

    result = await diavgeia.admin_get_diavgeia_decision(" abc-123 ", _key=True, db=db)

    assert result == {
        "ada": "ABC-123",
        "subject": "Δοκιμαστική απόφαση",
        "decisionType": "Α.2",
        "organizationLabel": "ΔΗΜΟΣ ΔΟΚΙΜΗΣ",
        "issueDate": published.isoformat(),
        "documentUrl": "https://diavgeia.gov.gr/doc/ABC-123",
        "periferiaId": 6,
        "dimosId": 22,
    }
    assert "ABC-123" in str(db.statement.compile(compile_kwargs={"literal_binds": True}))


@pytest.mark.asyncio
async def test_admin_diavgeia_lookup_returns_404_for_unknown_ada():
    with pytest.raises(HTTPException) as exc:
        await diavgeia.admin_get_diavgeia_decision("UNKNOWN-123", _key=True, db=_FakeDB())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_diavgeia_lookup_rejects_empty_ada():
    with pytest.raises(HTTPException) as exc:
        await diavgeia.admin_get_diavgeia_decision("   ", _key=True, db=_FakeDB())

    assert exc.value.status_code == 400
