import asyncio
import json
from email.utils import formatdate

import httpx
import pytest
import respx

from services.scraper_http import HostCooldown, HostRateLimiter, MAX_RETRY_AFTER, SCRAPER_HTTP_HOOKS

pytestmark = pytest.mark.usefixtures("scraper_clock")


async def test_concurrent_requests_share_host_spacing(scraper_clock):
    times = []

    async def attempt(path):
        await scraper_clock.limiter.acquire(f"https://example.org/{path}")
        times.append(scraper_clock.now)

    await asyncio.gather(*(attempt(path) for path in ("a", "b", "c")))
    assert times == [1000, 1005, 1010]
    await scraper_clock.limiter.acquire("https://other.org/")
    assert scraper_clock.sleeps == [5, 5]


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("http_date", [False, True])
async def test_retry_after_seconds_and_http_date(scraper_clock, status, http_date):
    limiter = scraper_clock.limiter
    await limiter.acquire("https://example.org/a")
    value = formatdate(scraper_clock.time() + 30, usegmt=True) if http_date else "30"
    limiter.observe("https://example.org/a", status, {"retry-after": value})
    await limiter.acquire("https://example.org/b")
    assert scraper_clock.now == 1030


@pytest.mark.parametrize("value", ["", "nonsense", "-10", "inf", "nan", "1e999", "Wed, 99 Jan 2026", "Tue, 14 Nov 2023 22:30:00", None])
async def test_invalid_retry_after_keeps_minimum_spacing(scraper_clock, value):
    limiter = scraper_clock.limiter
    await limiter.acquire("https://example.org/")
    limiter.observe("https://example.org/", 503, {"retry-after": value})
    await limiter.acquire("https://example.org/")
    assert scraper_clock.now == 1005


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("value", ["901", "86400", "1e100"])
async def test_retry_after_seconds_are_capped(scraper_clock, status, value):
    limiter = scraper_clock.limiter
    limiter.observe("https://example.org/", status, {"retry-after": value})
    await limiter.acquire("https://example.org/")
    assert scraper_clock.now == 1000 + MAX_RETRY_AFTER


@pytest.mark.parametrize("offset,expected_delay", [(-60, 5), (900, 900), (901, 5), (10 * 365 * 86400, 5)])
async def test_retry_after_dates_ignore_past_and_far_future(scraper_clock, offset, expected_delay):
    limiter = scraper_clock.limiter
    await limiter.acquire("https://example.org/")
    limiter.observe("https://example.org/", 503, {
        "retry-after": formatdate(scraper_clock.time() + offset, usegmt=True),
    })
    await limiter.acquire("https://example.org/")
    assert scraper_clock.now == 1000 + expected_delay


async def test_forbidden_cooldown_expires_and_does_not_block_other_hosts(scraper_clock):
    limiter = scraper_clock.limiter
    await limiter.record("https://example.org/a", 403, {})
    for url in ("https://example.org/b", "http://EXAMPLE.org/a"):
        with pytest.raises(HostCooldown):
            await limiter.acquire(url)
    assert scraper_clock.sleeps == []
    await limiter.acquire("https://other.org/")
    scraper_clock.now += 6 * 3600
    await limiter.acquire("https://example.org/b")


@respx.mock
async def test_http_redirect_attempts_are_paced(scraper_clock):
    times = []

    def respond(request):
        times.append(scraper_clock.now)
        return httpx.Response(302, headers={"location": "/final"}) if request.url.path == "/start" else httpx.Response(200)

    respx.get("https://example.org/start").mock(side_effect=respond)
    respx.get("https://example.org/final").mock(side_effect=respond)
    async with httpx.AsyncClient(follow_redirects=True, event_hooks=SCRAPER_HTTP_HOOKS) as client:
        await client.get("https://example.org/start")
    assert times == [1000, 1005]


@respx.mock
async def test_source_cooldown_cannot_be_bypassed_via_jina(scraper_clock):
    await scraper_clock.limiter.record("https://www.hellenicparliament.gr/", 403, {})
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown):
            await client.get("https://r.jina.ai/https://www.hellenicparliament.gr/law?private=value")
    assert len(respx.calls) == 0


