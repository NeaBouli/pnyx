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
