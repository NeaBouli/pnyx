"""Fixtures for API tests — cleanup shared resources between tests."""
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
