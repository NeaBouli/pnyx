"""EVA-003 PR5: POST /api/v2/identity/key-check (read-only proof that a key is current)."""
import os
import sys
import time

import pytest

pytest.importorskip("aiosqlite", reason="aiosqlite required for SQLite router tests")

from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import get_db
from main import app
from routers import identity
from nacl.signing import SigningKey


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_SessionLocal = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

V1 = "1" * 64
V2 = "v2:" + "2" * 64
PUB_OLD = "a" * 64
PUB_NEW = "b" * 64
PRIV_NEW = "c" * 64
hlr_calls: list[int] = []
lock_keys: list[str] = []


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
CREATE UNIQUE INDEX IF NOT EXISTS uq_identity_records_active_public_key
    ON identity_records (public_key_hex) WHERE status = 'ACTIVE';
CREATE TABLE IF NOT EXISTS polis_identity_keys (
    nullifier_hash TEXT PRIMARY KEY,
    pk_polis TEXT UNIQUE NOT NULL,
    signature TEXT,
    timestamp_ms INTEGER,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    metadata TEXT DEFAULT '{}' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS survey_responses (
    id INTEGER PRIMARY KEY,
    user_hash TEXT NOT NULL
);
"""


counted: list[str] = []


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
    counted.clear()
    monkeypatch.setenv("IDENTITY_KEY_CHECK_ENABLED", "true")

    async def count(outcome: str) -> None:
        counted.append(outcome)

    monkeypatch.setattr(identity, "_count_key_check", count)
    yield
    app.dependency_overrides.clear()
    async with _engine.begin() as conn:
        for table in ("audit_log", "polis_identity_keys", "survey_responses", "identity_records"):
            await conn.execute(text(f"DROP TABLE IF EXISTS {table}"))


NULLIFIER = "1" * 64


def _now_ms() -> int:
    return int(time.time() * 1000)


def _pk(sk: SigningKey) -> str:
    return sk.verify_key.encode().hex()


def _check(sk: SigningKey, *, nullifier: str = NULLIFIER, pk: str | None = None, ts: int | None = None) -> dict:
    ts = _now_ms() if ts is None else ts
    pk = pk or _pk(sk)
    msg = identity.identity_key_check_message(nullifier, pk, ts).encode()
    return {"nullifier_hash": nullifier, "public_key_hex": pk, "timestamp_ms": ts,
            "signature_hex": sk.sign(msg).signature.hex()}


async def _post(body: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/v2/identity/key-check", json=body)


async def _insert(nullifier: str, pk: str, status_: str = "ACTIVE") -> None:
    async with _engine.begin() as conn:
        await conn.execute(text("INSERT INTO identity_records (nullifier_hash, public_key_hex, status) VALUES (:n, :p, :s)"),
                           {"n": nullifier, "p": pk, "s": status_})


async def _snapshot():
    async with _engine.begin() as conn:
        rows = (await conn.execute(text("SELECT nullifier_hash, public_key_hex, status FROM identity_records"))).fetchall()
        audits = (await conn.execute(text("SELECT count(*) FROM audit_log"))).scalar()
    return rows, audits


@pytest.mark.asyncio
async def test_current_key_is_confirmed_without_side_effects() -> None:
    sk = SigningKey.generate()
    await _insert(NULLIFIER, _pk(sk))
    before = await _snapshot()
    response = await _post(_check(sk))
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert await _snapshot() == before
    assert counted == ["ok"]


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["unknown", "other_key", "revoked"])
async def test_mismatch_is_uniform(state) -> None:
    sk, other = SigningKey.generate(), SigningKey.generate()
    if state == "other_key":
        await _insert(NULLIFIER, _pk(other))
    elif state == "revoked":
        await _insert(NULLIFIER, _pk(sk), "REVOKED")
    response = await _post(_check(sk))
    assert response.status_code == 409
    assert response.json()["detail"] == "KEY_NOT_CURRENT"
    assert counted == ["mismatch"]


@pytest.mark.asyncio
async def test_signature_must_come_from_the_claimed_key() -> None:
    # Knowing the public key is not enough: no proof without the private key.
    owner, attacker = SigningKey.generate(), SigningKey.generate()
    await _insert(NULLIFIER, _pk(owner))
    response = await _post(_check(attacker, pk=_pk(owner)))
    assert response.status_code == 400
    assert response.json()["detail"] == "INVALID_SIGNATURE"
    assert counted == ["bad_signature"]


@pytest.mark.asyncio
async def test_signature_is_bound_to_the_nullifier() -> None:
    sk = SigningKey.generate()
    await _insert(NULLIFIER, _pk(sk))
    body = _check(sk, nullifier="2" * 64)
    body["nullifier_hash"] = NULLIFIER
    assert (await _post(body)).status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("offset_ms", [-(5 * 60 * 1000 + 1000), 5 * 60 * 1000 + 1000])
async def test_stale_timestamp_is_rejected(offset_ms) -> None:
    sk = SigningKey.generate()
    await _insert(NULLIFIER, _pk(sk))
    response = await _post(_check(sk, ts=_now_ms() + offset_ms))
    assert response.status_code == 400
    assert response.json()["detail"] == "POP_EXPIRED"


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["nullifier_hash", "public_key_hex", "signature_hex"])
async def test_non_canonical_hex_is_rejected(field) -> None:
    sk = SigningKey.generate()
    body = _check(sk)
    body[field] = body[field].upper() if field != "nullifier_hash" else "A" * 64
    response = await _post(body)
    assert response.status_code == 400
    assert response.json()["detail"] == "INVALID_KEY_FORMAT"


@pytest.mark.asyncio
async def test_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("IDENTITY_KEY_CHECK_ENABLED", raising=False)
    sk = SigningKey.generate()
    await _insert(NULLIFIER, _pk(sk))
    assert (await _post(_check(sk))).status_code == 404
    assert counted == []


def test_message_is_domain_separated() -> None:
    msg = identity.identity_key_check_message("1" * 64, "a" * 64, 1700000000000)
    assert msg == "ekklesia:identity-key-check:v1:" + "1" * 64 + ":" + "a" * 64 + ":1700000000000"
    assert msg != identity.identity_rotate_message("1" * 64, "a" * 64, "a" * 64, 1700000000000)
    assert msg != identity.identity_register_pop_message("a" * 64, 1700000000000)


def test_key_check_route_is_rate_limited() -> None:
    from rate_limit import limiter
    limits = limiter._route_limits.get("routers.identity.check_identity_key", [])
    assert [str(l.limit) for l in limits] == ["30 per 1 minute"]
