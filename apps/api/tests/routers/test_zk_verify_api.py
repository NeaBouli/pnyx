"""GH#112 Gate 2 disabled ZK verifier endpoint tests."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from database import get_db
from main import app
from models import BillStatus, GovernanceLevel, ZkIdentityCommitment, ZkMerkleRoot, ZkVoteReceipt, ZkVoteTierLock
from routers import zk
from services.zk_proof_binding import canonical_zk_message_value, canonical_zk_scope_value
from services.zk_merkle_root import poseidon2

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
    def __init__(self, values: list[object]):
        self._values = values

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._values)

    def scalar_one_or_none(self):
        return self._values[0] if self._values else None


class _FakeDb:
    def __init__(self, receipts: list[SimpleNamespace]):
        self.receipts = receipts

    async def execute(self, _statement):
        return _FakeResult(self.receipts)


class _FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value

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
        value = self.values.pop(0)
        if isinstance(value, list):
            return _FakeResult(value)
        return _FakeScalarResult(value)

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

    async def refresh(self, value):
        if getattr(value, "id", None) is None:
            value.id = self._next_id
            self._next_id += 1


def _zk_opt_in_payload() -> dict:
    return {
        "nullifier_hash": "a" * 64,
        "bill_id": "GR-0490a766",
        "commitment": "12345678901234567890",
        "signature_hex": "b" * 128,
    }


def _public_parliament_bill() -> SimpleNamespace:
    return SimpleNamespace(
        id="GR-0490a766",
        status=BillStatus.ACTIVE,
        governance_level=GovernanceLevel.NATIONAL,
        source="PARLIAMENT",
        admin_hidden=False,
        forum_topic_id=438,
        arweave_tx_id="ar_tx",
    )


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
async def test_zk_scope_status_requires_exact_production_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", "bill:OTHER")
    fake_db = _FakeSequenceDb([_public_parliament_bill(), 0, None])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/scopes/bill:GR-0490a766/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowlisted"] is False
    assert payload["can_opt_in"] is False
    assert payload["can_vote"] is False


@pytest.mark.asyncio
async def test_zk_scope_status_allows_opt_in_for_exact_public_scope(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", "bill:GR-0490a766")
    fake_db = _FakeSequenceDb([_public_parliament_bill(), 1, None])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/scopes/bill:GR-0490a766/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowlisted"] is True
    assert payload["active_commitments"] == 1
    assert payload["root_published"] is False
    assert payload["can_opt_in"] is True
    assert payload["can_vote"] is False


@pytest.mark.asyncio
async def test_zk_scope_status_reports_vote_ready_only_after_root(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", "bill:GR-0490a766")
    root = SimpleNamespace(id=1, status="OPEN")
    fake_db = _FakeSequenceDb([_public_parliament_bill(), 1, root])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/scopes/bill:GR-0490a766/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowlisted"] is True
    assert payload["root_published"] is True
    assert payload["can_opt_in"] is True
    assert payload["can_vote"] is True


@pytest.mark.asyncio
async def test_zk_canary_preflight_reports_safe_hidden_scope_without_private_fields(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_ROOT_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    bill = SimpleNamespace(
        id="ZK-CANARY-001",
        status=BillStatus.ACTIVE,
        source="ZK_CANARY",
        admin_hidden=True,
        forum_topic_id=None,
        arweave_tx_id=None,
    )
    root = SimpleNamespace(group_size=1, status="OPEN")
    fake_db = _FakeSequenceDb([bill, 1, 1, 0, root])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/zk/canary/preflight/bill:ZK-CANARY-001",
                headers={"Authorization": "Bearer dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowlisted"] is True
    assert payload["bill_exists"] is True
    assert payload["bill_admin_hidden"] is True
    assert payload["bill_source"] == "ZK_CANARY"
    assert payload["forum_topic_absent"] is True
    assert payload["arweave_absent"] is True
    assert payload["active_commitments"] == 1
    assert payload["tier_locks"] == 1
    assert payload["receipts"] == 0
    assert payload["latest_root_exists"] is True
    assert payload["ready_for_canary_opt_in"] is True
    assert payload["ready_to_publish_root"] is True
    assert payload["private_fields_exposed"] is False
    serialized = json.dumps(payload)
    assert "tier_guard_hash" not in serialized
    assert "identity_record_id" not in serialized
    assert "nullifier_hash" not in serialized


@pytest.mark.asyncio
async def test_zk_canary_preflight_stays_not_ready_for_public_bill(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_ROOT_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    bill = SimpleNamespace(
        id="GR-0490a766",
        status=BillStatus.ACTIVE,
        source="PARLIAMENT",
        admin_hidden=False,
        forum_topic_id=438,
        arweave_tx_id="ar_tx",
    )
    fake_db = _FakeSequenceDb([bill, 2, 0, 0, None])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/zk/canary/preflight/bill:GR-0490a766",
                headers={"Authorization": "Bearer dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowlisted"] is False
    assert payload["bill_admin_hidden"] is False
    assert payload["bill_source"] == "PARLIAMENT"
    assert payload["forum_topic_absent"] is False
    assert payload["arweave_absent"] is False
    assert payload["ready_for_canary_opt_in"] is False
    assert payload["ready_to_publish_root"] is False


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
    monkeypatch.setenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", "bill:GR-0490a766")
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
    stored_commitment = next(value for value in fake_db.added if isinstance(value, ZkIdentityCommitment))
    assert stored_commitment.vote_scope_id == "bill:GR-0490a766"


@pytest.mark.asyncio
async def test_zk_opt_in_rejects_existing_tier1_vote(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", "bill:GR-0490a766")
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
    monkeypatch.setenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", "bill:GR-0490a766")
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
async def test_zk_opt_in_canary_rejects_non_allowlisted_scope(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    monkeypatch.setattr(zk, "verify_signature", lambda *_args: True)
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

    assert response.status_code == 403
    assert response.json()["detail"] == "ZK canary scope is not allowed"
    assert fake_db.committed is False
    assert fake_db.added == []


@pytest.mark.asyncio
async def test_zk_opt_in_canary_rejects_allowlisted_public_bill(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:GR-0490a766")
    monkeypatch.setattr(zk, "verify_signature", lambda *_args: True)
    identity = SimpleNamespace(id=7, public_key_hex="c" * 64, periferia_id=None, dimos_id=None)
    fake_db = _FakeSequenceDb([identity, _public_parliament_bill()])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/zk/opt-in", json=_zk_opt_in_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "ZK canary bill is not isolated"
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
async def test_zk_receipts_canary_rejects_allowlisted_public_bill(monkeypatch) -> None:
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:GR-0490a766")
    fake_db = _FakeSequenceDb([_public_parliament_bill()])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/receipts/bill:GR-0490a766")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "ZK canary bill is not isolated"


@pytest.mark.asyncio
async def test_zk_current_root_endpoint_returns_public_payload_only() -> None:
    root = SimpleNamespace(
        id=42,
        vote_scope_id="bill:GR-0490a766",
        merkle_root="123",
        merkle_depth=1,
        group_size=2,
        commitment_version="semaphore-v4",
        status="OPEN",
        tier_guard_hash="private",
        identity_record_id=7,
    )
    fake_db = _FakeDb([root])

    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/roots/bill:GR-0490a766")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "vote_scope_id": "bill:GR-0490a766",
        "merkle_root": "123",
        "merkle_depth": 1,
        "group_size": 2,
        "commitment_version": "semaphore-v4",
        "status": "OPEN",
        "root_id": 42,
    }
    assert "tier_guard_hash" not in json.dumps(payload)
    assert "identity_record_id" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_zk_current_root_endpoint_returns_404_for_empty_scope() -> None:
    fake_db = _FakeDb([])

    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/roots/bill:EMPTY")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "ZK root not found"


@pytest.mark.asyncio
async def test_zk_current_root_canary_rejects_allowlisted_public_bill(monkeypatch) -> None:
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:GR-0490a766")
    fake_db = _FakeSequenceDb([_public_parliament_bill()])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/roots/bill:GR-0490a766")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "ZK canary bill is not isolated"


@pytest.mark.asyncio
async def test_zk_root_members_endpoint_returns_public_commitments_only(monkeypatch) -> None:
    monkeypatch.delenv("ZK_CANARY_ENABLED", raising=False)
    root = SimpleNamespace(
        id=42,
        vote_scope_id="bill:GR-0490a766",
        merkle_root=str(poseidon2(1, 2)),
        merkle_depth=16,
        group_size=2,
        commitment_version="semaphore-v4",
        status="OPEN",
        tier_guard_hash="private",
        identity_record_id=7,
    )
    fake_db = _FakeSequenceDb([_public_parliament_bill(), root, ["1", "2"]])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/roots/bill:GR-0490a766/members")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["members"] == ["1", "2"]
    assert payload["merkle_root"] == str(poseidon2(1, 2))
    assert payload["group_size"] == 2
    serialized = json.dumps(payload)
    assert "tier_guard_hash" not in serialized
    assert "identity_record_id" not in serialized


@pytest.mark.asyncio
async def test_zk_root_members_endpoint_rejects_stale_root(monkeypatch) -> None:
    monkeypatch.delenv("ZK_CANARY_ENABLED", raising=False)
    root = SimpleNamespace(
        id=42,
        vote_scope_id="bill:GR-0490a766",
        merkle_root=str(poseidon2(1, 2)),
        merkle_depth=1,
        group_size=2,
        commitment_version="semaphore-v4",
        status="OPEN",
    )
    fake_db = _FakeSequenceDb([_public_parliament_bill(), root, ["1", "2", "3"]])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/roots/bill:GR-0490a766/members")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "ZK root is stale; publish a fresh root before proof generation"


@pytest.mark.asyncio
async def test_zk_root_members_canary_rejects_non_allowlisted_scope(monkeypatch) -> None:
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    fake_db = _FakeSequenceDb([])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/roots/bill:GR-0490a766/members")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "ZK canary scope is not allowed"
    assert fake_db.executed == []


@pytest.mark.asyncio
async def test_zk_root_members_canary_rejects_allowlisted_public_bill(monkeypatch) -> None:
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:GR-0490a766")
    fake_db = _FakeSequenceDb([_public_parliament_bill()])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/zk/roots/bill:GR-0490a766/members")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "ZK canary bill is not isolated"


@pytest.mark.asyncio
async def test_zk_root_publish_is_fail_closed_even_for_admin(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.delenv("ZK_ROOT_PUBLICATION_ENABLED", raising=False)
    fake_db = _FakeSequenceDb([])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/roots/bill:GR-0490a766/publish",
                headers={"Authorization": "Bearer dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "ZK root publication is not enabled"
    assert fake_db.executed == []
    assert fake_db.added == []


@pytest.mark.asyncio
async def test_zk_root_publish_requires_admin(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ZK_ROOT_PUBLICATION_ENABLED", "true")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/zk/roots/bill:GR-0490a766/publish")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_zk_root_publish_requires_production_scope_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.setenv("ZK_ROOT_PUBLICATION_ENABLED", "true")
    monkeypatch.delenv("ZK_CANARY_ENABLED", raising=False)
    monkeypatch.delenv("ZK_GLOBAL_ROLLOUT_ENABLED", raising=False)
    monkeypatch.delenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", raising=False)
    fake_db = _FakeSequenceDb([])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/roots/bill:GR-0490a766/publish",
                headers={"Authorization": "Bearer dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "ZK production scope allowlist is not configured"
    assert fake_db.executed == []


@pytest.mark.asyncio
async def test_zk_root_publish_creates_root_from_public_commitments(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.setenv("ZK_ROOT_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", "bill:GR-0490a766")
    fake_db = _FakeSequenceDb([_public_parliament_bill(), ["1", "2"], None])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/roots/bill:GR-0490a766/publish",
                headers={"Authorization": "Bearer dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] is True
    assert payload["vote_scope_id"] == "bill:GR-0490a766"
    assert payload["merkle_root"] == str(poseidon2(1, 2))
    assert payload["merkle_depth"] == 16
    assert payload["group_size"] == 2
    assert payload["root_id"] == 1
    assert fake_db.committed is True
    assert any(isinstance(value, ZkMerkleRoot) for value in fake_db.added)
    assert "tier_guard_hash" not in json.dumps(payload)
    assert "identity_record_id" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_zk_root_publish_returns_existing_root_without_duplicate(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.setenv("ZK_ROOT_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", "bill:GR-0490a766")
    existing = SimpleNamespace(
        id=9,
        vote_scope_id="bill:GR-0490a766",
        merkle_root=str(poseidon2(1, 2)),
        merkle_depth=1,
        group_size=2,
        commitment_version="semaphore-v4",
        status="OPEN",
    )
    fake_db = _FakeSequenceDb([_public_parliament_bill(), ["1", "2"], existing])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/roots/bill:GR-0490a766/publish",
                headers={"Authorization": "Bearer dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["created"] is False
    assert fake_db.added == []
    assert fake_db.committed is False


@pytest.mark.asyncio
async def test_zk_root_publish_canary_rejects_non_allowlisted_scope(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.setenv("ZK_ROOT_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    fake_db = _FakeSequenceDb([])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/roots/bill:GR-0490a766/publish",
                headers={"Authorization": "Bearer dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "ZK canary scope is not allowed"
    assert fake_db.executed == []
    assert fake_db.added == []


@pytest.mark.asyncio
async def test_zk_root_publish_canary_rejects_allowlisted_public_bill(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.setenv("ZK_ROOT_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:GR-0490a766")
    bill = SimpleNamespace(
        id="GR-0490a766",
        source="PARLIAMENT",
        admin_hidden=False,
        forum_topic_id=438,
        arweave_tx_id="ar_tx",
    )
    fake_db = _FakeSequenceDb([bill])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/roots/bill:GR-0490a766/publish",
                headers={"Authorization": "Bearer dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "ZK canary bill is not isolated"
    assert fake_db.added == []
    assert fake_db.committed is False


@pytest.mark.asyncio
async def test_zk_verify_endpoint_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ZK_VOTING_ENABLED", raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/zk/verify", json={"proof": _native_proof()})

    assert response.status_code == 503
    assert response.json()["detail"] == "ZK voting verifier is not enabled"


@pytest.mark.asyncio
async def test_zk_vote_endpoint_is_fail_closed_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ZK_VOTING_ENABLED", raising=False)
    fake_db = _FakeSequenceDb([])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/vote",
                json={
                    "vote_scope_id": "bill:ZK-CANARY-001",
                    "vote_commitment": "YES",
                    "proof": _native_proof(),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "ZK voting is not enabled"
    assert fake_db.executed == []
    assert fake_db.added == []


@pytest.mark.asyncio
async def test_zk_vote_rejects_proof_not_bound_to_scope_and_vote(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    bill = SimpleNamespace(
        id="ZK-CANARY-001",
        source="ZK_CANARY",
        admin_hidden=True,
        forum_topic_id=None,
        arweave_tx_id=None,
    )
    fake_db = _FakeSequenceDb([bill])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/vote",
                json={
                    "vote_scope_id": "bill:ZK-CANARY-001",
                    "vote_commitment": "YES",
                    "proof": _native_proof(),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "ZK proof is not bound to this vote scope and commitment"
    assert fake_db.added == []


@pytest.mark.asyncio
async def test_zk_vote_rejects_mixed_native_and_canonical_proof_fields(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    bill = SimpleNamespace(
        id="ZK-CANARY-001",
        source="ZK_CANARY",
        admin_hidden=True,
        forum_topic_id=None,
        arweave_tx_id=None,
    )
    fake_db = _FakeSequenceDb([bill])
    proof = _native_proof()
    proof["merkleTreeDepth"] = proof["merkle_tree_depth"]

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/vote",
                json={
                    "vote_scope_id": "bill:ZK-CANARY-001",
                    "vote_commitment": "YES",
                    "proof": proof,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Malformed ZK proof"
    assert fake_db.added == []


@pytest.mark.asyncio
async def test_zk_vote_rejects_invalid_vote_commitment(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    bill = SimpleNamespace(
        id="ZK-CANARY-001",
        source="ZK_CANARY",
        admin_hidden=True,
        forum_topic_id=None,
        arweave_tx_id=None,
    )
    fake_db = _FakeSequenceDb([bill])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/vote",
                json={
                    "vote_scope_id": "bill:ZK-CANARY-001",
                    "vote_commitment": "MAYBE",
                    "proof": _native_proof(),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "ZK vote_commitment must be YES, NO, ABSTAIN, or UNKNOWN"
    assert fake_db.added == []


@pytest.mark.asyncio
async def test_zk_vote_canary_rejects_allowlisted_public_bill(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:GR-0490a766")
    fake_db = _FakeSequenceDb([_public_parliament_bill()])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/vote",
                json={
                    "vote_scope_id": "bill:GR-0490a766",
                    "vote_commitment": "YES",
                    "proof": _native_proof(),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "ZK canary bill is not isolated"
    assert fake_db.added == []
    assert fake_db.committed is False


@pytest.mark.asyncio
async def test_zk_vote_accepts_bound_proof_and_stores_public_receipt(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    monkeypatch.setattr(zk, "verify_semaphore_proof", lambda *_args: True)
    scope = "bill:ZK-CANARY-001"
    vote_commitment = "YES"
    bill = SimpleNamespace(
        id="ZK-CANARY-001",
        source="ZK_CANARY",
        admin_hidden=True,
        forum_topic_id=None,
        arweave_tx_id=None,
    )
    root = SimpleNamespace(id=8, merkle_depth=16)
    fake_db = _FakeSequenceDb([bill, root])
    proof = {
        "merkleTreeDepth": 16,
        "merkleTreeRoot": "123456789",
        "message": canonical_zk_message_value(
            vote_scope_id=scope,
            vote_commitment=vote_commitment,
        ),
        "nullifier": "987654321",
        "scope": canonical_zk_scope_value(scope),
        "points": ["1", "2", "3", "4", "5", "6", "7", "8"],
    }

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/vote",
                json={
                    "vote_scope_id": scope,
                    "vote_commitment": vote_commitment,
                    "proof": proof,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["vote_scope_id"] == scope
    assert payload["arweave_pending"] is True
    assert fake_db.committed is True
    receipt = next(value for value in fake_db.added if isinstance(value, ZkVoteReceipt))
    assert receipt.vote_scope_id == scope
    assert receipt.vote_commitment == vote_commitment
    assert receipt.semaphore_nullifier == "987654321"
    assert receipt.merkle_root == "123456789"
    assert receipt.signal_hash == proof["message"]
    assert receipt.external_nullifier == proof["scope"]
    assert receipt.proof_public_json == proof
    serialized = json.dumps(payload)
    assert "tier_guard_hash" not in serialized
    assert "identity_record_id" not in serialized


@pytest.mark.asyncio
async def test_zk_pending_receipt_publish_is_fail_closed_without_flag(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.delenv("ZK_ARWEAVE_PUBLICATION_ENABLED", raising=False)
    fake_db = _FakeSequenceDb([])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/receipts/bill:GR-0490a766/publish-pending",
                headers={"Authorization": "Bearer dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "ZK Arweave publication is not enabled"
    assert fake_db.executed == []


@pytest.mark.asyncio
async def test_zk_pending_receipt_publish_rejects_canary_mode(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.setenv("ZK_ARWEAVE_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    fake_db = _FakeSequenceDb([])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/receipts/bill:ZK-CANARY-001/publish-pending",
                headers={"Authorization": "Bearer dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "ZK canary receipts are not published to Arweave"
    assert fake_db.executed == []


@pytest.mark.asyncio
async def test_zk_pending_receipt_publish_updates_only_public_receipt_fields(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    monkeypatch.setenv("ZK_ARWEAVE_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", "bill:GR-0490a766")

    async def fake_publish_to_arweave(record, bill_id):
        assert record["vote_scope_id"] == "bill:GR-0490a766"
        assert record["bill_id"] == "GR-0490a766"
        serialized = json.dumps(record)
        assert "tier_guard_hash" not in serialized
        assert "identity_record_id" not in serialized
        return f"DRY_RUN_{bill_id}"

    import routers.arweave as arweave_router

    monkeypatch.setattr(arweave_router, "publish_to_arweave", fake_publish_to_arweave)
    receipt = SimpleNamespace(
        id=12,
        vote_scope_id="bill:GR-0490a766",
        vote_commitment="YES",
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
        publication_bucket=None,
    )
    root = SimpleNamespace(group_size=2)
    fake_db = _FakeSequenceDb([_public_parliament_bill(), [receipt], root])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/receipts/bill:GR-0490a766/publish-pending",
                headers={"Authorization": "Bearer dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["attempted"] == 1
    assert payload["published"] == 1
    assert payload["failed"] == 0
    assert payload["tx_ids"] == ["DRY_RUN_zk-GR-0490a766-12"]
    assert receipt.arweave_pending is False
    assert receipt.arweave_tx_id == "DRY_RUN_zk-GR-0490a766-12"
    assert receipt.publication_bucket
    assert fake_db.committed is True


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


@pytest.mark.asyncio
async def test_zk_verify_rejects_mixed_native_and_canonical_proof_fields(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    proof = _native_proof()
    proof["merkleTreeDepth"] = proof["merkle_tree_depth"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/zk/verify", json={"proof": proof})

    assert response.status_code == 200
    assert response.json()["proof_verified"] is False


@pytest.mark.asyncio
async def test_zk_verify_canary_requires_vote_scope_id(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/zk/verify", json={"proof": _native_proof()})

    assert response.status_code == 400
    assert response.json()["detail"] == "ZK vote_scope_id is required in canary mode"


@pytest.mark.asyncio
async def test_zk_verify_canary_rejects_non_allowlisted_scope(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/zk/verify",
            json={"proof": _native_proof(), "vote_scope_id": "bill:GR-0490a766"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "ZK canary scope is not allowed"


@pytest.mark.asyncio
async def test_zk_verify_canary_accepts_allowlisted_scope(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    proof = _native_proof()
    bill = SimpleNamespace(
        id="ZK-CANARY-001",
        source="ZK_CANARY",
        admin_hidden=True,
        forum_topic_id=None,
        arweave_tx_id=None,
    )
    root = SimpleNamespace(merkle_depth=int(proof["merkle_tree_depth"]))
    fake_db = _FakeSequenceDb([bill, root])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/verify",
                json={"proof": proof, "vote_scope_id": "bill:ZK-CANARY-001"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["proof_verified"] is True


@pytest.mark.asyncio
async def test_zk_verify_with_scope_rejects_depth_not_matching_published_root(monkeypatch) -> None:
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_SCOPE_ALLOWLIST", "bill:ZK-CANARY-001")
    proof = _native_proof()
    proof["merkle_tree_depth"] = int(proof["merkle_tree_depth"]) + 1
    bill = SimpleNamespace(
        id="ZK-CANARY-001",
        source="ZK_CANARY",
        admin_hidden=True,
        forum_topic_id=None,
        arweave_tx_id=None,
    )
    root = SimpleNamespace(merkle_depth=16)
    fake_db = _FakeSequenceDb([bill, root])

    async def override_get_db():
        async for value in _override_with(fake_db):
            yield value

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/zk/verify",
                json={"proof": proof, "vote_scope_id": "bill:ZK-CANARY-001"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["proof_verified"] is False
