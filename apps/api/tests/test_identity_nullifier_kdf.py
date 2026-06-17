import importlib.util
import os
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages/crypto"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import nullifier
from models import IdentityRecord
from routers import identity
from routers.identity import (
    IDENTITY_VERIFY_LOCK_TTL_SECONDS,
    _acquire_identity_verify_lock,
    _compatibility_nullifier,
    _identity_kdf_version,
    _identity_match_query,
    _release_identity_verify_lock,
    _select_identity_match,
)


def test_v1_nullifier_keeps_legacy_raw_input_compatibility(monkeypatch):
    monkeypatch.setattr(nullifier, "SERVER_SALT", "test-salt")

    raw = nullifier.generate_nullifier_hash("+30 690 000 0000")
    normalized = nullifier.generate_nullifier_hash("+306900000000")

    assert raw != normalized
    assert len(raw) == 64
    assert len(normalized) == 64


@pytest.mark.parametrize(
    ("phone", "expected"),
    [
        ("+30 690 000 0000", "+306900000000"),
        ("00306900000000", "+306900000000"),
        ("306900000000", "+306900000000"),
        ("6900000000", "+306900000000"),
    ],
)
def test_phone_normalization_for_v2(phone, expected):
    assert nullifier.normalize_phone_number(phone) == expected


def test_v2_nullifier_is_versioned_and_deterministic(monkeypatch):
    if importlib.util.find_spec("argon2") is None:
        pytest.skip("argon2-cffi not installed in this local Python environment")

    monkeypatch.setattr(nullifier, "SERVER_SALT", "test-salt")

    one = nullifier.generate_nullifier_hash_v2("+30 690 000 0000")
    two = nullifier.generate_nullifier_hash_v2("6900000000")

    assert one == two
    assert one.startswith("v2:")
    assert len(one) == 67
    assert one != nullifier.generate_nullifier_hash("+30 690 000 0000")


def test_identity_kdf_version_defaults_to_v1(monkeypatch):
    monkeypatch.delenv("IDENTITY_NULLIFIER_KDF_VERSION", raising=False)

    assert _identity_kdf_version() == "v1"


def test_identity_kdf_version_accepts_v2(monkeypatch):
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "v2")

    assert _identity_kdf_version() == "v2"


def test_identity_kdf_version_rejects_unknown(monkeypatch):
    monkeypatch.setenv("IDENTITY_NULLIFIER_KDF_VERSION", "banana")

    assert _identity_kdf_version() == "v1"


def test_existing_v2_match_keeps_stored_v1_compatibility_anchor():
    existing = SimpleNamespace(nullifier_hash="a" * 64)

    assert _compatibility_nullifier(existing, "b" * 64) == "a" * 64


def test_new_identity_uses_computed_v1_compatibility_anchor():
    assert _compatibility_nullifier(None, "b" * 64) == "b" * 64


def test_identity_match_prefers_exact_v1_anchor_when_multiple_rows_match():
    exact = SimpleNamespace(nullifier_hash="b" * 64)
    v2_only = SimpleNamespace(nullifier_hash="a" * 64)

    assert _select_identity_match([v2_only, exact], "b" * 64) is exact


def test_identity_match_falls_back_to_first_v2_match():
    v2_only = SimpleNamespace(nullifier_hash="a" * 64)

    assert _select_identity_match([v2_only], "b" * 64) is v2_only


def test_identity_match_query_locks_rows_for_reregistration():
    query = _identity_match_query(IdentityRecord.nullifier_hash == "a" * 64)

    compiled = str(query.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in compiled


class _FakeRedis:
    def __init__(self, set_result=True, eval_error: Exception | None = None):
        self.set_result = set_result
        self.eval_error = eval_error
        self.set_calls = []
        self.eval_calls = []

    async def set(self, *args, **kwargs):
        self.set_calls.append((args, kwargs))
        return self.set_result

    async def eval(self, *args):
        self.eval_calls.append(args)
        if self.eval_error:
            raise self.eval_error
        return 1


@pytest.mark.asyncio
async def test_identity_verify_lock_uses_nx_ttl(monkeypatch):
    redis = _FakeRedis(set_result=True)

    async def fake_redis():
        return redis

    monkeypatch.setattr(identity, "_get_hlr_redis", fake_redis)

    lock_key, token = await _acquire_identity_verify_lock("a" * 64)

    assert lock_key == "identity:verify:lock:" + "a" * 64
    assert token
    assert redis.set_calls == [
        (
            (lock_key, token),
            {"ex": IDENTITY_VERIFY_LOCK_TTL_SECONDS, "nx": True},
        )
    ]


@pytest.mark.asyncio
async def test_identity_verify_lock_conflict_returns_409(monkeypatch):
    redis = _FakeRedis(set_result=False)

    async def fake_redis():
        return redis

    monkeypatch.setattr(identity, "_get_hlr_redis", fake_redis)

    with pytest.raises(HTTPException) as exc:
        await _acquire_identity_verify_lock("a" * 64)

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_identity_verify_lock_release_uses_owner_token(monkeypatch):
    redis = _FakeRedis()

    async def fake_redis():
        return redis

    monkeypatch.setattr(identity, "_get_hlr_redis", fake_redis)

    await _release_identity_verify_lock("identity:verify:lock:test", "token")

    assert redis.eval_calls
    assert redis.eval_calls[0][1:] == (1, "identity:verify:lock:test", "token")


@pytest.mark.asyncio
async def test_identity_verify_lock_release_is_best_effort(monkeypatch):
    redis = _FakeRedis(eval_error=RuntimeError("redis down"))

    async def fake_redis():
        return redis

    monkeypatch.setattr(identity, "_get_hlr_redis", fake_redis)

    await _release_identity_verify_lock("identity:verify:lock:test", "token")
