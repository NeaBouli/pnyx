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
    """Offline Redis commands/scripts with expiry, independent time and lost ACKs."""
    import json
    import math
    from contextlib import asynccontextmanager
    from services import scraper_http, parliament_fetcher

    class Store:
        def __init__(self):
            self.values = {}
            self.expiry = {}
            self.down = False
            self.write_down = False
            self.set_down = False
            self.writes = 0
            self.lose_ack = 0
            self.server_time = lambda: scraper_http.time.time()

        def _get(self, key):
            if self.down:
                raise ConnectionError("Redis unavailable")
            if key in self.expiry and self.expiry[key] <= self.server_time():
                self.values.pop(key, None)
                self.expiry.pop(key, None)
            return self.values.get(key)

        async def get(self, key):
            return self._get(key)

        def _set(self, key, value, px=None):
            self.writes += 1
            self.values[key] = str(value)
            self.expiry.pop(key, None)
            if px is not None:
                self.expiry[key] = self.server_time() + px / 1000

        async def set(self, key, value, *, nx=False, px=None):
            if self.down or self.set_down:
                raise ConnectionError("Redis unavailable")
            if nx and self._get(key) is not None:
                return None
            self._set(key, value, px)
            return True

        def _delete(self, *keys):
            for key in keys:
                self.writes += 1
                self.values.pop(key, None)
                self.expiry.pop(key, None)

        def _snapshot(self, cooldown_key, streak_key):
            raw = self._get(streak_key)
            count = 0
            if raw is not None:
                if raw.isdecimal():
                    count = int(raw)
                else:
                    old = json.loads(raw)
                    assert old['reason'] == 'http_403'
                    assert 0 < old['started_at'] < old['cooldown_until']
                    count = old['consecutive_403']
                assert type(count) is int and count > 0
            active = self._get(cooldown_key) is not None
            if active and cooldown_key not in self.expiry:
                raise ValueError("Host cooldown has no expiry")
            until = round(self.expiry[cooldown_key] * 1000) if active else 0
            return [int(not active), until, count]

        async def eval(self, script, numkeys, *args):
            # Each branch runs without yielding, just like an atomic Redis EVAL.
            if self.down:
                raise ConnectionError("Redis unavailable")
            keys, argv = args[:numkeys], args[numkeys:]
            if script == scraper_http._RELEASE:
                if self._get(keys[0]) == argv[0]:
                    self._delete(keys[0])
                    return 1
                return 0
            if script == scraper_http._ADMISSION:
                result = self._snapshot(*keys[:2])
                if argv[0] and self._get(keys[2]) != argv[0]:
                    result[0] = -1
                return result
            assert script == scraper_http._OUTCOME
            if self.write_down:
                raise ConnectionError("Redis unavailable")
            replay = self._get(keys[3]) is not None
            if not replay and self._get(keys[2]) != argv[0]:
                return [-1, 0, 0]
            result = self._snapshot(*keys[:2])
            if replay:
                return [1, *result[1:]]
            status, base, maximum, event_ttl = map(int, argv[1:])
            if status == 403:
                count = result[2] + 1
                duration = min(base * 2 ** min(count - 1, 3), maximum)
                now_ms = math.floor(self.server_time() * 1000)
                until_ms = now_ms + duration
                self._set(keys[1], count)
                self._set(keys[0], json.dumps({
                    'started_at': now_ms / 1000, 'cooldown_until': until_ms / 1000,
                    'reason': 'http_403', 'consecutive_403': count,
                }), duration)
                result = [1, until_ms, count]
            elif 200 <= status < 300 or status == 304:
                self._delete(*keys[:2])
                result = [1, 0, 0]
            self._set(keys[3], '1', event_ttl)
            if self.lose_ack:
                self.lose_ack -= 1
                raise ConnectionError("EVAL committed; acknowledgement lost")
            return [1, *result[1:]]

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
