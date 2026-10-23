"""Fixtures for API tests — cleanup shared resources between tests."""
import os

# The global slowapi limiter (60/min/IP) would break request-heavy test
# modules; tests run with the limiter disabled unless explicitly enabled.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# EVA-033: invite codes are hashed with SERVER_SALT; tests need a non-production value.
os.environ.setdefault("SERVER_SALT", "test-only-server-salt-not-for-production")

import pytest
from routers import public_api


@pytest.fixture(autouse=True)
def scraper_redis(monkeypatch):
    """Isolate host cooldown storage; model Redis expiry and WATCH offline."""
    from contextlib import asynccontextmanager
    from redis.exceptions import WatchError
    from services import scraper_http, parliament_fetcher

    class Store:
        def __init__(self):
            self.values = {}
            self.expiry = {}
            self.versions = {}
            self.down = False
            self.write_down = False
            self.writes = 0

        async def get(self, key):
            if self.down:
                raise ConnectionError("Redis unavailable")
            if key in self.expiry and self.expiry[key] <= scraper_http.time.time():
                self.values.pop(key, None)
                self.expiry.pop(key, None)
                self.versions[key] = self.versions.get(key, 0) + 1
            return self.values.get(key)

        def pipeline(self):
            return Pipeline(self)

    class Pipeline:
        def __init__(self, store):
            self.store = store
            self.watched = {}
            self.ops = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def watch(self, key):
            await self.store.get(key)
            self.watched[key] = self.store.versions.get(key, 0)

        async def get(self, key):
            return await self.store.get(key)

        def multi(self):
            pass

        def set(self, key, value, ex=None):
            self.ops.append(("set", key, value, ex))

        def delete(self, *keys):
            for key in keys:
                self.ops.append(("delete", key, None, None))

        async def execute(self):
            store = self.store
            if store.down or store.write_down:
                raise ConnectionError("Redis unavailable")
            if any(store.versions.get(k, 0) != v for k, v in self.watched.items()):
                raise WatchError()
            for op, key, value, ex in self.ops:
                store.versions[key] = store.versions.get(key, 0) + 1
                store.writes += 1
                store.expiry.pop(key, None)
                if op == "set":
                    store.values[key] = value
                    if ex is not None:
                        store.expiry[key] = scraper_http.time.time() + ex
                else:
                    store.values.pop(key, None)

    store = Store()

    @asynccontextmanager
    async def connection():
        yield store

    limiter = scraper_http.HostRateLimiter()
    monkeypatch.setattr(scraper_http, "_redis", connection)
    monkeypatch.setattr(scraper_http, "host_limiter", limiter)
    monkeypatch.setattr(parliament_fetcher, "host_limiter", limiter)
    return store


@pytest.fixture(autouse=True)
async def cleanup_redis():
    """Close the module-level Redis client after each test to prevent
    'Event loop is closed' errors when pytest-asyncio creates a new loop."""
    yield
    if public_api._redis_client is not None:
        await public_api._redis_client.aclose()
        public_api._redis_client = None
