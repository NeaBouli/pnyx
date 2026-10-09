"""The paid Claude fallback stays inside the enforced budget (T-615)."""
from datetime import datetime, timezone

import httpx
import pytest

from routers import agent
from tests.budget_fakes import BudgetFakeRedis

HTTP_ATTEMPTS: list[str] = []


def _day_month():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")


class _NoHttp:
    """Records any attempt to build an HTTP client (the code swallows exceptions)."""

    def __init__(self, *args, **kwargs):
        HTTP_ATTEMPTS.append("client")
        raise AssertionError("Anthropic must not be called")


def _client(behaviour):
    class _Resp:
        def __init__(self, status=200, payload=None):
            self.status_code = status
            self._payload = payload
            self.text = "error"

        def raise_for_status(self):
            if self.status_code >= 400:
                request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
                raise httpx.HTTPStatusError("err", request=request, response=self)

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *args, **kwargs):
            HTTP_ATTEMPTS.append("client")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *args, **kwargs):
            if behaviour == "timeout":
                raise httpx.ReadTimeout("timeout after send")
            if isinstance(behaviour, int):
                return _Resp(status=behaviour)
            return _Resp(payload=behaviour)

    return _Client


def _setup(monkeypatch, redis, http):
    HTTP_ATTEMPTS.clear()
    monkeypatch.setattr(agent, "ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(agent.aioredis, "from_url", lambda *a, **k: redis)
    monkeypatch.setattr(agent.httpx, "AsyncClient", http)


def _held(redis):
    day, month = _day_month()
    return (
        int(float(redis.store.get(f"claude:reserved_tokens:{day}", "0"))),
        float(redis.store.get(f"claude:reserved_cost_usd:{month}", "0")),
    )


@pytest.mark.asyncio
async def test_no_paid_call_when_daily_limit_reached(monkeypatch):
    from services.claude_usage import DAILY_TOKEN_LIMIT

    day, _ = _day_month()
    redis = BudgetFakeRedis({f"claude:tokens:{day}": str(DAILY_TOKEN_LIMIT)})
    _setup(monkeypatch, redis, _NoHttp)
    assert await agent._claude_answer("q", [], "el") is None
    assert HTTP_ATTEMPTS == []


@pytest.mark.asyncio
async def test_no_paid_call_when_monthly_budget_reached(monkeypatch):
    from services.claude_usage import MONTHLY_BUDGET_EUR

    _, month = _day_month()
    redis = BudgetFakeRedis({f"claude:cost_usd:{month}": repr(MONTHLY_BUDGET_EUR)})
    _setup(monkeypatch, redis, _NoHttp)
    assert await agent._claude_answer("q", [], "el") is None
    assert HTTP_ATTEMPTS == []


@pytest.mark.asyncio
async def test_no_paid_call_when_redis_is_down(monkeypatch):
    _setup(monkeypatch, BudgetFakeRedis(broken=True), _NoHttp)
    assert await agent._claude_answer("q", [], "el") is None
    assert HTTP_ATTEMPTS == []


@pytest.mark.asyncio
async def test_success_tracks_real_usage_and_releases(monkeypatch):
    payload = {"content": [{"text": "answer"}], "usage": {"input_tokens": 900, "output_tokens": 100}}
    redis = BudgetFakeRedis()
    _setup(monkeypatch, redis, _client(payload))
    assert await agent._claude_answer("q", [], "el") == "answer"
    day, _ = _day_month()
    assert redis.store[f"claude:tokens:{day}"] == "1000"
    held_tokens, held_cost = _held(redis)
    assert held_tokens == 0 and abs(held_cost) < 1e-9


@pytest.mark.parametrize("behaviour", ["timeout", 500, 529])
@pytest.mark.asyncio
async def test_uncertain_outcome_books_full_reservation(monkeypatch, behaviour):
    redis = BudgetFakeRedis()
    _setup(monkeypatch, redis, _client(behaviour))
    assert await agent._claude_answer("q", [], "el") is None
    day, month = _day_month()
    booked = int(redis.store[f"claude:tokens:{day}"])
    assert booked > agent.CLAUDE_MAX_OUTPUT_TOKENS  # prompt bytes + max output
    assert float(redis.store[f"claude:cost_usd:{month}"]) > 0
    held_tokens, _ = _held(redis)
    assert held_tokens == 0


@pytest.mark.asyncio
async def test_missing_usage_books_full_reservation(monkeypatch):
    redis = BudgetFakeRedis()
    _setup(monkeypatch, redis, _client({"content": [{"text": "answer"}], "usage": {}}))
    assert await agent._claude_answer("q", [], "el") == "answer"
    day, _ = _day_month()
    assert int(redis.store[f"claude:tokens:{day}"]) > agent.CLAUDE_MAX_OUTPUT_TOKENS


@pytest.mark.asyncio
async def test_client_error_is_not_charged_and_releases(monkeypatch):
    redis = BudgetFakeRedis()
    _setup(monkeypatch, redis, _client(400))
    assert await agent._claude_answer("q", [], "el") is None
    day, _ = _day_month()
    assert f"claude:tokens:{day}" not in redis.store
    assert _held(redis)[0] == 0


@pytest.mark.asyncio
async def test_reservation_kept_when_cost_cannot_be_booked(monkeypatch):
    redis = BudgetFakeRedis()
    _setup(monkeypatch, redis, _client("timeout"))

    async def failing_charge(*args, **kwargs):
        return False

    monkeypatch.setattr(agent, "charge_reservation", failing_charge)
    assert await agent._claude_answer("q", [], "el") is None
    assert _held(redis)[0] > agent.CLAUDE_MAX_OUTPUT_TOKENS
