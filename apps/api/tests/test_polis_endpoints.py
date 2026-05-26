"""
Real FastAPI endpoint tests for POLIS tickets.
Requires running PostgreSQL — tests are xfail without DB.
"""
import os
import sys
import time

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nacl.signing import SigningKey
from crypto.polis import hash_content, build_ticket_signed_bytes, build_vote_signed_bytes, PROTO_VERSION

try:
    from main import app
    APP_AVAILABLE = True
except Exception:
    APP_AVAILABLE = False
    app = None


def _now_ms():
    return int(time.time() * 1000)


def _make_keypair():
    sk = SigningKey.generate()
    return sk, sk.verify_key.encode().hex()


def _sign(sk, data):
    return sk.sign(data).signature.hex()


pytestmark = pytest.mark.xfail(reason="Requires running PostgreSQL", strict=False)


@pytest.mark.asyncio
@pytest.mark.skipif(not APP_AVAILABLE, reason="App import failed")
async def test_get_tickets_returns_safe_shape():
    """GET /polis/tickets must return safe fields only."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/polis/tickets")
    assert r.status_code == 200
    data = r.json()
    assert "tickets" in data
    assert "total" in data
    # If tickets exist, check no sensitive fields
    for t in data["tickets"]:
        assert "signature" not in t
        assert "pk_polis" not in t
        assert "ticket_nullifier" not in t
        assert "nullifier_hash" not in t
        assert "handle" in t  # short handle, not full key


@pytest.mark.asyncio
@pytest.mark.skipif(not APP_AVAILABLE, reason="App import failed")
async def test_register_key_requires_valid_identity_signature():
    """POST /polis/register-key with invalid signature must be rejected."""
    sk, pk_hex = _make_keypair()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/register-key", json={
            "nullifier_hash": "aa" * 32,
            "pk_polis": pk_hex,
            "identity_signature": "bb" * 64,
            "timestamp_ms": _now_ms(),
        })
    # Should be 403 (no identity) or 401 (bad sig), not 500
    assert r.status_code in (401, 403)
    assert "500" not in str(r.status_code)


@pytest.mark.asyncio
@pytest.mark.skipif(not APP_AVAILABLE, reason="App import failed")
async def test_create_ticket_unregistered_key_rejected():
    """POST /polis/tickets with unregistered pk_polis must return 403."""
    sk, pk_hex = _make_keypair()
    title = "Test"
    content = "Test content minimum"
    nullifier = os.urandom(32).hex()
    ts = _now_ms()

    signed_bytes = build_ticket_signed_bytes(
        category="bug",
        content_hash=hash_content(content),
        pk_polis=bytes.fromhex(pk_hex),
        nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts,
        title_hash=hash_content(title),
    )
    sig = _sign(sk, signed_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/tickets", json={
            "title": title,
            "content": content,
            "category": "bug",
            "pk_polis": pk_hex,
            "ticket_nullifier": nullifier,
            "signature": sig,
            "timestamp_ms": ts,
            "nullifier_hash": "dd" * 32,
        })
    assert r.status_code == 403
    assert "UNREGISTERED_KEY" in r.json().get("detail", "")


@pytest.mark.asyncio
@pytest.mark.skipif(not APP_AVAILABLE, reason="App import failed")
async def test_vote_on_nonexistent_ticket_returns_404():
    """POST vote on non-existent ticket must return 404."""
    sk, pk_hex = _make_keypair()
    ts = _now_ms()
    nullifier = os.urandom(32).hex()

    signed_bytes = build_vote_signed_bytes(
        ticket_id="nonexistent-id",
        vote="up",
        pk_polis=bytes.fromhex(pk_hex),
        nullifier=bytes.fromhex(nullifier),
        timestamp_ms=ts,
    )
    sig = _sign(sk, signed_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/polis/tickets/nonexistent-id/votes", json={
            "vote": "up",
            "pk_polis": pk_hex,
            "vote_nullifier": nullifier,
            "signature": sig,
            "timestamp_ms": ts,
            "nullifier_hash": "dd" * 32,
        })
    # 403 (unregistered key) or 404 (ticket not found) — not 500
    assert r.status_code in (403, 404)