@pytest.mark.parametrize("target", [
    "https://www.hellenicparliament.gr/law",
    "https://r.jina.ai/https://www.hellenicparliament.gr/law",
    "http://ollama:11434/api/generate",
    "https://redirect.example.org/final",
])
@respx.mock
async def test_source_cooldown_is_rechecked_after_queue(scraper_clock, monkeypatch, target):
    from services import scraper_http, parliament_access
    from unittest.mock import AsyncMock
    # This test isolates cooldown ordering; robots behavior has dedicated coverage.
    monkeypatch.setattr(parliament_access, "check_robots", AsyncMock())

    source = "https://www.hellenicparliament.gr/law"
    limiter = scraper_clock.limiter
    await limiter.acquire(target)
    original_sleep = scraper_http.asyncio.sleep

    async def forbidden_while_queued(delay):
        await limiter.record(source, 403, {})
        await original_sleep(delay)

    monkeypatch.setattr(scraper_http.asyncio, "sleep", forbidden_while_queued)
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown):
            await client.get(target, extensions={"scraper_source_url": source})
    assert len(respx.calls) == 0


@respx.mock
async def test_jina_source_is_rechecked_after_queue_without_extensions(scraper_clock, monkeypatch):
    from services import scraper_http

    target = "https://r.jina.ai/https://www.hellenicparliament.gr/law"
    await scraper_clock.limiter.acquire(target)
    original_sleep = scraper_http.asyncio.sleep

    async def forbidden_while_queued(delay):
        await scraper_clock.limiter.record("https://www.hellenicparliament.gr/", 403, {})
        await original_sleep(delay)

    monkeypatch.setattr(scraper_http.asyncio, "sleep", forbidden_while_queued)
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown):
            await client.get(target)
    assert len(respx.calls) == 0


@respx.mock
async def test_cross_host_redirect_retains_source_cooldown(scraper_clock, monkeypatch):
    from services import scraper_http

    source = "https://source.example.org/start"
    target = "https://target.example.org/final"
    redirect = respx.get(source).respond(302, headers={"location": target})
    final = respx.get(target).respond(200)
    await scraper_clock.limiter.acquire(target)
    original_sleep = scraper_http.asyncio.sleep

    async def forbidden_while_queued(delay):
        await scraper_clock.limiter.record(source, 403, {})
        await original_sleep(delay)

    monkeypatch.setattr(scraper_http.asyncio, "sleep", forbidden_while_queued)
    async with httpx.AsyncClient(follow_redirects=True, event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown):
            await client.get(source)
    assert redirect.call_count == 1 and final.call_count == 0


@respx.mock
async def test_cooldown_survives_restart_and_stores_only_host_metadata(scraper_clock, scraper_redis, monkeypatch):
    from services import scraper_http

    url = "https://example.org/private?token=secret"
    blocked = respx.get(url).respond(403, text="private response content")
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        assert (await client.get(url)).status_code == 403
    key = "scraper:host:example.org:cooldown"
    record = json.loads(scraper_redis.values[key])
    assert record == {"started_at": scraper_clock.time(), "cooldown_until": scraper_clock.time() + 6 * 3600,
                      "reason": "http_403", "consecutive_403": 1}
    assert scraper_redis.expiry[key] - scraper_clock.time() == 6 * 3600
    assert "secret" not in str(scraper_redis.values) and "private" not in str(scraper_redis.values)

    # A new limiter and HTTP client share only Redis, with a reset monotonic clock.
    restarted = HostRateLimiter()
    monkeypatch.setattr(scraper_http, "host_limiter", restarted)
    monkeypatch.setattr(scraper_clock, "monotonic", lambda: -123.0)
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown):
            await client.get(url)
    assert blocked.call_count == 1
    assert await restarted.status(url) == {"cooldown_until": record["cooldown_until"], "consecutive_403": 1}


