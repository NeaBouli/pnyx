"""EVA-033: representative invite codes are stored only as a keyed hash."""
import hashlib
import hmac
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException, Response

from routers import representative
from routers.representative import InviteRequest, VerifyRequest
from services import invite_codes
from services.invite_codes import invite_code_hash, invite_code_hint

CODE = "QX7K-M2PA"


def _load_migration():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "y802a2b3c4d5_rep_invite_code_hash.py"
    spec = importlib.util.spec_from_file_location("y802", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Row:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._row or []


class _DB:
    def __init__(self, invite_row=None, consumed=True, list_rows=None):
        self.invite_row = invite_row
        self.consumed = consumed
        self.list_rows = list_rows or []
        self.executed: list[tuple[str, dict]] = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.executed.append((sql, params or {}))
        if "ORDER BY created_at DESC" in sql:
            return _Row(self.list_rows)
        if "FROM rep_invitations" in sql:
            return _Row(self.invite_row)
        if "UPDATE rep_invitations" in sql and "RETURNING" in sql:
            return _Row((7,) if self.consumed else None)
        return _Row()

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def test_hash_is_full_namespaced_hmac_with_server_salt(monkeypatch) -> None:
    monkeypatch.setenv("SERVER_SALT", "unit-test-salt-0123456789abcdef")
    expected = hmac.new(b"unit-test-salt-0123456789abcdef", b"rep-invite:v1:" + CODE.encode(), hashlib.sha256).hexdigest()

    assert invite_code_hash(CODE) == expected
    assert len(invite_code_hash(CODE)) == 64
    assert invite_code_hash(CODE) != invite_code_hash(CODE.lower())  # exact input, no case folding


def test_missing_salt_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("SERVER_SALT", "   ")
    with pytest.raises(RuntimeError):
        invite_code_hash(CODE)


def test_hint_reveals_only_two_characters() -> None:
    assert invite_code_hint(CODE) == "QX**-****"
    assert invite_code_hint("short") == "****-****"


def test_migration_hash_matches_runtime(monkeypatch) -> None:
    monkeypatch.setenv("SERVER_SALT", "unit-test-salt-0123456789abcdef")
    migration = _load_migration()
    assert migration._hash(migration._key(), CODE) == invite_code_hash(CODE)
    assert migration._hint(CODE) == invite_code_hint(CODE)


@pytest.mark.asyncio
async def test_create_stores_only_hash_and_hint_and_returns_code_once(monkeypatch) -> None:
    monkeypatch.setattr(representative, "_generate_invite_code", lambda: CODE)
    db = _DB()
    response = Response()

    result = await representative.create_invite(
        InviteRequest(role="Δήμαρχος", region="Αττικής"), response=response, _auth=True, db=db,
    )

    assert result["invite_code"] == CODE
    assert response.headers["Cache-Control"] == "no-store"
    insert_sql, params = next((sql, p) for sql, p in db.executed if "INSERT INTO rep_invitations" in sql)
    assert CODE not in repr(params)
    assert params["code_hash"] == invite_code_hash(CODE)
    assert params["code_hint"] == "QX**-****"
    assert "invite_code," not in insert_sql and "invite_code)" not in insert_sql


@pytest.mark.asyncio
async def test_list_shows_hint_never_code_or_hash() -> None:
    now = datetime.now()
    db = _DB(list_rows=[(3, "QX**-****", None, "Δήμαρχος", "Αττικής", None, False, now + timedelta(hours=1), now, None, None)])

    rows = await representative.list_invites(_auth=True, db=db)

    assert rows[0]["invite_code_hint"] == "QX**-****"
    assert "invite_code" not in rows[0]
    assert invite_code_hash(CODE) not in repr(rows)


@pytest.mark.asyncio
async def test_verify_looks_up_by_hash_not_plaintext(monkeypatch) -> None:
    async def _diavgeia(_ada):
        return {"org_label": "ΔΗΜΟΣ ΚΑΛΑΜΑΤΑΣ", "subject": "x"}

    monkeypatch.setattr(representative, "_verify_ada_diavgeia", _diavgeia)
    db = _DB(invite_row=(7, "Δήμαρχος", None, None, False, datetime.now() + timedelta(hours=1), None, None))

    await representative.verify_representative(VerifyRequest(ada_number="ΨΚΛ4ΟΡ1Γ-7ΑΒ", invite_code=CODE), db=db)

    select_sql, params = next((sql, p) for sql, p in db.executed if "FROM rep_invitations" in sql)
    assert "invite_code_hash = :code_hash" in select_sql
    assert params == {"code_hash": invite_code_hash(CODE)}
    assert db.committed is True


@pytest.mark.asyncio
async def test_concurrent_redemption_loses_atomically(monkeypatch) -> None:
    async def _diavgeia(_ada):
        return {"org_label": "ΔΗΜΟΣ ΚΑΛΑΜΑΤΑΣ", "subject": "x"}

    monkeypatch.setattr(representative, "_verify_ada_diavgeia", _diavgeia)
    # The row was unused at SELECT time, but another request consumed it first.
    db = _DB(invite_row=(7, "Δήμαρχος", None, None, False, datetime.now() + timedelta(hours=1), None, None), consumed=False)

    with pytest.raises(HTTPException) as exc_info:
        await representative.verify_representative(VerifyRequest(ada_number="ΨΚΛ4ΟΡ1Γ-7ΑΒ", invite_code=CODE), db=db)

    assert exc_info.value.status_code == 403
    assert db.rolled_back is True and db.committed is False
    assert not any("INSERT INTO representative_tokens" in sql for sql, _ in db.executed)


def test_no_module_reads_the_plaintext_column() -> None:
    source = Path(invite_codes.__file__).resolve().parents[1] / "routers" / "representative.py"
    text = source.read_text(encoding="utf-8")
    assert "WHERE invite_code =" not in text
    assert "SELECT id, invite_code," not in text
