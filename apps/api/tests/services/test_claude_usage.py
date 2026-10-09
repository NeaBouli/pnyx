from services.claude_usage import estimate_cost_usd, read_budget, token_total, track_usage


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.expired: set[str] = set()

    async def get(self, key):
        return self.store.get(key)

    async def incrby(self, key, amount):
        self.store[key] = str(int(self.store.get(key, "0")) + int(amount))

    async def incrbyfloat(self, key, amount):
        self.store[key] = str(float(self.store.get(key, "0")) + float(amount))

    async def expire(self, key, _ttl):
        self.expired.add(key)


def test_token_total_and_cost_estimate():
    usage = {"input_tokens": 1000, "output_tokens": 200}

    assert token_total(usage) == 1200
    assert estimate_cost_usd(usage) == 0.002


async def test_track_usage_writes_total_and_purpose_keys():
    redis = FakeRedis()

    total = await track_usage(redis, {"input_tokens": 1000, "output_tokens": 200}, purpose="analysis")

    assert total == 1200
    assert any(key.startswith("claude:tokens:20") for key in redis.store)
    assert any(key.startswith("claude:tokens:analysis:20") for key in redis.store)
    assert any(key.startswith("claude:cost_usd:analysis:20") for key in redis.store)


async def test_read_budget_splits_analysis_from_chat_tokens():
    redis = FakeRedis()
    await track_usage(redis, {"input_tokens": 1000, "output_tokens": 200}, purpose="analysis")
    await track_usage(redis, {"input_tokens": 300, "output_tokens": 100}, purpose="chat")

    budget = await read_budget(redis, api_key_configured=True)

    assert budget["tokens_today"] == 1600
    assert budget["analysis_tokens_today"] == 1200
    assert budget["chat_tokens_today"] == 400
    assert budget["is_active"] is True
    assert budget["balance_available"] is False
    assert budget["estimated_cost_usd_today"] > 0


def _day_month():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")


def test_reservation_size_is_utf8_bound_plus_max_output():
    from services.claude_usage import estimate_cost_usd, reservation_size

    system, user = "Κανόνες", "Ερώτηση: ψήφος;"
    tokens, cost = reservation_size(system, user, 400)
    input_bound = len(system.encode("utf-8")) + len(user.encode("utf-8"))
    assert tokens == input_bound + 400
    assert cost == estimate_cost_usd({"input_tokens": input_bound, "output_tokens": 400})


async def test_gate_admits_under_limit_and_release_restores():
    from services.claude_usage import release_budget, reserve_budget
    from tests.budget_fakes import BudgetFakeRedis

    redis = BudgetFakeRedis()
    res = await reserve_budget(redis, 3000, 0.01)
    assert res is not None
    assert redis.store[res.tokens_key] == "3000"
    await release_budget(redis, res)
    assert int(redis.store[res.tokens_key]) == 0
    assert abs(float(redis.store[res.cost_key])) < 1e-9


async def test_gate_closes_when_tokens_would_exceed_daily_limit():
    from services.claude_usage import DAILY_TOKEN_LIMIT, reserve_budget
    from tests.budget_fakes import BudgetFakeRedis

    day, _ = _day_month()
    redis = BudgetFakeRedis({f"claude:tokens:{day}": str(DAILY_TOKEN_LIMIT - 2999)})
    assert await reserve_budget(redis, 3000, 0.0) is None


async def test_gate_closes_when_cost_would_exceed_monthly_budget():
    from services.claude_usage import MONTHLY_BUDGET_EUR, reserve_budget
    from tests.budget_fakes import BudgetFakeRedis

    _, month = _day_month()
    redis = BudgetFakeRedis({f"claude:cost_usd:{month}": repr(MONTHLY_BUDGET_EUR - 0.005)})
    assert await reserve_budget(redis, 10, 0.01) is None


async def test_in_flight_cost_counts_against_monthly_budget():
    from services.claude_usage import MONTHLY_BUDGET_EUR, reserve_budget
    from tests.budget_fakes import BudgetFakeRedis

    redis = BudgetFakeRedis()
    first = await reserve_budget(redis, 10, MONTHLY_BUDGET_EUR - 0.001)
    assert first is not None
    assert await reserve_budget(redis, 10, 0.01) is None


async def test_gate_fails_closed_on_redis_error():
    from services.claude_usage import reserve_budget
    from tests.budget_fakes import BudgetFakeRedis

    assert await reserve_budget(BudgetFakeRedis(broken=True), 10, 0.0) is None


async def test_concurrent_reservations_cannot_exceed_daily_limit():
    import asyncio

    from services.claude_usage import DAILY_TOKEN_LIMIT, reserve_budget
    from tests.budget_fakes import BudgetFakeRedis

    day, _ = _day_month()
    redis = BudgetFakeRedis({f"claude:tokens:{day}": str(DAILY_TOKEN_LIMIT - 6000)})
    results = await asyncio.gather(*(reserve_budget(redis, 3000, 0.0) for _ in range(10)))
    assert sum(r is not None for r in results) == 2


async def test_charge_reservation_books_full_reservation():
    from services.claude_usage import charge_reservation, reserve_budget
    from tests.budget_fakes import BudgetFakeRedis

    day, month = _day_month()
    redis = BudgetFakeRedis()
    res = await reserve_budget(redis, 3000, 0.02)
    assert await charge_reservation(redis, res) is True
    assert redis.store[f"claude:tokens:{day}"] == "3000"
    assert abs(float(redis.store[f"claude:cost_usd:{month}"]) - 0.02) < 1e-9


async def test_lua_script_on_real_redis_when_available():
    """Runs the real Lua script in CI (redis service); skipped without Redis."""
    import os

    import pytest
    import redis.asyncio as aioredis

    from services.claude_usage import release_budget, reserve_budget

    from urllib.parse import urlparse

    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    if urlparse(url).hostname not in {"localhost", "127.0.0.1"}:
        pytest.skip("only against a local/CI Redis, never a shared or production instance")
    client = aioredis.from_url(url, decode_responses=True)
    try:
        await client.ping()
    except Exception:
        pytest.skip("no Redis available")
    day, month = _day_month()
    keys = [f"claude:tokens:{day}", f"claude:reserved_tokens:{day}",
            f"claude:cost_usd:{month}", f"claude:reserved_cost_usd:{month}"]
    saved = {k: await client.get(k) for k in keys}
    try:
        for k in keys:
            await client.delete(k)
        from services.claude_usage import DAILY_TOKEN_LIMIT
        await client.set(keys[0], DAILY_TOKEN_LIMIT - 5000)
        first = await reserve_budget(client, 3000, 0.01)
        second = await reserve_budget(client, 3000, 0.01)
        assert first is not None and second is None
        await release_budget(client, first)
        assert int(await client.get(keys[1])) == 0
    finally:
        for k, v in saved.items():
            if v is None:
                await client.delete(k)
            else:
                await client.set(k, v)
        await client.aclose()
