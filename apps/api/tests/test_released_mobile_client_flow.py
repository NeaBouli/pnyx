"""Released origin/main flows on the real app, singleton, middleware and routes."""
import asyncio
from collections import Counter, OrderedDict
from contextlib import asynccontextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from nacl.signing import SigningKey
import pytest

import main
from database import get_db
from models import BillStatus, GovernanceLevel, KeyStatus, ParliamentBill
from rate_limit import create_limiter, limiter
from routers import notify, parliament, zk
from services import client_flow_cache
from services.citizen_action_integrity import build_vote_status_read_payload
from services.push_registration import build_push_register_payload
from services.evaluation_integrity import build_evaluation_read_payload
from tests.test_rate_limit_coverage import iter_api_routes, route_policy


INVENTORY = json.loads((Path(__file__).parent / "fixtures/released_mobile_client_flow.json").read_text())
DOC = Path(__file__).resolve().parents[3] / "docs/operations/API_RATE_LIMIT_COVERAGE.md"


def inventory_table():
    return "\n".join(
        f"| {row['method']} | `{row['path']}` | {row['frequency']} | `{row['source']}` |"
        for row in INVENTORY["routes"]
    )


@pytest.mark.parametrize("entry", INVENTORY["routes"], ids=lambda row: f"{row['method']} {row['path']}")
def test_released_core_routes_are_client_flow_and_never_public_heavy(entry):
    route = next(route for route in iter_api_routes(main.app.routes)
                 if route.path == entry["path"] and entry["method"] in route.methods)
    assert route_policy(route, entry["method"])[0] == "client-flow"
    limits = limiter._route_limits[f"{route.endpoint.__module__}.{route.endpoint.__name__}"]
    assert not any(item.scope == "public-heavy" for item in limits)
    shared = [item for item in limits if item.scope in {"client-flow", "client-poll"}]
    assert len(shared) == 1 and shared[0].limit.amount >= 600


def test_documented_released_inventory_matches_fixture():
    table = DOC.read_text().split("<!-- client-flow:start -->")[1].split("<!-- client-flow:end -->")[0]
    assert inventory_table() in table
    assert INVENTORY["poll_seconds"] == 5


class Rows:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value or 0

    def scalars(self):
        return self

    def all(self):
        return self.value if isinstance(self.value, list) else []

    def fetchall(self):
        return self.all()

    def fetchone(self):
        return self.value

    def mappings(self):
        return self

    def one(self):
        return {key: 0 for key in ("total_diavgeia_bills", "geographically_represented_bills",
                                  "institutional_or_unresolved_bills", "geographic_mapping_gaps")}


