import importlib
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _reload_sso(monkeypatch, *, environment: str, secret: str = "", salt: str = ""):
    monkeypatch.setenv("ENVIRONMENT", environment)
    if secret:
        monkeypatch.setenv("DISCOURSE_SSO_SECRET", secret)
    else:
        monkeypatch.delenv("DISCOURSE_SSO_SECRET", raising=False)
    if salt:
        monkeypatch.setenv("FORUM_SSO_SALT", salt)
    else:
        monkeypatch.delenv("FORUM_SSO_SALT", raising=False)

    import routers.sso as sso
    return importlib.reload(sso)


@pytest.mark.parametrize(
    ("secret", "salt", "missing"),
    [
        ("", "", "DISCOURSE_SSO_SECRET, FORUM_SSO_SALT"),
        ("", "salt", "DISCOURSE_SSO_SECRET"),
        ("secret", "", "FORUM_SSO_SALT"),
    ],
)
def test_forum_sso_config_fails_closed_in_production(monkeypatch, secret, salt, missing):
    sso = _reload_sso(monkeypatch, environment="production", secret=secret, salt=salt)

    with pytest.raises(RuntimeError, match=missing):
        sso.validate_forum_sso_config()


def test_forum_sso_config_accepts_explicit_secret_and_salt(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")

    sso.validate_forum_sso_config()


def test_forum_sso_config_warns_only_in_development(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="development", secret="", salt="")

    sso.validate_forum_sso_config()


class _FakeRedis:
    def __init__(self, *, sso_url="https://pnyx.ekklesia.gr/session/sso_login", qr=None):
        self.deleted = []
        self.sso_url = sso_url
        self.qr = qr or {
            "status": "authenticated",
            "purpose": "forum_login",
            "nullifier_hash": "n" * 64,
            "public_key_hex": "p" * 64,
        }

    async def get(self, key):
        return self.sso_url if key.startswith("sso:discourse:") else None

    async def hgetall(self, key):
        return self.qr if key.startswith("polis_qr:") else {}

    async def delete(self, key):
        self.deleted.append(key)


class _FakeResult:
    def __init__(self, identity):
        self.identity = identity

    def scalar_one_or_none(self):
        return self.identity


class _FakeDB:
    def __init__(self, identity):
        self.identity = identity

    async def execute(self, _query):
        return _FakeResult(self.identity)

    async def get(self, _model, _id):
        return None


def _redis_factory(fake_redis):
    async def _fake_redis():
        return fake_redis
    return _fake_redis


@pytest.mark.asyncio
async def test_forum_sso_qr_complete_returns_discourse_redirect(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")
    fake_redis = _FakeRedis()
    monkeypatch.setattr(sso, "_redis", _redis_factory(fake_redis))
    identity = SimpleNamespace(
        nullifier_hash="n" * 64,
        public_key_hex="p" * 64,
        dimos_id=None,
        periferia_id=None,
    )

    result = await sso.discourse_sso_qr_complete(
        sso.DiscourseQRCompleteRequest(nonce="nonce12345", session_id="session12345"),
        db=_FakeDB(identity),
    )

    assert result["redirect_url"].startswith("https://pnyx.ekklesia.gr/session/sso_login?sso=")
    assert "&sig=" in result["redirect_url"]
    assert "sso:discourse:nonce12345" in fake_redis.deleted
    assert "polis_qr:session12345" in fake_redis.deleted


@pytest.mark.asyncio
async def test_forum_sso_qr_complete_rejects_wrong_purpose(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")
    monkeypatch.setattr(
        sso,
        "_redis",
        _redis_factory(_FakeRedis(qr={"status": "authenticated", "purpose": "vote"})),
    )

    with pytest.raises(sso.HTTPException) as exc:
        await sso.discourse_sso_qr_complete(
            sso.DiscourseQRCompleteRequest(nonce="nonce12345", session_id="session12345"),
            db=_FakeDB(None),
        )

    assert exc.value.status_code == 400
