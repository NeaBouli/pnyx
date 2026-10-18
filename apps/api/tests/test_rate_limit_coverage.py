"""EVA-011: audit the registered app, including FastAPI's lazy routers.

Defaults do not cover included routers in our FastAPI/SlowAPI combination.
An entry in the limiter registry alone is insufficient: the registered route
must also contain its decorator wrapper (decorator order matters). Token
authentication dependencies must be preceded by a limiter dependency.
"""

from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Request
import pytest

import main
from dependencies import verify_admin_key
from rate_limit import enforce_route_limit, limiter
from routers import admin, representative


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ADMIN_GUARDS = {verify_admin_key, admin.verify_admin, representative._verify_admin}
AUTH_GUARDS = {representative.verify_rep_token}

# Preserve established Redis policies without installing a second counter.
# Provider callbacks deliberately have no citizen-IP quota: providers share
# source IPs and retry/batch events; their existing verification stays required.
WRITE_EXCEPTIONS = {
    ("POST", "/api/v1/identity/verify"): "Atomic HLR Redis guard: 5/IP/min, 20/IP/day, 3/number/day and 300s cooldown.",
    ("POST", "/api/v2/identity/verify"): "Uses the same atomic HLR Redis guard as v1 registration.",
    ("POST", "/api/v1/public/keys/generate"): "Existing Redis guard: 5/IP/hour before generating a key.",
    ("POST", "/api/v1/newsletter/subscribe"): "Redis: 10/IP/hour and 3/email/day; confirmed subscriptions return without consuming quota.",
    ("POST", "/api/v1/contact/ngo"): "Existing Redis guard: 3/IP/hour before sending mail.",
    ("POST", "/api/v1/notify/register"): "Redis: 600/IP/hour before auth, 20/identity/day for changed device registrations.",
    ("POST", "/api/v1/payments/webhook"): "Stripe signature verification and event deduplication; preserve provider retries and bursts.",
    ("POST", "/api/v1/payments/webhook/paypal"): "PayPal IPN verification and transaction deduplication; preserve provider retries and bursts.",
    ("POST", "/api/v1/newsletter/webhook/brevo"): "Authenticated Brevo event batches; preserve provider retries and bursts.",
}

