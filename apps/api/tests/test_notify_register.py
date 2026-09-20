"""EKA-05: signed push registration contract tests (mock-only, no real Redis).

Golden canonical payload values must stay in sync with
apps/mobile/src/lib/push-registration.test.ts.
"""
import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from database import get_db
from routers import notify
from services import push_registration
from services.push_registration import build_push_register_payload

DEVICE_ID = "3f6b1c2e-9a4d-4e5f-8b6c-0d1e2f3a4b5c"
TOKEN = "ExponentPushToken[abcdefghijklmnopqrstuv]"
PLATFORM = "android"
NULLIFIER = "a" * 64
NOW = 1_788_000_000_000
KEY = SigningKey(bytes([7]) * 32)

GOLDEN_PAYLOAD = (
    'push-register:v1:["3f6b1c2e-9a4d-4e5f-8b6c-0d1e2f3a4b5c",'
    '"ExponentPushToken[abcdefghijklmnopqrstuv]","android",'
    f'"{NULLIFIER}",{NOW}]'
)


class FakeRedis:
    """In-memory stand-in for the redis.asyncio calls used on this path."""

    def __init__(self) -> None:
        self.store: dict[str, tuple[str, int]] = {}
        self.counters: dict[str, int] = {}

    async def eval(self, script: str, numkeys: int, key: str, window: int) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def get(self, key: str) -> str | None:
        item = self.store.get(key)
        return item[0] if item else None

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = (value, ttl)

    async def scan_iter(self, pattern: str):
        assert pattern == "push_tokens:*"
        for key in self.store:
            if key.startswith("push_tokens:"):
                yield key