@pytest.fixture
async def released_backend(monkeypatch):
    instance = create_limiter(storage_uri="memory://", enabled=True)
    for name in ("enabled", "_storage", "_limiter", "_fallback_storage", "_fallback_limiter",
                 "_storage_dead", "_Limiter__last_check_backend", "_Limiter__check_backend_count"):
        monkeypatch.setattr(limiter, name, getattr(instance, name))
    clock = SimpleNamespace(now=1_788_000_000.0)
    monkeypatch.setattr("limits.storage.memory.time.time", lambda: clock.now)
    monkeypatch.setattr(client_flow_cache, "monotonic", lambda: clock.now)
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
    monkeypatch.setenv("ZK_VOTING_ENABLED", "true")
    monkeypatch.setenv("ZK_OPT_IN_ENABLED", "true")
    monkeypatch.setenv("ZK_TIER1_GUARD_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "false")
    monkeypatch.setenv("ZK_PRODUCTION_SCOPE_ALLOWLIST", "bill:GR-released")
    bill = ParliamentBill(id="GR-released", title_el="Released client bill", status=BillStatus.OPEN_END,
                          source="PARLIAMENT", governance_level=GovernanceLevel.NATIONAL,
                          results_visibility="ALWAYS", admin_hidden=False, categories=[],
                          ai_summary_reviewed=False, consensus_count=0, flag_count=0)
    root = SimpleNamespace(id=1, vote_scope_id="bill:GR-released", merkle_root="3", merkle_depth=16,
                           group_size=2, commitment_version="semaphore-v4", status="OPEN")
    keys = {f"{i:064x}": SigningKey(bytes([i]) * 32) for i in range(1, 51)}

    async def execute(statement, *args):
        sql = str(statement)
        params = statement.compile().params
        if " AS results_visible" in sql:
            from services.bill_visibility import is_public_bill, results_hidden
            from services.small_cell import small_cell_k
            inputs = (*db.vote_counts, bill.status, bill.results_visibility) if small_cell_k() else ()
            return Rows([(bill.id, not results_hidden(bill), *inputs)] if is_public_bill(bill) else [])
        if sql.startswith("SELECT parliament_bills.id \n"):
            from services.bill_visibility import is_public_bill
            return Rows([bill.id] if is_public_bill(bill) else [])
        if "identity_records" in sql:
            if args:
                return Rows(keys[args[0]["nullifier"]].verify_key.encode().hex())
            key = keys[params["nullifier_hash_1"]]
            return Rows(SimpleNamespace(public_key_hex=key.verify_key.encode().hex(),
                                        status=KeyStatus.ACTIVE, created_at=None,
                                        region_locked=False, periferia_id=None, dimos_id=None))
        if "parliament_bills" in sql and params.get("id_1") == bill.id:
            return Rows(bill)
        if "zk_merkle_roots" in sql:
            return Rows(root)
        if "FROM representative_tokens WHERE ada_number" in sql:
            return Rows(("ADA-released", "Βουλευτής", "Region", "Released politician", True, 1, None))
        return Rows()

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute), scalar=AsyncMock(return_value=0),
                         vote_counts=(0,) * 8)
    monkeypatch.setitem(main.app.dependency_overrides, get_db, lambda: db)

    @asynccontextmanager
    async def refresh_session():
        yield db

    monkeypatch.setattr("database.AsyncSessionLocal", refresh_session)
    monkeypatch.setattr(parliament, "get_source_freshness", AsyncMock(return_value={}))
    monkeypatch.setattr(zk, "list_public_group_members_for_scope", AsyncMock(return_value=["1", "2"]))
    monkeypatch.setattr(zk, "build_semaphore_group_root", lambda members: SimpleNamespace(root="3", size=2))
    monkeypatch.setattr(zk, "_root_members_cache", OrderedDict())
    # Redis persistence remains exercised through the real push handler; counters
    # have expiry just like the production fixed-window Lua helper.
    counts, expirations = {}, {}
    async def increment(script, numkeys, key, seconds):
        if expirations.get(key, 0) <= clock.now:
            counts[key] = 0
            expirations[key] = clock.now + seconds
        counts[key] += 1
        return counts[key]
    redis = SimpleNamespace(eval=AsyncMock(side_effect=increment), get=AsyncMock(return_value=None),
                            setex=AsyncMock())
    monkeypatch.setattr(notify, "_get_redis", AsyncMock(return_value=redis))
    yield clock, db, keys
    for cache in [client_flow_cache.scope_status_cache, client_flow_cache.results_cache,
                  *client_flow_cache.public_caches.values()]:
        await asyncio.gather(*cache.flights._tasks, return_exceptions=True)


async def request_ok(client, method, path, **kwargs):
    response = await client.request(method, path, **kwargs)
    assert response.status_code == 200, (method, path, response.status_code, response.text)
    return response


async def signed_status(client, nullifier, key, now):
    timestamp = int(now * 1000)
    payload = build_vote_status_read_payload("GR-released", nullifier, timestamp)
    return await request_ok(client, "POST", "/api/v1/vote/GR-released/status", json={
        "nullifier_hash": nullifier, "timestamp_ms": timestamp,
        "signature_hex": key.sign(payload.encode()).signature.hex(),
    })


async def startup(client, nullifier, key, now):
    # Home + banner + legacy rotation feature discovery; F-Droid feed fallback
    # and push registration are included together as a conservative union.
    for _ in range(3):
        await request_ok(client, "GET", "/api/v1/app/version")
    await request_ok(client, "GET", "/api/v1/bills?limit=50")
    await request_ok(client, "GET", "/api/v1/analytics/overview")
    await request_ok(client, "GET", "/api/v1/bills/trending?limit=10")
    device = f"00000000-0000-4000-8000-{nullifier[-12:]}"
    token = f"ExponentPushToken[released-{nullifier[-4:]}]"
    timestamp = int(now * 1000)
    payload = build_push_register_payload(device, token, "android", nullifier, timestamp)
    await request_ok(client, "POST", "/api/v1/notify/register", json={
        "device_id": device, "token": token, "platform": "android", "nullifier_hash": nullifier,
        "timestamp_ms": timestamp, "signature_hex": key.sign(payload.encode()).signature.hex(),
    })


