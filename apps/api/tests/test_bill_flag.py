"""HTTP contract tests for signed bill flags using synthetic identities."""
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from nacl.signing import SigningKey
from sqlalchemy.exc import IntegrityError

from database import get_db
from models import BillStatus
from routers import parliament
from services.citizen_action_integrity import (
    build_flag_payload,
    build_vote_status_read_payload,
)

NULLIFIER = "a" * 64
BILL = "GR-0490a766"
NOW = 1_788_000_000_000
KEY = SigningKey(bytes([1]) * 32)


class FlagSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.identity: Any = SimpleNamespace(
            public_key_hex=KEY.verify_key.encode().hex(),
        )
        self.bill: Any = SimpleNamespace(
            id=BILL, status=BillStatus.ACTIVE, source="PARLIAMENT", admin_hidden=False,
        )
        self.duplicate = False
        self.fail_with: Exception | None = None
        self.committed = False
        self.rolled_back = False

    async def execute(self, statement: Any, params: Any = None) -> Any:
        sql = str(statement)
        self.calls.append((sql, params))
        if "identity_records" in sql:
            return SimpleNamespace(scalar_one_or_none=lambda: self.identity)
        if "INSERT INTO bill_flags" in sql:
            assert params == {"nh": NULLIFIER, "bid": BILL}
            if self.fail_with is not None:
                raise self.fail_with
            if self.duplicate:
                raise IntegrityError("INSERT INTO bill_flags", params, Exception("duplicate key"))
            return SimpleNamespace()
        assert "UPDATE parliament_bills" in sql
        return SimpleNamespace()

    async def get(self, model: Any, bill_id: str) -> Any:
        self.calls.append(("get", bill_id))
        return self.bill

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("CITIZEN_ACTION_MAX_SKEW_MS", "60000")
    monkeypatch.setattr("services.citizen_action_integrity.time.time", lambda: NOW / 1000)
    db = FlagSession()
    app = FastAPI()
    app.include_router(parliament.router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as http:
        yield http, db


def signed_body(
    bill_id: str = BILL,
    nullifier: str = NULLIFIER,
    timestamp: int = NOW,
    key: SigningKey = KEY,
) -> dict[str, Any]:
    payload = build_flag_payload(bill_id, nullifier, timestamp)
    return {
        "nullifier_hash": nullifier,
        "timestamp_ms": timestamp,
        "signature_hex": key.sign(payload.encode()).signature.hex(),
    }


def test_signed_flag_is_recorded_once(client: Any) -> None:
    http, db = client
    response = http.post(f"/api/v1/bills/{BILL}/flag", json=signed_body())
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "bill_id": BILL,
        "message": "Η αναφορά καταγράφηκε.",
    }
    assert db.committed
    assert not db.rolled_back
    assert any("INSERT INTO bill_flags" in sql for sql, _ in db.calls)
    assert any("UPDATE parliament_bills" in sql for sql, _ in db.calls)


def test_duplicate_flag_keeps_409_conflict(client: Any) -> None:
    http, db = client
    db.duplicate = True
    response = http.post(f"/api/v1/bills/{BILL}/flag", json=signed_body())
    assert response.status_code == 409
    assert db.rolled_back
    assert not db.committed


def test_database_failure_is_not_masked_as_duplicate(client: Any) -> None:
    http, db = client
    db.fail_with = RuntimeError("connection lost")
    with pytest.raises(RuntimeError, match="connection lost"):
        http.post(f"/api/v1/bills/{BILL}/flag", json=signed_body())
    assert not db.committed


@pytest.mark.parametrize("tamper", ["target", "owner", "timestamp", "key", "read_payload"])
def test_bad_signature_gets_generic_401_before_bill_access(client: Any, tamper: str) -> None:
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
        body["signature_hex"] = KEY.sign(
            build_vote_status_read_payload(BILL, NULLIFIER, NOW).encode(),
        ).signature.hex()
    response = http.post(f"/api/v1/bills/{BILL}/flag", json=body)
    assert response.status_code == 401
    assert response.json()["detail"] == "Μη έγκυρη υπογραφή."
    assert all("INSERT INTO bill_flags" not in sql for sql, _ in db.calls)


@pytest.mark.parametrize("offset", [-60_001, 60_001])
def test_rejects_stale_or_future_flags_before_database_access(
    client: Any, offset: int,
) -> None:
    http, db = client
    response = http.post(
        f"/api/v1/bills/{BILL}/flag", json=signed_body(timestamp=NOW + offset),
    )
    assert response.status_code == 401
    assert db.calls == []


def test_unknown_and_revoked_identity_are_indistinguishable(client: Any) -> None:
    http, db = client
    db.identity = None
    response = http.post(f"/api/v1/bills/{BILL}/flag", json=signed_body())
    assert response.status_code == 401
    unknown = response.json()["detail"]

    db.identity = SimpleNamespace(public_key_hex=KEY.verify_key.encode().hex())
    bad = signed_body(key=SigningKey(bytes([2]) * 32))
    bad_response = http.post(f"/api/v1/bills/{BILL}/flag", json=bad)
    assert bad_response.status_code == 401
    assert bad_response.json()["detail"] == unknown
    assert all("INSERT INTO bill_flags" not in sql for sql, _ in db.calls)


def test_unknown_bill_preserves_404(client: Any) -> None:
    http, db = client
    db.bill = None
    response = http.post(f"/api/v1/bills/{BILL}/flag", json=signed_body())
    assert response.status_code == 404


@pytest.mark.parametrize("field", ["nullifier_hash", "timestamp_ms", "signature_hex"])
def test_missing_body_fields_are_rejected(client: Any, field: str) -> None:
    http, db = client
    body = signed_body()
    del body[field]
    response = http.post(f"/api/v1/bills/{BILL}/flag", json=body)
    assert response.status_code == 422
    assert db.calls == []


def test_bare_header_request_has_no_legacy_path(client: Any) -> None:
    http, db = client
    response = http.post(
        f"/api/v1/bills/{BILL}/flag", headers={"X-Nullifier": NULLIFIER},
    )
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
    response = http.post(f"/api/v1/bills/{BILL}/flag", json=body)
    assert response.status_code == 422
    assert db.calls == []


def test_unknown_body_fields_are_rejected(client: Any) -> None:
    http, db = client
    body = signed_body()
    body["unsigned_hint"] = "ignored-by-signature"
    response = http.post(f"/api/v1/bills/{BILL}/flag", json=body)
    assert response.status_code == 422
    assert db.calls == []
