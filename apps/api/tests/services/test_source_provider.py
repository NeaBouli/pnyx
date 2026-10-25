import copy
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from routers import scraper
from services import source_freshness, source_provider as provider
from services import parliament_access as policy

LAW_ID = "97e0885f-30fe-45f3-bbe9-b4de0151a84f"
SOCKET = "/run/source-provider/provider.sock"


def payload():
    return {
        "schema_version": 1, "source": "PARLIAMENT", "source_status": "ok",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "bills": [{
            "law_id": LAW_ID, "title_el": "Κύρωση συμφωνίας για τη λειτουργία των θεσμών",
            "url": f"https://www.hellenicparliament.gr/Nomothetiko-Ergo/Psifisthenta-Nomoschedia?law_id={LAW_ID}",
            "date": "2026-10-23T00:00:00+00:00", "submitted_date": None,
        }],
    }


class Body(httpx.AsyncByteStream):
    def __init__(self, data):
        self.data = data

    async def __aiter__(self):
        yield self.data[:10]
        yield self.data[10:]


def response(data, *, status=200, headers=None):
    return httpx.Response(
        status, stream=Body(data),
        headers={"content-type": "application/json", **(headers or {})},
    )


@pytest.mark.parametrize("socket", ["", "relative.sock", "/run/" + "x" * 110])
async def test_unconfigured_or_invalid_socket_does_not_connect(monkeypatch, socket):
    monkeypatch.setenv("SOURCE_PROVIDER_SOCKET", socket)

    def unexpected(*args, **kwargs):
        raise AssertionError("No provider connection allowed")

    monkeypatch.setattr(provider.httpx, "AsyncHTTPTransport", unexpected)
    assert await provider.collect_source_rows(limit=20, require_dates=True) == []


def test_validated_rows_do_not_carry_generated_content():
    data = payload()
    data["bills"][0].update(official_text_verified=True, summary_long_el="untrusted content")
    rows = provider.validate_payload(data, limit=20, require_dates=True)
    assert rows[0]["law_id"] == LAW_ID
    assert rows[0]["date"] == "2026-10-23T00:00:00+00:00"
    assert "official_text_verified" not in rows[0]
    assert "summary_long_el" not in rows[0]


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("source", "OTHER"), ("source_status", "blocked"),
    ("captured_at", "not-a-date"), ("captured_at", "2026-01-01T00:00:00"),
    ("bills", []), ("bills", [{}]),
])
def test_invalid_envelopes_fail_closed(field, value):
    data = payload()
    data[field] = value
    with pytest.raises((ValueError, TypeError)):
        provider.validate_payload(data, limit=20, require_dates=True)


@pytest.mark.parametrize("minutes", [-16, 3])
def test_old_or_future_captures_are_rejected(minutes):
    data = payload()
    data["captured_at"] = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
    with pytest.raises(ValueError):
        provider.validate_payload(data, limit=20, require_dates=True)


@pytest.mark.parametrize("field,value", [
    ("law_id", ""), ("law_id", "00000000-0000-0000-0000-000000000000"),
    ("title_el", 1), ("title_el", "short"), ("ministry", {}),
    ("date", "2026-02-31"), ("date", True),
    ("url", f"https://example.org/Nomothetiko-Ergo/?law_id={LAW_ID}"),
    ("url", f"https://user:pass@www.hellenicparliament.gr/Nomothetiko-Ergo/?law_id={LAW_ID}"),
    ("url", f"https://www.hellenicparliament.gr:444/Nomothetiko-Ergo/?law_id={LAW_ID}"),
    ("url", f"http://www.hellenicparliament.gr/Nomothetiko-Ergo/?law_id={LAW_ID}"),
    ("url", f"https://www.hellenicparliament.gr/Nomothetiko-Ergo/?law_id={LAW_ID}&law_id={LAW_ID}"),
    ("url", f"https://www.hellenicparliament.gr/Nomothetiko-Ergo/?law_id={LAW_ID}#fragment"),
    ("url", "https://www.hellenicparliament.gr/Nomothetiko-Ergo/?law_id=726dad50-ab77-453c-9590-b4e4012a069e"),
])
def test_invalid_source_identity_date_or_link_is_rejected(field, value):
    data = payload()
    data["bills"][0][field] = value
    with pytest.raises((ValueError, TypeError)):
        provider.validate_payload(data, limit=20, require_dates=True)


def test_duplicate_source_identity_is_rejected():
    data = payload()
    data["bills"].append(copy.deepcopy(data["bills"][0]))
    with pytest.raises(ValueError):
        provider.validate_payload(data, limit=20, require_dates=True)


def test_strict_date_filter_runs_before_limit():
    data = payload()
    undated = copy.deepcopy(data["bills"][0])
    undated["law_id"] = "726dad50-ab77-453c-9590-b4e4012a069e"
    undated["url"] = undated["url"].replace(LAW_ID, undated["law_id"])
    undated["date"] = None
    data["bills"].insert(0, undated)
    assert provider.validate_payload(data, limit=1, require_dates=True)[0]["law_id"] == LAW_ID
    assert provider.validate_payload(data, limit=1, require_dates=False)[0]["date"] is None