async def session(client, nullifier, key, now):
    for suffix in ("?limit=40", "?governance=NATIONAL&source=PARLIAMENT&limit=4"):
        await request_ok(client, "GET", "/api/v1/bills" + suffix)
    await request_ok(client, "GET", "/api/v1/bills/GR-released")
    await signed_status(client, nullifier, key, now)
    await request_ok(client, "GET", "/api/v1/zk/status")
    await request_ok(client, "GET", "/api/v1/zk/scopes/bill%3AGR-released/status")
    await request_ok(client, "GET", "/api/v1/zk/roots/bill%3AGR-released/members")
    await request_ok(client, "GET", "/api/v1/vote/GR-released/results")
    await request_ok(client, "GET", "/api/v1/consensus/representation?limit=20")
    await mp_navigation(client, nullifier, key, now)
    # Returning to Bills refocuses and repeats BOTH first-page queries.
    for suffix in ("?limit=40", "?governance=NATIONAL&source=PARLIAMENT&limit=4"):
        await request_ok(client, "GET", "/api/v1/bills" + suffix)


async def mp_navigation(client, nullifier, key, now):
    """MP mount, politicians mode, then detail including both personal reads."""
    for path in ("/api/v1/mp/ranking", "/api/v1/politicians/",
                 "/api/v1/politicians/ADA-released/questions", "/api/v1/politicians/ADA-released/scores"):
        await request_ok(client, "GET", path)
    for ada, path in ((None, "/api/v1/politicians/my-evaluations/bulk"),
                      ("ADA-released", "/api/v1/politicians/ADA-released/my-evaluation")):
        timestamp = int(now * 1000)
        payload = build_evaluation_read_payload(ada, nullifier, timestamp)
        response = await request_ok(client, "GET", path, params={"nullifier_hash": nullifier}, headers={
            "X-Evaluation-Read-Timestamp": str(timestamp),
            "X-Evaluation-Read-Signature": key.sign(payload.encode()).signature.hex(),
        })
        assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_three_released_startup_bills_vote_results_bills_sessions(released_backend):
    clock, _, keys = released_backend
    async with AsyncClient(transport=ASGITransport(app=main.app, client=("198.51.100.8", 1234)),
                           base_url="http://test") as client:
        for nullifier, key in list(keys.items())[:3]:
            await startup(client, nullifier, key, clock.now)
            await session(client, nullifier, key, clock.now)


@pytest.mark.asyncio
@pytest.mark.parametrize("users", [10, 50])
async def test_released_five_second_polling_for_five_minutes_behind_one_ip(released_backend, users):
    clock, _, keys = released_backend
    start = clock.now
    status_counts = Counter()
    async with AsyncClient(transport=ASGITransport(app=main.app, client=("198.51.100.8", 1234)),
                           base_url="http://test") as client:
        for nullifier, key in list(keys.items())[:users]:
            await startup(client, nullifier, key, clock.now)
            await session(client, nullifier, key, clock.now)
        for second in range(0, 300, INVENTORY["poll_seconds"]):
            clock.now = start + second
            for nullifier, key in list(keys.items())[:users]:
                response = await request_ok(client, "GET", "/api/v1/zk/scopes/bill%3AGR-released/status")
                status_counts[response.status_code] += 1
                if second and second % 60 == 0:
                    await session(client, nullifier, key, clock.now)
        assert status_counts == {200: users * 60}
        print(f"NAT users={users} duration=300s MP+politician+signed-reads+core+5s-polls: zero 429; polls={users * 60}")
        # Exhaust the independent heavy bucket, then rotate heavy route/target.
        for _ in range(20):
            assert (await client.get("/api/v1/export/results.json")).status_code == 200
        assert (await client.get("/api/v1/mp/compare/ND")).status_code == 429
        await request_ok(client, "GET", "/api/v1/vote/GR-released/results")
        await request_ok(client, "GET", "/api/v1/zk/scopes/bill%3AGR-released/status")


