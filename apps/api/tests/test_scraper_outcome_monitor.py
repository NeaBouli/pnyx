"""T-9069: latest scraper outcome visible in Redis job state and monitor."""
import asyncio
import os
import sys
import types

sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *a, **k: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import scraper_state  # noqa: E402

_saved_redis = sys.modules.get("redis")
sys.modules["redis"] = types.SimpleNamespace(from_url=lambda *a, **k: None)
import monitor  # noqa: E402
if _saved_redis is not None:
    sys.modules["redis"] = _saved_redis


class FakePipe:
    def __init__(self, store):
        self.store, self.ops = store, []

    def set(self, k, v, ex=None):
        self.ops.append(("set", k, str(v)))

    def incr(self, k):
        self.ops.append(("incr", k, None))

    def delete(self, k):
        self.ops.append(("del", k, None))

    async def execute(self):
        out = []
        for op, k, v in self.ops:
            if op == "set":
                self.store[k] = v
                out.append(True)
            elif op == "incr":
                self.store[k] = str(int(self.store.get(k, 0)) + 1)
                out.append(int(self.store[k]))
            else:
                self.store.pop(k, None)
                out.append(1)
        return out


class FakeAsyncRedis:
    def __init__(self, store):
        self.store, self.closed = store, False

    def pipeline(self):
        return FakePipe(self.store)

    async def set(self, k, v, ex=None):
        self.store[k] = str(v)

    async def get(self, k):
        return self.store.get(k)

    async def aclose(self):
        self.closed = True


class SyncView:
    def __init__(self, store):
        self.store = store

    def get(self, k):
        return self.store.get(k)


def _patch(monkeypatch, store):
    async def _r():
        return FakeAsyncRedis(store)
    monkeypatch.setattr(scraper_state, "_redis", _r)


def _outcome_alerts(store):
    return [a for a in monitor.check_scraper_jobs(SyncView(store)) if a.type == "scraper_job_outcome"]


def test_degraded_check_violation_visible_then_clean_clears(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    raw = "CheckViolation ADA-XYZ token=abc user@example.test"
    asyncio.run(scraper_state.record_success("diavgeia_municipal"))
    asyncio.run(scraper_state.record_outcome("diavgeia_municipal", "degraded", "scrape_errors", 2))
    assert store["scraper:diavgeia_municipal:last_outcome"] == "degraded"
    assert store["scraper:diavgeia_municipal:error_count"] == "0"
    alerts = _outcome_alerts(store)
    assert len(alerts) == 1 and alerts[0].severity == "warning" and alerts[0].recovery_allowed is False
    assert "scrape_errors" in alerts[0].message
    for v in list(store.values()) + [alerts[0].message]:
        assert "ADA-XYZ" not in v and "CheckViolation" not in v and raw not in v
    asyncio.run(scraper_state.record_outcome("diavgeia_municipal", "clean"))
    assert _outcome_alerts(store) == []
    assert "scraper:diavgeia_municipal:last_nonclean_time" in store


def test_first_full_failure_warns_without_leaking(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    n = asyncio.run(scraper_state.record_failure("parliament", "boom postgres://u:p@h/db"))
    assert n == 1
    assert store["scraper:parliament:last_outcome"] == "failed"
    assert store["scraper:parliament:last_outcome_reason"] == "exception"
    alerts = _outcome_alerts(store)
    assert len(alerts) == 1 and "postgres" not in alerts[0].message


def test_unknown_codes_sanitized(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    asyncio.run(scraper_state.record_outcome("x", "weird secret", "raw text secret", -5))
    assert store["scraper:x:last_outcome"] == "failed"
    assert store["scraper:x:last_outcome_reason"] == "exception"
    assert store["scraper:x:last_outcome_count"] == "0"


def test_legacy_missing_or_malformed_state_no_alert():
    assert monitor.check_scraper_jobs(SyncView({})) == []
    bad = {"scraper:parliament:last_outcome": "garbage", "scraper:parliament:error_count": "nan"}
    assert monitor.check_scraper_jobs(SyncView(bad)) == []
    store = {"scraper:parliament:last_outcome": "failed", "scraper:parliament:last_outcome_reason": "<raw>"}
    alerts = _outcome_alerts(store)
    assert len(alerts) == 1 and "<raw>" not in alerts[0].message and "unknown" in alerts[0].message


def test_no_duplicate_with_legacy_threshold():
    store = {"scraper:parliament:error_count": "21", "scraper:parliament:last_outcome": "failed",
             "scraper:parliament:last_outcome_reason": "exception"}
    alerts = monitor.check_scraper_jobs(SyncView(store))
    assert [a.type for a in alerts] == ["scraper_job_errors"]


def test_redis_outage_record_outcome_never_raises(monkeypatch):
    async def _boom():
        raise ConnectionError("down")
    monkeypatch.setattr(scraper_state, "_redis", _boom)
    asyncio.run(scraper_state.record_outcome("diavgeia_municipal", "degraded", "scrape_errors", 1))


def test_circuit_semantics_unchanged(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    for _ in range(3):
        asyncio.run(scraper_state.record_failure("diavgeia_municipal", "e"))
    assert asyncio.run(scraper_state.is_circuit_open("diavgeia_municipal")) is True
    asyncio.run(scraper_state.record_outcome("diavgeia_municipal", "clean"))
    assert asyncio.run(scraper_state.is_circuit_open("diavgeia_municipal")) is True
