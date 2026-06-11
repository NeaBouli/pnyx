"""GH#112 Gate 2 disabled ZK verifier endpoint tests."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from database import get_db
from main import app
from models import BillStatus, GovernanceLevel, ZkIdentityCommitment, ZkVoteTierLock
from routers import zk

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "gh112_s10_fixture.json"


def _native_proof() -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text())
    return json.loads(fixture["proof"])


class _FakeScalars:
    def __init__(self, values: list[SimpleNamespace]):
        self._values = values

    def all(self) -> list[SimpleNamespace]:
        return self._values


class _FakeResult:
    def __init__(self, values: list[SimpleNamespace]):
        self._values = values

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._values)


class _FakeDb:
    def __init__(self, receipts: list[SimpleNamespace]):
        self.receipts = receipts

    async def execute(self, _statement):
        return _FakeResult(self.receipts)


class _FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeSequenceDb:
    def __init__(self, values: list[object | None]):
        self.values = list(values)
        self.executed = []
        self.added = []
        self.committed = False
        self.rolled_back = False
        self._next_id = 1

    async def execute(self, statement):
        self.executed.append(statement)
        return _FakeScalarResult(self.values.pop(0))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = self._next_id
                self._next_id += 1

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def _zk_opt_in_payload() -> dict:
    return {
        "nullifier_hash": "a" * 64,
        "bill_id": "GR-0490a766",
        "commitment": "12345678901234567890",
        "signature_hex": "b" * 128,
    }


async def _override_with(fake_db):
    yield fake_db


@pytest.mark.asyncio
async def test_zk_status_is_fail_closed_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ZK_VOTING_ENABLED", raising=False)
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/zk/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["production_enabled"] is False
    assert payload["verifier_enabled"] is False
    assert payload["opt_in_enabled"] is False
    assert payload["canary_enabled"] is False
    assert payload["merkle_tree_depth"] == 16
    assert payload["message_el"] == "Η παραγωγική ZK ψηφοφορία δεν είναι ενεργή ακόμη."


@pytest.mark.asyncio
async def test_zk_status_requires_parent_flag_for_subfeatures(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/zk/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["production_enabled"] is True
    assert payload["verifier_enabled"] is True
    assert payload["opt_in_enabled"] is True
    assert payload["canary_enabled"] is True


@pytest.mark.asyncio
async def test_zk_status_keeps_opt_in_closed_without_tier1_guard(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.delenv("ZK_TIER1_GUARD_ENABLED", raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/zk/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["production_enabled"] is True
    assert payload["opt_in_enabled"] is False


@pytest.mark.asyncio
async def test_zk_opt_in_is_fail_closed_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ZK_VOTING_ENABLED", raising=False)
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    fake_db = _FakeSequenceDb([])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/zk/opt-in", json=_zk_opt_in_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "ZK opt-in is not enabled"
    assert fake_db.executed == []
    assert fake_db.added == []


@pytest.mark.asyncio
async def test_zk_opt_in_creates_commitment_and_private_tier_lock(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(zk, "verify_signature", lambda *_args: True)
    identity = SimpleNamespace(
        id=7,
        public_key_hex="c" * 64,
        periferia_id=None,
        dimos_id=None,
    )
    bill = SimpleNamespace(
        id="GR-0490a766",
        status=BillStatus.ACTIVE,
        governance_level=GovernanceLevel.NATIONAL,
    )
    fake_db = _FakeSequenceDb([identity, bill, None, None])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/zk/opt-in", json=_zk_opt_in_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending_root"
    assert payload["vote_scope_id"] == "bill:GR-0490a766"
    assert payload["tier_locked"] is True
    assert "tier_guard_hash" not in str(payload)
    assert "identity_record_id" not in str(payload)
    assert fake_db.committed is True
    assert any(isinstance(value, ZkIdentityCommitment) for value in fake_db.added)
    assert any(isinstance(value, ZkVoteTierLock) for value in fake_db.added)


@pytest.mark.asyncio
async def test_zk_opt_in_rejects_existing_tier1_vote(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(zk, "verify_signature", lambda *_args: True)
    identity = SimpleNamespace(id=7, public_key_hex="c" * 64, periferia_id=None, dimos_id=None)
    bill = SimpleNamespace(
        id="GR-0490a766",
        status=BillStatus.ACTIVE,
        governance_level=GovernanceLevel.NATIONAL,
    )
    fake_db = _FakeSequenceDb([identity, bill, 99])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/zk/opt-in", json=_zk_opt_in_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert fake_db.committed is False
    assert fake_db.added == []


@pytest.mark.asyncio
async def test_zk_opt_in_rejects_invalid_signature(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setattr(zk, "verify_signature", lambda *_args: False)
    identity = SimpleNamespace(id=7, public_key_hex="c" * 64, periferia_id=None, dimos_id=None)
    bill = SimpleNamespace(
        id="GR-0490a766",
        status=BillStatus.ACTIVE,
        governance_level=GovernanceLevel.NATIONAL,
    )
    fake_db = _FakeSequenceDb([identity, bill])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/zk/opt-in", json=_zk_opt_in_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert fake_db.committed is False
    assert fake_db.added == []


@pytest.mark.asyncio
async def test_zk_receipts_endpoint_returns_public_payload_only() -> None:
    receipt = SimpleNamespace(
        vote_scope_id="bill:GR-0490a766",
        semaphore_nullifier="123",
        merkle_root="456",
        merkle_depth=16,
        signal_hash="789",
        external_nullifier="101112",
        proof_public_json={"proof": {"pi_a": ["1", "2"]}},
        verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
        circuit_version="semaphore-v4-depth16",
        arweave_tx_id=None,
        arweave_pending=True,
        publication_bucket="2026-06-12T00",
        tier_guard_hash="private",
        tier1_nullifier_hash="private",
        identity_record_id=7,
    )
    fake_db = _FakeDb([receipt])

    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/receipts/bill:GR-0490a766")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["vote_scope_id"] == "bill:GR-0490a766"
    assert payload["limit"] == 100
    assert payload["offset"] == 0
    assert payload["receipts"][0]["arweave_pending"] is True

    serialized = json.dumps(payload)
    assert "tier_guard_hash" not in serialized
    assert "tier1_nullifier_hash" not in serialized
    assert "identity_record_id" not in serialized


@pytest.mark.asyncio
async def test_zk_receipts_endpoint_returns_empty_list() -> None:
    fake_db = _FakeDb([])

    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/receipts/bill:EMPTY")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"vote_scope_id": "bill:EMPTY", "limit": 100, "offset": 0, "receipts": []}


@pytest.mark.asyncio
async def test_zk_receipts_endpoint_rejects_invalid_scope() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/zk/receipts/not-a-scope")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_zk_verify_endpoint_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ZK_VOTING_ENABLED", raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/zk/verify", json={"proof": _native_proof()})

    assert response.status_code == 503
    assert response.json()["detail"] == "ZK voting verifier is not enabled"


@pytest.mark.asyncio
async def test_zk_verify_endpoint_accepts_s10_fixture_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/zk/verify", json={"proof": _native_proof()})

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["proof_verified"] is True
    assert payload["merkle_tree_depth"] == 16
    assert payload["verifier_version"] == "py-ecc-groth16-bn254:v1:semaphore-v4-depth16"


@pytest.mark.asyncio
async def test_zk_verify_endpoint_rejects_mutated_fixture_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    proof = _native_proof()
    proof["scope"] = str(int(proof["scope"]) + 1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/zk/verify", json={"proof": proof})

    assert response.status_code == 200
    assert response.json()["proof_verified"] is False
