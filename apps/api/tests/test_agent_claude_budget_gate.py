"""The paid Claude fallback must not call Anthropic once the budget gate closes (T-615)."""
import pytest

from routers import agent


class _FakeRedis:
    def __init__(self, store=None):
        self.store = dict(store or {})

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value):
        self.store[key] = value

    async def incrby(self, key, amount):
        self.store[key] = str(int(self.store.get(key, "0")) + int(amount))
        return int(self.store[key])

    async def decrby(self, key, amount):
        self.store[key] = str(int(self.store.get(key, "0")) - int(amount))
        return int(self.store[key])

    async def incrbyfloat(self, key, amount):
        self.store[key] = str(float(self.store.get(key, "0")) + float(amount))

    async def expire(self, key, ttl):
        return True


HTTP_ATTEMPTS: list[str] = []


class _NoHttp:
    """Records any attempt to build an HTTP client (the code swallows exceptions)."""

    def __init__(self, *args, **kwargs):
        HTTP_ATTEMPTS.append("client")
        raise AssertionError("Anthropic must not be called")


def _setup(monkeypatch, redis):
    monkeypatch.setattr(agent, "ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(agent.aioredis, "from_url", lambda *a, **k: redis)


@pytest.mark.asyncio
async def test_no_paid_call_when_daily_limit_reached(monkeypatch):
    from services.claude_usage import DAILY_TOKEN_LIMIT
    from datetime import datetime, timezone

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    redis = _FakeRedis({f"claude:tokens:{day}": str(DAILY_TOKEN_LIMIT)})
    _setup(monkeypatch, redis)
    monkeypatch.setattr(agent.httpx, "AsyncClient", _NoHttp)

    HTTP_ATTEMPTS.clear()
    assert await agent._claude_answer("q", [], "el") is None
    assert HTTP_ATTEMPTS == []


@pytest.mark.asyncio
async def test_no_paid_call_when_redis_is_down(monkeypatch):
    class _Down:
        async def get(self, key):
            raise ConnectionError("down")

    _setup(monkeypatch, _Down())
    monkeypatch.setattr(agent.httpx, "AsyncClient", _NoHttp)

    HTTP_ATTEMPTS.clear()
    assert await agent._claude_answer("q", [], "el") is None
    assert HTTP_ATTEMPTS == []


@pytest.mark.asyncio
async def test_one_call_under_limit_tracks_usage_and_releases_reservation(monkeypatch):
    from datetime import datetime, timezone

    calls = []

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"content": [{"text": "answer"}], "usage": {"input_tokens": 900, "output_tokens": 100}}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *args, **kwargs):
            calls.append(kwargs["json"]["max_tokens"])
            return _Resp()

    redis = _FakeRedis()
    _setup(monkeypatch, redis)
    monkeypatch.setattr(agent.httpx, "AsyncClient", _Client)

    assert await agent._claude_answer("q", [], "el") == "answer"
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert calls == [400]
    assert redis.store[f"claude:tokens:{day}"] == "1000"
    assert redis.store[f"claude:reserved:{day}"] == "0"
