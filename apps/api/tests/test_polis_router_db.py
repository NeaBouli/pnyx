"""
Real Router/DB tests for POLIS tickets using in-memory SQLite.
Tests actual FastAPI endpoints with dependency override for get_db.
Non-xfail — runs without PostgreSQL.
"""
import os
import sys
import time
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nacl.signing import SigningKey
from crypto.polis import (
    build_ticket_signed_bytes,
    build_vote_signed_bytes,
    hash_content,
    PROTO_VERSION,
)

# ─── Test DB Setup ───────────────────────────────────────────────────────────

# SQLite needs now() → replace with CURRENT_TIMESTAMP via connection event
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_engine = create_async_engine(TEST_DB_URL, echo=False)
_SessionLocal = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(_engine.sync_engine, "connect")
def _sqlite_now(dbapi_conn, _):
    """Register now() as alias for datetime('now') in SQLite."""
    dbapi_conn.create_function("now", 0, lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS identity_records (
    id INTEGER PRIMARY KEY,
    nullifier_hash TEXT UNIQUE NOT NULL,
    public_key_hex TEXT NOT NULL,
    status TEXT DEFAULT 'ACTIVE'
);
CREATE TABLE IF NOT EXISTS polis_identity_keys (
    nullifier_hash TEXT PRIMARY KEY,
    pk_polis TEXT UNIQUE NOT NULL,
    signature TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS polis_tickets (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT NOT NULL,
    pk_polis TEXT NOT NULL,
    ticket_nullifier TEXT UNIQUE NOT NULL,
    signature TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    up_votes INTEGER DEFAULT 0,
    down_votes INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS polis_votes (
    id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES polis_tickets(id),
    vote TEXT NOT NULL,
    pk_polis TEXT NOT NULL,
    vote_nullifier TEXT UNIQUE NOT NULL,
    signature TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticket_id, pk_polis)
);
"""


async def _get_test_db():
    async with _SessionLocal() as session:
        yield session


def _now_ms():
    return int(time.time() * 1000)


def _make_keypair():
    sk = SigningKey.generate()
    return sk, sk.verify_key.encode().hex()


def _sign(sk, data):
    return sk.sign(data).signature.hex()


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
async def setup_db():
    """Create schema + override get_db for each test."""
    from main import app
    from database import get_db

    async with _engine.begin() as conn:
        for stmt in SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(text(stmt))

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()

    # Drop tables
    async with _engine.begin() as conn:
        for tbl in ["polis_votes", "polis_tickets", "polis_identity_keys", "identity_records"]:
            await conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))


async def _seed_identity(nullifier_hash: str, public_key_hex: str):
    """Insert a verified identity into test DB."""
    async with _SessionLocal() as db:
        await db.execute(text(
            "INSERT INTO identity_records (nullifier_hash, public_key_hex, status) VALUES (:nh, :pk, 'ACTIVE')"
        ), {"nh": nullifier_hash, "pk": public_key_hex})
        await db.commit()


async def _register_key(nullifier_hash: str, pk_polis: str, identity_sk, identity_pk_hex: str):
    """Register pk_polis via the API endpoint."""
    from main import app
    ts = _now_ms()
    message = f"polis-register:{pk_polis}:{nullifier_hash}:{ts}".encode()
    sig = _sign(identity_sk, message)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/register-key", json={
            "nullifier_hash": nullifier_hash,
            "pk_polis": pk_polis,
            "identity_signature": sig,
            "timestamp_ms": ts,
        })
    return r


# ─── Tests ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_key_valid(setup_db):
    """Valid register-key inserts into polis_identity_keys."""
    from main import app
    id_sk, id_pk = _make_keypair()
    _, polis_pk = _make_keypair()
    nh = os.urandom(32).hex()

    await _seed_identity(nh, id_pk)
    r = await _register_key(nh, polis_pk, id_sk, id_pk)

    assert r.status_code == 201
    assert r.json()["status"] == "registered"

    # Verify DB
    async with _SessionLocal() as db:
        result = await db.execute(text("SELECT pk_polis FROM polis_identity_keys WHERE nullifier_hash = :nh"), {"nh": nh})
        row = result.fetchone()
        assert row is not None
        assert row[0] == polis_pk


@pytest.mark.asyncio
async def test_register_key_invalid_sig_rejected(setup_db):
    """Wrong identity key cannot register."""
    from main import app
    id_sk, id_pk = _make_keypair()
    attacker_sk, _ = _make_keypair()
    _, polis_pk = _make_keypair()
    nh = os.urandom(32).hex()

    await _seed_identity(nh, id_pk)

    ts = _now_ms()
    message = f"polis-register:{polis_pk}:{nh}:{ts}".encode()
    bad_sig = _sign(attacker_sk, message)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/register-key", json={
            "nullifier_hash": nh, "pk_polis": polis_pk,
            "identity_signature": bad_sig, "timestamp_ms": ts,
        })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_register_key_idempotent(setup_db):
    """Same key re-registration is OK."""
    id_sk, id_pk = _make_keypair()
    _, polis_pk = _make_keypair()
    nh = os.urandom(32).hex()

    await _seed_identity(nh, id_pk)
    r1 = await _register_key(nh, polis_pk, id_sk, id_pk)
    assert r1.status_code == 201

    r2 = await _register_key(nh, polis_pk, id_sk, id_pk)
    assert r2.status_code == 201
    assert r2.json()["status"] == "already_registered"


@pytest.mark.asyncio
async def test_register_key_different_key_same_nullifier_409(setup_db):
    """Different pk_polis for same nullifier → 409."""
    id_sk, id_pk = _make_keypair()
    _, polis_pk1 = _make_keypair()
    _, polis_pk2 = _make_keypair()
    nh = os.urandom(32).hex()

    await _seed_identity(nh, id_pk)
    r1 = await _register_key(nh, polis_pk1, id_sk, id_pk)
    assert r1.status_code == 201

    r2 = await _register_key(nh, polis_pk2, id_sk, id_pk)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_create_ticket_unregistered_rejected(setup_db):
    """Ticket with unregistered pk_polis → 403."""
    from main import app
    polis_sk, polis_pk = _make_keypair()
    nh = os.urandom(32).hex()
    title = "Test"
    content = "Test content minimum length"
    ts = _now_ms()
    nullifier = os.urandom(32).hex()

    signed_bytes = build_ticket_signed_bytes(
        category="bug", content_hash=hash_content(content),
        pk_polis=bytes.fromhex(polis_pk), nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts, title_hash=hash_content(title),
    )
    sig = _sign(polis_sk, signed_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/tickets", json={
            "title": title, "content": content, "category": "bug",
            "pk_polis": polis_pk, "ticket_nullifier": nullifier,
            "signature": sig, "timestamp_ms": ts, "nullifier_hash": nh,
        })
    assert r.status_code == 403
    assert "UNREGISTERED_KEY" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_ticket_registered_201(setup_db):
    """Ticket with registered pk_polis → 201 + DB row."""
    from main import app
    id_sk, id_pk = _make_keypair()
    polis_sk, polis_pk = _make_keypair()
    nh = os.urandom(32).hex()

    await _seed_identity(nh, id_pk)
    await _register_key(nh, polis_pk, id_sk, id_pk)

    title = "Real Bug Report"
    content = "The app crashes when pressing back"
    ts = _now_ms()
    nullifier = os.urandom(32).hex()

    signed_bytes = build_ticket_signed_bytes(
        category="bug", content_hash=hash_content(content),
        pk_polis=bytes.fromhex(polis_pk), nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts, title_hash=hash_content(title),
    )
    sig = _sign(polis_sk, signed_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/tickets", json={
            "title": title, "content": content, "category": "bug",
            "pk_polis": polis_pk, "ticket_nullifier": nullifier,
            "signature": sig, "timestamp_ms": ts, "nullifier_hash": nh,
        })
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["status"] == "pending"

    # Verify in DB
    async with _SessionLocal() as db:
        result = await db.execute(text("SELECT title, category FROM polis_tickets WHERE id = :id"), {"id": data["id"]})
        row = result.fetchone()
        assert row is not None
        assert row[0] == title
        assert row[1] == "bug"


@pytest.mark.asyncio
async def test_duplicate_ticket_409(setup_db):
    """Same ticket_nullifier twice → 409."""
    from main import app
    id_sk, id_pk = _make_keypair()
    polis_sk, polis_pk = _make_keypair()
    nh = os.urandom(32).hex()

    await _seed_identity(nh, id_pk)
    await _register_key(nh, polis_pk, id_sk, id_pk)

    title = "Dup"
    content = "Duplicate content test"
    ts = _now_ms()
    nullifier = os.urandom(32).hex()

    signed_bytes = build_ticket_signed_bytes(
        category="proposal", content_hash=hash_content(content),
        pk_polis=bytes.fromhex(polis_pk), nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts, title_hash=hash_content(title),
    )
    sig = _sign(polis_sk, signed_bytes)

    payload = {
        "title": title, "content": content, "category": "proposal",
        "pk_polis": polis_pk, "ticket_nullifier": nullifier,
        "signature": sig, "timestamp_ms": ts, "nullifier_hash": nh,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.post("/api/v1/polis/tickets", json=payload)
        assert r1.status_code == 201

        r2 = await client.post("/api/v1/polis/tickets", json=payload)
        assert r2.status_code in (400, 409)  # 400 from validate_ticket or 409 from IntegrityError
        assert "DUPLICATE" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_vote_valid_201(setup_db):
    """Valid vote → 201 + counter increment."""
    from main import app
    # Owner
    id1_sk, id1_pk = _make_keypair()
    polis1_sk, polis1_pk = _make_keypair()
    nh1 = os.urandom(32).hex()
    await _seed_identity(nh1, id1_pk)
    await _register_key(nh1, polis1_pk, id1_sk, id1_pk)

    # Voter
    id2_sk, id2_pk = _make_keypair()
    polis2_sk, polis2_pk = _make_keypair()
    nh2 = os.urandom(32).hex()
    await _seed_identity(nh2, id2_pk)
    await _register_key(nh2, polis2_pk, id2_sk, id2_pk)

    # Create ticket
    title = "Vote test"
    content = "Content for vote test ticket"
    ts = _now_ms()
    t_null = os.urandom(32).hex()
    t_bytes = build_ticket_signed_bytes(
        category="bug", content_hash=hash_content(content),
        pk_polis=bytes.fromhex(polis1_pk), nullifier=bytes.fromhex(t_null),
        timestamp_ms=ts, title_hash=hash_content(title),
    )
    t_sig = _sign(polis1_sk, t_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/tickets", json={
            "title": title, "content": content, "category": "bug",
            "pk_polis": polis1_pk, "ticket_nullifier": t_null,
            "signature": t_sig, "timestamp_ms": ts, "nullifier_hash": nh1,
        })
    ticket_id = r.json()["id"]

    # Vote
    v_null = os.urandom(32).hex()
    v_bytes = build_vote_signed_bytes(
        ticket_id=ticket_id, vote="up",
        pk_polis=bytes.fromhex(polis2_pk), nullifier=bytes.fromhex(v_null),
        timestamp_ms=ts,
    )
    v_sig = _sign(polis2_sk, v_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(f"/api/v1/polis/tickets/{ticket_id}/votes", json={
            "vote": "up", "pk_polis": polis2_pk, "vote_nullifier": v_null,
            "signature": v_sig, "timestamp_ms": ts, "nullifier_hash": nh2,
        })
    assert r.status_code == 201

    # Check counter
    async with _SessionLocal() as db:
        result = await db.execute(text("SELECT up_votes FROM polis_tickets WHERE id = :id"), {"id": ticket_id})
        assert result.fetchone()[0] == 1


@pytest.mark.asyncio
async def test_self_vote_rejected(setup_db):
    """Owner voting on own ticket → 400."""
    from main import app
    id_sk, id_pk = _make_keypair()
    polis_sk, polis_pk = _make_keypair()
    nh = os.urandom(32).hex()
    await _seed_identity(nh, id_pk)
    await _register_key(nh, polis_pk, id_sk, id_pk)

    title = "Self vote"
    content = "Self vote test content"
    ts = _now_ms()
    t_null = os.urandom(32).hex()
    t_bytes = build_ticket_signed_bytes(
        category="bug", content_hash=hash_content(content),
        pk_polis=bytes.fromhex(polis_pk), nullifier=bytes.fromhex(t_null),
        timestamp_ms=ts, title_hash=hash_content(title),
    )
    t_sig = _sign(polis_sk, t_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/tickets", json={
            "title": title, "content": content, "category": "bug",
            "pk_polis": polis_pk, "ticket_nullifier": t_null,
            "signature": t_sig, "timestamp_ms": ts, "nullifier_hash": nh,
        })
    ticket_id = r.json()["id"]

    v_null = os.urandom(32).hex()
    v_bytes = build_vote_signed_bytes(
        ticket_id=ticket_id, vote="up",
        pk_polis=bytes.fromhex(polis_pk), nullifier=bytes.fromhex(v_null),
        timestamp_ms=ts,
    )
    v_sig = _sign(polis_sk, v_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(f"/api/v1/polis/tickets/{ticket_id}/votes", json={
            "vote": "up", "pk_polis": polis_pk, "vote_nullifier": v_null,
            "signature": v_sig, "timestamp_ms": ts, "nullifier_hash": nh,
        })
    assert r.status_code == 400
    assert "SELF_VOTE" in r.json()["detail"]


@pytest.mark.asyncio
async def test_get_tickets_safe_fields(setup_db):
    """GET /polis/tickets must not expose pk_polis, nullifier, signature."""
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/polis/tickets")
    assert r.status_code == 200
    data = r.json()
    assert "tickets" in data
    for t in data.get("tickets", []):
        assert "pk_polis" not in t
        assert "ticket_nullifier" not in t
        assert "signature" not in t
        assert "nullifier_hash" not in t


# ─── Edge cases requested by Codex ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_same_pk_polis_different_nullifier_409(setup_db):
    """Same pk_polis registered to a different nullifier → 409."""
    from main import app
    id1_sk, id1_pk = _make_keypair()
    id2_sk, id2_pk = _make_keypair()
    _, polis_pk = _make_keypair()  # same polis key for both
    nh1 = os.urandom(32).hex()
    nh2 = os.urandom(32).hex()

    await _seed_identity(nh1, id1_pk)
    await _seed_identity(nh2, id2_pk)

    r1 = await _register_key(nh1, polis_pk, id1_sk, id1_pk)
    assert r1.status_code == 201

    r2 = await _register_key(nh2, polis_pk, id2_sk, id2_pk)
    assert r2.status_code == 409
    assert "KEY_CONFLICT" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_wrong_nullifier_pk_pair_rejected(setup_db):
    """Ticket with pk_polis registered to different nullifier → exact 403 KEY_MISMATCH."""
    from main import app
    # User 1: registers polis1_pk to nh1
    id1_sk, id1_pk = _make_keypair()
    polis1_sk, polis1_pk = _make_keypair()
    nh1 = os.urandom(32).hex()
    await _seed_identity(nh1, id1_pk)
    await _register_key(nh1, polis1_pk, id1_sk, id1_pk)

    # User 2: registers polis2_pk to nh2
    id2_sk, id2_pk = _make_keypair()
    polis2_sk, polis2_pk = _make_keypair()
    nh2 = os.urandom(32).hex()
    await _seed_identity(nh2, id2_pk)
    await _register_key(nh2, polis2_pk, id2_sk, id2_pk)

    # Now: submit ticket with nh2 (User 2's nullifier) but polis1_pk (User 1's key)
    title = "Wrong pair"
    content = "Testing wrong nullifier/pk pair"
    ts = _now_ms()
    nullifier = os.urandom(32).hex()

    signed_bytes = build_ticket_signed_bytes(
        category="bug", content_hash=hash_content(content),
        pk_polis=bytes.fromhex(polis1_pk), nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts, title_hash=hash_content(title),
    )
    sig = _sign(polis1_sk, signed_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/tickets", json={
            "title": title, "content": content, "category": "bug",
            "pk_polis": polis1_pk, "ticket_nullifier": nullifier,
            "signature": sig, "timestamp_ms": ts, "nullifier_hash": nh2,
        })
    assert r.status_code == 403
    assert "KEY_MISMATCH" in r.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_vote_same_nullifier(setup_db):
    """Same vote_nullifier twice → controlled 400 (validator catches)."""
    from main import app
    id1_sk, id1_pk = _make_keypair()
    polis1_sk, polis1_pk = _make_keypair()
    nh1 = os.urandom(32).hex()
    await _seed_identity(nh1, id1_pk)
    await _register_key(nh1, polis1_pk, id1_sk, id1_pk)

    id2_sk, id2_pk = _make_keypair()
    polis2_sk, polis2_pk = _make_keypair()
    nh2 = os.urandom(32).hex()
    await _seed_identity(nh2, id2_pk)
    await _register_key(nh2, polis2_pk, id2_sk, id2_pk)

    title = "Dup vote nullifier"
    content = "Duplicate vote nullifier test"
    ts = _now_ms()
    t_null = os.urandom(32).hex()
    t_bytes = build_ticket_signed_bytes(
        category="bug", content_hash=hash_content(content),
        pk_polis=bytes.fromhex(polis1_pk), nullifier=bytes.fromhex(t_null),
        timestamp_ms=ts, title_hash=hash_content(title),
    )
    t_sig = _sign(polis1_sk, t_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/tickets", json={
            "title": title, "content": content, "category": "bug",
            "pk_polis": polis1_pk, "ticket_nullifier": t_null,
            "signature": t_sig, "timestamp_ms": ts, "nullifier_hash": nh1,
        })
    ticket_id = r.json()["id"]

    v_null = os.urandom(32).hex()
    v_bytes = build_vote_signed_bytes(
        ticket_id=ticket_id, vote="up",
        pk_polis=bytes.fromhex(polis2_pk), nullifier=bytes.fromhex(v_null),
        timestamp_ms=ts,
    )
    v_sig = _sign(polis2_sk, v_bytes)
    vote_payload = {
        "vote": "up", "pk_polis": polis2_pk, "vote_nullifier": v_null,
        "signature": v_sig, "timestamp_ms": ts, "nullifier_hash": nh2,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.post(f"/api/v1/polis/tickets/{ticket_id}/votes", json=vote_payload)
        assert r1.status_code == 201

        r2 = await client.post(f"/api/v1/polis/tickets/{ticket_id}/votes", json=vote_payload)
        assert r2.status_code in (400, 409)
        assert "DUPLICATE" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_vote_db_unique_constraint(setup_db):
    """Same voter (pk_polis) + same ticket but different vote_nullifier → 409 via DB UNIQUE(ticket_id, pk_polis)."""
    from main import app
    id1_sk, id1_pk = _make_keypair()
    polis1_sk, polis1_pk = _make_keypair()
    nh1 = os.urandom(32).hex()
    await _seed_identity(nh1, id1_pk)
    await _register_key(nh1, polis1_pk, id1_sk, id1_pk)

    id2_sk, id2_pk = _make_keypair()
    polis2_sk, polis2_pk = _make_keypair()
    nh2 = os.urandom(32).hex()
    await _seed_identity(nh2, id2_pk)
    await _register_key(nh2, polis2_pk, id2_sk, id2_pk)

    title = "DB unique vote"
    content = "Test DB unique constraint on (ticket_id, pk_polis)"
    ts = _now_ms()
    t_null = os.urandom(32).hex()
    t_bytes = build_ticket_signed_bytes(
        category="bug", content_hash=hash_content(content),
        pk_polis=bytes.fromhex(polis1_pk), nullifier=bytes.fromhex(t_null),
        timestamp_ms=ts, title_hash=hash_content(title),
    )
    t_sig = _sign(polis1_sk, t_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/tickets", json={
            "title": title, "content": content, "category": "bug",
            "pk_polis": polis1_pk, "ticket_nullifier": t_null,
            "signature": t_sig, "timestamp_ms": ts, "nullifier_hash": nh1,
        })
    ticket_id = r.json()["id"]

    # First vote
    v_null1 = os.urandom(32).hex()
    v_bytes1 = build_vote_signed_bytes(
        ticket_id=ticket_id, vote="up",
        pk_polis=bytes.fromhex(polis2_pk), nullifier=bytes.fromhex(v_null1),
        timestamp_ms=ts,
    )
    v_sig1 = _sign(polis2_sk, v_bytes1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.post(f"/api/v1/polis/tickets/{ticket_id}/votes", json={
            "vote": "up", "pk_polis": polis2_pk, "vote_nullifier": v_null1,
            "signature": v_sig1, "timestamp_ms": ts, "nullifier_hash": nh2,
        })
        assert r1.status_code == 201

        # Second vote: DIFFERENT nullifier, same pk_polis + same ticket → DB unique
        v_null2 = os.urandom(32).hex()
        v_bytes2 = build_vote_signed_bytes(
            ticket_id=ticket_id, vote="down",
            pk_polis=bytes.fromhex(polis2_pk), nullifier=bytes.fromhex(v_null2),
            timestamp_ms=ts,
        )
        v_sig2 = _sign(polis2_sk, v_bytes2)

        r2 = await client.post(f"/api/v1/polis/tickets/{ticket_id}/votes", json={
            "vote": "down", "pk_polis": polis2_pk, "vote_nullifier": v_null2,
            "signature": v_sig2, "timestamp_ms": ts, "nullifier_hash": nh2,
        })
        assert r2.status_code == 409
        assert "DUPLICATE" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_get_tickets_safe_fields_after_insert(setup_db):
    """GET /polis/tickets with real data must not expose sensitive fields."""
    from main import app
    id_sk, id_pk = _make_keypair()
    polis_sk, polis_pk = _make_keypair()
    nh = os.urandom(32).hex()

    await _seed_identity(nh, id_pk)
    await _register_key(nh, polis_pk, id_sk, id_pk)

    title = "Safe fields test"
    content = "Testing GET response shape with real data"
    ts = _now_ms()
    nullifier = os.urandom(32).hex()

    signed_bytes = build_ticket_signed_bytes(
        category="proposal", content_hash=hash_content(content),
        pk_polis=bytes.fromhex(polis_pk), nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts, title_hash=hash_content(title),
    )
    sig = _sign(polis_sk, signed_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/polis/tickets", json={
            "title": title, "content": content, "category": "proposal",
            "pk_polis": polis_pk, "ticket_nullifier": nullifier,
            "signature": sig, "timestamp_ms": ts, "nullifier_hash": nh,
        })

        r = await client.get("/api/v1/polis/tickets")

    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1

    ticket = data["tickets"][0]
    # Must have safe fields
    assert "id" in ticket
    assert "title" in ticket
    assert "category" in ticket
    assert "handle" in ticket
    assert "status" in ticket
    assert "up_votes" in ticket
    assert "down_votes" in ticket
    assert "created_at" in ticket
    assert ticket["title"] == title

    # Must NOT have sensitive fields
    assert "pk_polis" not in ticket
    assert "ticket_nullifier" not in ticket
    assert "signature" not in ticket
    assert "nullifier_hash" not in ticket
    assert "content" not in ticket
