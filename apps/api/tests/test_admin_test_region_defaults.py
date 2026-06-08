import os
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import AuditLog, Dimos, IdentityRecord, Periferia
from routers import admin_account, representative


class _FakeAdminDB:
    def __init__(self):
        self.added = []
        self.committed = False

    async def get(self, model, row_id):
        if model is Periferia and row_id == 6:
            return SimpleNamespace(id=6, name_el="Πελοποννήσου")
        if model is Dimos and row_id == 22:
            return SimpleNamespace(id=22, name_el="Καλαμάτας", periferia_id=6)
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if isinstance(obj, IdentityRecord) and obj.id is None:
                obj.id = 123

    async def commit(self):
        self.committed = True

    async def refresh(self, _obj):
        return None


class _FakeResult:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _FakeRepresentativeDB:
    def __init__(self, invite_row):
        self.invite_row = invite_row
        self.params_by_sql = []
        self.committed = False

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.params_by_sql.append((sql, params or {}))
        if "FROM rep_invitations" in sql:
            return _FakeResult(self.invite_row)
        return _FakeResult()

    async def commit(self):
        self.committed = True

    @property
    def representative_token_params(self):
        for sql, params in self.params_by_sql:
            if "INSERT INTO representative_tokens" in sql:
                return params
        raise AssertionError("representative_tokens insert was not executed")


@pytest.mark.asyncio
async def test_admin_test_account_defaults_to_locked_test_region():
    db = _FakeAdminDB()

    result = await admin_account.create_test_account(req=None, _auth=True, db=db)

    record = next(obj for obj in db.added if isinstance(obj, IdentityRecord))
    audit = next(obj for obj in db.added if isinstance(obj, AuditLog))

    assert result.periferia_id == 6
    assert result.dimos_id == 22
    assert result.region_locked is True
    assert record.periferia_id == 6
    assert record.dimos_id == 22
    assert record.region_locked is True
    assert "periferia_id=6" in result.qr_data
    assert "dimos_id=22" in result.qr_data
    assert audit.details["periferia_id"] == 6
    assert audit.details["dimos_id"] == 22
    assert audit.details["region_locked"] is True
    assert db.committed is True


@pytest.mark.asyncio
async def test_admin_test_account_keeps_explicit_matching_region():
    db = _FakeAdminDB()

    result = await admin_account.create_test_account(
        req=admin_account.TestAccountRequest(periferia_id=6, dimos_id=22),
        _auth=True,
        db=db,
    )

    assert result.periferia_id == 6
    assert result.dimos_id == 22
    assert result.region_locked is True


@pytest.mark.asyncio
async def test_admin_test_account_rejects_mismatched_region():
    db = _FakeAdminDB()

    with pytest.raises(HTTPException) as exc:
        await admin_account.create_test_account(
            req=admin_account.TestAccountRequest(periferia_id=7, dimos_id=22),
            _auth=True,
            db=db,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid periferia_id: 7"


@pytest.mark.asyncio
async def test_demo_123_defaults_region_when_invite_has_no_ids(monkeypatch):
    monkeypatch.setattr(representative.secrets, "token_urlsafe", lambda _n: "token-demo")
    invite_row = (
        1,
        "Βουλευτής",
        None,
        None,
        False,
        datetime.now() + timedelta(hours=1),
        None,
        None,
    )
    db = _FakeRepresentativeDB(invite_row)

    result = await representative.verify_representative(
        representative.VerifyRequest(ada_number="DEMO-123", invite_code="ABCD-1234"),
        db=db,
    )

    params = db.representative_token_params
    assert result["ada_number"] == "DEMO-123"
    assert params["periferia_id"] == 6
    assert params["dimos_id"] == 22
    assert params["region"] == "Πελοποννήσου"
    assert params["municipality"] == "Καλαμάτας"
    assert db.committed is True


@pytest.mark.asyncio
async def test_demo_123_keeps_invite_region_when_present(monkeypatch):
    monkeypatch.setattr(representative.secrets, "token_urlsafe", lambda _n: "token-demo")
    invite_row = (
        1,
        "Βουλευτής",
        "Αττικής",
        "Αθηναίων",
        False,
        datetime.now() + timedelta(hours=1),
        1,
        10,
    )
    db = _FakeRepresentativeDB(invite_row)

    await representative.verify_representative(
        representative.VerifyRequest(ada_number="DEMO-123", invite_code="ABCD-1234"),
        db=db,
    )

    params = db.representative_token_params
    assert params["periferia_id"] == 1
    assert params["dimos_id"] == 10
    assert params["region"] == "Αττικής"
    assert params["municipality"] == "Αθηναίων"
