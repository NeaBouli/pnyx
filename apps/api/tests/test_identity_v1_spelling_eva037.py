"""EVA-037: one identity per number regardless of spelling (real v1/v2 derivation, no hash mocks)."""
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
    monkeypatch.setattr(identity, "verify_greek_number", fake_hlr)
    monkeypatch.setattr(identity, "_increment_hlr_usage", fake_increment_hlr_usage)
    monkeypatch.setattr(identity, "_acquire_identity_verify_lock", fake_acquire_identity_verify_lock)
    monkeypatch.setattr(identity, "_release_identity_verify_lock", fake_release_identity_verify_lock)
    monkeypatch.setattr(identity, "_enforce_hlr_verify_limits", fake_enforce_hlr_verify_limits)
    counter = iter(range(10_000))
    monkeypatch.setattr(
        identity,
        "generate_keypair",
        lambda: {"public_key_hex": f"{next(counter):064x}", "private_key_hex": PRIV_NEW},
    )

    yield

    app.dependency_overrides.clear()
    async with _engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS survey_responses"))
        await conn.execute(text("DROP TABLE IF EXISTS identity_records"))


from nullifier import generate_nullifier_hash  # noqa: E402  (real v1, SERVER_SALT from the test env)

CANONICAL = "+306912345678"
SPELLINGS = [
    "+306912345678",
    "6912345678",
    "06912345678",
    "306912345678",
    "00306912345678",
    "0030 691 234 5678",
    "+30 69 1234 5678",
    "069-1234-5678",
    "(+30) 691.234.5678",
]


async def _verify(phone: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/v1/identity/verify", json={"phone_number": phone})


async def _rows():
    async with _engine.begin() as conn:
        return (await conn.execute(text(
            "SELECT nullifier_hash, nullifier_hash_v2, status FROM identity_records ORDER BY id"))).fetchall()


async def _insert_legacy(anchor: str) -> None:
    # A v1-only identity (no v2 nullifier), like the 15 legacy rows in prod.
    async with _engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO identity_records (nullifier_hash, nullifier_version, public_key_hex, status) "
            "VALUES (:n, 'v1', :p, 'ACTIVE')"), {"n": anchor, "p": PUB_OLD})


@pytest.mark.asyncio
@pytest.mark.parametrize("kdf", ["v1", "v2"])
@pytest.mark.parametrize("spelling", SPELLINGS)
async def test_any_spelling_finds_the_legacy_v1_identity(monkeypatch, kdf, spelling) -> None:
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", kdf)
    await _insert_legacy(generate_nullifier_hash(CANONICAL))
    response = await _verify(spelling)
    assert response.status_code == 200, response.text
    rows = await _rows()
    assert len(rows) == 1, f"second identity created for spelling {spelling!r}"
    assert rows[0][0] == generate_nullifier_hash(CANONICAL)
    assert response.json()["nullifier_hash"] == generate_nullifier_hash(CANONICAL)


@pytest.mark.asyncio
@pytest.mark.parametrize("kdf", ["v1", "v2"])
async def test_new_identity_gets_the_canonical_anchor(monkeypatch, kdf) -> None:
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", kdf)
    response = await _verify("0030 691 234 5678")
    assert response.status_code == 200, response.text
    rows = await _rows()
    assert [r[0] for r in rows] == [generate_nullifier_hash(CANONICAL)]
    # ... and every other spelling afterwards stays on that one identity
    for spelling in SPELLINGS:
        assert (await _verify(spelling)).status_code == 200
    assert len(await _rows()) == 1


@pytest.mark.asyncio
async def test_row_created_from_a_raw_spelling_is_still_found_by_that_spelling(monkeypatch) -> None:
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "v1")
    raw = "69 1234 5678"
    await _insert_legacy(generate_nullifier_hash(raw))  # pre-fix row from a direct API call
    assert (await _verify(raw)).status_code == 200
    rows = await _rows()
    assert len(rows) == 1 and rows[0][0] == generate_nullifier_hash(raw)


@pytest.mark.asyncio
@pytest.mark.parametrize("spelling", ["6912345678", "0030 691 234 5678", "+306912345678"])
async def test_revoke_accepts_another_spelling(monkeypatch, spelling) -> None:
    anchor = generate_nullifier_hash(CANONICAL)
    await _insert_legacy(anchor)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/identity/revoke", json={"nullifier_hash": anchor, "phone_number": spelling})
    assert response.status_code == 200, response.text
    assert (await _rows())[0][2] == "REVOKED"