@respx.mock
async def test_valid_provider_response_uses_bounded_local_contract(monkeypatch):
    monkeypatch.setenv("SOURCE_PROVIDER_SOCKET", SOCKET)
    route = respx.post("http://source-provider/v1/collect").mock(
        return_value=response(json.dumps(payload()).encode()),
    )
    rows = await provider.collect_source_rows(limit=20, require_dates=True)
    assert len(rows) == 1
    assert json.loads(route.calls.last.request.content) == {
        "source": "PARLIAMENT", "limit": 20, "require_dates": True,
    }
    assert route.calls.last.request.headers["accept-encoding"] == "identity"


@pytest.mark.parametrize("status", [302, 403, 429, 500])
@respx.mock
async def test_provider_failures_are_not_redirected_or_retried(monkeypatch, status):
    monkeypatch.setenv("SOURCE_PROVIDER_SOCKET", SOCKET)
    route = respx.post("http://source-provider/v1/collect").mock(
        return_value=response(b"{}", status=status, headers={"location": "https://example.org/"}),
    )
    assert await provider.collect_source_rows(limit=20, require_dates=True) == []
    assert route.call_count == 1


@pytest.mark.parametrize("body,headers", [
    (b"{}", {"content-encoding": "gzip"}),
    (b"{}", {"content-type": "text/html"}),
    (b"not json", {}),
], ids=["compressed", "wrong-content-type", "malformed-json"])
@respx.mock
async def test_bad_or_oversized_bodies_fail_closed(monkeypatch, body, headers):
    monkeypatch.setenv("SOURCE_PROVIDER_SOCKET", SOCKET)
    respx.post("http://source-provider/v1/collect").mock(return_value=response(body, headers=headers))
    assert await provider.collect_source_rows(limit=20, require_dates=True) == []


@respx.mock
async def test_oversized_valid_payload_is_rejected(monkeypatch):
    monkeypatch.setenv("SOURCE_PROVIDER_SOCKET", SOCKET)
    data = payload()
    data["padding"] = "x" * provider.MAX_RESPONSE_BYTES
    # Without the transport byte cap this otherwise valid envelope is accepted.
    assert provider.validate_payload(data, limit=20, require_dates=True)
    respx.post("http://source-provider/v1/collect").mock(
        return_value=response(json.dumps(data).encode()),
    )
    assert await provider.collect_source_rows(limit=20, require_dates=True) == []


async def test_ordinary_discovery_success_does_not_call_provider(monkeypatch):
    monkeypatch.setenv("SOURCE_PROVIDER_SOCKET", SOCKET)
    rows = payload()["bills"]
    monkeypatch.setattr(scraper, "_scrape_parliament_bills", AsyncMock(return_value=rows))
    collect = AsyncMock(side_effect=AssertionError("Ordinary path succeeded"))
    monkeypatch.setattr(provider, "collect_source_rows", collect)
    assert await scraper.scrape_parliament_bills() == rows
    collect.assert_not_awaited()


async def test_configured_provider_restores_dated_source_after_direct_failure(monkeypatch):
    monkeypatch.setenv("SOURCE_PROVIDER_SOCKET", SOCKET)

    async def blocked(limit, require_dates, errors):
        errors.extend(["source_blocked", "api_http_403_cooldown"])
        return []

    monkeypatch.setattr(scraper, "_scrape_parliament_bills", blocked)
    collect = AsyncMock(return_value=provider.validate_payload(payload(), limit=20, require_dates=True))
    monkeypatch.setattr(provider, "collect_source_rows", collect)
    result = await scraper.get_parliament_freshness_probe(limit=20)
    assert result["source_status"] == "ok" and result["dated_count"] == 1
    assert result["bills"][0]["law_id"] == LAW_ID
    assert result["bills"][0]["summary_short_el"].startswith("Η Βουλή δημοσίευσε εγγραφή για:")
    collect.assert_awaited_once_with(limit=20, require_dates=True)


async def test_explicit_robots_disallow_prevents_provider_requests(monkeypatch):
    monkeypatch.setenv("SOURCE_PROVIDER_SOCKET", SOCKET)

    async def forbidden(limit, require_dates, errors):
        errors.append("robots_disallowed")
        return []

    monkeypatch.setattr(scraper, "_scrape_parliament_bills", forbidden)
    collect = AsyncMock(side_effect=AssertionError("Robots excluded source"))
    monkeypatch.setattr(provider, "collect_source_rows", collect)
    record = AsyncMock()
    monkeypatch.setattr(source_freshness, "record_source_blocked", record)
    assert await scraper.scrape_parliament_bills() == []
    collect.assert_not_awaited()
    record.assert_awaited_once_with(force=True)


