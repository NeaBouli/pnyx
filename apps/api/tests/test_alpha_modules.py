"""
Tests für alle Alpha-Module (MOD-06, 07, 09, 11, 12, 14, 15)
Kein DB nötig — testet Route-Existenz, Validierung, Auth-Schutz.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── MOD-06 Analytics ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_info():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/analytics/info")
    assert r.status_code == 200
    assert "endpoints" in r.json()
    assert "never_tracked" in r.json()


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_analytics_overview_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/analytics/overview")
    assert r.status_code in (200, 500)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_analytics_trends_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/analytics/divergence-trends")
    assert r.status_code in (200, 500)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_analytics_top_divergence_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/analytics/top-divergence")
    assert r.status_code in (200, 500)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_analytics_timeline_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/analytics/votes-timeline")
    assert r.status_code in (200, 500)


# ── MOD-07 Notifications ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notifications_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/notifications/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "active"
    assert "SSE" in data["transport"]
    assert "WebSocket" in data["transport"]


@pytest.mark.asyncio
async def test_notifications_events_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/notifications/status")
    data = r.json()
    assert "bill.status_changed" in data["events"]
    assert "bill.vote_milestone" in data["events"]


@pytest.mark.asyncio
async def test_notifications_publish_requires_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/notifications/test/publish?event_type=test&bill_id=T",
            headers={"Authorization": "Bearer wrong"},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_notifications_publish_valid():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/notifications/test/publish?event_type=test&bill_id=T",
            headers={"Authorization": "Bearer dev-admin-key"},
        )
    assert r.status_code == 200
    assert r.json()["published"] is True


# ── MOD-09 gov.gr OAuth ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_govgr_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/auth/govgr/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "stub"
    assert "gates" in data


@pytest.mark.asyncio
async def test_govgr_gates():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/auth/govgr/status")
    gates = r.json()["gates"]
    assert gates["roadmap_publiziert"] is True
    assert gates["500_aktive_nutzer"] is False


@pytest.mark.asyncio
async def test_govgr_login_503():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/auth/govgr/login")
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_govgr_family_stub():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/auth/govgr/family/verify")
    assert r.status_code == 200
    assert r.json()["active"] is False


@pytest.mark.asyncio
async def test_govgr_info():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/auth/govgr/info")
    assert r.status_code == 200
    assert "flow" in r.json()


# ── MOD-11 Public API ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_public_info():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/public/info")
    assert r.status_code == 200
    data = r.json()
    assert "rate_limits" in data
    assert "100" in data["rate_limits"]["anonymous"]
    assert "1000" in data["rate_limits"]["with_key"]


@pytest.mark.asyncio
async def test_public_key_generate():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/public/keys/generate?label=test")
    assert r.status_code == 200
    data = r.json()
    assert data["api_key"].startswith("ek_")
    assert len(data["api_key"]) > 20


@pytest.mark.asyncio
async def test_public_key_status_no_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/public/keys/status")
    assert r.status_code == 200
    assert r.json()["authenticated"] is False


@pytest.mark.asyncio
async def test_public_key_status_invalid():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/public/keys/status", headers={"X-API-Key": "ek_invalid"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_public_key_roundtrip():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        gen = await c.post("/api/v1/public/keys/generate?label=roundtrip")
        key = gen.json()["api_key"]
        r = await c.get("/api/v1/public/keys/status", headers={"X-API-Key": key})
    assert r.status_code == 200
    assert r.json()["authenticated"] is True
    assert r.json()["label"] == "roundtrip"


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_public_bills_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/public/bills")
    assert r.status_code in (200, 500)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_public_stats_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/public/stats")
    assert r.status_code in (200, 500)


# ── MOD-12 MP Comparison ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mp_info():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/mp/info")
    assert r.status_code == 200
    assert "endpoints" in r.json()


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_mp_parties_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/mp/parties")
    assert r.status_code in (200, 500)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_mp_ranking_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/mp/ranking")
    assert r.status_code in (200, 500)


# ── MOD-14 Data Export ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_info():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/export/info")
    assert r.status_code == 200
    data = r.json()
    assert data["license"] == "CC BY 4.0"
    never = data["never_exported"]
    assert "individual_votes" in never
    assert "nullifier_hashes" in never
    assert "phone_numbers" in never


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_export_bills_csv_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/export/bills.csv")
    assert r.status_code in (200, 500)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_export_results_json_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/export/results.json")
    assert r.status_code in (200, 500)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_export_divergence_csv_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/export/divergence.csv")
    assert r.status_code in (200, 500)


# ── MOD-15 Admin Panel ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_dashboard_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/admin/dashboard", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_bills_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/admin/bills", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/admin/stats", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403


@pytest.mark.asyncio
@pytest.mark.xfail(reason="DB offline")
async def test_admin_dashboard_valid_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/admin/dashboard", headers={"Authorization": "Bearer dev-admin-key"})
    assert r.status_code in (200, 500)


@pytest.mark.asyncio
async def test_admin_review_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/admin/bills/TEST/review?approved=true", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_reset_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.delete("/api/v1/admin/bills/TEST/votes?confirm=CONFIRM_DELETE", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403


# ── Health Check — alle Module ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_all_modules():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    modules = r.json()["modules"]
    for mod in ["MOD-06", "MOD-07", "MOD-09", "MOD-11", "MOD-12", "MOD-15"]:
        assert any(mod in m for m in modules), f"{mod} nicht in Health"
