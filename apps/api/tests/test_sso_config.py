import importlib
import base64
import hashlib
import hmac
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
        self.consumed = []
        self.sso_url = sso_url
        self.qr = qr or {
            "status": "authenticated",
            "purpose": "forum_login",
            "nullifier_hash": "n" * 64,
            "public_key_hex": "p" * 64,
        }

    async def get(self, key):
        return self.sso_url if key.startswith("sso:discourse:") else None

    async def getdel(self, key):
        if not key.startswith("sso:discourse:") or self.sso_url is None:
            return None
        value = self.sso_url
        self.sso_url = None
        self.consumed.append(key)
        return value

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


class _InitiateRedis:
    def __init__(self):
        self.values = {}

    async def setex(self, key, ttl, value):
        self.values[key] = (ttl, value)


def _signed_sso_request(sso, params):
    return sso._build_payload(params)


def _sign_encoded_payload(encoded):
    signature = hmac.new(b"secret", encoded.encode(), hashlib.sha256).hexdigest()
    return encoded, signature


@pytest.mark.asyncio
async def test_forum_sso_initiate_accepts_canonical_return_url(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")
    fake_redis = _InitiateRedis()
    monkeypatch.setattr(sso, "_redis", _redis_factory(fake_redis))
    return_url = "https://pnyx.ekklesia.gr/session/sso_login"
    payload, signature = _signed_sso_request(
        sso, {"nonce": "nonce12345", "return_sso_url": return_url}
    )

    response = await sso.discourse_sso_initiate(sso=payload, sig=signature)

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "https://ekklesia.gr/el/sso-verify?nonce=nonce12345"
    )
    assert fake_redis.values["sso:discourse:nonce12345"] == (300, return_url)