async def test_backoff_survives_expiry_and_restart_then_resets_on_success(scraper_clock, scraper_redis):
    url = "https://example.org/"
    limiter = HostRateLimiter()
    for count, hours in enumerate((6, 12, 24, 48, 48), start=1):
        await limiter.acquire(url)
        await limiter.record(url, 403, {})
        status = await limiter.status(url)
        assert status == {"cooldown_until": scraper_clock.time() + hours * 3600, "consecutive_403": count}
        scraper_clock.now += hours * 3600
        assert await scraper_redis.get("scraper:host:example.org:cooldown") is None
        limiter = HostRateLimiter()
    await limiter.acquire(url)
    await limiter.record(url, 200, {})
    assert await HostRateLimiter().status(url) == {"cooldown_until": None, "consecutive_403": 0}
    assert not any(k.endswith((":cooldown", ":streak", ":lease")) for k in scraper_redis.values)
    await limiter.record(url, 403, {})
    assert (await limiter.status(url))["cooldown_until"] == scraper_clock.time() + 6 * 3600


@pytest.mark.parametrize("known", [False, True])
@respx.mock
async def test_redis_outage_fails_closed_even_for_unknown_hosts(scraper_clock, scraper_redis, known):
    url = "https://example.org/"
    if known:
        await scraper_clock.limiter.record(url, 403, {})
        scraper_clock.now += 6 * 3600
    scraper_redis.down = True
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown, match="state unavailable"):
            await client.get(url)
    assert len(respx.calls) == 0


@respx.mock
async def test_failed_outcome_defers_without_pending_local_increments(scraper_clock, scraper_redis):
    from services.scraper_http import HOST_LEASE_MS

    url = "https://example.org/"
    scraper_redis.write_down = True
    blocked = respx.get(url).respond(403)
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown, match="state unavailable"):
            await client.get(url)
        assert await scraper_clock.limiter.status(url) == {"cooldown_until": None, "consecutive_403": 0}
        # Keep the lease after an unacknowledged outcome, including on recovery.
        with pytest.raises(HostCooldown, match="lease busy"):
            await client.get(url)
        scraper_redis.write_down = False
        with pytest.raises(HostCooldown, match="lease busy"):
            await client.get(url)
        assert blocked.call_count == 1
        scraper_clock.now += HOST_LEASE_MS / 1000
        assert (await client.get(url)).status_code == 403
    assert (await HostRateLimiter().status(url))["consecutive_403"] == 1


@pytest.mark.parametrize("raw", ["not JSON", "{}", '[]', '{"reason":"private?secret"}'])
@respx.mock
async def test_invalid_persisted_state_fails_closed(scraper_redis, raw):
    scraper_redis.values["scraper:host:example.org:streak"] = raw
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown, match="state unavailable"):
            await client.get("https://example.org/")
    assert len(respx.calls) == 0


async def test_reset_uses_persisted_count_and_fences_old_generation(scraper_clock, scraper_redis):
    from services.scraper_http import HOST_LEASE_MS

    url = "https://example.org/"
    first, second = HostRateLimiter(), HostRateLimiter()
    # Both workers saw an expired streak of three.
    scraper_redis.values["scraper:host:example.org:streak"] = "3"
    await first.check_persisted(url)
    await second.check_persisted(url)
    assert first._state(url).consecutive_403 == second._state(url).consecutive_403 == 3
    stale = (await second.reserve(url))[0]
    scraper_clock.now += HOST_LEASE_MS / 1000
    await first.record(url, 200, {})
    # A delayed response from the previous lease cannot resurrect that streak.
    with pytest.raises(HostCooldown):
        await second.record(url, 403, {}, lease=stale)
    assert await first.status(url) == {"cooldown_until": None, "consecutive_403": 0}
    # A new response uses persisted zero, even with stale local display evidence.
    await second.record(url, 403, {})
    assert await first.status(url) == {
        "cooldown_until": scraper_clock.time() + 6 * 3600, "consecutive_403": 1,
    }


