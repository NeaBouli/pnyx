"""T-9071: latest-outcome metadata + honest unknown in public scraper status readers.

Exercises the real producer (record_success/record_failure), the real
get_all_states pipeline and the actual /api/v1/scraper/jobs and
/api/v1/health/modules routes against one shared in-memory Redis fake.
No network, no real Redis, no provider probes (Ollama/DeepL mocked).
ASGITransport does not run the app lifespan, so scheduler startup is not covered.
"""
import asyncio

import pytest
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient

import main
from services import ollama_service, scraper_state

SCRAPER_MODS = {"MOD-03": "parliament", "MOD-21": "diavgeia_municipal", "MOD-24": "forum_sync"}
RAW = "CheckViolation ADA-XYZ postgres://u:p@h/db user@example.test"


class FakePipe:
    def __init__(self, store):
        self.store, self.ops = store, []

    def set(self, k, v, ex=None):
        self.ops.append(("set", k, str(v)))

    def incr(self, k):
        self.ops.append(("incr", k, None))

    def delete(self, k):
        self.ops.append(("del", k, None))

    def get(self, k):
        self.ops.append(("get", k, None))

    async def execute(self):
        out = []
        for op, k, v in self.ops:
            if op == "set":
                self.store[k] = v
                out.append(True)
            elif op == "incr":
                self.store[k] = str(int(self.store.get(k, 0)) + 1)
                out.append(int(self.store[k]))
            elif op == "get":
                out.append(self.store.get(k))
            else:
                self.store.pop(k, None)
                out.append(1)
        return out


class FakeRedis:
    def __init__(self, store, down=False):
        self.store, self.down, self.writes = store, down, 0

    def pipeline(self):
        if self.down:
            raise ConnectionError("redis down")
        return FakePipe(self.store)

    async def get(self, k):
        if self.down:
            raise ConnectionError("redis down")
        return self.store.get(k)

    async def set(self, k, v, ex=None):
        self.writes += 1
        self.store[k] = str(v)

    async def aclose(self):
        pass


@pytest.fixture
def env(monkeypatch):
    store, state = {}, {"down": False}

    def _client(*a, **k):
        return FakeRedis(store, state["down"])

    async def _r():
        return _client()

    async def _true():
        return True

    monkeypatch.setattr(scraper_state, "_redis", _r)
    monkeypatch.setattr(aioredis, "from_url", _client)
    monkeypatch.setattr(ollama_service, "ollama_available", _true)
    monkeypatch.setattr(ollama_service, "deepl_available", _true)
    monkeypatch.delenv("GREEK_SCRAPER_ENABLED", raising=False)
    return store, state


async def _get(path):
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
        r = await c.get(path)
    assert r.status_code == 200
    return r.json()


def _job(body, name):
    return next(s for s in body["scrapers"] if s["name"] == name)


async def _all_clean():
    for n in SCRAPER_MODS.values():
        await scraper_state.record_success(n)


async def test_degraded_producer_flows_to_jobs_and_mod21(env):
    store, _ = env
    await _all_clean()
    await scraper_state.record_success("diavgeia_municipal", "degraded", "scrape_errors", 2)
    snapshot = dict(store)

    job = _job(await _get("/api/v1/scraper/jobs"), "diavgeia_municipal")
    assert job["error_count"] == 0 and job["status"] == "warning"
    assert job["last_outcome"] == "degraded" and job["last_outcome_reason"] == "scrape_errors"
    assert job["last_outcome_count"] == 2
    assert job["last_outcome_time"].endswith("+00:00") and job["last_nonclean_time"]

    health = await _get("/api/v1/health/modules")
    mod = health["modules"]["MOD-21"]
    assert mod["status"] == "degraded" and mod["last_outcome_reason"] == "scrape_errors"
    assert health["overall"] == "degraded"
    assert store == snapshot  # readers never write


