"""Every public response cache declares and enforces its bill-data schema."""
import ast
from collections import Counter
from pathlib import Path
import pytest

import main
from routers import analytics, parliament, voting, zk
from services import client_flow_cache, cplm
from services.public_bill_response import CONTRIBUTOR_KEYS, serve_public_bill_body
from tests.test_rate_limit_coverage import iter_api_routes


PUBLIC_CACHES = {
    "routers.parliament.get_bills": "rows",
    "routers.parliament.get_trending": "rows",
    "routers.analytics.analytics_overview": "aggregate",
    "routers.mp.party_ranking": "aggregate",
    "routers.consensus_results.get_consensus_representation": "aggregate",
    "routers.evaluation.list_politicians": "independent",
    "routers.evaluation.get_questions": "independent",
    "routers.evaluation.get_scores": "independent",
    "routers.municipal.list_periferies": "independent",
    "routers.municipal.list_dimos_by_periferia": "independent",
    "routers.polis_tickets.list_tickets": "independent",
}
INLINE_CACHES = (
    (analytics.get_cached_representation, "representation"),
    (cplm.get_cplm_cached, "aggregate"),
    (cplm.get_cplm_history, "history"),
    (parliament.get_bill_summary, "point"),
    (voting.get_results, "point"),
    (zk.get_zk_scope_status, "point"),
    (zk.get_current_zk_root_members, "point"),
)


def assert_bill_cache_inventory():
    endpoints = {f"{route.endpoint.__module__}.{route.endpoint.__name__}": route.endpoint
                 for route in iter_api_routes(main.app.routes)
                 if getattr(route.endpoint, "public_cache", None) is not None}
    assert endpoints.keys() == PUBLIC_CACHES.keys(), "Review the bill schema of every new public cache"
    for name, schema in PUBLIC_CACHES.items():
        endpoint = endpoints[name]
        assert endpoint.public_bill_schema == schema, name
        if schema in {"aggregate", "representation"}:
            assert endpoint.public_bill_contributor_keys == CONTRIBUTOR_KEYS, name
            assert endpoint.public_cache.public_bill_contributor_keys == CONTRIBUTOR_KEYS, name
        assert endpoint.public_visibility_filter is serve_public_bill_body, name
        assert endpoint.public_cache is client_flow_cache.public_caches[name], name
    for name, cache in client_flow_cache.public_caches.items():
        assert cache.public_visibility_filter is serve_public_bill_body, name
        assert cache.public_bill_schema in {"rows", "aggregate", "representation", "independent"}, name
    for function, schema in INLINE_CACHES:
        assert function.public_bill_schema == schema, function.__name__
        if schema in {"aggregate", "representation", "history"}:
            assert function.public_bill_contributor_keys == CONTRIBUTOR_KEYS, function.__name__
        assert function.public_visibility_filter is serve_public_bill_body, function.__name__


def test_all_cached_public_bill_schemas_use_the_shared_serve_helper():
    assert_bill_cache_inventory()
    for name, schema in PUBLIC_CACHES.items():
        print(f"CACHE {name}: {schema} -> serve_public_bill_body")
    for function, schema in INLINE_CACHES:
        print(f"CACHE {function.__module__}.{function.__name__}: {schema} -> serve_public_bill_body")


@pytest.mark.parametrize("function", [parliament.get_trending, *(function for function, _ in INLINE_CACHES)],
                         ids=lambda function: function.__name__)
def test_guard_rejects_a_bill_cache_without_the_helper(monkeypatch, function):
    monkeypatch.setattr(function, "public_visibility_filter", None)
    with pytest.raises(AssertionError, match=function.__name__):
        assert_bill_cache_inventory()


def test_cache_factory_requires_an_explicit_bill_schema():
    with pytest.raises(TypeError, match="bill_schema"):
        client_flow_cache.public_client_cache()
    with pytest.raises(ValueError, match="bill schema"):
        client_flow_cache.public_client_cache(bill_schema="unreviewed")


def test_inline_client_cache_calls_cannot_bypass_inventory_review():
    api = Path(__file__).resolve().parents[1]
    calls = Counter()
    for folder in ("routers", "services"):
        for path in (api / folder).glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get_or_fill"):
                    calls[(str(path.relative_to(api)), ast.unparse(node.func.value))] += 1
    assert calls == Counter({
        ("services/client_flow_cache.py", "cache"): 2,
        ("routers/voting.py", "results_cache"): 2,  # Bill totals and independent regional population.
        ("routers/zk.py", "scope_status_cache"): 1,
    }), "Review every new inline public cache and wire bill-derived bodies through the helper"


def test_guard_rejects_missing_contributor_sets(monkeypatch):
    monkeypatch.setattr(analytics.analytics_overview, "public_bill_contributor_keys", frozenset())
    with pytest.raises(AssertionError, match="analytics_overview"):
        assert_bill_cache_inventory()