@pytest.mark.asyncio
async def test_forum_sso_initiate_accepts_explicit_https_port(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")
    fake_redis = _InitiateRedis()
    monkeypatch.setattr(sso, "_redis", _redis_factory(fake_redis))
    return_url = "https://pnyx.ekklesia.gr:443/session/sso_login"
    payload, signature = _signed_sso_request(
        sso, {"nonce": "nonce12345", "return_sso_url": return_url}
    )

    response = await sso.discourse_sso_initiate(sso=payload, sig=signature)

    assert response.status_code == 302
    assert fake_redis.values["sso:discourse:nonce12345"] == (300, return_url)


@pytest.mark.parametrize(
    "return_url",
    [
        "http://pnyx.ekklesia.gr/session/sso_login",
        "https://attacker.example/session/sso_login",
        "https://pnyx.ekklesia.gr.attacker.example/session/sso_login",
        "https://attacker.example@pnyx.ekklesia.gr/session/sso_login",
        "https://pnyx.ekklesia.gr:8443/session/sso_login",
        "https://pnyx.ekklesia.gr/session/sso_login?next=https://attacker.example",
        "https://pnyx.ekklesia.gr/session/sso_login#fragment",
        "https://pnyx.ekklesia.gr/session/other",
        "https://pnyx.ekklesia.gr/session/sso_login?",
        " https://pnyx.ekklesia.gr/session/sso_login",
        "https://pnyx.ekklesia.gr/session/sso_login\t",
        "https://pnyx.ekklesia.gr/session/sso_login\r\n",
    ],
)
@pytest.mark.asyncio
async def test_forum_sso_initiate_rejects_unsafe_return_url(monkeypatch, return_url):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")
    fake_redis = _InitiateRedis()
    monkeypatch.setattr(sso, "_redis", _redis_factory(fake_redis))
    payload, signature = _signed_sso_request(
        sso, {"nonce": "nonce12345", "return_sso_url": return_url}
    )

    with pytest.raises(sso.HTTPException) as exc:
        await sso.discourse_sso_initiate(sso=payload, sig=signature)

    assert exc.value.status_code == 400
    assert fake_redis.values == {}


@pytest.mark.asyncio
async def test_forum_sso_initiate_rejects_invalid_signature(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")
    fake_redis = _InitiateRedis()
    monkeypatch.setattr(sso, "_redis", _redis_factory(fake_redis))
    payload, _signature = _signed_sso_request(
        sso,
        {
            "nonce": "nonce12345",
            "return_sso_url": "https://pnyx.ekklesia.gr/session/sso_login",
        },
    )

    with pytest.raises(sso.HTTPException) as exc:
        await sso.discourse_sso_initiate(sso=payload, sig="0" * 64)

    assert exc.value.status_code == 403
    assert fake_redis.values == {}


@pytest.mark.parametrize(
    "encoded_payload",
    [
        "%%%",
        base64.b64encode(
            b"nonce=one&nonce=two&return_sso_url="
            b"https%3A%2F%2Fpnyx.ekklesia.gr%2Fsession%2Fsso_login"
        ).decode(),
    ],
)
@pytest.mark.asyncio
async def test_forum_sso_initiate_rejects_malformed_or_duplicate_payload(
    monkeypatch, encoded_payload
):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")
    fake_redis = _InitiateRedis()
    monkeypatch.setattr(sso, "_redis", _redis_factory(fake_redis))
    payload, signature = _sign_encoded_payload(encoded_payload)

    with pytest.raises(sso.HTTPException) as exc:
        await sso.discourse_sso_initiate(sso=payload, sig=signature)

    assert exc.value.status_code == 400
    assert fake_redis.values == {}


@pytest.mark.asyncio
async def test_forum_sso_browser_callback_consumes_nonce_once(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")
    fake_redis = _FakeRedis()
    monkeypatch.setattr(sso, "_redis", _redis_factory(fake_redis))
    import keypair

    monkeypatch.setattr(keypair, "verify_signature", lambda *_args: True)
    identity = SimpleNamespace(
        nullifier_hash="n" * 64,
        public_key_hex="p" * 64,
        dimos_id=None,
        periferia_id=None,
    )

    result = await sso.discourse_sso_callback(
        request=SimpleNamespace(),
        nonce="nonce12345",
        public_key_hex="p" * 64,
        signature_hex="s" * 128,
        db=_FakeDB(identity),
    )

    assert result["redirect_url"].startswith(
        "https://pnyx.ekklesia.gr/session/sso_login?sso="
    )
    assert "sso:discourse:nonce12345" in fake_redis.consumed

    with pytest.raises(sso.HTTPException) as exc:
        await sso.discourse_sso_callback(
            request=SimpleNamespace(),
            nonce="nonce12345",
            public_key_hex="p" * 64,
            signature_hex="s" * 128,
            db=_FakeDB(identity),
        )

    assert exc.value.status_code == 410


@pytest.mark.asyncio
async def test_forum_sso_browser_callback_rejects_noncanonical_stored_url(
    monkeypatch,
):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")
    fake_redis = _FakeRedis(
        sso_url="https://attacker.example/session/sso_login"
    )
    monkeypatch.setattr(sso, "_redis", _redis_factory(fake_redis))
    import keypair

    monkeypatch.setattr(keypair, "verify_signature", lambda *_args: True)

    with pytest.raises(sso.HTTPException) as exc:
        await sso.discourse_sso_callback(
            request=SimpleNamespace(),
            nonce="nonce12345",
            public_key_hex="p" * 64,
            signature_hex="s" * 128,
            db=_FakeDB(None),
        )

    assert exc.value.status_code == 410
    assert fake_redis.consumed == []


@pytest.mark.asyncio
async def test_forum_sso_nonce_consume_rejects_changed_callback_target(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")
    fake_redis = _FakeRedis(
        sso_url="https://pnyx.ekklesia.gr:443/session/sso_login"
    )

    with pytest.raises(sso.HTTPException) as exc:
        await sso._consume_discourse_nonce(
            fake_redis,
            "nonce12345",
            "https://pnyx.ekklesia.gr/session/sso_login",
        )

    assert exc.value.status_code == 410
    assert "sso:discourse:nonce12345" in fake_redis.consumed


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
    assert "sso:discourse:nonce12345" in fake_redis.consumed
    assert "polis_qr:session12345" in fake_redis.deleted

    with pytest.raises(sso.HTTPException) as exc:
        await sso.discourse_sso_qr_complete(
            sso.DiscourseQRCompleteRequest(
                nonce="nonce12345", session_id="session12345"
            ),
            db=_FakeDB(identity),
        )

    assert exc.value.status_code == 410


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