@pytest.mark.asyncio
async def test_revoke_rejects_another_number() -> None:
    anchor = generate_nullifier_hash(CANONICAL)
    await _insert_legacy(anchor)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/identity/revoke", json={"nullifier_hash": anchor, "phone_number": "+306900000000"})
    assert response.status_code == 400


from nullifier import generate_nullifier_hash_v2  # noqa: E402


async def _insert(anchor: str, v2: str | None, pk: str = PUB_OLD) -> None:
    async with _engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO identity_records (nullifier_hash, nullifier_hash_v2, nullifier_version, public_key_hex, status) "
            "VALUES (:n, :v2, :ver, :p, 'ACTIVE')"),
            {"n": anchor, "v2": v2, "ver": "v2" if v2 else "v1", "p": pk})


@pytest.mark.asyncio
async def test_existing_duplicate_rows_do_not_cause_500_and_v2_is_not_moved(monkeypatch) -> None:
    # Pre-fix state: canonical row A (no v2) and a raw-spelling row B that owns the v2 anchor.
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "v2")
    raw = "69 1234 5678"
    canonical_v2 = generate_nullifier_hash_v2(CANONICAL)
    await _insert(generate_nullifier_hash(CANONICAL), None)
    await _insert(generate_nullifier_hash(raw), canonical_v2, pk="d" * 64)
    response = await _verify(raw)
    assert response.status_code == 200, response.text
    rows = await _rows()
    assert len(rows) == 2
    assert rows[1][1] == canonical_v2  # B keeps its v2 anchor
    assert rows[0][1] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("kdf", ["v1", "v2"])
async def test_row_created_from_the_leading_zero_form_is_found_canonically(monkeypatch, kdf) -> None:
    # v2 keeps the leading zero of "069…", so such rows had different v1 AND v2 anchors.
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", kdf)
    zero_form = "06912345678"
    await _insert(generate_nullifier_hash(zero_form), generate_nullifier_hash_v2(zero_form))
    response = await _verify(CANONICAL)
    assert response.status_code == 200, response.text
    assert len(await _rows()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("form", ["6912345678", "306912345678", "00306912345678", "06912345678"])
async def test_v1_only_row_from_any_standard_form_is_found(monkeypatch, form) -> None:
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "v1")
    await _insert(generate_nullifier_hash(form), None)
    response = await _verify("+30 69 1234 5678")
    assert response.status_code == 200, response.text
    rows = await _rows()
    assert len(rows) == 1 and rows[0][0] == generate_nullifier_hash(form)


@pytest.mark.asyncio
async def test_revoke_raw_anchor_with_canonical_spelling_via_v2(monkeypatch) -> None:
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "v2")
    raw = "69 1234 5678"
    anchor = generate_nullifier_hash(raw)
    await _insert(anchor, generate_nullifier_hash_v2(CANONICAL))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/identity/revoke", json={"nullifier_hash": anchor, "phone_number": CANONICAL})
    assert response.status_code == 200, response.text
    assert (await _rows())[0][2] == "REVOKED"


@pytest.mark.asyncio
async def test_row_reachable_only_through_the_leading_zero_v2_anchor(monkeypatch) -> None:
    # v1 from an exotic spelling (not one of the standard forms), v2 from "069…":
    # only the always-looked-up leading-zero v2 variant can find it.
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "v2")
    exotic = "069 1234 5678"
    await _insert(generate_nullifier_hash(exotic), generate_nullifier_hash_v2(exotic))
    response = await _verify(CANONICAL)
    assert response.status_code == 200, response.text
    assert len(await _rows()) == 1


@pytest.mark.asyncio
async def test_revoke_with_unknown_anchor_never_runs_the_memory_hard_kdf(monkeypatch) -> None:
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "v2")
    calls: list[str] = []
    real = identity.generate_nullifier_hash_v2
    monkeypatch.setattr(identity, "generate_nullifier_hash_v2", lambda p: (calls.append(p), real(p))[1])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/identity/revoke", json={"nullifier_hash": "f" * 64, "phone_number": CANONICAL})
    assert response.status_code == 400
    assert calls == []


def test_revoke_route_is_rate_limited() -> None:
    from rate_limit import limiter
    limits = limiter._route_limits.get("routers.identity.revoke_identity", [])
    assert [str(l.limit) for l in limits] == ["10 per 1 minute"]