@respx.mock
async def test_parliament_block_is_counted_once_and_robots_success_preserves_streak(scraper_clock, monkeypatch):
    from services import parliament_access, source_freshness
    from unittest.mock import AsyncMock

    base = "https://www.hellenicparliament.gr"
    monkeypatch.setattr(parliament_access, "robots", {})
    monkeypatch.setattr(parliament_access, "responses", {})
    monkeypatch.setattr(source_freshness, "record_source_blocked", AsyncMock())
    respx.get(base + "/robots.txt").respond(200, text="User-agent: *\nDisallow:")
    denied = respx.get(base + "/law").respond(403)
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown):
            await client.get(base + "/law")
        assert (await scraper_clock.limiter.status(base))["consecutive_403"] == 1
        scraper_clock.now += 6 * 3600
        monkeypatch.setattr(parliament_access, "robots", {})
        with pytest.raises(HostCooldown):
            await client.get(base + "/law")
    assert denied.call_count == 2
    assert (await scraper_clock.limiter.status(base))["consecutive_403"] == 2


@respx.mock
async def test_403_response_is_observed_before_queued_request_leaves(scraper_clock, monkeypatch):
    from services import scraper_http

    url = "https://example.org/"
    await scraper_clock.limiter.acquire(url)
    original_sleep = scraper_http.asyncio.sleep

    async def response_while_queued(delay):
        await HostRateLimiter().record(url, 403, {})
        await original_sleep(delay)

    monkeypatch.setattr(scraper_http.asyncio, "sleep", response_while_queued)
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown):
            await client.get(url)
    assert len(respx.calls) == 0
    assert (await scraper_clock.limiter.status(url))["consecutive_403"] == 1


def worker_hooks(limiter):
    from functools import partial
    from services.scraper_http import pace_request, record_response
    return {"request": [partial(pace_request, limiter=limiter)],
            "response": [partial(record_response, limiter=limiter)]}


@respx.mock
async def test_two_workers_403_between_admission_and_dispatch_does_not_send(scraper_clock, monkeypatch):
    url = "https://example.org/private?token=secret"
    first, second = HostRateLimiter(min_interval=0), HostRateLimiter(min_interval=0)
    in_flight, admission, persist = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def forbidden(request):
        in_flight.set()
        await persist.wait()
        return httpx.Response(403)

    route = respx.get(url).mock(side_effect=forbidden)
    original_acquire = second.acquire

    async def pause_after_admission(target):
        await original_acquire(target)
        admission.set()
        await persist.wait()

    monkeypatch.setattr(second, "acquire", pause_after_admission)
    async with httpx.AsyncClient(event_hooks=worker_hooks(first)) as a, httpx.AsyncClient(event_hooks=worker_hooks(second)) as b:
        first_request = asyncio.create_task(a.get(url))
        await in_flight.wait()
        second_request = asyncio.create_task(b.get(url))
        await admission.wait()
        persist.set()
        assert (await first_request).status_code == 403
        with pytest.raises(HostCooldown):
            await second_request
    assert route.call_count == 1
    assert (await second.status(url))["consecutive_403"] == 1


@respx.mock
async def test_final_admission_lease_excludes_another_worker_until_persistence(scraper_clock, monkeypatch, scraper_redis):
    url = "https://example.org/"
    first, second = HostRateLimiter(min_interval=0), HostRateLimiter(min_interval=0)
    admitted, dispatch, persisting, commit = (asyncio.Event() for _ in range(4))
    original_admission = first._admission
    original_record = first.record

    async def pause_before_send(target, token=""):
        await original_admission(target, token)
        if token:
            admitted.set()
            await dispatch.wait()

    async def pause_persistence(*args, **kwargs):
        persisting.set()
        await commit.wait()
        await original_record(*args, **kwargs)

    monkeypatch.setattr(first, "_admission", pause_before_send)
    monkeypatch.setattr(first, "record", pause_persistence)
    route = respx.get(url).respond(403)
    async with httpx.AsyncClient(event_hooks=worker_hooks(first)) as a, httpx.AsyncClient(event_hooks=worker_hooks(second)) as b:
        request = asyncio.create_task(a.get(url))
        await admitted.wait()
        with pytest.raises(HostCooldown, match="lease busy"):
            await b.get(url)
        assert route.call_count == 0
        dispatch.set()
        await persisting.wait()
        with pytest.raises(HostCooldown, match="lease busy"):
            await b.get(url)
        assert route.call_count == 1
        commit.set()
        assert (await request).status_code == 403
        with pytest.raises(HostCooldown):
            await b.get(url)
    assert route.call_count == 1 and scraper_clock.sleeps == []
    assert await scraper_redis.get("scraper:host:example.org:lease") is None


