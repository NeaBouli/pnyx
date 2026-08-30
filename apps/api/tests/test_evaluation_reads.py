"""HTTP contract tests for private evaluation reads using synthetic identities."""
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from database import get_db
from routers import evaluation
from services.evaluation_integrity import build_evaluation_read_payload

NULLIFIER = "a" * 64
ADA = "ADA-ΕΛ-1"
NOW = 1_788_000_000_000
KEY = SigningKey(bytes([1]) * 32)
UPDATED = datetime(2026, 8, 30, tzinfo=timezone.utc)


class ReadSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.active = True

    async def execute(self, statement: Any, params: dict[str, Any]) -> Any:
        sql = str(statement)
        self.calls.append((sql, params))
        if "identity_records" in sql:
            assert params["status"] == "ACTIVE"
            public_key = KEY.verify_key.encode().hex() if self.active else None
            return SimpleNamespace(scalar_one_or_none=lambda: public_key)
        assert "politician_evaluations" in sql
        assert params["null"] == NULLIFIER
        if "GROUP BY" in sql:
            rows = [(ADA, UPDATED)]
        else:
            assert params["ada"] == ADA
            rows = [(2, -3, UPDATED), (8, 5, UPDATED)]
        return SimpleNamespace(fetchall=lambda: rows)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.delenv("EVALUATION_REQUIRE_V2", raising=False)
    monkeypatch.setenv("EVALUATION_V2_MAX_SKEW_MS", "60000")
    monkeypatch.setattr("services.evaluation_integrity.time.time", lambda: NOW / 1000)
    db = ReadSession()
    app = FastAPI()
    app.include_router(evaluation.router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as http:
        yield http, db


def path(ada: str | None) -> str:
    route = "my-evaluations/bulk" if ada is None else f"{ada}/my-evaluation"
    return f"/api/v1/politicians/{route}"


def headers(
    ada: str | None,
    nullifier: str = NULLIFIER,
    timestamp: int = NOW,
    key: SigningKey = KEY,
) -> dict[str, str]:
    payload = build_evaluation_read_payload(ada, nullifier, timestamp)
    return {
        "X-Evaluation-Read-Timestamp": str(timestamp),
        "X-Evaluation-Read-Signature": key.sign(payload.encode()).signature.hex(),
    }


def test_read_payload_matches_mobile_golden_vectors() -> None:
    assert build_evaluation_read_payload(ADA, NULLIFIER, NOW) == (
        f'evaluation-read:v1:["{ADA}","{NULLIFIER}",{NOW}]'
    )
    assert build_evaluation_read_payload(None, NULLIFIER, NOW) == (
        f'evaluation-read:v1:[null,"{NULLIFIER}",{NOW}]'
    )


@pytest.mark.parametrize("ada", [ADA, None])
@pytest.mark.parametrize("cutoff", [False, True])
def test_signed_read_preserves_prefill_history(
    client: Any, monkeypatch: pytest.MonkeyPatch, ada: str | None, cutoff: bool,
) -> None:
    http, db = client
    monkeypatch.setenv("EVALUATION_REQUIRE_V2", str(cutoff).lower())
    response = http.get(path(ada), params={"nullifier_hash": NULLIFIER}, headers=headers(ada))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-evaluation-read-integrity"] == "signed"
    if ada is None:
        assert response.json() == [{"ada_number": ADA, "last_updated": UPDATED.isoformat()}]
    else:
        assert response.json() == [
            {"question_id": 2, "score": -3, "updated_at": UPDATED.isoformat()},
            {"question_id": 8, "score": 5, "updated_at": UPDATED.isoformat()},
        ]
    assert len(db.calls) == 2


@pytest.mark.parametrize("ada", [ADA, None])
def test_legacy_clients_remain_compatible_until_cutoff(
    client: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, ada: str | None,
) -> None:
    http, db = client
    response = http.get(path(ada), params={"nullifier_hash": NULLIFIER})
    assert response.status_code == 200
    assert response.headers["x-evaluation-read-integrity"] == "legacy"
    assert response.headers["cache-control"] == "private, no-store"
    assert "Legacy personal read accepted" in caplog.text
    assert NULLIFIER not in caplog.text
    assert ADA not in caplog.text
    db.calls.clear()
    monkeypatch.setenv("EVALUATION_REQUIRE_V2", "true")
    response = http.get(path(ada), params={"nullifier_hash": NULLIFIER})
    assert response.status_code == 426
    assert "ενημέρωση" in response.json()["detail"]
    assert response.headers["cache-control"] == "private, no-store"
    assert db.calls == []
    monkeypatch.setenv("EVALUATION_REQUIRE_V2", "false")
    assert http.get(path(ada), params={"nullifier_hash": NULLIFIER}).status_code == 200


@pytest.mark.parametrize("ada", [ADA, None])
@pytest.mark.parametrize("tamper", ["target", "owner", "timestamp", "key", "write_payload"])
def test_bad_signature_never_downgrades_to_legacy(client: Any, ada: str | None, tamper: str) -> None:
    http, db = client
    signed = headers(ada)
    if tamper == "target":
        signed = headers(None if ada is not None else ADA)
    elif tamper == "owner":
        signed = headers(ada, nullifier="b" * 64)
    elif tamper == "timestamp":
        signed["X-Evaluation-Read-Timestamp"] = str(NOW + 1)
    elif tamper == "key":
        signed = headers(ada, key=SigningKey(bytes([2]) * 32))
    else:
        signed["X-Evaluation-Read-Signature"] = KEY.sign(
            f"evaluate:{ADA}:{NULLIFIER}".encode(),
        ).signature.hex()
    response = http.get(path(ada), params={"nullifier_hash": NULLIFIER}, headers=signed)
    assert response.status_code == 401
    assert all("politician_evaluations" not in sql for sql, _ in db.calls)


@pytest.mark.parametrize("ada", [ADA, None])
def test_other_politician_cannot_reuse_signature(client: Any, ada: str | None) -> None:
    http, db = client
    response = http.get(path(ada), params={"nullifier_hash": NULLIFIER}, headers=headers("ADA-OTHER"))
    assert response.status_code == 401
    assert len(db.calls) == 1


@pytest.mark.parametrize("ada", [ADA, None])
@pytest.mark.parametrize("offset", [-60001, 60001])
def test_rejects_stale_or_future_reads_before_database_access(client: Any, ada: str | None, offset: int) -> None:
    http, db = client
    response = http.get(path(ada), params={"nullifier_hash": NULLIFIER}, headers=headers(ada, timestamp=NOW + offset))
    assert response.status_code == 401
    assert db.calls == []


@pytest.mark.parametrize("ada", [ADA, None])
def test_unknown_or_revoked_identity_cannot_read(client: Any, ada: str | None) -> None:
    http, db = client
    db.active = False
    response = http.get(path(ada), params={"nullifier_hash": NULLIFIER}, headers=headers(ada))
    assert response.status_code == 401
    assert len(db.calls) == 1


@pytest.mark.parametrize("ada", [ADA, None])
@pytest.mark.parametrize("field", ["X-Evaluation-Read-Timestamp", "X-Evaluation-Read-Signature"])
def test_partial_signed_request_is_not_legacy(client: Any, ada: str | None, field: str) -> None:
    http, db = client
    signed = headers(ada)
    del signed[field]
    response = http.get(path(ada), params={"nullifier_hash": NULLIFIER}, headers=signed)
    assert response.status_code == 401
    assert db.calls == []


@pytest.mark.parametrize("ada", [ADA, None])
@pytest.mark.parametrize("field,value", [
    ("X-Evaluation-Read-Signature", ""),
    ("X-Evaluation-Read-Signature", "z" * 128),
    ("X-Evaluation-Read-Signature", "a" * 127),
    ("X-Evaluation-Read-Timestamp", "not-a-number"),
    ("X-Evaluation-Read-Timestamp", "-1"),
    ("X-Evaluation-Read-Timestamp", "9007199254740992"),
])
def test_malformed_headers_cannot_trigger_legacy_read(
    client: Any, ada: str | None, field: str, value: str,
) -> None:
    http, db = client
    signed = headers(ada)
    signed[field] = value
    response = http.get(path(ada), params={"nullifier_hash": NULLIFIER}, headers=signed)
    assert response.status_code == 422
    assert db.calls == []