class RegisterSession:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.identity: Any = SimpleNamespace(
            public_key_hex=KEY.verify_key.encode().hex(),
        )

    async def execute(self, statement: Any, params: Any = None) -> Any:
        sql = str(statement)
        self.calls.append(sql)
        assert "identity_records" in sql
        return SimpleNamespace(scalar_one_or_none=lambda: self.identity)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("CITIZEN_ACTION_MAX_SKEW_MS", "60000")
    monkeypatch.setattr(
        "services.citizen_action_integrity.time.time", lambda: NOW / 1000,
    )
    redis = FakeRedis()
    monkeypatch.setattr(notify, "_redis", redis)
    db = RegisterSession()
    app = FastAPI()
    app.include_router(notify.router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as http:
        yield http, db, redis


def signed_body(
    device_id: str = DEVICE_ID,
    token: str = TOKEN,
    platform: str = PLATFORM,
    nullifier: str = NULLIFIER,
    timestamp: int = NOW,
    key: SigningKey = KEY,
) -> dict[str, Any]:
    payload = build_push_register_payload(
        device_id, token, platform, nullifier, timestamp,
    )
    return {
        "token": token,
        "device_id": device_id,
        "platform": platform,
        "nullifier_hash": nullifier,
        "timestamp_ms": timestamp,
        "signature_hex": key.sign(payload.encode()).signature.hex(),
    }


def assert_no_writes(redis: FakeRedis) -> None:
    assert redis.store == {}


def test_canonical_payload_golden_vector() -> None:
    assert build_push_register_payload(
        DEVICE_ID, TOKEN, PLATFORM, NULLIFIER, NOW,
    ) == GOLDEN_PAYLOAD


def test_valid_signed_registration_writes_hmac_key(client: Any) -> None:
    http, db, redis = client
    response = http.post("/api/v1/notify/register", json=signed_body())
    assert response.status_code == 200
    assert response.json() == {"registered": True, "integrity": "signed-v1"}
    assert db.calls, "identity lookup must happen"
    assert len(redis.store) == 1
    (key, (value, ttl)), = redis.store.items()
    assert key.startswith("push_tokens:")
    assert ttl == push_registration.PUSH_TOKEN_TTL_SECONDS
    # Value carries only token/platform — no nullifier, no extras.
    assert json.loads(value) == {"token": TOKEN, "platform": PLATFORM}


@pytest.mark.parametrize("tamper", [
    "device_id", "token", "platform", "nullifier", "timestamp", "key",
])
def test_bad_signature_gets_401_and_no_write(client: Any, tamper: str) -> None:
    http, db, redis = client
    body = signed_body()
    if tamper == "device_id":
        body = signed_body(device_id="3f6b1c2e-9a4d-4e5f-8b6c-ffffffffffff")
        body["device_id"] = DEVICE_ID
    elif tamper == "token":
        body = signed_body(token="ExpoPushToken[other]")
        body["token"] = TOKEN
    elif tamper == "platform":
        body = signed_body(platform="ios")
        body["platform"] = PLATFORM
    elif tamper == "nullifier":
        body = signed_body(nullifier="b" * 64)
        body["nullifier_hash"] = NULLIFIER
    elif tamper == "timestamp":
        body["timestamp_ms"] = NOW + 1
    else:
        body = signed_body(key=SigningKey(bytes([8]) * 32))
    response = http.post("/api/v1/notify/register", json=body)
    assert response.status_code == 401
    assert response.json()["detail"] == "Μη έγκυρη υπογραφή."
    assert_no_writes(redis)


def test_missing_and_revoked_identity_are_indistinguishable(client: Any) -> None:
    http, db, redis = client
    db.identity = None  # unknown or non-ACTIVE both resolve to None here
    response = http.post("/api/v1/notify/register", json=signed_body())
    assert response.status_code == 401
    unknown = response.json()["detail"]

    db.identity = SimpleNamespace(public_key_hex=KEY.verify_key.encode().hex())
    bad = signed_body(key=SigningKey(bytes([8]) * 32))
    bad_response = http.post("/api/v1/notify/register", json=bad)
    assert bad_response.status_code == 401
    assert bad_response.json()["detail"] == unknown
    assert_no_writes(redis)


@pytest.mark.parametrize("offset", [-60_001, 60_001])
def test_stale_or_future_timestamp_rejected_before_db(client: Any, offset: int) -> None:
    http, db, redis = client
    response = http.post(
        "/api/v1/notify/register", json=signed_body(timestamp=NOW + offset),
    )
    assert response.status_code == 401
    assert db.calls == []
    assert_no_writes(redis)


def test_extra_fields_are_rejected(client: Any) -> None:
    http, db, redis = client
    body = signed_body()
    body["unsigned_hint"] = "ignore-me"
    response = http.post("/api/v1/notify/register", json=body)
    assert response.status_code == 422
    assert db.calls == []
    assert_no_writes(redis)


@pytest.mark.parametrize("field", [
    "token", "device_id", "platform", "nullifier_hash", "timestamp_ms",
    "signature_hex",
])
def test_missing_fields_are_rejected(client: Any, field: str) -> None:
    http, db, redis = client
    body = signed_body()
    del body[field]
    response = http.post("/api/v1/notify/register", json=body)
    assert response.status_code == 422
    assert_no_writes(redis)


@pytest.mark.parametrize("field,value", [
    ("token", "ExponentPushToken"),                       # no brackets
    ("token", "expopushtoken[abc]"),                      # wrong casing
    ("token", "ExponentPushToken[]"),                     # empty inner
    ("token", "ExponentPushToken[abc]def]"),              # inner bracket
    ("token", "ExponentPushToken[" + "x" * 257 + "]"),    # too long
    ("token", "ExponentPushToken[tökën]"),                # non-ASCII inner
    ("token", "FcmPushToken[abc]"),                       # unknown form
    ("device_id", "android-Pixel-7"),                     # legacy model id
    ("device_id", "3f6b1c2e9a4d4e5f8b6c0d1e2f3a4b5c"),    # no hyphens
    ("device_id", "3f6b1c2e-9a4d-1e5f-8b6c-0d1e2f3a4b5c"),  # not v4
    ("device_id", "3F6B1C2E-9A4D-4E5F-8B6C-0D1E2F3A4B5C"),  # uppercase
    ("platform", "windows"),
    ("platform", "ANDROID"),
    ("nullifier_hash", "A" * 64),                         # uppercase
    ("nullifier_hash", "a" * 63),
    ("nullifier_hash", "z" * 64),
    ("timestamp_ms", -1),
    ("timestamp_ms", 9_007_199_254_740_992),
    ("timestamp_ms", "not-a-number"),
    ("signature_hex", ""),
    ("signature_hex", "z" * 128),
    ("signature_hex", "a" * 127),
])
def test_malformed_fields_are_rejected(client: Any, field: str, value: Any) -> None:
    http, db, redis = client
    body = signed_body()
    body[field] = value
    response = http.post("/api/v1/notify/register", json=body)
    assert response.status_code == 422
    assert db.calls == []
    assert_no_writes(redis)


def test_expo_push_token_form_is_accepted(client: Any) -> None:
    http, _, redis = client
    response = http.post(
        "/api/v1/notify/register",
        json=signed_body(token="ExpoPushToken[xxxxxxxxxxxxxx]"),
    )
    assert response.status_code == 200


def test_per_ip_limit_runs_before_db_and_blocks_overflow(
    client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, db, redis = client
    monkeypatch.setattr(push_registration, "PUSH_REGISTER_IP_LIMIT", 2)
    assert http.post("/api/v1/notify/register", json=signed_body()).status_code == 200
    # Unsigned garbage still passes the schema and consumes the IP bucket.
    rejected = signed_body(key=SigningKey(bytes([8]) * 32))
    assert http.post("/api/v1/notify/register", json=rejected).status_code == 401
    db.calls.clear()
    response = http.post("/api/v1/notify/register", json=signed_body())
    assert response.status_code == 429
    assert db.calls == [], "IP limit must trigger before identity DB work"


def test_identity_quota_bounds_new_and_changed_registrations(
    client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, _, redis = client
    monkeypatch.setattr(push_registration, "PUSH_REGISTER_IDENTITY_LIMIT", 1)
    assert http.post("/api/v1/notify/register", json=signed_body()).status_code == 200
    # A changed token consumes new-key quota and is rejected at the boundary.
    changed = signed_body(token="ExpoPushToken[xxxxxxxxxxxxxx]")
    response = http.post("/api/v1/notify/register", json=changed)
    assert response.status_code == 429
    assert len(redis.store) == 1


def test_same_value_reregistration_is_idempotent_without_identity_quota(
    client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, _, redis = client
    monkeypatch.setattr(push_registration, "PUSH_REGISTER_IDENTITY_LIMIT", 1)
    first = http.post("/api/v1/notify/register", json=signed_body())
    assert first.status_code == 200
    # Same-value repeats refresh the TTL and never hit the exhausted quota.
    for _ in range(3):
        repeat = http.post("/api/v1/notify/register", json=signed_body())
        assert repeat.status_code == 200
        assert repeat.json() == {"registered": True, "integrity": "signed-v1"}
    assert len(redis.store) == 1
    identity_keys = [
        k for k in redis.counters if k.startswith("ratelimit:push_register:id:")
    ]
    assert len(identity_keys) == 1
    assert redis.counters[identity_keys[0]] == 1


def test_raw_identifiers_never_appear_in_redis_keys_or_logs(
    client: Any, caplog: pytest.LogCaptureFixture,
) -> None:
    http, _, redis = client
    with caplog.at_level("DEBUG"):
        assert http.post("/api/v1/notify/register", json=signed_body()).status_code == 200
        http.post("/api/v1/notify/register", json=signed_body(timestamp=NOW + 1))
    for key in list(redis.store) + list(redis.counters):
        assert DEVICE_ID not in key
        assert NULLIFIER not in key
        assert TOKEN not in key
    assert DEVICE_ID not in caplog.text
    assert NULLIFIER not in caplog.text
    assert TOKEN not in caplog.text


async def test_migration_deduplicates_tokens_and_skips_invalid_entries() -> None:
    redis = FakeRedis()
    value = json.dumps({"token": TOKEN, "platform": PLATFORM})
    redis.store = {
        "push_tokens:android-SM-G991B": (value, 100),
        "push_tokens:" + "a" * 64: (value, 200),
        "push_tokens:" + "b" * 64: ("not-json", 200),
        "push_tokens:" + "c" * 64: (json.dumps({"platform": PLATFORM}), 200),
    }

    assert await notify._registered_push_tokens(redis) == [TOKEN]
