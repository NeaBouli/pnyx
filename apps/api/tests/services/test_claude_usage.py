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


class GateRedis(FakeRedis):
    """FakeRedis with Redis INCRBY/DECRBY return values for the budget gate."""

    async def incrby(self, key, amount):
        await super().incrby(key, amount)
        return int(self.store[key])

    async def decrby(self, key, amount):
        self.store[key] = str(int(self.store.get(key, "0")) - int(amount))
        return int(self.store[key])


class BrokenRedis:
    async def get(self, key):
        raise ConnectionError("redis down")


def _today_month():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")


async def test_budget_gate_allows_under_limit_and_releases():
    from services.claude_usage import RESERVATION_TOKENS, release_budget, reserve_budget

    redis = GateRedis()
    day, _ = _today_month()
    key = await reserve_budget(redis)
    assert key == f"claude:reserved:{day}"
    assert redis.store[key] == str(RESERVATION_TOKENS)
    await release_budget(redis, key)
    assert redis.store[key] == "0"


async def test_budget_gate_closes_at_daily_token_limit():
    from services.claude_usage import DAILY_TOKEN_LIMIT, reserve_budget

    redis = GateRedis()
    day, _ = _today_month()
    redis.store[f"claude:tokens:{day}"] = str(DAILY_TOKEN_LIMIT)
    assert await reserve_budget(redis) is None
    assert redis.store[f"claude:reserved:{day}"] == "0"


async def test_budget_gate_closes_at_monthly_budget():
    from services.claude_usage import MONTHLY_BUDGET_EUR, reserve_budget

    redis = GateRedis()
    _, month = _today_month()
    redis.store[f"claude:cost_usd:{month}"] = str(MONTHLY_BUDGET_EUR)
    assert await reserve_budget(redis) is None


async def test_budget_gate_fails_closed_on_redis_error():
    from services.claude_usage import reserve_budget

    assert await reserve_budget(BrokenRedis()) is None


async def test_concurrent_reservations_cannot_exceed_daily_limit():
    import asyncio

    from services.claude_usage import DAILY_TOKEN_LIMIT, RESERVATION_TOKENS, reserve_budget

    redis = GateRedis()
    day, _ = _today_month()
    redis.store[f"claude:tokens:{day}"] = str(DAILY_TOKEN_LIMIT - 2 * RESERVATION_TOKENS)
    keys = await asyncio.gather(*(reserve_budget(redis) for _ in range(10)))
    assert sum(k is not None for k in keys) == 2