# Classify every public router GET, so a new expensive/oracle read cannot hide
# behind an incomplete path-name heuristic. Public cacheable reads keep the
# main-branch policy: SSR shares one IP.
READ_EXCEPTIONS = {
    "/api/v1/analytics/bill/{bill_id}": "public cacheable read; SSR shares one IP",
    "/api/v1/analytics/divergence-trends": "public cacheable read; SSR shares one IP",
    "/api/v1/analytics/info": "public cacheable read; SSR shares one IP",
    "/api/v1/analytics/overview": "public cacheable read; SSR shares one IP",
    "/api/v1/analytics/representation": "public cacheable read; SSR shares one IP",
    "/api/v1/analytics/top-divergence": "public cacheable read; SSR shares one IP",
    "/api/v1/analytics/votes-timeline": "public cacheable read; SSR shares one IP",
    "/api/v1/app/version": "Static client update metadata; retain existing polling access policy.",
    "/api/v1/arweave/bill/{bill_id}": "Single stored archive pointer; no gateway/provider request.",
    "/api/v1/auth/govgr/family/verify": "public cacheable read; SSR shares one IP",
    "/api/v1/auth/govgr/info": "Static integration metadata.",
    "/api/v1/auth/govgr/status": "public cacheable read; SSR shares one IP",
    "/api/v1/bills/sources/freshness": "public cacheable read; SSR shares one IP",
    "/api/v1/bills": "Paginated public feed; retain existing SSR access policy.",
    "/api/v1/bills/trending": "public cacheable read; SSR shares one IP",
    "/api/v1/bills/{bill_id}": "Single public bill lookup.",
    "/api/v1/bills/{bill_id}/summary": "public cacheable read; SSR shares one IP",
    "/api/v1/claude/budget": "public cacheable read; SSR shares one IP",
    "/api/v1/consensus/representation": "public cacheable read; SSR shares one IP",
    "/api/v1/cplm/aggregate": "public cacheable read; SSR shares one IP",
    "/api/v1/cplm/history": "public cacheable read; SSR shares one IP",
    "/api/v1/decisions": "Paginated public decision feed.",
    "/api/v1/export/info": "Static format metadata; CSV downloads have explicit limits.",
    "/api/v1/export/parties.json": "public cacheable read; SSR shares one IP",
    "/api/v1/export/results.json": "public cacheable read; SSR shares one IP",
    "/api/v1/identity/hlr/credits": "public cacheable read; SSR shares one IP",
    "/api/v1/mp/bill/{bill_id}": "public cacheable read; SSR shares one IP",
    "/api/v1/mp/compare/{party_abbr}": "public cacheable read; SSR shares one IP",
    "/api/v1/mp/info": "Static module metadata.",
    "/api/v1/mp/parties": "Small public party catalogue.",
    "/api/v1/mp/ranking": "public cacheable read; SSR shares one IP",
    "/api/v1/municipal/{dimos_id}/decisions": "Paginated public municipal decision feed.",
    "/api/v1/municipal/{dimos_id}/voteable": "public cacheable read; SSR shares one IP",
    "/api/v1/newsletter/lists": "Static subscription options.",
    "/api/v1/newsletter/stats": "public cacheable read; SSR shares one IP",
    "/api/v1/notifications/status": "public cacheable read; SSR shares one IP",
    "/api/v1/payments/public/finance": "public cacheable read; SSR shares one IP",
    "/api/v1/payments/status": "public cacheable read; SSR shares one IP",
    "/api/v1/periferia": "Small public region catalogue.",
    "/api/v1/periferia/{periferia_id}/dimos": "Bounded public municipality catalogue for one region.",
    "/api/v1/polis/tickets": "Public ticket list capped at 100 records.",
    "/api/v1/politicians/": "public cacheable read; SSR shares one IP",
    "/api/v1/politicians/{ada_number}/questions": "Small public evaluation question catalogue; no personal scores.",
    "/api/v1/politicians/{ada_number}/scores": "public cacheable read; SSR shares one IP",
    "/api/v1/public/bills": "Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key.",
    "/api/v1/public/bills/{bill_id}/results": "Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key.",
    "/api/v1/public/cplm": "Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key.",
    "/api/v1/public/cplm/history": "Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key.",
    "/api/v1/public/info": "Static API metadata.",
    "/api/v1/public/representation": "Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key.",
    "/api/v1/public/stats": "Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key.",
    "/api/v1/public/vaa/parties": "Existing shared Redis public-data quota: 100/min/IP or 1000/min/valid key.",
    "/api/v1/regions/{periferia_id}/decisions": "Paginated public regional decision feed.",
    "/api/v1/rep/bills": "Representative-authenticated public bill list capped at 100 records.",
    "/api/v1/scraper/jobs": "public cacheable read; SSR shares one IP",
    "/api/v1/vaa/parties": "Small public party catalogue.",
    "/api/v1/vaa/questions": "Bounded public question lookup.",
    "/api/v1/vaa/statements": "Bounded public statement lookup.",
    "/api/v1/vote/results/in-progress": "public cacheable read; SSR shares one IP",
    "/api/v1/vote/results/latest": "public cacheable read; SSR shares one IP",
    "/api/v1/vote/{bill_id}/results": "public cacheable read; SSR shares one IP",
    "/api/v1/zk/receipts/{vote_scope_id}": "public cacheable read; SSR shares one IP",
    "/api/v1/zk/roots/{vote_scope_id}": "public cacheable read; SSR shares one IP",
    "/api/v1/zk/roots/{vote_scope_id}/members": "public cacheable read; SSR shares one IP",
    "/api/v1/zk/scopes/{vote_scope_id}/status": "public cacheable read; SSR shares one IP",
    "/api/v1/zk/status": "public cacheable read; SSR shares one IP",
}


def iter_api_routes(routes: Any) -> Iterator[Any]:
    for route in routes:
        if hasattr(route, "effective_candidates"):
            # FastAPI 0.142+: includes prefixes and inclusion dependencies.
            yield from iter_api_routes(route.effective_candidates())
        elif (getattr(route, "endpoint", None) and getattr(route, "methods", None)
              and getattr(route, "dependant", None) is not None):
            yield route


def dependency_calls(dependant: Any) -> Iterator[Any]:
    for dependency in dependant.dependencies:
        yield from dependency_calls(dependency)
        yield dependency.call


def is_admin(route: Any) -> bool:
    return bool(ADMIN_GUARDS.intersection(dependency_calls(route.dependant)))


