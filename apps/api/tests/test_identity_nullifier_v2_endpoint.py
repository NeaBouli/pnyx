"""
Focused endpoint tests for ADR-004 / GH#111 identity nullifier v2 activation.

These tests exercise the real /identity/verify router path with an in-memory
SQLite database. HLR and key generation are mocked so no phone lookup or secret
material is used.
"""
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
V2 = "v2:" + "2" * 64
PUB_OLD = "a" * 64
PUB_NEW = "b" * 64
PRIV_NEW = "c" * 64


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

    async def fake_increment_hlr_usage() -> int:
        return 1

    monkeypatch.setattr(identity, "verify_greek_number", fake_hlr)
    monkeypatch.setattr(identity, "_increment_hlr_usage", fake_increment_hlr_usage)
    monkeypatch.setattr(identity, "generate_nullifier_hash", lambda _phone: V1)
    monkeypatch.setattr(identity, "generate_nullifier_hash_v2", lambda _phone: V2)
    monkeypatch.setattr(
        identity,
        "generate_keypair",
        lambda: {"public_key_hex": PUB_NEW, "private_key_hex": PRIV_NEW},
    )

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
                SELECT id, nullifier_hash, nullifier_hash_v2, nullifier_version,
                       public_key_hex, status, revoked_at
                FROM identity_records
                ORDER BY id
                """
            )
        )
        return [dict(row._mapping) for row in result.fetchall()]


@pytest.mark.asyncio
async def test_v2_verify_migrates_existing_v1_identity_same_row(monkeypatch):
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "v2")

    async with _SessionLocal() as db:
        await db.execute(
            text(
                """
                INSERT INTO identity_records
                  (id, nullifier_hash, public_key_hex, status, nullifier_version)
                VALUES (7, :v1, :pub, 'ACTIVE', 'v1')
                """
            ),
            {"v1": V1, "pub": PUB_OLD},
        )
        await db.execute(text("INSERT INTO survey_responses (user_hash) VALUES (:v1)"), {"v1": V1})
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/identity/verify", json={"phone_number": "+306900000001"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["nullifier_hash"] == V1
    assert payload["public_key_hex"] == PUB_NEW

    rows = await _identity_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == 7
    assert rows[0]["nullifier_hash"] == V1
    assert rows[0]["nullifier_hash_v2"] == V2
    assert rows[0]["nullifier_version"] == "v2"
    assert rows[0]["status"] == "ACTIVE"
    assert rows[0]["public_key_hex"] == PUB_NEW

    async with _SessionLocal() as db:
        survey_count = (
            await db.execute(text("SELECT COUNT(*) FROM survey_responses WHERE user_hash = :v1"), {"v1": V1})
        ).scalar_one()
    assert survey_count == 0


@pytest.mark.asyncio
async def test_existing_identity_stays_active_if_reregistration_key_generation_fails(monkeypatch):
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "v2")

    async with _SessionLocal() as db:
        await db.execute(
            text(
                """
                INSERT INTO identity_records
                  (id, nullifier_hash, public_key_hex, status, nullifier_version)
                VALUES (7, :v1, :pub, 'ACTIVE', 'v1')
                """
            ),
            {"v1": V1, "pub": PUB_OLD},
        )
        await db.commit()

    def failing_keypair() -> dict[str, str]:
        raise RuntimeError("simulated key generation failure")

    monkeypatch.setattr(identity, "generate_keypair", failing_keypair)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with pytest.raises(RuntimeError, match="simulated key generation failure"):
            await client.post("/api/v1/identity/verify", json={"phone_number": "+306900000001"})

    rows = await _identity_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == 7
    assert rows[0]["status"] == "ACTIVE"
    assert rows[0]["public_key_hex"] == PUB_OLD
    assert rows[0]["nullifier_hash_v2"] is None
    assert rows[0]["nullifier_version"] == "v1"


@pytest.mark.asyncio
async def test_v2_verify_new_identity_writes_v1_anchor_and_v2_hash(monkeypatch):
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "v2")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/identity/verify", json={"phone_number": "+306900000002"})

    assert response.status_code == 200
    assert response.json()["nullifier_hash"] == V1

    rows = await _identity_rows()
    assert len(rows) == 1
    assert rows[0]["nullifier_hash"] == V1
    assert rows[0]["nullifier_hash_v2"] == V2
    assert rows[0]["nullifier_version"] == "v2"
    assert rows[0]["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_v1_verify_leaves_v2_fields_empty_by_default(monkeypatch):
    monkeypatch.delenv("IDENTITY_NULLIFIER_KDF_VERSION", raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/identity/verify", json={"phone_number": "+306900000003"})

    assert response.status_code == 200

    rows = await _identity_rows()
    assert len(rows) == 1
    assert rows[0]["nullifier_hash"] == V1
    assert rows[0]["nullifier_hash_v2"] is None
    assert rows[0]["nullifier_version"] == "v1"