async def test_clean_is_ok_and_overall_ok(env):
    await _all_clean()
    job = _job(await _get("/api/v1/scraper/jobs"), "parliament")
    assert job["status"] == "ok" and job["last_outcome"] == "clean"
    assert job["last_nonclean_time"] is None
    health = await _get("/api/v1/health/modules")
    assert all(health["modules"][m]["status"] == "ok" for m in SCRAPER_MODS)
    assert health["modules"]["MOD-23"]["status"] == "disabled"
    assert health["overall"] == "ok"


async def test_failed_outcome_no_raw_leak_in_new_fields(env):
    store, _ = env
    await _all_clean()
    await scraper_state.record_failure("parliament", RAW)
    job = _job(await _get("/api/v1/scraper/jobs"), "parliament")
    assert job["status"] == "warning" and job["last_outcome"] == "failed"
    assert job["last_outcome_reason"] == "exception"
    new = {k: v for k, v in job.items() if k.startswith("last_outcome") or k == "last_nonclean_time"}
    assert "ADA-XYZ" not in str(new) and "postgres" not in str(new)
    assert job["last_error"] == RAW  # legacy field preserved, not extended
    mod = (await _get("/api/v1/health/modules"))["modules"]["MOD-03"]
    assert mod["status"] == "degraded" and mod["last_outcome"] == "failed"


async def test_failed_outcome_with_zero_count_still_degraded(env):
    store, _ = env
    await _all_clean()
    store["scraper:forum_sync:last_outcome"] = "failed"
    store["scraper:forum_sync:last_outcome_reason"] = "exception"
    assert _job(await _get("/api/v1/scraper/jobs"), "forum_sync")["status"] == "warning"
    mod = (await _get("/api/v1/health/modules"))["modules"]["MOD-24"]
    assert mod["status"] == "degraded" and mod["error_count"] == 0 and "error" not in mod


async def test_missing_telemetry_is_unknown_not_ok(env):
    store, _ = env
    store["scraper:parliament:last_success"] = "2026-10-10T10:00:00+00:00"  # not clean evidence
    store["scraper:parliament:error_count"] = "0"
    job = _job(await _get("/api/v1/scraper/jobs"), "parliament")
    assert job["status"] == "unknown" and job["last_outcome"] == "unknown"
    assert job["last_outcome_count"] is None and job["last_outcome_time"] is None
    health = await _get("/api/v1/health/modules")
    assert health["modules"]["MOD-03"]["status"] == "unknown"
    assert health["modules"]["MOD-23"]["status"] == "disabled"
    assert health["overall"] == "unknown"


async def test_redis_down_is_unknown(env):
    _, state = env
    state["down"] = True
    health = await _get("/api/v1/health/modules")
    for m in SCRAPER_MODS:
        assert health["modules"][m] == {"name": health["modules"][m]["name"], "status": "unknown"}
    assert health["overall"] == "unknown"
    body = await _get("/api/v1/scraper/jobs")
    assert all(s["status"] == "unknown" for s in body["scrapers"])


async def test_malformed_fields_rejected_not_echoed(env):
    store, _ = env
    await _all_clean()
    p = "scraper:parliament:"
    store[p + "last_outcome"] = "clean<script>"
    store[p + "last_outcome_reason"] = RAW
    store[p + "last_outcome_count"] = "99999999"
    store[p + "last_outcome_time"] = RAW
    store[p + "last_nonclean_time"] = "2026-10-10T10:00:00"  # naive -> rejected
    job = _job(await _get("/api/v1/scraper/jobs"), "parliament")
    assert job["last_outcome"] == "unknown" and job["last_outcome_reason"] == "unknown"
    assert job["last_outcome_count"] == 10_000
    assert job["last_outcome_time"] is None and job["last_nonclean_time"] is None
    assert job["status"] == "unknown"
    assert RAW not in str(await _get("/api/v1/health/modules"))

    store[p + "last_outcome"] = b"clean"
    store[p + "last_outcome_count"] = "-7"
    store[p + "last_outcome_time"] = "2026-10-10T12:00:00+02:00"
    job = _job(await _get("/api/v1/scraper/jobs"), "parliament")
    assert job["last_outcome"] == "unknown" and job["last_outcome_count"] == 0
    assert job["last_outcome_time"] == "2026-10-10T10:00:00+00:00"