@pytest.mark.asyncio
async def test_scope_cache_coalesces_expires_and_rechecks_policy_and_visibility(released_backend, monkeypatch):
    clock, db, _ = released_backend
    monkeypatch.setattr(limiter, "enabled", False)
    scope = "bill:GR-released"
    counts = AsyncMock(return_value=2)
    monkeypatch.setattr(zk, "_count_rows", counts)
    results = await asyncio.gather(*(zk.get_zk_scope_status(vote_scope_id=scope, db=db) for _ in range(25)))
    assert all(result.can_vote for result in results)
    assert counts.await_count == 1
    clock.now += 4
    await zk.get_zk_scope_status(vote_scope_id=scope, db=db)
    assert counts.await_count == 1
    clock.now += 1
    await zk.get_zk_scope_status(vote_scope_id=scope, db=db)
    await asyncio.gather(*client_flow_cache.scope_status_cache.flights._tasks)
    assert counts.await_count == 2
    monkeypatch.setenv("ZK_VOTING_ENABLED", "false")
    assert not (await zk.get_zk_scope_status(vote_scope_id=scope, db=db)).can_vote
    assert counts.await_count == 3
    monkeypatch.setattr(zk, "_ensure_scope_public_or_safe_canary", AsyncMock(side_effect=HTTPException(404)))
    with pytest.raises(HTTPException) as exc:
        await zk.get_zk_scope_status(vote_scope_id=scope, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_client_cache_bounds_errors_and_committed_write_invalidation(monkeypatch):
    from services.representation_cache import commit_and_invalidate_representation
    cache = client_flow_cache.ClientFlowCache(capacity=2)
    work = AsyncMock(return_value=42)
    for key in range(3):
        assert await cache.get_or_fill(key, work) == 42
    assert len(cache.entries) == 2
    fail = AsyncMock(side_effect=ValueError("failed"))
    with pytest.raises(ValueError):
        await cache.get_or_fill("error", fail)
    assert "error" not in cache.entries
    await client_flow_cache.scope_status_cache.get_or_fill("scope", work)
    await client_flow_cache.results_cache.get_or_fill("bill", work)
    # Exercise the actual shared commit hook; avoid external Redis invalidation.
    monkeypatch.setattr("services.representation_cache.aioredis.from_url", lambda *a, **k: None)
    await commit_and_invalidate_representation(SimpleNamespace(commit=AsyncMock()))
    assert not client_flow_cache.scope_status_cache.entries
    assert not client_flow_cache.results_cache.entries


@pytest.mark.asyncio
async def test_results_cache_reuses_totals_but_checks_visibility_and_privacy(released_backend, monkeypatch):
    from routers import voting
    from services.zk_vote_aggregation import VoteTotals

    clock, db, _ = released_backend
    monkeypatch.setattr(limiter, "enabled", False)
    totals = AsyncMock(return_value=VoteTotals(yes=2, no=1, abstain=0, unknown=0,
                                             tier1_total=3, zk_total=0))
    db.vote_counts = (2, 1, 0, 0, 0, 0, 0, 0)
    monkeypatch.setattr(voting, "aggregate_bill_vote_totals", totals)
    for _ in range(25):
        await voting.get_results("GR-released", db=db)
    assert totals.await_count == 1
    clock.now += 5
    await voting.get_results("GR-released", db=db)
    await asyncio.gather(*client_flow_cache.results_cache.flights._tasks)
    assert totals.await_count == 2
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "5")
    result = await voting.get_results("GR-released", db=db)
    assert result.total_votes is None
    assert totals.await_count == 3
    monkeypatch.setattr(voting, "is_public_bill", lambda bill: False)
    with pytest.raises(HTTPException) as exc:
        await voting.get_results("GR-released", db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_slow_fill_and_invalidation_cannot_renew_stale_cache(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(client_flow_cache, "monotonic", lambda: now[0])
    cache = client_flow_cache.ClientFlowCache()

    async def slow():
        now[0] += 6
        return "old"

    assert await cache.get_or_fill("slow", slow) == "old"
    assert cache.entries["slow"][0] <= now[0]
    entered, finish = asyncio.Event(), asyncio.Event()

    async def racing():
        entered.set()
        await finish.wait()
        return "before-commit"

    task = asyncio.create_task(cache.get_or_fill("race", racing))
    await entered.wait()
    cache.clear()
    finish.set()
    assert await task == "before-commit"
    assert "race" not in cache.entries
