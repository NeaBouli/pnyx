"""HTTP and concurrency regressions for the B01 review findings."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from limits import parse
from redis.exceptions import ConnectionError as RedisConnectionError

import main
from database import get_db
from rate_limit import BoundedMemoryStorage, ConservativeMemoryLimiter, limiter
from routers import export, parliament, payments, public_api, vaa, zk
from services import cplm, request_work
from tests.test_rate_limit_route_enforcement import limited_app


# These handlers must reject before resolving a DB dependency, including auth.
HEAVY_READS = [
    "/api/v1/analytics/divergence-trends",
    "/api/v1/analytics/top-divergence", "/api/v1/analytics/votes-timeline",
    "/api/v1/analytics/bill/target", "/api/v1/analytics/representation",
    "/api/v1/mp/compare/ND", "/api/v1/mp/bill/target",
    "/api/v1/municipal/1/voteable", "/api/v1/vote/results/latest",
    "/api/v1/vote/results/in-progress",
    "/api/v1/export/results.json",
    "/api/v1/decisions",
    "/api/v1/municipal/1/decisions", "/api/v1/regions/1/decisions",
    "/api/v1/zk/receipts/bill:target",
    "/api/v1/cplm/aggregate",
]


@pytest.mark.parametrize("path", HEAVY_READS)
def test_heavy_class_runs_before_database(limited_app, monkeypatch, path):
    client, _, _ = limited_app
    calls = 0
    async def database():
        nonlocal calls
        calls += 1
        raise HTTPException(418, "DB boundary")
    monkeypatch.setitem(main.app.dependency_overrides, get_db, database)
    for _ in range(20):
        assert client.get(path).status_code == 418
    assert client.get(path).status_code == 429
    # The class is shared across routes and target IDs.
    assert client.get("/api/v1/analytics/bill/another").status_code == 429
    assert calls == 20


def test_rep_bills_limit_precedes_auth(limited_app):
    client, session, _ = limited_app
    for _ in range(20):
        assert client.get("/api/v1/rep/bills", headers={"Authorization": "Bearer forged"}).status_code == 401
    calls = session.execute.await_count
    assert client.get("/api/v1/rep/bills", headers={"Authorization": "Bearer fresh"}).status_code == 429
    assert session.execute.await_count == calls


def test_generate_language_and_global_budgets(limited_app, monkeypatch):
    client, session, _ = limited_app
    from services import ollama_service
    generate = AsyncMock(return_value="summary")
    monkeypatch.setattr(ollama_service, "summarize_bill", generate)
    assert client.get("/api/v1/bills/test/summary?lang=fr").status_code == 422
    generate.assert_not_awaited()
    session.execute.assert_not_awaited()
    # Invalid targets and languages still consume the class; changing IP is the
    # only way to avoid its per-IP counter, and cannot avoid the global counter.
    for _ in range(4):
        assert client.get("/api/v1/bills/test/summary?lang=el").status_code == 404
    assert client.get("/api/v1/bills/other/summary?lang=en").status_code == 429
    for index in range(5):
        for _ in range(5):
            assert client.get("/api/v1/bills/test/summary?lang=en", headers={"X-Forwarded-For": f"198.51.100.{index+1}"}).status_code == 404
    assert client.get("/api/v1/bills/test/summary", headers={"X-Forwarded-For": "198.51.100.99"}).status_code == 429
    assert session.execute.await_count == 29


@pytest.mark.parametrize("path", ["/api/v1/vaa/questions", "/api/v1/vaa/statements"])
def test_vaa_database_bound_and_defaults(limited_app, path):
    client, session, _ = limited_app
    assert client.get(path).status_code == 200
    query = session.execute.call_args.args[0]
    assert query._limit_clause.value == 30
    assert client.get(path+"?limit=100").status_code == 200
    assert session.execute.call_args.args[0]._limit_clause.value == 100
    for value in (0, -1, 101):
        assert client.get(path+f"?limit={value}").status_code == 422
    for _ in range(115):
        assert client.get(path).status_code == 200
    assert client.get(path).status_code == 429


@pytest.mark.asyncio
async def test_export_bounds_restrict_bills_and_vote_aggregation():
    from tests.test_rate_limit_route_enforcement import EmptyResult
    db = SimpleNamespace(execute=AsyncMock(return_value=EmptyResult()))
    assert await export.get_all_results(db, limit=25, offset=50) == []
    bills, votes = [call.args[0] for call in db.execute.await_args_list]
    assert bills._limit_clause.value == 25
    assert bills._offset_clause.value == 50
    assert "citizen_votes.bill_id IN" in str(votes)


@pytest.mark.parametrize("path", ["results.json", "bills.csv", "divergence.csv"])
def test_export_pagination_validated_before_work(limited_app, monkeypatch, path):
    client, _, _ = limited_app
    work = AsyncMock(return_value=[])
    monkeypatch.setattr(export, "get_all_results", work)
    assert client.get(f"/api/v1/export/{path}?limit=12&offset=24").status_code == 200
    assert work.call_args.kwargs["limit"] == 12
    assert work.call_args.kwargs["offset"] == 24
    work.reset_mock()
    assert client.get(f"/api/v1/export/{path}?limit=501").status_code == 422
    assert client.get(f"/api/v1/export/{path}?offset=10001").status_code == 422
    work.assert_not_awaited()


def test_paypal_forged_callbacks_have_per_ip_and_global_limits(limited_app, monkeypatch):
    client, _, _ = limited_app
    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "merchant@example.org")
    monkeypatch.delenv("PAYPAL_MERCHANT_ID", raising=False)
    verification = AsyncMock(return_value=False)
    monkeypatch.setattr(payments, "_verify_paypal_ipn", verification)
    payload = {"payment_status": "Completed", "txn_id": "forged", "receiver_email": "merchant@example.org", "mc_currency": "EUR", "custom": "infrastructure_support"}
    statuses = []
    for index in range(6):
        headers = {"X-Forwarded-For": f"198.51.100.{index+1}"}
        for _ in range(10):
            statuses.append(client.post("/api/v1/payments/webhook/paypal", data=payload, headers=headers).status_code)
        assert client.post("/api/v1/payments/webhook/paypal", data=payload, headers=headers).status_code == 429
    assert 429 not in statuses
    assert verification.await_count <= 60
    # Forged requests must actually reach verification during the allowance.
    assert verification.await_count > 0
    before = verification.await_count
    assert client.post("/api/v1/payments/webhook/paypal", data=payload, headers={"X-Forwarded-For": "198.51.100.99"}).status_code == 429
    assert verification.await_count == before


@pytest.mark.asyncio
async def test_paypal_verification_slots_reject_without_queue_and_release(monkeypatch):
    from fastapi import Request
    import urllib.parse
    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "merchant@example.org")
    monkeypatch.delenv("PAYPAL_MERCHANT_ID", raising=False)
    gate = asyncio.Event()
    entered = 0
    async def verify(_):
        nonlocal entered
        entered += 1
        await gate.wait()
        return False
    monkeypatch.setattr(payments, "_verify_paypal_ipn", verify)
    async def call():
        body = urllib.parse.urlencode({"payment_status": "Completed", "txn_id": "forged", "receiver_email": "merchant@example.org", "custom": "infrastructure_support"}).encode()
        async def receive():
            return {"type": "http.request", "body": body}
        request = Request({"type": "http", "headers": []}, receive=receive)
        try:
            return await payments.paypal_ipn_webhook(request=request)
        except HTTPException as exc:
            return exc.status_code
    tasks = [asyncio.create_task(call()) for _ in range(4)]
    while entered < 4:
        await asyncio.sleep(0)
    assert await call() == 429
    gate.set()
    await asyncio.gather(*tasks)
    assert await call() != 429


def test_slowapi_fallback_never_exceeds_live_cardinality(monkeypatch):
    storage = BoundedMemoryStorage()
    strategy = ConservativeMemoryLimiter(storage)
    quota = parse("4/minute")
    for index in range(10_000):
        assert strategy.hit(quota, f"client-{index}")
    assert not strategy.hit(quota, "client-overflow")
    assert len(storage.storage) == len(storage.expirations) == 10_000
    assert not storage.locks and not storage.events
    assert strategy.hit(quota, "client-0")
    assert not strategy.hit(quota, "client-0")
    # Expired capacity is reusable without resetting any live quota.
    first = next(iter(storage.expirations))
    storage.expirations[first] = 0
    assert strategy.hit(quota, "new-client")
    assert len(storage.storage) == 10_000


def test_bounded_memory_admission_is_atomic_across_threads():
    storage = BoundedMemoryStorage(max_buckets=10)
    strategy = ConservativeMemoryLimiter(storage)
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda i: strategy.hit(parse("2/minute"), str(i)), range(100)))
    assert sum(results) == len(storage.storage) == 10


@pytest.mark.asyncio
async def test_api_key_outage_uses_anonymous_half_quota(monkeypatch):
    import ip_utils
    from starlette.requests import Request
    ip_utils._fallback_counts.clear()
    store = SimpleNamespace(hexists=AsyncMock(side_effect=RedisConnectionError("down")), eval=AsyncMock(side_effect=RedisConnectionError("down")))
    monkeypatch.setattr(public_api, "get_redis", AsyncMock(return_value=store))
    request = Request({"type": "http", "client": ("198.51.100.78", 123), "headers": []})
    for index in range(50):
        assert await public_api.rate_limit_check(request, x_api_key=f"rotating-{index}") is None
    with pytest.raises(HTTPException) as exc:
        await public_api.rate_limit_check(request, x_api_key="another")
    assert exc.value.status_code == 429
    assert store.eval.await_count == 51
    assert len(ip_utils._fallback_counts) == 1


@pytest.mark.asyncio
async def test_cplm_concurrent_misses_compute_once(monkeypatch):
    store = SimpleNamespace(get=AsyncMock(return_value=None), setex=AsyncMock(), lindex=AsyncMock(return_value=None), lpush=AsyncMock(), ltrim=AsyncMock(), aclose=AsyncMock())
    monkeypatch.setattr(cplm.aioredis, "from_url", lambda *a, **k: store)
    async def compute(_):
        await asyncio.sleep(0.01)
        return {"x": 0.1, "y": 0.2}
    calculate = AsyncMock(side_effect=compute)
    monkeypatch.setattr(cplm, "compute_cplm", calculate)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        all=lambda: [], scalars=lambda: SimpleNamespace(all=lambda: []),
    )))
    results = await asyncio.gather(*(cplm.get_cplm_cached(db) for _ in range(50)))
    assert all(result == results[0] for result in results)
    assert calculate.await_count == store.lpush.await_count == 1


@pytest.mark.asyncio
async def test_newsletter_concurrent_misses_call_provider_once(monkeypatch):
    from routers import newsletter
    store = SimpleNamespace(get=AsyncMock(return_value=None), setex=AsyncMock(), hlen=AsyncMock(return_value=123))
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=store))
    monkeypatch.setattr(newsletter, "BREVO_API_KEY", "test")
    monkeypatch.setattr(newsletter, "LISTMONK_PW", "")
    calls = []
    class Provider:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, **kwargs):
            calls.append(url)
            await asyncio.sleep(0.01)
            return SimpleNamespace(status_code=200, json=lambda: {})
    monkeypatch.setattr(newsletter.httpx, "AsyncClient", lambda **kwargs: Provider())
    results = await asyncio.gather(*(newsletter.newsletter_stats() for _ in range(50)))
    assert len(calls) == 2  # One account request and one statistics request.
    assert store.hlen.await_count == store.setex.await_count == 1
    assert all(result["subscribers"] == 123 for result in results)


@pytest.mark.asyncio
async def test_singleflight_errors_cancellation_and_capacity_do_not_leak():
    flight = request_work.SingleFlight(capacity=1)
    gate = asyncio.Event()
    async def work():
        await gate.wait()
        return 42
    leader = asyncio.create_task(flight.run("key", work))
    await asyncio.sleep(0)
    follower = asyncio.create_task(flight.run("key", work))
    await asyncio.sleep(0)
    follower.cancel()
    with pytest.raises(asyncio.CancelledError): await follower
    with pytest.raises(HTTPException) as exc: await flight.run("new", work)
    assert exc.value.status_code == 429
    gate.set()
    assert await leader == 42
    async def failed(): raise ValueError("failed fill")
    with pytest.raises(ValueError): await flight.run("key", failed)
    assert await flight.run("key", work) == 42


def test_global_cache_fill_quota_uses_shared_store_and_half_quota(limited_app, monkeypatch):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from slowapi.errors import RateLimitExceeded
    from rate_limit import rate_limit_exceeded_handler
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    @app.get("/fill")
    async def fill():
        await request_work.cache_fill_quota("representation")
        return {"ok": True}
    client = TestClient(app)
    try:
        for _ in range(6): assert client.get("/fill").status_code == 200
        assert client.get("/fill").status_code == 429
        storage = BoundedMemoryStorage()
        monkeypatch.setattr(limiter, "_fallback_limiter", ConservativeMemoryLimiter(storage))
        monkeypatch.setattr(limiter, "_storage_dead", True)
        monkeypatch.setattr(limiter, "_in_memory_fallback_enabled", True)
        monkeypatch.setattr(limiter, "_Limiter__should_check_backend", lambda: False)
        for _ in range(3): assert client.get("/fill").status_code == 200
        assert client.get("/fill").status_code == 429
    finally:
        client.close()


@pytest.mark.asyncio
async def test_zk_members_cache_is_by_published_root_off_thread_and_detects_changes(monkeypatch):
    zk._root_members_cache.clear()
    root = SimpleNamespace(id=42, vote_scope_id="bill:target", merkle_root="3", merkle_depth=16, group_size=2, commitment_version="semaphore-v4", status="OPEN")
    members = ["1", "2"]
    monkeypatch.setattr(zk, "_ensure_scope_public_or_safe_canary", AsyncMock())
    monkeypatch.setattr(zk, "list_public_group_members_for_scope", AsyncMock(side_effect=lambda *a, **k: list(members)))
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalar_one_or_none=lambda: root,
        scalars=lambda: SimpleNamespace(all=lambda: ["target"]),
    )))
    threads = []
    def build(values):
        threads.append(threading.get_ident())
        return SimpleNamespace(root=str(sum(map(int, values))), size=len(values))
    monkeypatch.setattr(zk, "build_semaphore_group_root", build)
    results = await asyncio.gather(*(zk.get_current_zk_root_members(vote_scope_id="bill:target", db=db) for _ in range(25)))
    assert all(result.members == ["1", "2"] for result in results)
    assert len(threads) == 1 and threads[0] != threading.get_ident()
    await zk.get_current_zk_root_members(vote_scope_id="bill:target", db=db)
    assert len(threads) == 1
    members.append("3")
    with pytest.raises(HTTPException) as exc:
        await zk.get_current_zk_root_members(vote_scope_id="bill:target", db=db)
    assert exc.value.status_code == 409
    root.merkle_root, root.group_size = "6", 3
    assert (await zk.get_current_zk_root_members(vote_scope_id="bill:target", db=db)).members == members
    assert len(threads) == 2


def test_slowapi_capacity_rejects_new_clients_with_429_without_reset(limited_app, monkeypatch):
    client, _, _ = limited_app
    storage = BoundedMemoryStorage(max_buckets=1)
    monkeypatch.setattr(limiter, "_fallback_storage", storage)
    monkeypatch.setattr(limiter, "_fallback_limiter", ConservativeMemoryLimiter(storage))
    monkeypatch.setattr(limiter, "_storage_dead", True)
    monkeypatch.setattr(limiter, "_in_memory_fallback_enabled", True)
    monkeypatch.setattr(limiter, "_Limiter__should_check_backend", lambda: False)
    from tests.test_rate_limit_route_enforcement import EmptyResult
    async def boundary(): raise HTTPException(418, "Database boundary")
    monkeypatch.setitem(main.app.dependency_overrides, get_db, boundary)
    assert client.get("/api/v1/bills").status_code == 418
    assert client.get("/api/v1/bills", headers={"X-Forwarded-For": "198.51.100.200"}).status_code == 429
    for _ in range(599): assert client.get("/api/v1/bills").status_code == 418
    assert client.get("/api/v1/bills").status_code == 429
    assert len(storage.storage) == 1


def test_summary_generation_only_uses_allowlisted_cache_keys(limited_app, monkeypatch):
    from models import BillStatus
    from services import ollama_service
    client, session, _ = limited_app
    bill = SimpleNamespace(summary_short_el=None, summary_short_en=None, summary_long_el=None, summary_long_en=None, pill_el=None, pill_en=None, source="PARLIAMENT", title_el="title", title_en=None, status=BillStatus.ACTIVE, categories=[])
    async def execute(statement):
        if str(statement).startswith("SELECT parliament_bills.id \n"):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: ["first"]))
        return SimpleNamespace(scalar_one_or_none=lambda: bill)
    session.execute.side_effect = execute
    cache = SimpleNamespace(get=AsyncMock(return_value=None), setex=AsyncMock())
    import redis.asyncio as redis
    monkeypatch.setattr(redis, "from_url", lambda *a, **k: cache)
    generator = AsyncMock(return_value="Η ρύθμιση ορίζει τη διαδικασία.")
    monkeypatch.setattr(ollama_service, "summarize_bill", generator)
    assert client.get("/api/v1/bills/first/summary?lang=el").status_code == 200
    assert client.get("/api/v1/bills/first/summary?lang=en").status_code == 200
    assert {call.args[0] for call in cache.get.await_args_list} == {"bill_summary:first:el", "bill_summary:first:en"}
    for language in ("de", "fr", "el-GR"):
        assert client.get(f"/api/v1/bills/first/summary?lang={language}").status_code == 422
    assert generator.await_count == 2
    assert client.get("/api/v1/bills/second/summary").status_code == 429
    assert generator.await_count == 2


def test_invalid_key_redis_outage_http_returns_anonymous_429(limited_app, monkeypatch):
    import ip_utils
    client, session, _ = limited_app
    ip_utils._fallback_counts.clear()
    store = SimpleNamespace(hexists=AsyncMock(side_effect=RedisConnectionError("down")), eval=AsyncMock(side_effect=RedisConnectionError("down")))
    monkeypatch.setattr(public_api, "get_redis", AsyncMock(return_value=store))
    for index in range(50):
        response = client.get("/api/v1/public/vaa/parties", headers={"X-API-Key": f"invalid-{index}"})
        assert response.status_code == 200
    response = client.get("/api/v1/public/vaa/parties", headers={"X-API-Key": "another"})
    assert response.status_code == 429
    assert response.json()["detail"]["limit"] == 100
    assert store.eval.await_count == 51
    assert session.execute.await_count == 50


def test_public_representation_uses_coalesced_cache_and_preserves_fill_429(limited_app, monkeypatch):
    from routers import analytics
    client, _, _ = limited_app
    monkeypatch.setitem(main.app.dependency_overrides, public_api.rate_limit_check, lambda: None)
    shared_result = {"cumulative_representation": 50, "bills": []}
    cached = AsyncMock(return_value=shared_result)
    monkeypatch.setattr(analytics, "get_cached_representation", cached)
    assert client.get("/api/v1/public/representation").status_code == 200
    assert "data_license" not in shared_result
    cached.side_effect = HTTPException(429, "Fill quota", headers={"Retry-After": "60"})
    response = client.get("/api/v1/public/representation")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
