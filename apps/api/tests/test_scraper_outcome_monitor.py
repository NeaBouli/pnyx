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


# --- T-9076: completeness_check outer outcome consumed by monitor ---

def _cc_alerts(store):
    return [a for a in monitor.check_scraper_jobs(SyncView(store)) if "completeness_check" in a.message]


def test_completeness_first_failure_warns_then_clean_clears(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    asyncio.run(scraper_state.record_failure("completeness_check", "boom dsn=pw"))
    alerts = _cc_alerts(store)
    assert len(alerts) == 1
    a = alerts[0]
    assert a.type == "scraper_job_errors" and a.severity == "warning" and a.recovery_allowed is False
    assert "failed (exception)" in a.message and "pw" not in a.message
    asyncio.run(scraper_state.record_success("completeness_check"))
    assert _cc_alerts(store) == []


def test_completeness_absent_or_malformed_no_alarm():
    assert _cc_alerts({}) == []
    bad = {"scraper:completeness_check:last_outcome": "junk",
           "scraper:completeness_check:error_count": "nan"}
    assert _cc_alerts(bad) == []
    assert _cc_alerts({"scraper:completeness_check:last_outcome": b"\xff"}) == []


def test_completeness_legacy_threshold_not_duplicated():
    store = {"scraper:completeness_check:error_count": "21",
             "scraper:completeness_check:last_outcome": "failed",
             "scraper:completeness_check:last_outcome_reason": "exception"}
    alerts = _cc_alerts(store)
    assert len(alerts) == 1 and alerts[0].recovery_allowed is False


def test_completeness_distinct_identity_from_parliament(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    asyncio.run(scraper_state.record_failure("parliament", "e"))
    asyncio.run(scraper_state.record_failure("completeness_check", "e"))
    ids = {monitor.alert_identity(a) for a in _outcome_alerts(store)}
    assert len(ids) == 2


# T-9078: caught per-item text fetch/merge errors in completeness_check -> degraded
def _load_completeness(monkeypatch, bills, fetch, commit_exc=None, src_path=None):
    path = src_path or os.path.join(os.path.dirname(__file__), "..", "main.py")
    src = open(path, encoding="utf-8").read()
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "scheduled_completeness_check")
    mod = ast.Module(body=[fn], type_ignores=[])
    calls = []

    class _Col:
        def __getattr__(self, n):
            return self

        def __call__(self, *a, **k):
            return self

        def __eq__(self, o):
            return self

        __hash__ = object.__hash__

    class _Sel:
        def where(self, *a, **k):
            return self

    class _Res:
        def __init__(self, rows):
            self.rows = rows

        def scalars(self):
            return self

        def all(self):
            return list(self.rows)

    class _DB:
        async def execute(self, *a, **k):
            calls.append("execute")
            return _Res(bills)

        async def commit(self):
            calls.append("commit")
            if commit_exc:
                raise commit_exc

    class _CM:
        async def __aenter__(self):
            return _DB()

        async def __aexit__(self, *a):
            return False

    def merge(text, existing):
        return text

    fakes = {
        "database": types.SimpleNamespace(AsyncSessionLocal=_CM),
        "sqlalchemy": types.SimpleNamespace(select=lambda *a: _Sel(), or_=lambda *a: None),
        "models": types.SimpleNamespace(ParliamentBill=_Col(), BillStatus=_Col()),
        "services.parliament_fetcher": types.SimpleNamespace(
            _DOCUMENT_BLOCK_HEADING="DOC", _is_bad_parliament_text=lambda t: t == "BAD",
            _is_parliament_document_block_only=lambda s: False,
            _merge_text_with_existing_document_block=merge, fetch_bill_text=fetch),
    }
    for k, v in fakes.items():
        monkeypatch.setitem(sys.modules, k, v)
    g = {"logger": logging.getLogger("t9078"), "__name__": "t9078"}
    exec(compile(mod, "main.py", "exec"), g)
    return g["scheduled_completeness_check"], calls


def _bill(bid, votes=None):
    return types.SimpleNamespace(id=bid, parliament_url="u://" + bid, summary_long_el=None,
                                 party_votes_parliament=votes)


_LEAKS = ("B-1", "B-2", "B-3", "u://", "boom-xyz", "dsn=pw")


def _no_leak(store, alerts):
    vals = [v for k, v in store.items() if not k.endswith(":last_error")] + [a.message for a in alerts]
    for v in vals:
        for leak in _LEAKS:
            assert leak not in v, (leak, v)


def test_completeness_one_text_failure_degraded_other_merged(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    b1, b2 = _bill("B-1", votes={"x": 1}), _bill("B-2", votes={"x": 1})

    async def fetch(bid, url):
        if bid == "B-1":
            raise RuntimeError("boom-xyz dsn=pw")
        return "good text"

    fn, calls = _load_completeness(monkeypatch, [b1, b2], fetch)
    asyncio.run(fn())
    assert calls.count("commit") == 1
    assert b2.summary_long_el == "good text" and b1.summary_long_el is None
    assert b1.party_votes_parliament == {"x": 1} and b2.party_votes_parliament == {"x": 1}
    assert store["scraper:completeness_check:last_outcome"] == "degraded"
    assert store["scraper:completeness_check:last_outcome_reason"] == "scrape_errors"
    assert store["scraper:completeness_check:last_outcome_count"] == "1"
    assert store["scraper:completeness_check:error_count"] == "0"
    alerts = _cc_alerts(store)
    assert len(alerts) == 1 and alerts[0].severity == "warning" and alerts[0].recovery_allowed is False
    _no_leak(store, alerts)


def test_completeness_multiple_failures_counted_then_clean_clears(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    bills = [_bill("B-1"), _bill("B-2"), _bill("B-3")]

    async def fail(bid, url):
        raise RuntimeError("boom-xyz")

    fn, _ = _load_completeness(monkeypatch, bills, fail)
    asyncio.run(fn())
    assert store["scraper:completeness_check:last_outcome_count"] == "3"
    assert len(_cc_alerts(store)) == 1
    _no_leak(store, _cc_alerts(store))

    async def ok(bid, url):
        return "fine"

    fn, _ = _load_completeness(monkeypatch, [_bill("B-1")], ok)
    asyncio.run(fn())
    assert store["scraper:completeness_check:last_outcome"] == "clean"
    assert _cc_alerts(store) == []


def test_completeness_empty_none_rejected_text_stay_clean(monkeypatch):
    store = {}
    _patch(monkeypatch, store)
    texts = {"B-1": None, "B-2": "", "B-3": "BAD"}
    bills = [_bill(b) for b in texts]

    async def fetch(bid, url):
        return texts[bid]

    fn, calls = _load_completeness(monkeypatch, bills, fetch)
    asyncio.run(fn())
    assert calls.count("commit") == 1
    assert all(b.summary_long_el is None and b.party_votes_parliament is None for b in bills)
    assert store["scraper:completeness_check:last_outcome"] == "clean"
    assert _cc_alerts(store) == []
    # no candidates at all -> clean
    store.clear()
    fn, _ = _load_completeness(monkeypatch, [], fetch)
    asyncio.run(fn())
    assert store["scraper:completeness_check:last_outcome"] == "clean"


def test_completeness_commit_failure_stays_failed(monkeypatch):
    store = {}
    _patch(monkeypatch, store)

    async def ok(bid, url):
        return "fine"

    fn, _ = _load_completeness(monkeypatch, [_bill("B-1")], ok, commit_exc=RuntimeError("dsn=pw"))
    asyncio.run(fn())
    assert store["scraper:completeness_check:last_outcome"] == "failed"
    assert store["scraper:completeness_check:last_outcome_reason"] == "exception"
    assert store["scraper:completeness_check:error_count"] == "1"
    alerts = _cc_alerts(store)
    assert len(alerts) == 1 and "pw" not in alerts[0].message