def has_explicit_limit(endpoint: Any, method: str) -> bool:
    name = f"{endpoint.__module__}.{endpoint.__name__}"
    limits = limiter._route_limits.get(name, [])
    if not any(not item.methods or method.lower() in item.methods for item in limits):
        return False
    originals = limiter._Limiter__marked_for_limiting.get(name, [])
    while hasattr(endpoint, "__wrapped__"):
        endpoint = endpoint.__wrapped__
        if endpoint in originals:
            return True
    return False


def has_route_limit(route: Any, method: str) -> bool:
    if not has_explicit_limit(route.endpoint, method):
        return False
    # FastAPI resolves dependencies before calling the decorated endpoint.
    # A wrapper alone cannot count rejected credentials or bound auth DB work.
    calls = list(dependency_calls(route.dependant))
    return all(
        enforce_route_limit in calls[:index]
        for index, call in enumerate(calls) if call in AUTH_GUARDS
    )


def uncovered_routes(app: FastAPI) -> list[tuple[str, str]]:
    missing = []
    for route in iter_api_routes(app.routes):
        if is_admin(route):
            continue
        for method in route.methods & WRITE_METHODS:
            key = (method, route.path)
            if key not in WRITE_EXCEPTIONS and not has_route_limit(route, method):
                missing.append(key)
    return sorted(missing)


def test_every_public_write_has_an_explicit_rate_limit() -> None:
    paths = {r.path for r in iter_api_routes(main.app.routes)}
    assert "/api/v1/vote/{bill_id}/correct" in paths  # Never silently skip lazy routers.
    assert not (missing := uncovered_routes(main.app)), f"Unprotected public writes: {missing}"


def test_every_public_router_get_has_a_limit_or_reviewed_reason() -> None:
    missing = []
    for route in iter_api_routes(main.app.routes):
        if "GET" not in route.methods or not route.endpoint.__module__.startswith("routers.") or is_admin(route):
            continue
        if route.path not in READ_EXCEPTIONS and not has_route_limit(route, "GET"):
            missing.append(route.path)
    assert not missing, f"Unreviewed public GETs: {missing}"


def test_rate_limit_exceptions_have_reasons_and_are_not_stale() -> None:
    public = {
        (method, route.path): route
        for route in iter_api_routes(main.app.routes) if not is_admin(route)
        for method in route.methods
    }
    exceptions = {**WRITE_EXCEPTIONS, **{("GET", path): reason for path, reason in READ_EXCEPTIONS.items()}}
    for key, reason in exceptions.items():
        assert reason.strip(), f"Missing exception reason: {key}"
        assert key in public, f"Stale exception: {key}"
        assert not has_explicit_limit(public[key].endpoint, key[0]), f"Redundant exception: {key}"


def test_rate_limit_audit_rejects_nested_default_only_writes_even_under_admin_path() -> None:
    app = FastAPI()
    nested = APIRouter(prefix="/admin")

    @nested.post("/unguarded")
    async def unguarded():
        return {}

    @nested.post("/guarded", dependencies=[Depends(verify_admin_key)])
    async def guarded():
        return {}

    outer = APIRouter(prefix="/api/v1")
    outer.include_router(nested)
    app.include_router(outer)
    assert uncovered_routes(app) == [("POST", "/api/v1/admin/unguarded")]


def test_rate_limit_audit_requires_the_registered_decorator_wrapper() -> None:
    endpoint = next(r.endpoint for r in iter_api_routes(main.app.routes)
                    if r.path == "/api/v1/vote/{bill_id}/correct")
    assert has_explicit_limit(endpoint, "PUT")
    assert not has_explicit_limit(endpoint.__wrapped__, "PUT")


@pytest.mark.parametrize("guard_order", ["missing", "after_auth", "before_auth"])
def test_rate_limit_audit_requires_throttling_before_auth_dependency(guard_order: str) -> None:
    app = FastAPI()
    auth = Depends(representative.verify_rep_token)
    guard = Depends(enforce_route_limit)
    dependencies = {
        "missing": [auth], "after_auth": [auth, guard], "before_auth": [guard, auth],
    }[guard_order]

    @app.api_route("/api/v1/authenticated", methods=["GET", "POST"], dependencies=dependencies)
    @limiter.limit("30/minute")
    async def authenticated(request: Request):
        return {}

    route = next(iter_api_routes(app.routes))
    assert has_explicit_limit(route.endpoint, "POST")
    assert has_route_limit(route, "GET") == (guard_order == "before_auth")
    assert uncovered_routes(app) == (
        [] if guard_order == "before_auth" else [("POST", "/api/v1/authenticated")]
    )
