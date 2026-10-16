"""EVA-001 PR2: POST /api/v2/identity/rotate-key (old+new signature, CAS, flag off by default).
Real router path on in-memory SQLite with throwaway test keys."""
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
    monkeypatch.setenv("IDENTITY_ROTATE_ENABLED", "true")
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


def _rotation(old: SigningKey, new: SigningKey, *, nullifier: str = NULLIFIER, ts: int | None = None) -> dict:
    ts = _now_ms() if ts is None else ts
    msg = identity.identity_rotate_message(nullifier, _pk(old), _pk(new), ts).encode()
    return {
        "nullifier_hash": nullifier,
        "old_public_key_hex": _pk(old),
        "new_public_key_hex": _pk(new),
        "timestamp_ms": ts,
        "old_signature_hex": old.sign(msg).signature.hex(),
        "new_signature_hex": new.sign(msg).signature.hex(),
    }


async def _post(body: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/v2/identity/rotate-key", json=body)


async def _insert(nullifier: str, pk: str, status_: str = "ACTIVE") -> None:
    async with _engine.begin() as conn:
        await conn.execute(text("INSERT INTO identity_records (nullifier_hash, public_key_hex, status) VALUES (:n, :p, :s)"),
                           {"n": nullifier, "p": pk, "s": status_})


async def _keys() -> list[tuple]:
    async with _engine.begin() as conn:
        return (await conn.execute(text("SELECT nullifier_hash, public_key_hex, status FROM identity_records ORDER BY id"))).fetchall()


async def _audit() -> list[tuple]:
    async with _engine.begin() as conn:
        return (await conn.execute(text("SELECT action, actor, target_type, target_id, metadata FROM audit_log"))).fetchall()


@pytest.mark.asyncio
async def test_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("IDENTITY_ROTATE_ENABLED", raising=False)
    old, new = SigningKey.generate(), SigningKey.generate()
    await _insert(NULLIFIER, _pk(old))
    response = await _post(_rotation(old, new))
    assert response.status_code == 404
    assert await _keys() == [(NULLIFIER, _pk(old), "ACTIVE")]


@pytest.mark.asyncio
async def test_rotation_swaps_key_and_audits_without_key_material() -> None:
    old, new = SigningKey.generate(), SigningKey.generate()
    await _insert(NULLIFIER, _pk(old))
    response = await _post(_rotation(old, new))
    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "public_key_hex": _pk(new), "already_rotated": False}
    assert await _keys() == [(NULLIFIER, _pk(new), "ACTIVE")]
    audit = await _audit()
    assert audit == [("identity.key_rotated", "identity_holder", "identity_record", "1", "{}")]
    flat = repr(audit)
    assert _pk(old) not in flat and _pk(new) not in flat and NULLIFIER not in flat


@pytest.mark.asyncio
async def test_retry_after_rotation_is_idempotent_without_second_audit() -> None:
    # PR4 crash recovery: the app re-sends its staged rotation.
    old, new = SigningKey.generate(), SigningKey.generate()
    await _insert(NULLIFIER, _pk(old))
    assert (await _post(_rotation(old, new))).status_code == 200
    retry = await _post(_rotation(old, new))
    assert retry.status_code == 200
    assert retry.json() == {"success": True, "public_key_hex": _pk(new), "already_rotated": True}
    assert await _keys() == [(NULLIFIER, _pk(new), "ACTIVE")]
    assert len(await _audit()) == 1


@pytest.mark.asyncio
async def test_old_message_cannot_undo_a_later_rotation() -> None:
    # A->B then B->C: replaying A->B is neither applied nor confirmed.
    a, b, c = SigningKey.generate(), SigningKey.generate(), SigningKey.generate()
    await _insert(NULLIFIER, _pk(a))
    first = _rotation(a, b)
    assert (await _post(first)).status_code == 200
    assert (await _post(_rotation(b, c))).status_code == 200
    replay = await _post(first)
    assert replay.status_code == 409
    assert replay.json()["detail"] == "ROTATION_CONFLICT"
    assert await _keys() == [(NULLIFIER, _pk(c), "ACTIVE")]


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["old", "new"])
async def test_both_signatures_are_required(which) -> None:
    old, new, other = SigningKey.generate(), SigningKey.generate(), SigningKey.generate()
    await _insert(NULLIFIER, _pk(old))
    body = _rotation(old, new)
    msg = identity.identity_rotate_message(NULLIFIER, _pk(old), _pk(new), body["timestamp_ms"]).encode()
    body[f"{which}_signature_hex"] = other.sign(msg).signature.hex()
    response = await _post(body)
    assert response.status_code == 400
    assert response.json()["detail"] == "INVALID_SIGNATURE"
    assert await _keys() == [(NULLIFIER, _pk(old), "ACTIVE")]


