import pytest

from routers import identity


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]


@pytest.mark.asyncio
async def test_hlr_usage_counts_each_queried_provider_once(monkeypatch) -> None:
    redis = FakeRedis()

    async def fake_get_hlr_redis() -> FakeRedis:
        return redis

    monkeypatch.setattr(identity, "_get_hlr_redis", fake_get_hlr_redis)

    await identity._increment_hlr_usage(["primary", "fallback", "primary"])

    assert redis.values == {
        identity.HLR_PRIMARY_REDIS_KEY: 1,
        identity.HLR_FALLBACK_REDIS_KEY: 1,
    }


@pytest.mark.asyncio
async def test_hlr_usage_does_not_use_stale_global_failover_state(monkeypatch) -> None:
    redis = FakeRedis()

    async def fake_get_hlr_redis() -> FakeRedis:
        return redis

    monkeypatch.setattr(identity, "_get_hlr_redis", fake_get_hlr_redis)

    await identity._increment_hlr_usage(["primary"])

    assert redis.values == {identity.HLR_PRIMARY_REDIS_KEY: 1}
