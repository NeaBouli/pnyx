import pytest
from starlette.requests import Request

from routers import contact, public_api


def _request(headers: dict[str, str] | None = None, client_host: str = "10.0.0.4") -> Request:
    raw_headers = [
        (key.lower().encode(), value.encode())
        for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": raw_headers,
            "client": (client_host, 12345),
        }
    )


class FakeRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.expirations: dict[str, int] = {}
        self.hashes: dict[str, dict[str, str]] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds

    async def eval(self, _script: str, _numkeys: int, key: str, seconds: int) -> int:
        count = await self.incr(key)
        if count == 1:
            await self.expire(key, seconds)
        return count

    async def hexists(self, name: str, key: str) -> bool:
        return key in self.hashes.get(name, {})

    async def hset(self, name: str, key: str, value: str) -> None:
        self.hashes.setdefault(name, {})[key] = value


class FakeBrevoResponse:
    status_code = 201
    text = "ok"


class FakeAsyncClient:
    payloads: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        self.payloads.append(kwargs["json"])
        return FakeBrevoResponse()


def _redis_factory(redis: FakeRedis):
    async def _get_redis():
        return redis

    return _get_redis


@pytest.mark.asyncio
async def test_contact_email_uses_redacted_request_ref(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setattr(contact, "_get_redis", _redis_factory(redis))
    monkeypatch.setattr(contact.httpx, "AsyncClient", FakeAsyncClient)
    FakeAsyncClient.payloads.clear()

    body = contact.NgoContactRequest(
        first_name="Gio",
        last_name="Test",
        email="gio@example.com",
        message="hello",
        consent=True,
    )
    req = _request({"X-Forwarded-For": "198.51.100.44"})

    response = await contact.contact_ngo(body, req)

    assert response["status"] == "ok"
    html = FakeAsyncClient.payloads[0]["htmlContent"]
    assert "Request ref: ipref:" in html
    assert "198.51.100.44" not in html
    assert all("198.51.100.44" not in key for key in redis.counts)


@pytest.mark.asyncio
async def test_public_api_anonymous_rate_limit_uses_hashed_ip_bucket(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(public_api, "get_redis", _redis_factory(redis))
    req = _request({"X-Forwarded-For": "198.51.100.55"})

    await public_api.rate_limit_check(req, x_api_key=None)

    assert len(redis.counts) == 1
    key = next(iter(redis.counts))
    assert key.startswith("ratelimit:public_api:anon:")
    assert "198.51.100.55" not in key


@pytest.mark.asyncio
async def test_invalid_api_key_does_not_create_per_key_limit_bypass(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(public_api, "get_redis", _redis_factory(redis))
    req = _request({"X-Forwarded-For": "198.51.100.55"})

    await public_api.rate_limit_check(req, x_api_key="fake-key")

    key = next(iter(redis.counts))
    assert key.startswith("ratelimit:public_api:anon:")
    assert "fake-key" not in key


@pytest.mark.asyncio
async def test_public_api_key_generation_uses_hashed_ip_bucket(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    monkeypatch.setattr(public_api, "get_redis", _redis_factory(redis))
    req = _request({"X-Forwarded-For": "198.51.100.66"})

    response = await public_api.generate_api_key(req)

    assert response["api_key"].startswith("ek_")
    assert any(key.startswith("ratelimit:public_api:keygen:") for key in redis.counts)
    assert all("198.51.100.66" not in key for key in redis.counts)
