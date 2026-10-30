"""EVA-011: audit the registered app, including FastAPI's lazy routers.

Defaults do not cover included routers in our FastAPI/SlowAPI combination.
An entry in the limiter registry alone is insufficient: the registered route
must also contain its decorator wrapper (decorator order matters). Token
authentication dependencies must be preceded by a limiter dependency.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Request
import pytest

import main
from dependencies import verify_admin_key
from rate_limit import enforce_route_limit, limiter
from routers import admin, public_api, representative


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


# Explicit operator exemptions: adding an admin route requires policy review.
ADMIN_EXCEPTIONS = {
    key: "Admin-key authentication required; operator batch/maintenance traffic has no citizen-IP quota."
    for key in {
        ('DELETE', '/api/v1/admin/bills/{bill_id}/votes'),
        ('GET', '/api/v1/admin/bills'),
        ('GET', '/api/v1/admin/compass/pending-review'),
        ('GET', '/api/v1/admin/dashboard'),
        ('GET', '/api/v1/admin/diavgeia/decision/{ada}'),
        ('GET', '/api/v1/admin/diavgeia/refresh-orgs-cache/{job_id}'),
        ('GET', '/api/v1/admin/hlr/credits'),
        ('GET', '/api/v1/admin/logs/containers'),
        ('GET', '/api/v1/admin/logs/ollama'),
        ('GET', '/api/v1/admin/logs/stream'),
        ('GET', '/api/v1/admin/newsletter/dispatch-status'),
        ('GET', '/api/v1/admin/newsletter/readiness'),
        ('GET', '/api/v1/admin/newsletter/stats'),
        ('GET', '/api/v1/admin/stats'),
        ('GET', '/api/v1/payments/admin/finance/btc'),
        ('GET', '/api/v1/payments/admin/finance/events'),
        ('GET', '/api/v1/payments/admin/finance/ltc'),
        ('GET', '/api/v1/payments/admin/finance/overview'),
        ('GET', '/api/v1/payments/admin/finance/server'),
        ('GET', '/api/v1/payments/admin/logs'),
        ('GET', '/api/v1/rep/admin/invites'),
        ('GET', '/api/v1/zk/canary/preflight/{vote_scope_id}'),
        ('PATCH', '/api/v1/admin/bills/{bill_id}'),
        ('POST', '/api/v1/admin/bills'),
        ('POST', '/api/v1/admin/bills/{bill_id}/fetch-text'),
        ('POST', '/api/v1/admin/bills/{bill_id}/party-votes'),
        ('POST', '/api/v1/admin/bills/{bill_id}/review'),
        ('POST', '/api/v1/admin/bills/{bill_id}/set-text'),
        ('POST', '/api/v1/admin/compass/approve/{question_id}'),
        ('POST', '/api/v1/admin/compass/generate-questions'),
        ('POST', '/api/v1/admin/compass/reject/{question_id}'),
        ('POST', '/api/v1/admin/diavgeia/convert-to-bills'),
        ('POST', '/api/v1/admin/diavgeia/refresh-orgs-cache'),
        ('POST', '/api/v1/admin/diavgeia/resolve-orgs'),
        ('POST', '/api/v1/admin/diavgeia/scrape'),
        ('POST', '/api/v1/admin/forum/resync-all'),
        ('POST', '/api/v1/admin/forum/sync-new'),
        ('POST', '/api/v1/admin/logs/explain'),
        ('POST', '/api/v1/admin/maintenance/resolve-org-labels'),
        ('POST', '/api/v1/admin/newsletter/audience'),
        ('POST', '/api/v1/admin/newsletter/backfill'),
        ('POST', '/api/v1/admin/newsletter/draft'),
        ('POST', '/api/v1/admin/newsletter/preview'),
        ('POST', '/api/v1/admin/newsletter/reconfirm'),
        ('POST', '/api/v1/admin/newsletter/reconfirm/expire'),
        ('POST', '/api/v1/admin/newsletter/send'),
        ('POST', '/api/v1/admin/scraper/catch-up'),
        ('POST', '/api/v1/admin/scraper/enrich-all'),
        ('POST', '/api/v1/admin/scraper/heal-status'),
        ('POST', '/api/v1/admin/test-account'),
        ('POST', '/api/v1/bills/admin/create'),
        ('POST', '/api/v1/bills/{bill_id}/transition'),
        ('POST', '/api/v1/newsletter/unsubscribe'),
        ('POST', '/api/v1/notifications/test/publish'),
        ('POST', '/api/v1/notify/send'),
        ('POST', '/api/v1/rep/admin/invite'),
        ('POST', '/api/v1/scraper/fetch'),
        ('POST', '/api/v1/scraper/import'),
        ('POST', '/api/v1/zk/receipts/{vote_scope_id}/publish-pending'),
        ('POST', '/api/v1/zk/roots/{vote_scope_id}/publish'),
        ('PUT', '/api/v1/admin/newsletter/preferences'),
    }
}

DIRECT_DEFAULTS = {
    "/", "/health", "/api/v1/health/modules", "/api/v1/version",
    "/api/v1/admin/sentry/status", "/robots.txt",
}
FRAMEWORK_DEFAULTS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def iter_api_routes(routes: Any, *, include_framework: bool = False) -> Iterator[Any]:
    for route in routes:
        if hasattr(route, "effective_candidates"):
            # Lazy FastAPI routers include prefixes and inclusion dependencies.
            yield from iter_api_routes(route.effective_candidates(), include_framework=include_framework)
        elif (getattr(route, "endpoint", None) and getattr(route, "methods", None)
              and (include_framework or getattr(route, "dependant", None) is not None)):
            yield route


def dependency_calls(dependant: Any) -> Iterator[Any]:
    for dependency in dependant.dependencies:
        yield from dependency_calls(dependency)
        yield dependency.call


def is_admin(route: Any) -> bool:
    dependant = getattr(route, "dependant", None)
    return bool(dependant and ADMIN_GUARDS.intersection(dependency_calls(dependant)))


def route_policy(route: Any, method: str) -> tuple[str, str] | None:
    """The actual wrapper/guard and an exact route entry determine the class."""
    key = (method, route.path)
    if has_route_limit(route, method):
        name = f"{route.endpoint.__module__}.{route.endpoint.__name__}"
        limits = limiter._route_limits[name]
        return "explicit", "; ".join(str(item.limit) for item in limits)
    if key in ADMIN_EXCEPTIONS and is_admin(route):
        return "admin-exempt", ADMIN_EXCEPTIONS[key]
    if is_admin(route):
        return None
    if key in WRITE_EXCEPTIONS:
        reason = WRITE_EXCEPTIONS[key]
        return ("provider-exempt" if "/webhook" in route.path else "dedicated-redis", reason)
    if method == "GET" and route.path in READ_EXCEPTIONS:
        reason = READ_EXCEPTIONS[route.path]
        if "shared Redis public-data quota" in reason:
            if public_api.rate_limit_check not in dependency_calls(route.dependant):
                return None
            return "public-shared-redis", reason
        return "public-read-exempt", reason
    if method in {"GET", "HEAD"} and (
        route.path in DIRECT_DEFAULTS and route.endpoint.__module__ == "main"
        or route.path in FRAMEWORK_DEFAULTS and route.endpoint.__module__.startswith("fastapi.")
    ):
        return "direct-default", "60/minute/IP per endpoint via SlowAPI middleware (including health)."
    return None


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


def unclassified_routes(app: FastAPI) -> list[tuple[str, str]]:
    return sorted(
        (method, route.path)
        for route in iter_api_routes(app.routes, include_framework=True)
        for method in route.methods
        if route_policy(route, method) is None
    )


def test_every_http_route_has_an_explicit_policy_class() -> None:
    assert not (missing := unclassified_routes(main.app)), f"Unclassified HTTP routes: {missing}"
    actual = {(method, route.path): route for route in iter_api_routes(main.app.routes) for method in route.methods}
    for key, reason in ADMIN_EXCEPTIONS.items():
        assert key in actual, f"Stale admin policy: {key}"
        assert is_admin(actual[key]), f"Admin policy has lost authentication: {key}"
        assert reason.strip()


def test_policy_rejects_new_public_admin_and_method_entries_without_review() -> None:
    app = FastAPI()

    @app.get("/new-admin", dependencies=[Depends(verify_admin_key)])
    async def new_admin() -> dict[str, bool]:
        return {}

    @app.api_route("/new-public", methods=["GET", "POST"])
    async def new_public() -> dict[str, bool]:
        return {}

    @app.api_route("/new-method", methods=["HEAD", "OPTIONS", "TRACE"])
    async def new_method() -> dict[str, bool]:
        return {}

    missing = unclassified_routes(app)
    assert ("GET", "/new-admin") in missing
    assert all((method, "/new-public") in missing for method in {"GET", "POST"})
    assert all((method, "/new-method") in missing for method in {"HEAD", "OPTIONS", "TRACE"})


def test_policy_rejects_a_shared_public_quota_without_its_dependency() -> None:
    app = FastAPI()

    @app.get("/api/v1/public/vaa/parties")
    async def unguarded_public_parties() -> dict[str, bool]:
        return {}

    assert ("GET", "/api/v1/public/vaa/parties") in unclassified_routes(app)


def test_documented_route_table_matches_actual_policy() -> None:
    documentation = Path(__file__).resolve().parents[3] / "docs/operations/API_RATE_LIMIT_COVERAGE.md"
    table = documentation.read_text().split("<!-- route-policy:start -->")[1].split("<!-- route-policy:end -->")[0]
    expected = set()
    for route in iter_api_routes(main.app.routes, include_framework=True):
        if route.path in FRAMEWORK_DEFAULTS and route.endpoint.__module__.startswith("fastapi."):
            continue
        for method in route.methods:
            policy = route_policy(route, method)
            assert policy is not None
            expected.add(f"| {method} | `{route.path}` | {policy[0]} | {policy[1]} |")
    # Development-only metadata is listed separately from runtime routes.
    actual = {line for line in table.splitlines() if line.startswith("| ") and "`" in line}
    assert actual == expected


def test_development_metadata_routes_have_a_class() -> None:
    app = FastAPI()
    assert not unclassified_routes(app)


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
