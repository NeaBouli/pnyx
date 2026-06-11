"""GH#112 Gate 2 disabled ZK verifier endpoint tests."""
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "gh112_s10_fixture.json"


def _native_proof() -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text())
    return json.loads(fixture["proof"])


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
