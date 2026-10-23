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
async def cleanup_redis():
    """Close the module-level Redis client after each test to prevent
    'Event loop is closed' errors when pytest-asyncio creates a new loop."""
    yield
    if public_api._redis_client is not None:
        await public_api._redis_client.aclose()
        public_api._redis_client = None


@pytest.fixture
def campaign_support(monkeypatch):
    """Isolate provider lists in content/lease tests; real lists have HTTP tests."""
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock
    from services import newsletter_audience, newsletter_dispatch
    from services.newsletter_consent import CONFIRMED_KEY, SUPPRESSED_KEY, RECONFIRM_KEY

    monkeypatch.setenv("BREVO_NEWSLETTER_SEGMENTS", '{"el:monthly:all":1,"en:monthly:all":2}')

    async def select(store, plan):
        selected = {"campaign-fixture@example.org"} if plan.language == "el" else set()
        selected.difference_update(await store.hgetall(RECONFIRM_KEY))
        return newsletter_audience.Audience(
            await store.hgetall(CONFIRMED_KEY), await store.hgetall(SUPPRESSED_KEY), selected,
            {"selected": len(selected), "excluded": 0, "failed": 0},
        )

    @asynccontextmanager
    async def target(lease, audience):
        yield type("Target", (), {"recipients": {"listIds": [123]}, "verify": AsyncMock(), "verify_campaign": AsyncMock()})()

    monkeypatch.setattr(newsletter_audience, "select_audience", select)
    monkeypatch.setattr(newsletter_dispatch, "temporary_campaign_list", target)
    from routers import newsletter_admin
    monkeypatch.setattr(newsletter_admin, "temporary_campaign_list", target)
