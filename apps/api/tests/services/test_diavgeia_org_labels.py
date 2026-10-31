"""Synthetic organization lookups; real HTTP hooks, mocked HTTP and Redis."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from services import diavgeia_org_lookup as lookup


@pytest.fixture
def label_store(monkeypatch, scraper_clock, offline_http_client):
    clock = scraper_clock

    class Store:
        def __init__(self):
            self.hashes = {}
            self.expiry = {}
            self.slot_until = 0
            self.acquired = []
            self.reads = 0
            self.down = False

        async def hgetall(self, key):
            self.reads += 1
            if self.down:
                raise ConnectionError("synthetic secret")
            if self.expiry.get(key, 0) <= clock.now:
                self.hashes.pop(key, None)
            return self.hashes.get(key, {})

        async def set(self, key, value, *, nx, px):
            assert key == lookup.LABEL_RATE_KEY and nx and px == 500
            if self.down:
                raise ConnectionError("synthetic secret")
            if clock.now < self.slot_until:
                return None
            self.slot_until = clock.now + px / 1000
            self.acquired.append(clock.now)
            return True

        @asynccontextmanager
        async def pipeline(self, *, transaction):
            assert transaction
            store = self

            class Pipeline:
                def hset(self, key, *, mapping):
                    store.hashes[key] = mapping

                def expire(self, key, ttl):
                    store.expiry[key] = clock.now + ttl

                async def execute(self):
                    pass

            yield Pipeline()

    store = Store()

    @asynccontextmanager
    async def connection():
        yield store

    monkeypatch.setattr(lookup, "_redis", connection)
    monkeypatch.setattr(lookup, "_org_cache", {"1": {"uid": "1", "label": "ΔΗΜΟΣ ΔΟΚΙΜΗΣ"}})
    monkeypatch.setattr(lookup, "asyncio", SimpleNamespace(sleep=clock.sleep, timeout=asyncio.timeout))
    return store


async def test_snapshot_precedes_persistent_cache_and_http(label_store):
    label_store.down = True
    with respx.mock(assert_all_called=False) as mock:
        assert await lookup.resolve_org_label("1") == "ΔΗΜΟΣ ΔΟΚΙΜΗΣ"
        assert not mock.calls
    assert label_store.reads == 0


async def test_positive_cache_is_shared_without_polluting_geography(label_store, scraper_clock):
    uid = "42"
    with respx.mock() as mock:
        route = mock.get(f"{lookup.ORGANIZATIONS_URL}/{uid}").respond(
            200, json={"uid": uid, "label": "  SYNTHETIC AGENCY AE  ", "category": "MINISTRY"})
        assert await lookup.resolve_org_label(uid) == "SYNTHETIC AGENCY AE"
        request = route.calls[0].request
        assert request.headers["Accept"] == "application/json"
        assert request.headers["User-Agent"] == lookup.USER_AGENT
        assert not request.content and not request.url.query
        # A fresh snapshot/process still sees the persistent cache.
        lookup._org_cache = {}
        assert lookup.get_org(uid) is None
        assert await lookup.resolve_org_label(uid) == "SYNTHETIC AGENCY AE"
        assert route.call_count == 1
    assert label_store.expiry[lookup.LABEL_CACHE_PREFIX + uid] - scraper_clock.now == lookup.POSITIVE_TTL


@pytest.mark.parametrize("response", [
    httpx.Response(404), httpx.Response(200, json={"uid": "42", "label": "[unknown:42]"}),
    httpx.Response(200, json={"uid": "99", "label": "Wrong organization"}),
    httpx.Response(200, json={"uid": "42", "label": None}),
    httpx.Response(200, json=[]), httpx.Response(200, text="invalid JSON"),
])
async def test_negative_cache_and_expiry(label_store, scraper_clock, response):
    with respx.mock() as mock:
        route = mock.get(f"{lookup.ORGANIZATIONS_URL}/42").mock(return_value=response)
        assert await lookup.resolve_org_label("42") is None
        assert await lookup.resolve_org_label("42") is None
        assert route.call_count == 1
        assert label_store.expiry[lookup.LABEL_CACHE_PREFIX + "42"] - scraper_clock.now == lookup.NEGATIVE_TTL
        scraper_clock.now += lookup.NEGATIVE_TTL + 1
        route.respond(200, json={"uid": "42", "label": "New agency"})
        assert await lookup.resolve_org_label("42") == "New agency"
        assert route.call_count == 2


@pytest.mark.parametrize("failure", [429, 503, httpx.ReadTimeout, httpx.ConnectError])
async def test_retry_with_backoff_and_release_failed_host_lease(label_store, scraper_clock, failure):
    first = httpx.Response(failure) if isinstance(failure, int) else failure("synthetic transport error")
    with respx.mock() as mock:
        route = mock.get(f"{lookup.ORGANIZATIONS_URL}/42").mock(side_effect=[
            first, httpx.Response(200, json={"uid": "42", "label": "Recovered agency"}),
        ])
        assert await lookup.resolve_org_label("42") == "Recovered agency"
        assert route.call_count == 2
    assert lookup.RETRY_BASE_DELAY in scraper_clock.sleeps


async def test_transient_failures_are_bounded_and_not_negative_cached(label_store, scraper_clock):
    with respx.mock() as mock:
        route = mock.get(f"{lookup.ORGANIZATIONS_URL}/42").respond(503)
        assert await lookup.resolve_org_label("42") is None
        assert route.call_count == lookup.MAX_RETRIES
    assert lookup.LABEL_CACHE_PREFIX + "42" not in label_store.hashes
    assert lookup.RETRY_BASE_DELAY * 2 in scraper_clock.sleeps


async def test_attempt_deadline_retries_a_stalled_request(label_store, monkeypatch):
    monkeypatch.setattr(lookup, "LOOKUP_TIMEOUT", 0.05)
    attempts = []

    async def stall(request):
        attempts.append(request)
        await asyncio.Future()

    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{lookup.ORGANIZATIONS_URL}/42").mock(side_effect=stall)
        assert await lookup.resolve_org_label("42") is None
        # Cancelled transport calls may not be recorded by respx, but each
        # attempt acquired a slot after releasing the previous host lease.
    assert len(label_store.acquired) == lookup.MAX_RETRIES
    assert len(attempts) == lookup.MAX_RETRIES
    assert lookup.LABEL_CACHE_PREFIX + "42" not in label_store.hashes


async def test_shared_rate_slot_limits_concurrent_requests(label_store):
    request = httpx.Request("GET", f"{lookup.ORGANIZATIONS_URL}/42")
    await asyncio.gather(*(lookup._pace_label_request(request) for _ in range(6)))
    assert len(label_store.acquired) == 6
    assert all(b - a >= 0.5 for a, b in zip(label_store.acquired, label_store.acquired[1:]))


async def test_cache_outage_falls_back_without_dispatch_or_secret_logging(label_store, caplog):
    label_store.down = True
    with respx.mock(assert_all_called=False) as mock:
        assert await lookup.resolve_org_label("42") is None
        assert not mock.calls
    assert "synthetic secret" not in caplog.text
    assert "unavailable" in caplog.text


@pytest.mark.parametrize("uid", ["", "../units/42", "person@example.test", "１２３", "9" * 17])
async def test_invalid_uid_never_leaves_process(label_store, uid):
    assert await lookup.resolve_org_label(uid) is None
    assert label_store.reads == 0


@pytest.mark.parametrize("label", [None, "", "unknown", "[unknown:42]", "[no-label:42]", "42"])
def test_neutral_pill_never_contains_unknown_or_uid(label):
    assert lookup.org_pill(label) == "Διαύγεια"


@pytest.mark.parametrize("live_label", ["SYNTHETIC AGENCY AE", None])
async def test_conversion_uses_shared_live_resolution_and_neutral_fallback(label_store, monkeypatch, live_label):
    from services import diavgeia_scraper as scraper

    subject = "Επίσημη απόφαση για Example Endpoint Package for synthetic office"
    added = []
    rows = [(f"SYNTH-{i}", subject, "Α.2", "[unknown:42]", "https://example.test/doc",
             "OTHER", None, None, None, "42") for i in range(2)]
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(fetchall=lambda: rows)),
                         add=added.append, flush=AsyncMock())
    monkeypatch.setattr(scraper, "_sync_existing_decision_bill_scopes", AsyncMock(return_value=0))
    monkeypatch.setattr(scraper, "commit_and_invalidate_representation", AsyncMock())
    with respx.mock() as mock:
        route = mock.get(f"{lookup.ORGANIZATIONS_URL}/42")
        if live_label:
            route.respond(200, json={"uid": "42", "label": live_label})
        else:
            route.respond(404)
        result = await scraper.convert_decisions_to_bills(db)
        assert route.call_count == 1
    assert result["created"] == 2
    assert all(bill.pill_el == lookup.org_pill(live_label) and bill.org_label == live_label for bill in added)
    assert all(bill.title_el == bill.summary_short_el == subject for bill in added)
    assert all(bill.generated_content_provenance is None for bill in added)
    assert "d.organization_uid" in str(db.execute.await_args.args[0])


@pytest.mark.parametrize("live_label", ["Synthetic agency", None])
async def test_scrape_stores_resolved_label_and_retains_raw_uid(label_store, monkeypatch, live_label):
    from datetime import datetime, timezone
    from services import diavgeia_scraper as scraper

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def iter_decisions(self, **kwargs):
            yield {"ada": "SYNTHETIC", "organizationId": "42", "issueDate": "2026-10-01T00:00:00Z",
                   "subject": "Synthetic official text"}

    monkeypatch.setattr(scraper, "DiavgeiaClient", Client)
    monkeypatch.setattr(scraper, "_resolve_org", AsyncMock(return_value=(None, None, "OTHER")))
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(rowcount=1)), commit=AsyncMock())
    with respx.mock() as mock:
        mock.get(f"{lookup.ORGANIZATIONS_URL}/42").respond(
            200 if live_label else 404, json={"uid": "42", "label": live_label})
        result = await scraper.scrape_decisions(db, decision_type_uids=["Α.2"], published_after=datetime.now(timezone.utc))
    assert result.inserted == 1
    params = db.execute.await_args.args[0].compile().params
    assert params["organization_uid"] == "42"
    assert params["organization_label"] == (live_label or "")
    assert scraper.DiavgeiaDecision.__table__.c.organization_label.nullable is False


@pytest.mark.parametrize("batch_size", [1, 100])
@pytest.mark.parametrize("live_label", ["Synthetic agency", None])
async def test_historical_import_uses_shared_resolver_in_both_flush_paths(label_store, monkeypatch, batch_size, live_label):
    from scripts import backfill_diavgeia_decisions as historical
    from services import diavgeia_client, diavgeia_scraper
    import database

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def search_decisions(self, **kwargs):
            return {"decisions": [{"ada": "SYNTHETIC", "organizationId": "42",
                                   "issueDate": "2026-10-01T00:00:00Z", "subject": "Official title"}]}

    db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())

    @asynccontextmanager
    async def session():
        yield db

    monkeypatch.setattr(historical, "parse_args", lambda: SimpleNamespace(
        since="2026-01-01", until="2026-10-31", resume=False, decision_type_uid="Α.2",
        organization_uid=None, max_pages=1, batch_size=batch_size, dry_run=False))
    monkeypatch.setattr(historical.signal, "signal", lambda *args: None)
    monkeypatch.setattr(historical, "save_cursor", lambda *args: None)
    monkeypatch.setattr(diavgeia_client, "DiavgeiaClient", Client)
    monkeypatch.setattr(diavgeia_scraper, "_resolve_org", AsyncMock(return_value=(None, None, "OTHER")))
    monkeypatch.setattr(database, "AsyncSessionLocal", session)
    with respx.mock() as mock:
        mock.get(f"{lookup.ORGANIZATIONS_URL}/42").respond(
            200 if live_label else 404, json={"uid": "42", "label": live_label})
        await historical.main()
    params = db.execute.await_args.args[0].compile().params
    assert params["organization_uid_m0"] == "42"
    assert params["organization_label_m0"] == (live_label or "")
    assert params["governance_level_m0"] == "OTHER"
    db.commit.assert_awaited_once()
