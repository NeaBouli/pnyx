"""
EVA-002: Raw demographic attributes (age_group, region, gender_code,
demographic_hash) must never be persisted on identity_records.

- Registration with demographic fields in the request persists none of them
  (all NULL incl. demographic_hash).
- Re-registration does not write them (and clears legacy residue).
- Revoke clears previously stored values.
- Old-client payloads that still send the fields get the same success
  response (fields accepted, ignored — no 422).
"""
import logging
import os
import sys
import time

import pytest

pytest.importorskip("aiosqlite", reason="aiosqlite required for SQLite router tests")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import get_db
from main import app
from routers import identity


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_SessionLocal = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

V1 = "1" * 64
PUB = "a" * 64
PRIV = "c" * 64

DEMOGRAPHIC_PAYLOAD = {
    "age_group": "AGE_26_40",
    "region": "REG_ATTICA",
    "gender_code": "GENDER_FEMALE",
}


@event.listens_for(_engine.sync_engine, "connect")
def _sqlite_now(dbapi_conn, _):
    dbapi_conn.create_function("now", 0, lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS identity_records (
    id INTEGER PRIMARY KEY,
    nullifier_hash TEXT UNIQUE NOT NULL,
    nullifier_hash_v2 TEXT UNIQUE,
    nullifier_version TEXT DEFAULT 'v1' NOT NULL,
    nullifier_migrated_at TIMESTAMP,
    public_key_hex TEXT NOT NULL,
    demographic_hash TEXT,
    age_group TEXT,
    region TEXT,
    gender_code TEXT,
    periferia_id INTEGER,
    dimos_id INTEGER,
    region_locked BOOLEAN DEFAULT 0 NOT NULL,
    source TEXT DEFAULT 'SMS' NOT NULL,
    status TEXT DEFAULT 'ACTIVE' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS survey_responses (
    id INTEGER PRIMARY KEY,
    user_hash TEXT NOT NULL
);
"""


async def _get_test_db():
    async with _SessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
async def setup_db(monkeypatch):
    async with _engine.begin() as conn:
        for stmt in SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(text(stmt))

    app.dependency_overrides[get_db] = _get_test_db

    async def fake_hlr(_phone: str) -> dict[str, object]:
        return {"valid": True, "network": "TEST", "country": "GR", "status": "LIVE", "error": None}

    async def fake_increment_hlr_usage(_providers: list[str]) -> int:
        return 1

    async def fake_acquire_identity_verify_lock(_nullifier_hash: str) -> tuple[str, str]:
        return ("identity:verify:lock:test", "token")

    async def fake_release_identity_verify_lock(_lock_key: str, _token: str) -> None:
        return None

    async def fake_enforce_hlr_verify_limits(_request, _normalized_number: str) -> None:
        return None

    monkeypatch.setattr(identity, "verify_greek_number", fake_hlr)
    monkeypatch.setattr(identity, "_increment_hlr_usage", fake_increment_hlr_usage)
    monkeypatch.setattr(identity, "_acquire_identity_verify_lock", fake_acquire_identity_verify_lock)
    monkeypatch.setattr(identity, "_release_identity_verify_lock", fake_release_identity_verify_lock)
    monkeypatch.setattr(identity, "_enforce_hlr_verify_limits", fake_enforce_hlr_verify_limits)
    monkeypatch.setattr(identity, "generate_nullifier_hash", lambda _phone: V1)
    monkeypatch.setattr(
        identity,
        "generate_keypair",
        lambda: {"public_key_hex": PUB, "private_key_hex": PRIV},
    )
    monkeypatch.delenv("IDENTITY_NULLIFIER_KDF_VERSION", raising=False)

    yield

    app.dependency_overrides.clear()
    async with _engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS survey_responses"))
        await conn.execute(text("DROP TABLE IF EXISTS identity_records"))


async def _identity_rows() -> list[dict[str, object]]:
    async with _SessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT id, nullifier_hash, status, demographic_hash,
                       age_group, region, gender_code, revoked_at
                FROM identity_records
                ORDER BY id
                """
            )
        )
        return [dict(row._mapping) for row in result.fetchall()]


