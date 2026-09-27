"""HTTP contract tests for signed vote-status reads using synthetic identities."""
import logging
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from database import get_db
from models import BillStatus, VoteChoice
from routers import voting
from services.citizen_action_integrity import build_vote_status_read_payload

NULLIFIER = "a" * 64
BILL = "GR-0490a766"
NOW = 1_788_000_000_000
KEY = SigningKey(bytes([1]) * 32)


class StatusSession:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.identity: Any = SimpleNamespace(
            public_key_hex=KEY.verify_key.encode().hex(),
        )
        self.bill: Any = SimpleNamespace(
            id=BILL, status=BillStatus.ACTIVE, source="PARLIAMENT", admin_hidden=False,
        )
        self.vote: Any = SimpleNamespace(vote=VoteChoice.YES, is_correction=False)

    async def execute(self, statement: Any, params: Any = None) -> Any:
        sql = str(statement)
        self.calls.append(sql)
        if "identity_records" in sql:
            return SimpleNamespace(scalar_one_or_none=lambda: self.identity)
        if "parliament_bills" in sql:
            return SimpleNamespace(scalar_one_or_none=lambda: self.bill)
        assert "citizen_votes" in sql
        return SimpleNamespace(scalar_one_or_none=lambda: self.vote)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.delenv("VOTE_STATUS_REQUIRE_SIGNED", raising=False)
    monkeypatch.setenv("CITIZEN_ACTION_MAX_SKEW_MS", "60000")
    monkeypatch.setattr("services.citizen_action_integrity.time.time", lambda: NOW / 1000)
    db = StatusSession()
    app = FastAPI()
    app.include_router(voting.router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as http:
        yield http, db


def signed_body(
    bill_id: str = BILL,
    nullifier: str = NULLIFIER,
    timestamp: int = NOW,
    key: SigningKey = KEY,
) -> dict[str, Any]:
    payload = build_vote_status_read_payload(bill_id, nullifier, timestamp)
    return {
        "nullifier_hash": nullifier,
        "timestamp_ms": timestamp,
        "signature_hex": key.sign(payload.encode()).signature.hex(),
    }


EXPECTED_BODY = {
    "bill_id": BILL,
    "status": "ACTIVE",
    "has_voted": True,
    "vote": "YES",
    "is_correction": False,
    "can_correct": False,
}


def test_signed_read_returns_status_with_integrity_headers(client: Any) -> None:
    http, db = client
    response = http.post(f"/api/v1/vote/{BILL}/status", json=signed_body())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-vote-read-integrity"] == "signed"
    assert response.json() == EXPECTED_BODY
    assert any("identity_records" in sql for sql in db.calls)


def test_signed_read_logs_no_identity_or_target(
    client: Any, caplog: pytest.LogCaptureFixture,
) -> None:
    http, _ = client
    caplog.set_level(logging.INFO, logger="routers.voting")
    response = http.post(f"/api/v1/vote/{BILL}/status", json=signed_body())
    assert response.status_code == 200
    assert "Signed vote-status read accepted" in caplog.text
    assert NULLIFIER not in caplog.text
    assert BILL not in caplog.text


def test_signed_post_matches_legacy_get_response_shape(client: Any) -> None:
    http, db = client
    legacy = http.get(f"/api/v1/vote/{BILL}/status", params={"nullifier_hash": NULLIFIER})
    assert legacy.status_code == 200
    assert legacy.headers["x-vote-read-integrity"] == "legacy"
    assert legacy.headers["cache-control"] == "private, no-store"
    signed = http.post(f"/api/v1/vote/{BILL}/status", json=signed_body())
    assert signed.status_code == 200
    assert signed.json() == legacy.json() == EXPECTED_BODY


def test_legacy_get_logs_scope_only_warning(
    client: Any, caplog: pytest.LogCaptureFixture,
) -> None:
    http, db = client
    response = http.get(f"/api/v1/vote/{BILL}/status", params={"nullifier_hash": NULLIFIER})
    assert response.status_code == 200
    assert "Legacy unsigned vote-status read accepted" in caplog.text
    assert NULLIFIER not in caplog.text
    assert BILL not in caplog.text


def test_cutoff_returns_426_without_database_access(
    client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, db = client
    monkeypatch.setenv("VOTE_STATUS_REQUIRE_SIGNED", "true")
    response = http.get(f"/api/v1/vote/{BILL}/status", params={"nullifier_hash": NULLIFIER})
    assert response.status_code == 426
    assert response.headers["cache-control"] == "private, no-store"
    assert db.calls == []
    monkeypatch.setenv("VOTE_STATUS_REQUIRE_SIGNED", "false")
    assert http.get(
        f"/api/v1/vote/{BILL}/status", params={"nullifier_hash": NULLIFIER},
    ).status_code == 200


def test_signed_post_still_works_during_cutoff(
    client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, db = client
    monkeypatch.setenv("VOTE_STATUS_REQUIRE_SIGNED", "true")
    response = http.post(f"/api/v1/vote/{BILL}/status", json=signed_body())
    assert response.status_code == 200
    assert response.headers["x-vote-read-integrity"] == "signed"


@pytest.mark.parametrize("tamper", ["target", "owner", "timestamp", "key", "flag_payload"])
def test_bad_signature_is_rejected_before_vote_access(client: Any, tamper: str) -> None:
    http, db = client
    body = signed_body()
    if tamper == "target":
        body = signed_body(bill_id="GR-OTHER")
    elif tamper == "owner":
        body = signed_body(nullifier="b" * 64)
        body["nullifier_hash"] = NULLIFIER
    elif tamper == "timestamp":
        body["timestamp_ms"] = NOW + 1
    elif tamper == "key":
        body = signed_body(key=SigningKey(bytes([2]) * 32))
    else:
        from services.citizen_action_integrity import build_flag_payload
        body["signature_hex"] = KEY.sign(
            build_flag_payload(BILL, NULLIFIER, NOW).encode(),
        ).signature.hex()
    response = http.post(f"/api/v1/vote/{BILL}/status", json=body)
    assert response.status_code == 401
    assert all("citizen_votes" not in sql for sql in db.calls)


@pytest.mark.parametrize("offset", [-60_001, 60_001])
def test_rejects_stale_or_future_reads_before_database_access(
    client: Any, offset: int,
) -> None:
    http, db = client
    response = http.post(
        f"/api/v1/vote/{BILL}/status", json=signed_body(timestamp=NOW + offset),
    )
    assert response.status_code == 401
    assert db.calls == []


def test_unknown_and_revoked_identity_are_indistinguishable(client: Any) -> None:
    http, db = client
    db.identity = None
    response = http.post(f"/api/v1/vote/{BILL}/status", json=signed_body())
    assert response.status_code == 401
    unknown_detail = response.json()["detail"]

    db.identity = SimpleNamespace(public_key_hex=KEY.verify_key.encode().hex())
    bad = signed_body(key=SigningKey(bytes([2]) * 32))
    bad_response = http.post(f"/api/v1/vote/{BILL}/status", json=bad)
    assert bad_response.status_code == 401
    assert bad_response.json()["detail"] == unknown_detail
    assert all("citizen_votes" not in sql for sql in db.calls)


@pytest.mark.parametrize("field", ["nullifier_hash", "timestamp_ms", "signature_hex"])
def test_partial_signed_body_is_never_legacy(client: Any, field: str) -> None:
    http, db = client
    body = signed_body()
    del body[field]
    response = http.post(f"/api/v1/vote/{BILL}/status", json=body)
    assert response.status_code == 422
    assert db.calls == []


@pytest.mark.parametrize("field,value", [
    ("signature_hex", ""),
    ("signature_hex", "z" * 128),
    ("signature_hex", "a" * 127),
    ("nullifier_hash", "a" * 63),
    ("nullifier_hash", "z" * 64),
    ("timestamp_ms", -1),
    ("timestamp_ms", 9_007_199_254_740_992),
    ("timestamp_ms", "not-a-number"),
])
def test_malformed_body_fields_are_rejected(
    client: Any, field: str, value: Any,
) -> None:
    http, db = client
    body = signed_body()
    body[field] = value
    response = http.post(f"/api/v1/vote/{BILL}/status", json=body)
    assert response.status_code == 422
    assert db.calls == []


def test_unknown_body_fields_are_rejected(client: Any) -> None:
    http, db = client
    body = signed_body()
    body["unsigned_hint"] = "ignored-by-signature"
    response = http.post(f"/api/v1/vote/{BILL}/status", json=body)
    assert response.status_code == 422
    assert db.calls == []


def test_unknown_bill_preserves_404(client: Any) -> None:
    http, db = client
    db.bill = None
    response = http.post(f"/api/v1/vote/{BILL}/status", json=signed_body())
    assert response.status_code == 404
    legacy = http.get(f"/api/v1/vote/{BILL}/status", params={"nullifier_hash": NULLIFIER})
    assert legacy.status_code == 404
