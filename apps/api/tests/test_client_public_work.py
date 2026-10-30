"""Bound actual HTTP aggregate work independently of successful read volume."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient
import pytest

import main
from models import BillStatus, ParliamentBill
from rate_limit import limiter
from routers import analytics, evaluation, mp
from services import bill_visibility, client_flow_cache
from services.zk_vote_aggregation import VoteTotals
from tests.test_released_mobile_client_flow import Rows, released_backend


def overview_data(monkeypatch, db, count=100):
    bills = [ParliamentBill(id=f'GR-{i}', title_el=f'Public {i}', source='PARLIAMENT',
                           status=BillStatus.PARLIAMENT_VOTED, party_votes_parliament={'ND': 'YES'})
             for i in range(count)]
    db.execute = AsyncMock(return_value=Rows(bills))
    db.scalar = AsyncMock(return_value=count)
    votes = AsyncMock(wraps=analytics.count_public_votes)
    monkeypatch.setattr(analytics, 'count_public_votes', votes)

    async def aggregate(*args, **kwargs):
        await asyncio.sleep(0)  # Force followers to arrive during the fill.
        return VoteTotals(20, 20, 20, 20, 80, 0)

    totals = AsyncMock(side_effect=aggregate)
    monkeypatch.setattr(analytics, 'aggregate_bill_vote_totals', totals)
    return totals, votes


@pytest.mark.asyncio
async def test_fifty_overview_http_reads_aggregate_one_hundred_bills_once(released_backend, monkeypatch):
    clock, db, _ = released_backend
    totals, votes = overview_data(monkeypatch, db)
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url='http://test') as client:
        responses = await asyncio.gather(*(client.get('/api/v1/analytics/overview') for _ in range(50)))
        assert all(r.status_code == 200 for r in responses)
        assert all(r.json() == responses[0].json() for r in responses)
        assert totals.await_count == 100
        assert db.execute.await_count == 1 and db.scalar.await_count == 9
        assert votes.await_count == 3
        # Hits don't extend TTL; the next window recomputes exactly once.
        clock.now += 5
        assert (await client.get('/api/v1/analytics/overview')).status_code == 200
        assert totals.await_count == 200
    print('overview 50 concurrent HTTP 200s / 100 bills: 100 aggregations, 1 bill scan, 9 count SQL calls (one fill)')


@pytest.mark.asyncio
async def test_overview_fill_budget_is_global_and_hits_do_not_consume_it(released_backend, monkeypatch):
    _, db, _ = released_backend
    totals, _ = overview_data(monkeypatch, db, count=1)
    cache = analytics.analytics_overview.public_cache
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url='http://test') as client:
        for _ in range(30):
            cache.clear()
            assert (await client.get('/api/v1/analytics/overview')).status_code == 200
        assert totals.await_count == 30
        for _ in range(50):
            assert (await client.get('/api/v1/analytics/overview')).status_code == 200
        cache.clear()
        calls = db.execute.await_count
        async with AsyncClient(transport=ASGITransport(app=main.app, client=('203.0.113.99', 9)),
                               base_url='http://test') as other:
            response = await other.get('/api/v1/analytics/overview')
        assert response.status_code == 429 and int(response.headers['retry-after']) > 0
        assert db.execute.await_count == calls


@pytest.mark.asyncio
async def test_public_cache_keys_query_defaults_privacy_and_visibility_rules(released_backend, monkeypatch):
    from routers import parliament
    clock, db, _ = released_backend
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url='http://test') as client:
        paths = ['/api/v1/bills?limit=4', '/api/v1/bills?limit=40',
                 '/api/v1/bills?limit=4&source=PARLIAMENT',
                 '/api/v1/bills?limit=4&offset=1', '/api/v1/bills?limit=4&status=ACTIVE']
        for path in paths:
            for _ in range(2):
                assert (await client.get(path)).status_code == 200
        assert db.execute.await_count == len(paths)
        monkeypatch.setenv('PUBLIC_RESULTS_MIN_COUNT', '10')
        assert (await client.get(paths[0])).status_code == 200
        assert db.execute.await_count == len(paths) + 1
        monkeypatch.setattr(bill_visibility, 'DIAVGEIA_SENSITIVE_PUBLIC_TERMS', ('new-marker',))
        assert (await client.get(paths[0])).status_code == 200
        assert db.execute.await_count == len(paths) + 2
        # Unknown fields have no effect on public handlers and must not retain
        # signed/identity material in a shared key or create arbitrary variants.
        assert (await client.get(paths[0] + '&nullifier_hash=private-marker')).status_code == 200
        assert 'private-marker' not in repr(parliament.get_bills.public_cache.entries)
        clock.now += 4
        await client.get(paths[0])
        assert db.execute.await_count == len(paths) + 2
        clock.now += 1
        await client.get(paths[0])
        assert db.execute.await_count == len(paths) + 3


@pytest.mark.asyncio
async def test_mp_ranking_aggregates_each_bill_once_across_parties_and_readers(released_backend, monkeypatch):
    _, db, _ = released_backend
    parties = [SimpleNamespace(abbreviation=f'P{i}', name_el=f'Party {i}', color_hex='#000') for i in range(8)]
    bills = [SimpleNamespace(id=f'GR-{i}', party_votes_parliament={p.abbreviation: 'YES' for p in parties})
             for i in range(100)]
    async def execute(statement):
        await asyncio.sleep(0)
        return Rows(bills if 'parliament_bills' in str(statement) else parties)
    db.execute = AsyncMock(side_effect=execute)
    majority = AsyncMock(return_value=('YES', 50, 30, 80))
    monkeypatch.setattr(mp, 'citizen_majority_for', majority)
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url='http://test') as client:
        responses = await asyncio.gather(*(client.get('/api/v1/mp/ranking') for _ in range(50)))
        assert all(r.status_code == 200 and len(r.json()['ranking']) == 8 for r in responses)
        assert majority.await_count == 100 and db.execute.await_count == 2


@pytest.mark.asyncio
async def test_politician_public_scans_coalesce_and_errors_are_not_cached(released_backend, monkeypatch):
    _, db, _ = released_backend
    async def execute(*args, **kwargs):
        await asyncio.sleep(0)
        return Rows([])
    db.execute = AsyncMock(side_effect=execute)
    enabled = AsyncMock(return_value={'org_label': 'Public politician'})
    monkeypatch.setattr(evaluation, '_get_enabled_politician', enabled)
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url='http://test') as client:
        for path in ('/api/v1/politicians/', '/api/v1/politicians/ADA-1/questions', '/api/v1/politicians/ADA-1/scores'):
            responses = await asyncio.gather(*(client.get(path) for _ in range(50)))
            assert all(r.status_code == 200 for r in responses)
        assert db.execute.await_count == 3
        assert enabled.await_count == 2
        monkeypatch.setattr(evaluation, 'EVALUATION_K_ANONYMITY_MIN', 20)
        assert (await client.get('/api/v1/politicians/ADA-1/scores')).status_code == 200
        assert db.execute.await_count == 4
    cache = evaluation.get_scores.public_cache
    cache.clear()
    db.execute = AsyncMock(side_effect=RuntimeError('query failed'))
    monkeypatch.setattr(limiter, 'enabled', False)
    with pytest.raises(RuntimeError, match='query failed'):
        await evaluation.get_scores('ADA-1', db=db)
    assert not cache.entries
    db.execute = AsyncMock(return_value=Rows([]))
    result = await evaluation.get_scores('ADA-1', db=db)
    result['questions'].append({'mutated': True})
    assert (await evaluation.get_scores('ADA-1', db=db))['questions'] == []


@pytest.mark.asyncio
async def test_committed_writes_clear_every_public_cache_and_failed_commits_do_not(monkeypatch):
    from services.representation_cache import commit_and_invalidate_representation
    work = AsyncMock(return_value={'public': 1})
    for cache in client_flow_cache.public_caches.values():
        await cache.get_or_fill('public', work)
    monkeypatch.setattr('services.representation_cache.aioredis.from_url', lambda *a, **k: None)
    with pytest.raises(RuntimeError):
        await commit_and_invalidate_representation(SimpleNamespace(commit=AsyncMock(side_effect=RuntimeError())))
    assert all(cache.entries for cache in client_flow_cache.public_caches.values())
    await commit_and_invalidate_representation(SimpleNamespace(commit=AsyncMock()))
    assert not any(cache.entries for cache in client_flow_cache.public_caches.values())


@pytest.mark.asyncio
async def test_results_regional_population_scan_is_shared(released_backend):
    from models import GovernanceLevel
    from routers.voting import representativity_for_bill
    clock, db, _ = released_backend
    db.execute = AsyncMock(return_value=Rows(123456))
    bill = SimpleNamespace(governance_level=GovernanceLevel.REGIONAL, periferia_id=1)
    results = await asyncio.gather(*(representativity_for_bill(db, bill, 80) for _ in range(50)))
    assert all(result == results[0] for result in results)
    assert db.execute.await_count == 1
    clock.now += 5
    await representativity_for_bill(db, bill, 80)
    assert db.execute.await_count == 2