@pytest.mark.asyncio
async def test_signature_bound_to_nullifier() -> None:
    # A rotation signed for another nullifier cannot be redirected.
    old, new = SigningKey.generate(), SigningKey.generate()
    await _insert(NULLIFIER, _pk(old))
    body = _rotation(old, new, nullifier="2" * 64)
    body["nullifier_hash"] = NULLIFIER
    response = await _post(body)
    assert response.status_code == 400
    assert await _keys() == [(NULLIFIER, _pk(old), "ACTIVE")]


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["unknown_nullifier", "wrong_current_key", "revoked"])
async def test_conflicts_are_uniform(state) -> None:
    old, new, current = SigningKey.generate(), SigningKey.generate(), SigningKey.generate()
    if state == "wrong_current_key":
        await _insert(NULLIFIER, _pk(current))
    elif state == "revoked":
        await _insert(NULLIFIER, _pk(old), "REVOKED")
    response = await _post(_rotation(old, new))
    assert response.status_code == 409
    assert response.json()["detail"] == "ROTATION_CONFLICT"
    assert await _audit() == []


@pytest.mark.asyncio
async def test_new_key_active_elsewhere_is_rejected() -> None:
    old, new = SigningKey.generate(), SigningKey.generate()
    await _insert(NULLIFIER, _pk(old))
    await _insert("3" * 64, _pk(new))
    response = await _post(_rotation(old, new))
    assert response.status_code == 409
    assert response.json()["detail"] == "PUBLIC_KEY_IN_USE"
    assert await _keys() == [(NULLIFIER, _pk(old), "ACTIVE"), ("3" * 64, _pk(new), "ACTIVE")]
    assert await _audit() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("offset_ms", [-(5 * 60 * 1000 + 1000), 5 * 60 * 1000 + 1000])
async def test_stale_or_future_timestamp_is_rejected(offset_ms) -> None:
    old, new = SigningKey.generate(), SigningKey.generate()
    await _insert(NULLIFIER, _pk(old))
    response = await _post(_rotation(old, new, ts=_now_ms() + offset_ms))
    assert response.status_code == 400
    assert response.json()["detail"] == "POP_EXPIRED"


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["nullifier_hash", "old_public_key_hex", "new_public_key_hex", "old_signature_hex", "new_signature_hex"])
async def test_non_canonical_hex_is_rejected(field) -> None:
    old, new = SigningKey.generate(), SigningKey.generate()
    await _insert(NULLIFIER, _pk(old))
    body = _rotation(old, new)
    body[field] = body[field].upper() if field != "nullifier_hash" else "A" * 64
    response = await _post(body)
    assert response.status_code == 400
    assert response.json()["detail"] == "INVALID_KEY_FORMAT"


@pytest.mark.asyncio
async def test_same_key_is_rejected() -> None:
    old = SigningKey.generate()
    await _insert(NULLIFIER, _pk(old))
    response = await _post(_rotation(old, old))
    assert response.status_code == 400
    assert response.json()["detail"] == "SAME_KEY"


def test_rotation_message_is_domain_separated() -> None:
    msg = identity.identity_rotate_message("1" * 64, "a" * 64, "b" * 64, 1700000000000)
    assert msg == "ekklesia:identity-rotate:v1:" + "1" * 64 + ":" + "a" * 64 + ":" + "b" * 64 + ":1700000000000"
    assert msg != identity.identity_register_pop_message("b" * 64, 1700000000000)


def test_rotate_route_is_rate_limited() -> None:
    from rate_limit import limiter
    limits = limiter._route_limits.get("routers.identity.rotate_identity_key", [])
    assert [str(l.limit) for l in limits] == ["10 per 1 minute"]


async def _register_polis(identity_key: SigningKey, pk_polis: str):
    ts = _now_ms()
    msg = f"polis-register:{pk_polis}:{NULLIFIER}:{ts}".encode()
    body = {"nullifier_hash": NULLIFIER, "pk_polis": pk_polis, "timestamp_ms": ts,
            "identity_signature": identity_key.sign(msg).signature.hex()}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/v1/polis/register-key", json=body)


@pytest.mark.asyncio
async def test_polis_binding_survives_rotation_without_a_second_polis_identity() -> None:
    # Contract for PR4/PR6: the client keeps its POLIS key across a rotation; the
    # server neither drops nor rebinds it (a rebind would allow a second POLIS
    # vote per ticket, unique per (ticket_id, pk_polis)).
    old, new = SigningKey.generate(), SigningKey.generate()
    pk_polis = _pk(SigningKey.generate())
    await _insert(NULLIFIER, _pk(old))
    assert (await _register_polis(old, pk_polis)).status_code == 201
    assert (await _post(_rotation(old, new))).status_code == 200

    again = await _register_polis(new, pk_polis)
    assert again.status_code == 201 and again.json()["status"] == "already_registered"
    other = await _register_polis(new, _pk(SigningKey.generate()))
    assert other.status_code == 409
    stale = await _register_polis(old, pk_polis)
    assert stale.status_code == 401  # the rotated-away identity key no longer authorises
