"""T-9069: latest scraper outcome visible in Redis job state and monitor."""
import ast
import asyncio
import logging
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
    return [a for a in monitor.check_scraper_jobs(SyncView(store))
            if a.type == "scraper_job_errors" and "last run" in a.message]


def test_degraded_check_violation_visible_then_clean_clears(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    raw = "CheckViolation ADA-XYZ token=abc user@example.test"
    asyncio.run(scraper_state.record_success("diavgeia_municipal", "degraded", "scrape_errors", 2))
    assert store["scraper:diavgeia_municipal:last_outcome"] == "degraded"
    assert store["scraper:diavgeia_municipal:error_count"] == "0"
    alerts = _outcome_alerts(store)
    assert len(alerts) == 1 and alerts[0].severity == "warning" and alerts[0].recovery_allowed is False
    assert "scrape_errors" in alerts[0].message
    for v in list(store.values()) + [alerts[0].message]:
        assert "ADA-XYZ" not in v and "CheckViolation" not in v and raw not in v
    asyncio.run(scraper_state.record_success("diavgeia_municipal"))
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
    asyncio.run(scraper_state.record_success("parliament"))
    assert _outcome_alerts(store) == []


def test_unknown_codes_sanitized(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    asyncio.run(scraper_state.record_success("x", "weird secret", "raw text secret", -5))
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


def test_circuit_semantics_unchanged(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    for _ in range(3):
        asyncio.run(scraper_state.record_failure("diavgeia_municipal", "e"))
    assert asyncio.run(scraper_state.is_circuit_open("diavgeia_municipal")) is True
    asyncio.run(scraper_state.record_success("diavgeia_municipal", "degraded", "scrape_errors", 1))
    assert store["scraper:diavgeia_municipal:error_count"] == "0"


def test_two_jobs_have_distinct_dedupe_identity():
    store = {"scraper:parliament:last_outcome": "failed", "scraper:parliament:last_outcome_reason": "exception",
             "scraper:diavgeia_municipal:last_outcome": "degraded",
             "scraper:diavgeia_municipal:last_outcome_reason": "scrape_errors"}
    ids = {monitor.alert_identity(a) for a in _outcome_alerts(store)}
    assert len(ids) == 2


def test_malformed_bytes_safe():
    store = {"scraper:parliament:last_outcome": b"fail\xffed", "scraper:x:last_outcome": b"\xff"}
    assert _outcome_alerts(store) == []
    store = {"scraper:parliament:last_outcome": b"failed", "scraper:parliament:last_outcome_reason": b"\xfe"}
    assert "unknown" in _outcome_alerts(store)[0].message


# --- Real scheduled_diavgeia_scrape body (loaded from main.py AST, not copied) ---

def _load_scheduler(monkeypatch, result=None, convert_exc=None, scrape_exc=None):
    src = open(os.path.join(os.path.dirname(__file__), "..", "main.py"), encoding="utf-8").read()
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "scheduled_diavgeia_scrape")
    mod = ast.Module(body=[fn], type_ignores=[])

    class _CM:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *a):
            return False

    async def scrape_decisions(*a, **k):
        if scrape_exc:
            raise scrape_exc
        return result

    async def convert(*a, **k):
        if convert_exc:
            raise convert_exc
        return {"created": 0, "skipped": 0}

    async def backfill(*a, **k):
        return 0

    fakes = {
        "services.diavgeia_scraper": types.SimpleNamespace(
            scrape_decisions=scrape_decisions, convert_decisions_to_bills=convert,
            backfill_diavgeia_bill_dates=backfill),
        "database": types.SimpleNamespace(AsyncSessionLocal=_CM),
    }
    for k, v in fakes.items():
        monkeypatch.setitem(sys.modules, k, v)
    g = {"logger": logging.getLogger("t9069"), "__name__": "t9069"}
    exec(compile(mod, "main.py", "exec"), g)
    return g["scheduled_diavgeia_scrape"]


def _result(errors):
    return types.SimpleNamespace(fetched=3, inserted=1, errors=errors)


def test_scheduler_check_violation_degraded_then_clean(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    err = 'asyncpg.exceptions.CheckViolationError: ADA-T1 violates check constraint "ck_x"'
    asyncio.run(_load_scheduler(monkeypatch, _result([err]))())
    assert store["scraper:diavgeia_municipal:last_outcome"] == "degraded"
    assert store["scraper:diavgeia_municipal:last_outcome_reason"] == "scrape_errors"
    assert store["scraper:diavgeia_municipal:error_count"] == "0"
    alerts = _outcome_alerts(store)
    assert len(alerts) == 1 and alerts[0].recovery_allowed is False
    for v in list(store.values()) + [alerts[0].message]:
        assert "ADA-T1" not in v and "CheckViolation" not in v
    asyncio.run(_load_scheduler(monkeypatch, _result([]))())
    assert store["scraper:diavgeia_municipal:last_outcome"] == "clean"
    assert _outcome_alerts(store) == []


def test_scheduler_conversion_failure_degraded(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    asyncio.run(_load_scheduler(monkeypatch, _result([]), convert_exc=RuntimeError("x"))())
    assert store["scraper:diavgeia_municipal:last_outcome"] == "degraded"
    assert store["scraper:diavgeia_municipal:last_outcome_reason"] == "conversion_failed"


def test_scheduler_outer_exception_failed(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    asyncio.run(_load_scheduler(monkeypatch, scrape_exc=RuntimeError("dsn=secret"))())
    assert store["scraper:diavgeia_municipal:last_outcome"] == "failed"
    assert store["scraper:diavgeia_municipal:error_count"] == "1"
    assert all("secret" not in m.message for m in _outcome_alerts(store))
