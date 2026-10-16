"""
EVA-001 PR1: POST /api/v2/identity/verify with a device-generated key and
proof of possession. Real router path on in-memory SQLite; HLR, rate limits and
the verify lock are mocked. Keys are throwaway test keys generated per run.
"""
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
        hlr_calls.append(1)
        return {"valid": True, "network": "TEST", "country": "GR", "status": "LIVE", "error": None}

    async def fake_increment_hlr_usage(_providers: list[str]) -> int:
        return 1

    async def fake_acquire_identity_verify_lock(_nullifier_hash: str) -> tuple[str, str]:
        return ("identity:verify:lock:test", "token")

    async def fake_release_identity_verify_lock(_lock_key: str, _token: str) -> None:
        return None

    async def fake_enforce_hlr_verify_limits(_request, _normalized_number: str) -> None:
        return None

    hlr_calls.clear()
    monkeypatch.setenv("IDENTITY_V2_ENABLED", "true")
    monkeypatch.setattr(identity, "verify_greek_number", fake_hlr)
    monkeypatch.setattr(identity, "_increment_hlr_usage", fake_increment_hlr_usage)
    monkeypatch.setattr(identity, "_acquire_identity_verify_lock", fake_acquire_identity_verify_lock)
    monkeypatch.setattr(identity, "_release_identity_verify_lock", fake_release_identity_verify_lock)
    monkeypatch.setattr(identity, "_enforce_hlr_verify_limits", fake_enforce_hlr_verify_limits)
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


def _now_ms() -> int:
    return int(time.time() * 1000)


def _signed_body(sk: SigningKey | None = None, *, ts: int | None = None, message_pk: str | None = None) -> dict:
    sk = sk or SigningKey.generate()
    pk = sk.verify_key.encode().hex()
    ts = _now_ms() if ts is None else ts
    msg = identity.identity_register_pop_message(message_pk or pk, ts)
    return {
        "phone_number": "+306900000000",
        "public_key_hex": pk,
        "pop_timestamp_ms": ts,
        "pop_signature_hex": sk.sign(msg.encode()).signature.hex(),
    }


async def _post(body: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/v2/identity/verify", json=body)


async def _rows():
    async with _engine.begin() as conn:
        return (await conn.execute(text("SELECT nullifier_hash, public_key_hex, status FROM identity_records ORDER BY id"))).fetchall()


async def _insert(nullifier: str, pk: str, status_: str) -> None:
    async with _engine.begin() as conn:
        await conn.execute(text("INSERT INTO identity_records (nullifier_hash, public_key_hex, status) VALUES (:n, :p, :s)"), {"n": nullifier, "p": pk, "s": status_})


@pytest.mark.asyncio
async def test_disabled_by_default_returns_404_without_hlr(monkeypatch) -> None:
    monkeypatch.delenv("IDENTITY_V2_ENABLED", raising=False)
    response = await _post(_signed_body())
    assert response.status_code == 404
    assert hlr_calls == [] and await _rows() == []


@pytest.mark.asyncio
async def test_registers_client_key_and_never_returns_a_private_key() -> None:
    body = _signed_body()
    response = await _post(body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["public_key_hex"] == body["public_key_hex"]
    assert "private_key_hex" not in data
    assert data["nullifier_hash"] == V1
    assert await _rows() == [(V1, body["public_key_hex"], "ACTIVE")]
    assert hlr_calls == [1]


@pytest.mark.asyncio
@pytest.mark.parametrize("mutate,detail", [
    (lambda b: b.update(pop_signature_hex="0" * 128), "INVALID_POP_SIGNATURE"),
    (lambda b: b.update(public_key_hex=b["public_key_hex"].upper()), "INVALID_KEY_FORMAT"),
    (lambda b: b.update(public_key_hex=b["public_key_hex"][:62]), "INVALID_KEY_FORMAT"),
    (lambda b: b.update(pop_signature_hex=b["pop_signature_hex"][:-2]), "INVALID_KEY_FORMAT"),
    (lambda b: b.update(pop_timestamp_ms=b["pop_timestamp_ms"] + 1), "INVALID_POP_SIGNATURE"),
])
async def test_rejects_bad_pop_before_hlr(mutate, detail) -> None:
    body = _signed_body()
    mutate(body)
    response = await _post(body)
    assert response.status_code == 400
    assert response.json()["detail"] == detail
    assert hlr_calls == [] and await _rows() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("offset_ms", [-(5 * 60 * 1000 + 1000), 5 * 60 * 1000 + 1000])
async def test_rejects_pop_outside_time_window(offset_ms) -> None:
    response = await _post(_signed_body(ts=_now_ms() + offset_ms))
    assert response.status_code == 400
    assert response.json()["detail"] == "POP_EXPIRED"
    assert hlr_calls == []


@pytest.mark.asyncio
async def test_signature_for_another_key_is_rejected() -> None:
    # A PoP made by key A cannot register key B (no key squatting).
    other = SigningKey.generate().verify_key.encode().hex()
    body = _signed_body(message_pk=other)
    body["public_key_hex"] = other
    response = await _post(body)
    assert response.status_code == 400
    assert response.json()["detail"] == "INVALID_POP_SIGNATURE"


def test_small_order_key_with_trivial_signature_is_rejected() -> None:
    # Identity point: (R=identity, S=0) would satisfy the naive equation for any message.
    identity_point = "01" + "00" * 31
    body = {"phone_number": "+306900000000", "public_key_hex": identity_point,
            "pop_timestamp_ms": _now_ms(), "pop_signature_hex": identity_point + "00" * 32}
    with pytest.raises(HTTPException) as exc:
        identity._check_registration_pop(identity.VerifyV2Request(**body), body["pop_timestamp_ms"])
    assert exc.value.detail == "INVALID_POP_SIGNATURE"


@pytest.mark.asyncio
async def test_key_active_on_another_identity_is_rejected_before_hlr() -> None:
    sk = SigningKey.generate()
    await _insert("9" * 64, sk.verify_key.encode().hex(), "ACTIVE")
    response = await _post(_signed_body(sk))
    assert response.status_code == 409
    assert response.json()["detail"] == "PUBLIC_KEY_IN_USE"
    assert hlr_calls == []


@pytest.mark.asyncio
async def test_active_identity_is_not_rekeyed_by_hlr_alone() -> None:
    # D3: swapping the key of an ACTIVE identity needs the old key (rotate-key).
    await _insert(V1, PUB_OLD, "ACTIVE")
    response = await _post(_signed_body())
    assert response.status_code == 409
    assert response.json()["detail"].startswith("IDENTITY_ACTIVE")
    assert await _rows() == [(V1, PUB_OLD, "ACTIVE")]


@pytest.mark.asyncio
async def test_revoked_identity_is_reactivated_with_the_client_key() -> None:
    await _insert(V1, PUB_OLD, "REVOKED")
    body = _signed_body()
    response = await _post(body)
    assert response.status_code == 200, response.text
    assert await _rows() == [(V1, body["public_key_hex"], "ACTIVE")]


def test_pop_message_is_domain_separated_and_has_no_phone() -> None:
    msg = identity.identity_register_pop_message("ab" * 32, 1700000000000)
    assert msg == "ekklesia:identity-register:v1:" + "ab" * 32 + ":1700000000000"
    assert "+30" not in msg


@pytest.mark.asyncio
async def test_v1_still_returns_server_generated_key() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/identity/verify", json={"phone_number": "+306900000000"})
    assert response.status_code == 200, response.text
    assert response.json()["private_key_hex"] == PRIV_NEW
    assert await _rows() == [(V1, PUB_NEW, "ACTIVE")]
