import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_cors_preflight_allows_known_origin_method_and_headers():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/v1/bills",
            headers={
                "Origin": "https://ekklesia.gr",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Authorization, X-API-Key",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://ekklesia.gr"
    assert "POST" in response.headers["access-control-allow-methods"]
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "content-type" in allowed_headers
    assert "authorization" in allowed_headers
    assert "x-api-key" in allowed_headers
    assert "x-nullifier" not in allowed_headers


@pytest.mark.asyncio
async def test_cors_preflight_rejects_retired_nullifier_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/v1/bills/example/flag",
            headers={
                "Origin": "https://ekklesia.gr",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-Nullifier",
            },
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_cors_exposes_vote_read_integrity_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/does-not-exist",
            headers={"Origin": "https://ekklesia.gr"},
        )

    exposed_headers = response.headers["access-control-expose-headers"].lower()
    assert "x-vote-read-integrity" in exposed_headers


@pytest.mark.asyncio
async def test_cors_preflight_rejects_unknown_request_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/v1/bills",
            headers={
                "Origin": "https://ekklesia.gr",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-Not-Allowed",
            },
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_cors_preflight_rejects_unknown_origin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/v1/bills",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_cors_preflight_rejects_trace_method():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/v1/bills",
            headers={
                "Origin": "https://ekklesia.gr",
                "Access-Control-Request-Method": "TRACE",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

    assert response.status_code == 400