async def test_direct_block_does_not_mark_all_providers_unavailable(monkeypatch):
    monkeypatch.setattr(source_freshness, "_blocked_at", None)
    monkeypatch.setenv("SOURCE_PROVIDER_SOCKET", SOCKET)
    redis = AsyncMock()
    connect = AsyncMock(return_value=redis)
    monkeypatch.setattr(source_freshness.scraper_state, "_redis", connect)
    await source_freshness.record_source_blocked()
    connect.assert_not_awaited()
    await source_freshness.record_source_blocked(force=True)
    redis.set.assert_awaited_once()


@pytest.mark.parametrize("robots_status", [200, 503])
@respx.mock
async def test_actual_policy_distinguishes_exclusion_from_unavailable_transport(monkeypatch, scraper_clock, robots_status):
    monkeypatch.setenv("SOURCE_PROVIDER_SOCKET", SOCKET)
    monkeypatch.setattr(policy, "robots", {})
    monkeypatch.setattr(policy, "responses", {})
    respx.get(scraper.PARLIAMENT_BASE + "/robots.txt").respond(
        robots_status, text="User-agent: *\nDisallow: /",
    )
    collect = AsyncMock(return_value=provider.validate_payload(payload(), limit=20, require_dates=True))
    monkeypatch.setattr(provider, "collect_source_rows", collect)
    monkeypatch.setattr(source_freshness, "record_source_blocked", AsyncMock())
    errors = []
    rows = await scraper.scrape_parliament_bills(require_dates=True, probe_errors=errors)
    if robots_status == 200:
        assert not rows and "robots_disallowed" in errors
        collect.assert_not_awaited()
    else:
        assert rows and "robots_unavailable" in errors
        collect.assert_awaited_once()
    assert len(respx.calls) == 1  # neither case permits ordinary content access


@pytest.mark.parametrize("existing", [False, True, "legacy-law-number"])
async def test_provider_metadata_uses_existing_scheduled_upsert_without_duplicates(monkeypatch, existing):
    import ast
    import logging
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    from models import ParliamentBill, BillStatus
    from services import scraper_state, representation_cache, telegram_community, bill_lifecycle

    monkeypatch.setenv("SOURCE_PROVIDER_SOCKET", SOCKET)
    monkeypatch.setattr(scraper, "_scrape_parliament_bills", AsyncMock(return_value=[]))
    monkeypatch.setattr(provider, "collect_source_rows", AsyncMock(
        return_value=provider.validate_payload(payload(), limit=20, require_dates=True),
    ))
    events = []
    rows = {}
    bid = "GR-5422-2026" if existing == "legacy-law-number" else "GR-" + LAW_ID[:8]
    if existing:
        rows[bid] = ParliamentBill(id=bid, title_el="Προηγούμενος τίτλος νομοσχεδίου",
                                   source="PARLIAMENT", status=BillStatus.ACTIVE,
                                   parliament_url=f"https://www.hellenicparliament.gr/Nomothetiko-Ergo/Anazitisi-Nomothetikon-Ergon?law_id={LAW_ID}",
                                   summary_short_el="Manually reviewed summary")
        original = rows[bid]

    class DB:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, statement):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: list(rows.values())))

        def add(self, row):
            assert row.id not in rows
            rows[row.id] = row

    async def commit(db):
        events.append("commit")

    async def success(name):
        events.append("success")

    monkeypatch.setitem(sys.modules, "database", SimpleNamespace(AsyncSessionLocal=DB))
    monkeypatch.setattr(scraper_state, "is_circuit_open", AsyncMock(return_value=False))
    monkeypatch.setattr(scraper_state, "record_run", AsyncMock())
    monkeypatch.setattr(scraper_state, "record_success", success)
    failure = AsyncMock()
    monkeypatch.setattr(scraper_state, "record_failure", failure)
    monkeypatch.setattr(representation_cache, "commit_and_invalidate_representation", commit)
    monkeypatch.setattr(telegram_community, "notify_announced", AsyncMock())
    monkeypatch.setattr(bill_lifecycle, "run_bill_lifecycle", AsyncMock(return_value={}))
    path = Path(__file__).resolve().parents[2] / "main.py"
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "scheduled_scrape")
    namespace = {"logger": logging.getLogger("test.provider-ingestion")}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)

    await namespace["scheduled_scrape"]()
    await namespace["scheduled_scrape"]()

    assert list(rows) == [bid]
    assert rows[bid].parliament_url == payload()["bills"][0]["url"]
    assert rows[bid].parliament_vote_date.isoformat() == "2026-10-23T00:00:00"
    assert events.index("commit") < events.index("success")
    assert events.count("success") == 2
    failure.assert_not_awaited()
    if existing:
        assert rows[bid] is original
        assert rows[bid].status == BillStatus.ACTIVE
        assert rows[bid].summary_short_el == "Manually reviewed summary"