async def test_malformed_error_count_is_unknown_not_crash(env):
    store, _ = env
    await _all_clean()
    store["scraper:parliament:error_count"] = "abc"
    body = await _get("/api/v1/scraper/jobs")
    job = _job(body, "parliament")
    assert job["status"] == "unknown" and job["error_count"] == 0
    assert _job(body, "forum_sync")["status"] == "ok"  # other jobs unaffected
    assert (await _get("/api/v1/health/modules"))["modules"]["MOD-03"]["status"] == "unknown"


@pytest.mark.parametrize("raw", ["--1", "\u00b2", "1\u00b2", "\u0663", "9" * 13, "9" * 400])
async def test_non_ascii_or_oversized_counts_are_unknown_not_500(env, raw):
    store, _ = env
    await _all_clean()
    store["scraper:parliament:error_count"] = raw
    store["scraper:parliament:last_outcome_count"] = raw
    job = _job(await _get("/api/v1/scraper/jobs"), "parliament")
    assert job["status"] == "unknown" and job["last_outcome_count"] is None
    assert raw not in str(job)
    mod = (await _get("/api/v1/health/modules"))["modules"]["MOD-03"]
    assert mod["status"] == "unknown" and raw not in str(mod)


async def test_negative_legacy_count_clamped_consistently(env):
    store, _ = env
    await _all_clean()
    store["scraper:parliament:error_count"] = "-5"
    assert _job(await _get("/api/v1/scraper/jobs"), "parliament")["status"] == "ok"
    assert (await _get("/api/v1/health/modules"))["modules"]["MOD-03"]["status"] == "ok"


async def test_timezone_overflow_time_is_none_not_500(env):
    store, _ = env
    await _all_clean()
    p = "scraper:parliament:"
    store[p + "last_outcome_time"] = "9999-12-31T23:59:59-12:00"
    store[p + "last_nonclean_time"] = "0001-01-01T00:00:00+12:00"
    job = _job(await _get("/api/v1/scraper/jobs"), "parliament")
    assert job["last_outcome_time"] is None and job["last_nonclean_time"] is None
    mod = (await _get("/api/v1/health/modules"))["modules"]["MOD-03"]
    assert mod["last_outcome_time"] is None


async def test_legacy_counts_and_circuit_precedence(env):
    store, _ = env
    await _all_clean()
    store["scraper:parliament:error_count"] = "1"  # outcome says clean, legacy count wins
    store["scraper:forum_sync:error_count"] = "3"
    body = await _get("/api/v1/scraper/jobs")
    assert _job(body, "parliament")["status"] == "warning"
    assert _job(body, "forum_sync")["status"] == "circuit_open"
    health = await _get("/api/v1/health/modules")
    assert health["modules"]["MOD-03"]["status"] == "degraded"
    assert health["modules"]["MOD-24"]["status"] == "error"
    assert health["overall"] == "error"
    # legacy counts without outcome keys keep warning/circuit, not unknown
    del store["scraper:forum_sync:last_outcome"]
    assert _job(await _get("/api/v1/scraper/jobs"), "forum_sync")["status"] == "circuit_open"


async def test_greek_enabled_uses_reader_disabled_excluded(env, monkeypatch):
    await _all_clean()
    assert (await _get("/api/v1/health/modules"))["overall"] == "ok"
    monkeypatch.setenv("GREEK_SCRAPER_ENABLED", "true")
    health = await _get("/api/v1/health/modules")
    assert health["modules"]["MOD-23"]["status"] == "unknown"
    assert health["overall"] == "unknown"
