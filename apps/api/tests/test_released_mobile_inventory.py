"""Source-derived release coverage and a fail-closed public work policy."""
from inspect import getsource, signature, unwrap
from pathlib import Path
import re
import sys

import pytest

import main
from rate_limit import limiter
from services.client_flow_cache import ClientFlowCache, public_caches
from services.request_work import SingleFlight
from tests.test_rate_limit_coverage import iter_api_routes, route_policy
from tests.test_released_mobile_client_flow import INVENTORY

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from released_mobile_inventory import calls_in_source, git, released_calls


def shape(path):
    return re.sub(r'\{[^}]+\}', '{param}', path)


def test_all_released_mobile_calls_are_in_inventory_and_classified():
    routes = {(method, shape(route.path)): route for route in iter_api_routes(main.app.routes)
              for method in route.methods}
    derived = []
    for call in released_calls():
        route = routes.get((call['method'], call['path']))
        assert route is not None, f'Released route not registered: {call}'
        derived.append(dict(call, path=route.path))
    assert INVENTORY['released_commit'] == git('rev-parse', 'origin/main').strip()
    assert derived == INVENTORY['source_calls'], 'Regenerate source_calls from origin/main; review every new pattern'
    actions = {(r['method'], r['path']): r['reason'] for r in INVENTORY['justified_actions']}
    flow = {(r['method'], r['path']) for r in INVENTORY['routes']}
    seen = {(r['method'], r['path']) for r in derived}
    assert not actions.keys() - seen, 'Stale action justifications'
    for call in derived:
        key = call['method'], call['path']
        route = routes[(call['method'], shape(call['path']))]
        if key in actions:
            assert actions[key].startswith('Explicit ') and len(actions[key]) > 30
            assert call['method'] != 'GET', 'Automatic released reads need client-flow'
        else:
            assert key in flow, f'Missing released request pattern: {call}'
            assert route_policy(route, call['method'])[0] == 'client-flow', call


def test_scanner_covers_templates_multiline_methods_and_new_wrappers():
    source = '''// fetch("/api/v1/ignored")
      request<Result[]>(`/api/v1/new/${encodeURIComponent(id)}?limit=${limit}`, {method: "POST"});
      fetch(`${base}/api/v1/other`);
      customClient(`/api/v1/third`, {method: "PATCH"});
    '''
    assert [(r['method'], r['path']) for r in calls_in_source(source, 'screen.tsx')] == [
        ('POST', '/api/v1/new/{param}'), ('GET', '/api/v1/other'), ('PATCH', '/api/v1/third')]
    with pytest.raises(AssertionError, match='Unresolved API literal'):
        calls_in_source('const endpoint = "/api/v1/new";', 'screen.tsx')
    with pytest.raises(AssertionError, match='Unresolved HTTP call'):
        calls_in_source('fetch(endpoint)', 'screen.tsx')
    with pytest.raises(AssertionError, match='Unresolved HTTP method'):
        calls_in_source('fetch("/api/v1/new", {method: verb})', 'screen.tsx')


# These GETs cannot scan/aggregate: constants or an indexed single-row lookup.
# Personal reads use POST or signed evaluation GETs and are audited separately.
POINT_READS = {
    '/api/v1/app/version': 'Static version manifest and feature flags.',
    '/api/v1/version': 'Static legacy version manifest.',
    '/api/v1/bills/{bill_id}': 'One bill by primary key; no aggregates.',
    '/api/v1/notifications/status': 'In-memory event-bus status; no I/O.',
    '/api/v1/zk/status': 'Static rollout configuration; no I/O.',
    '/api/v1/zk/roots/{vote_scope_id}': 'One indexed published root plus visibility lookup.',
    '/api/v1/politicians/{ada_number}/my-evaluation': 'Signed private per-identity scores; never shared.',
    '/api/v1/politicians/my-evaluations/bulk': 'Signed private per-identity evaluation summary; never shared.',
}
# These cache only their expensive public component so visibility/membership
# checks still run per request. Behaviour is exercised by compatibility/work tests.
INLINE_CACHES = {
    '/api/v1/vote/{bill_id}/results': 'results_cache.get_or_fill',
    '/api/v1/zk/scopes/{vote_scope_id}/status': 'scope_status_cache.get_or_fill',
    '/api/v1/zk/roots/{vote_scope_id}/members': '_root_members_flights.run',
}


def assert_public_read_cache_policy(routes):
    seen = set()
    for route in routes:
        if 'GET' not in route.methods or route_policy(route, 'GET')[0] != 'client-flow':
            continue
        seen.add(route.path)
        cache = getattr(route.endpoint, 'public_cache', None)
        if route.path in POINT_READS:
            assert cache is None, f'Private or cheap point read unexpectedly cached: {route.path}'
            if not POINT_READS[route.path].startswith('Signed private'):
                source = getsource(unwrap(route.endpoint))
                assert not re.search(r'aggregate_|func\.(count|sum|avg)|\.(all|fetchall)\(|GROUP BY', source), (
                    f'Point read acquired a scan/aggregate: {route.path}')
            continue
        if route.path in INLINE_CACHES:
            assert INLINE_CACHES[route.path] in getsource(unwrap(route.endpoint))
            continue
        assert isinstance(cache, ClientFlowCache), f'Client scan/aggregate needs public single-flight cache: {route.path}'
        assert isinstance(cache.flights, SingleFlight)
        assert 0 < cache.capacity <= 128 and 0 < cache.ttl <= 5
        params = set(signature(route.endpoint).parameters) - {'db', 'request'}
        assert params == route.endpoint.public_cache_parameters
    return seen


def test_every_client_flow_or_polling_scan_has_a_bounded_public_cache():
    seen = assert_public_read_cache_policy(iter_api_routes(main.app.routes))
    assert not (POINT_READS.keys() | INLINE_CACHES.keys()) - seen, 'Stale public work policy'
    assert len(public_caches) >= 11


def test_new_client_read_cannot_bypass_cache_review():
    from fastapi import FastAPI, Request
    from rate_limit import client_flow
    app = FastAPI()

    @app.get('/new-aggregate')
    @client_flow
    async def uncached(request: Request):
        return {}

    with pytest.raises(AssertionError, match='needs public single-flight cache'):
        assert_public_read_cache_policy(iter_api_routes(app.routes))