def _assert_demographics_null(row: dict[str, object]) -> None:
    assert row["demographic_hash"] is None
    assert row["age_group"] is None
    assert row["region"] is None
    assert row["gender_code"] is None


@pytest.mark.asyncio
async def test_registration_with_demographics_persists_none(caplog):
    """New identity: demographic fields in the request are ignored, all four
    columns stay NULL (including demographic_hash)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with caplog.at_level(logging.INFO, logger="routers.identity"):
            response = await client.post(
                "/api/v1/identity/verify",
                json={"phone_number": "+306900000001", **DEMOGRAPHIC_PAYLOAD},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["nullifier_hash"] == V1
    assert payload["public_key_hex"] == PUB
    assert payload["private_key_hex"] == PRIV

    rows = await _identity_rows()
    assert len(rows) == 1
    _assert_demographics_null(rows[0])

    # Scope-only log marker, never the raw values
    assert "demographic fields supplied and discarded" in caplog.text
    for value in DEMOGRAPHIC_PAYLOAD.values():
        assert value not in caplog.text


@pytest.mark.asyncio
async def test_reregistration_does_not_write_demographics():
    """Re-registering an existing active identity with demographic fields in
    the payload must not persist them."""
    async with _SessionLocal() as db:
        await db.execute(
            text(
                """
                INSERT INTO identity_records
                  (id, nullifier_hash, public_key_hex, status, nullifier_version)
                VALUES (7, :v1, :pub, 'ACTIVE', 'v1')
                """
            ),
            {"v1": V1, "pub": "b" * 64},
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/identity/verify",
            json={"phone_number": "+306900000001", **DEMOGRAPHIC_PAYLOAD},
        )

    assert response.status_code == 200
    assert response.json()["success"] is True

    rows = await _identity_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == 7
    assert rows[0]["status"] == "ACTIVE"
    _assert_demographics_null(rows[0])


@pytest.mark.asyncio
async def test_reregistration_clears_legacy_demographics():
    """A row that still carries raw demographics from an old release is
    cleaned when the identity re-registers."""
    async with _SessionLocal() as db:
        await db.execute(
            text(
                """
                INSERT INTO identity_records
                  (id, nullifier_hash, public_key_hex, status, nullifier_version,
                   demographic_hash, age_group, region, gender_code)
                VALUES (7, :v1, :pub, 'ACTIVE', 'v1',
                        'd' * 64, 'AGE_18_25', 'REG_CRETE', 'GENDER_MALE')
                """
            ),
            {"v1": V1, "pub": "b" * 64},
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/identity/verify", json={"phone_number": "+306900000001"}
        )

    assert response.status_code == 200

    rows = await _identity_rows()
    assert len(rows) == 1
    _assert_demographics_null(rows[0])


@pytest.mark.asyncio
async def test_revoke_clears_previously_stored_demographics():
    """Revoking a key nulls any previously stored raw demographics."""
    async with _SessionLocal() as db:
        await db.execute(
            text(
                """
                INSERT INTO identity_records
                  (id, nullifier_hash, public_key_hex, status, nullifier_version,
                   demographic_hash, age_group, region, gender_code)
                VALUES (7, :v1, :pub, 'ACTIVE', 'v1',
                        'e' * 64, 'AGE_41_65', 'REG_THESSALY', 'GENDER_DIVERSE')
                """
            ),
            {"v1": V1, "pub": "b" * 64},
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/identity/revoke",
            json={"nullifier_hash": V1, "phone_number": "+306900000001"},
        )

    assert response.status_code == 200
    assert response.json()["success"] is True

    rows = await _identity_rows()
    assert len(rows) == 1
    assert rows[0]["status"] == "REVOKED"
    assert rows[0]["revoked_at"] is not None
    _assert_demographics_null(rows[0])


@pytest.mark.asyncio
async def test_verify_without_demographics_unchanged(caplog):
    """Payload without demographic fields behaves exactly as before."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/identity/verify", json={"phone_number": "+306900000009"}
        )

    assert response.status_code == 200
    assert response.json()["success"] is True

    rows = await _identity_rows()
    assert len(rows) == 1
    _assert_demographics_null(rows[0])
    assert "demographic fields supplied and discarded" not in caplog.text
