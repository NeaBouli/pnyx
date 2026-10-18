"""Offline scraper clock: exercise real pacing without waiting or making requests."""
import asyncio
import sys
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture
def offline_http_client(monkeypatch):
    """Keep OS certificate/proxy setup out of the short deadline tests."""
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", partial(httpx.AsyncClient, verify=False, trust_env=False))


@pytest.fixture
def scraper_clock(monkeypatch):
    from services import diavgeia_client, parliament_fetcher, scraper_http

    real_sleep = asyncio.sleep

    class Clock:
        now = 1000.0
        sleeps = None

        def monotonic(self):
            return self.now

        def time(self):
            return 1_700_000_000 + self.now

        async def sleep(self, delay):
            self.sleeps.append(delay)
            self.now += delay
            await real_sleep(0)

    clock = Clock()
    clock.sleeps = []
    monkeypatch.setattr(scraper_http, "time", clock)
    fake_asyncio = SimpleNamespace(sleep=clock.sleep, Lock=asyncio.Lock)
    for module in (scraper_http, parliament_fetcher, diavgeia_client):
        monkeypatch.setattr(module, "asyncio", fake_asyncio)
    limiter = scraper_http.HostRateLimiter()
    monkeypatch.setattr(scraper_http, "host_limiter", limiter)
    monkeypatch.setattr(parliament_fetcher, "host_limiter", limiter)
    clock.limiter = limiter
    return clock