@pytest.mark.parametrize("offset", [61, -61, 10 * 365 * 86400, -10 * 365 * 86400])
@respx.mock
async def test_admission_uses_server_ttl_with_independent_worker_clock(scraper_clock, scraper_redis, monkeypatch, offset):
    server = [1_800_000_000.0]
    scraper_redis.server_time = lambda: server[0]
    monkeypatch.setattr(scraper_clock, "time", lambda: server[0] + offset)
    url = "https://example.org/"
    first = HostRateLimiter(forbidden_cooldown=60)
    await first.record(url, 403, {})
    second = HostRateLimiter(min_interval=0)
    assert await second.status(url) == {"cooldown_until": server[0] + 60, "consecutive_403": 1}
    route = respx.get(url).respond(403)
    async with httpx.AsyncClient(event_hooks=worker_hooks(second)) as client:
        with pytest.raises(HostCooldown):
            await client.get(url)
        server[0] += 59.999
        with pytest.raises(HostCooldown):
            await client.get(url)
        server[0] += .001
        assert (await client.get(url)).status_code == 403
    assert route.call_count == 1
    assert (await second.status(url))["cooldown_until"] == server[0] + 12 * 3600


@respx.mock
async def test_lost_commit_ack_and_replayed_response_increment_once(scraper_clock, scraper_redis):
    from services.scraper_http import record_response
    url = "https://example.org/"
    scraper_redis.lose_ack = 1
    route = respx.get(url).respond(403)
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        response = await client.get(url)
        await record_response(response)
        with pytest.raises(HostCooldown):
            await client.get(url)
    assert scraper_redis.lose_ack == 0 and route.call_count == 1
    assert await HostRateLimiter().status(url) == {
        "cooldown_until": scraper_clock.time() + 6 * 3600, "consecutive_403": 1,
    }


async def test_stale_release_and_success_cannot_mutate_new_lease(scraper_clock, scraper_redis):
    from services.scraper_http import HOST_LEASE_MS
    url = "https://example.org/"
    first, second = HostRateLimiter(), HostRateLimiter()
    old = await first.reserve(url)
    scraper_clock.now += HOST_LEASE_MS / 1000
    current = await second.reserve(url)
    await first.release(old)
    assert await scraper_redis.get("scraper:host:example.org:lease") == current[0].token
    await second.record(url, 403, {}, lease=current[0])
    with pytest.raises(HostCooldown):
        await first.record(url, 200, {}, lease=old[0])
    assert (await second.status(url))["consecutive_403"] == 1
    await second.release(current)


@respx.mock
async def test_source_lease_and_target_lease_are_both_held(scraper_clock):
    source, target = "https://z-source.example.org/", "https://a-target.example.org/"
    first, second = HostRateLimiter(), HostRateLimiter()
    leases = await first.reserve(source)
    route = respx.get(target).respond(200)
    async with httpx.AsyncClient(event_hooks=worker_hooks(second)) as client:
        with pytest.raises(HostCooldown, match="lease busy"):
            await client.get(target, extensions={"scraper_source_url": source})
        # A partially acquired lease set must be released on deferral.
        await first.release(leases)
        assert (await client.get(target, extensions={"scraper_source_url": source})).status_code == 200
    assert route.call_count == 1


@respx.mock
async def test_redis_failure_acquiring_lease_defers_and_logs_counts_only(scraper_clock, scraper_redis, caplog):
    import logging
    caplog.set_level(logging.INFO)
    scraper_redis.set_down = True
    async with httpx.AsyncClient(event_hooks=SCRAPER_HTTP_HOOKS) as client:
        with pytest.raises(HostCooldown, match="state unavailable"):
            await client.get("https://example.org/private?token=secret")
    assert len(respx.calls) == 0 and scraper_clock.sleeps == []
    assert "deferred=1" in caplog.text
    assert all(value not in caplog.text for value in ("example.org", "private", "secret", "Redis unavailable"))
