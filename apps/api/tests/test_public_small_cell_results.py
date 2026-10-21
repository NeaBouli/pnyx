"""ADR-007 S2: public counts, derived shares and complementary cells stay private."""
import logging
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from database import get_db
from models import BillStatus, VoteChoice
from routers import analytics, arweave, export, mp, municipal, public_api, voting
from services.small_cell import small_cell_k, suppress_cell, suppress_public_cells
from services.zk_vote_aggregation import VoteTotals

CHOICES = ("yes", "no", "abstain", "unknown")


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")


@pytest.mark.parametrize("raw,expected,warn", [
    (None, 0, False), ("0", 0, False), ("10", 10, False), (" 12 ", 12, False),
    ("-7", 0, True), ("secret-env-value", 0, True), ("1.5", 0, True), ("", 0, True),
])
def test_public_results_flag_parsing(monkeypatch, caplog, raw, expected, warn):
    if raw is None:
        monkeypatch.delenv("PUBLIC_RESULTS_MIN_COUNT")
    else:
        monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", raw)
    with caplog.at_level(logging.WARNING, logger="services.small_cell"):
        assert small_cell_k() == expected
    assert bool(caplog.records) is warn
    if warn and raw:
        assert raw not in caplog.text
    assert all(r.exc_info is None for r in caplog.records)


def payload(counts):
    total = sum(counts)
    return dict(zip(CHOICES, counts), total=total,
                yes_pct=round(counts[0] / total * 100, 1) if total else 0,
                divergence=0.1, tier1=total - 1, zk=1)


def publish(counts):
    return suppress_public_cells(payload(counts), choices=CHOICES, total="total",
                                 percentages=("yes_pct",), partitions=("tier1", "zk"),
                                 derived=("divergence",))


@pytest.mark.parametrize("raw", [None, "0", "invalid", "-1"])
def test_public_results_flag_off_preserves_exact_payload(monkeypatch, raw):
    if raw is None:
        monkeypatch.delenv("PUBLIC_RESULTS_MIN_COUNT")
    else:
        monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", raw)
    assert publish([8, 1, 0, 0]) == payload([8, 1, 0, 0])
    assert suppress_cell(1) == {"count": 1, "suppressed": False}


@pytest.mark.parametrize("counts,total", [([8, 1, 0, 0], None), ([9, 10, 10, 10], None),
                                          ([100, 10, 10, 1], None), ([10, 10, 10, 0], None)])
def test_public_results_secondary_suppression_prevents_total_minus_other_cells(counts, total):
    result = publish(counts)
    assert result["total"] == total
    assert all(result[c] is None for c in CHOICES)
    assert result["yes_pct"] is None and result["divergence"] is None
    assert result["tier1"] is None and result["zk"] is None
    assert result["suppressed"] is True and result["suppression_k"] == 10


def test_public_results_threshold_requires_complete_source_evidence():
    original = dict(zip(CHOICES, [10] * 4), total=40, tier1=30, zk=10, yes_pct=25)
    result = suppress_public_cells(original, choices=CHOICES, total="total",
                                   percentages=("yes_pct",), partitions=("tier1", "zk"), public_source_total=10)
    assert result["suppressed"] is True and result["total"] is None
    safe = VoteTotals(20, 20, 20, 20, 40, 40, sources=((10,)*4, (10,)*4))
    assert safe.publishable
    assert suppress_cell(9) == {"count": None, "suppressed": True}
    assert suppress_cell(10) == {"count": 10, "suppressed": False}


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar_one_or_none(self):
        return self.rows[0] if self.rows else None

    def mappings(self):
        return self.rows


class Db:
    def __init__(self, bill=None, rows=(), scalars=()):
        self.bill = bill or bill_fixture()
        self.rows = list(rows)
        self.scalars = iter(scalars)
        self.queries = []

    async def get(self, *_):
        return self.bill

    async def execute(self, query, *_):
        self.queries.append(query)
        return Rows(self.rows.pop(0))

    async def scalar(self, *_):
        return next(self.scalars)


def bill_fixture():
    return SimpleNamespace(
        id="GR-PRIVACY", title_el="Δοκιμή", title_en="Test", pill_el=None, pill_en=None,
        summary_short_el=None, summary_long_el=None, ai_summary_reviewed=False,
        parliament_url=None, diavgeia_ada=None, status=BillStatus.OPEN_END,
        source="PARLIAMENT", results_visibility="ALWAYS", admin_hidden=False,
        party_votes_parliament={"A": "YES"}, parliament_vote_date=None,
        categories=[], arweave_tx_id=None,
    )


def aggregate(monkeypatch, module, counts):
    async def fake(*_, **__):
        return VoteTotals(*counts, sum(counts) - 1, 1)
    monkeypatch.setattr(module, "aggregate_bill_vote_totals", fake)


@pytest.mark.asyncio
@pytest.mark.parametrize("counts,total", [([8, 1, 0, 0], None), ([39, 1, 10, 10], None)])
async def test_public_and_ordinary_results_suppress_counts_shares_and_derived_values(monkeypatch, counts, total):
    bill = bill_fixture()
    for module in (public_api, voting, analytics):
        aggregate(monkeypatch, module, counts)
    public = await public_api.public_bill_results(bill.id, _key=None, db=Db())
    assert public["citizen_votes"]["total"] == total
    assert all(public["citizen_votes"][c] is None for c in CHOICES)
    assert public["divergence_score"] is None
    ordinary = await voting.get_results(bill.id, db=Db(rows=[[bill]]))
    assert ordinary.total_votes == total
    assert ordinary.yes_count is None and ordinary.no_percent is None
    assert ordinary.divergence is None and ordinary.suppressed is True
    assert ordinary.tier1_vote_count is None and ordinary.zk_vote_count is None
    if total is None:
        assert ordinary.representativity is None  # also encodes exact total/percentages
    detail = await analytics.bill_analytics(bill.id, db=Db(rows=[[]]))
    assert detail["votes"]["total"] == total
    assert detail["votes"]["unknown"] is None
    assert detail["divergence"]["score"] is None


@pytest.mark.asyncio
async def test_public_results_http_response_preserves_nulls_and_schema(monkeypatch):
    aggregate(monkeypatch, voting, [8, 1, 0, 0])
    bill = bill_fixture()
    app = FastAPI()
    app.include_router(voting.router)
    app.dependency_overrides[get_db] = lambda: Db(rows=[[bill]])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/vote/{bill.id}/results")
    assert response.status_code == 200
    data = response.json()
    assert data["total_votes"] is None and data["suppressed"] is True
    assert data["yes_count"] is None and data["unknown_percent"] is None


@pytest.mark.asyncio
async def test_public_results_latest_and_in_progress_cannot_leak_shares(monkeypatch):
    bill = bill_fixture()
    aggregate(monkeypatch, voting, [39, 1, 10, 10])
    latest = await voting.get_latest_result(db=Db(rows=[[], [bill]]))
    assert latest["total_votes"] is None and latest["yes_pct"] is None
    db = Db(rows=[[dict(id=bill.id, title_el=bill.title_el, title_en=bill.title_en,
                       status="OPEN_END", governance_level="NATIONAL", total_votes=60,
                       yes_count=39, no_count=1, abstain_count=10, unknown_count=10)]])
    monkeypatch.setenv("VOTES_IN_PROGRESS_THRESHOLD", "1")
    db.rows.insert(0, [])
    ticker = await voting.get_votes_in_progress(db=db)
    assert ticker["threshold"] == 10
    assert ticker["bills"] == []


def export_db():
    below = bill_fixture()
    below.id = "BELOW"
    mixed = bill_fixture()
    safe = bill_fixture()
    safe.id = "SAFE"
    days = [SimpleNamespace(bill_id=bill.id, vote=c.value, count=n, zk=0,
                            day=datetime(2026, 10, 15))
            for bill, counts in [(below, [9,0,0,0]), (mixed, [39,1,10,10]), (safe, [10]*4)]
            for c, n in zip(VoteChoice, counts) if n]
    return Db(rows=[[below, mixed, safe], days])


@pytest.mark.asyncio
@pytest.mark.parametrize("min_votes", [0, 1, 9, 10])
async def test_export_results_caller_cannot_bypass_threshold(min_votes):
    app = FastAPI()
    app.include_router(export.router)
    app.dependency_overrides[get_db] = export_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/export/results.json?min_votes={min_votes}")
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 1 and rows[0]["bill_id"] == "SAFE"
    assert rows[0]["citizen_yes"] == 10 and rows[0]["yes_pct"] == 25


@pytest.mark.asyncio
async def test_export_population_includes_zk_and_csv_omits_suppressed_scores():
    db = export_db()
    await export.get_all_results(db, min_votes=0)
    assert "zk_vote_receipts" in str(db.queries[1])
    response = await export.export_divergence_csv(min_votes=0, db=export_db())
    body = "".join([chunk async for chunk in response.body_iterator])
    assert "SAFE" in body and "GR-PRIVACY" not in body and "BELOW" not in body
    assert "suppressed,suppression_k" in body
    response = await export.export_bills_csv(db=export_db())
    body = "".join([chunk async for chunk in response.body_iterator])
    assert "GR-PRIVACY" not in body and "False,10" in body and "BELOW" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize("bill_id", [None, "GR-PRIVACY"])
@pytest.mark.parametrize("small", [[9, 10, 10, 10], [1, 0, 0, 0]])
async def test_analytics_timeline_suppresses_small_and_complementary_buckets(bill_id, small):
    rows = [SimpleNamespace(bill_id="GR-PRIVACY", zk=0, day=datetime(2026, 10, day), vote=choice.upper(), count=count)
            for day, counts in [(14, small), (15, [10] * 4)]
            for choice, count in zip(CHOICES, counts)]
    result = await analytics.votes_timeline(bill_id=bill_id, days=30, db=Db(rows=[rows]))
    assert result["status"] == "ok"
    if bill_id is None:
        assert result["timeline"] == []  # Suppressed bills never enter a platform sum.
        return
    assert len(result["timeline"]) == 2
    for bucket in result["timeline"]:
        assert all(bucket[c] is None for c in CHOICES)
        assert bucket["suppressed"] is True
    totals = [b["total"] for b in result["timeline"]]
    assert totals == [None, None]


@pytest.mark.asyncio
async def test_analytics_divergence_rankings_and_weekday_buckets(monkeypatch):
    bill = bill_fixture()
    aggregate(monkeypatch, analytics, [39, 1, 10, 10])
    trends = await analytics.divergence_trends(days=30, db=Db(rows=[[bill]]))
    ranked = await analytics.top_divergence(limit=10, db=Db(rows=[[bill]]))
    assert trends["trends"] == [] and ranked["data"] == []
    result = await analytics.bill_analytics(bill.id, db=Db(rows=[[
        SimpleNamespace(weekday=0, count=1), SimpleNamespace(weekday=1, count=59)]]))
    assert result["by_weekday"] == []


@pytest.mark.asyncio
async def test_municipal_public_totals_and_complementary_cells():
    decision = SimpleNamespace(ada="ADA", subject="Test", organization_label="Test", dimos_id=1,
                               decision_type_uid="x", publish_timestamp=None, document_url=None)
    for counts, total in [([8, 1, 0], None), ([40, 1, 10], None), ([10, 10, 10], 30)]:
        result = await municipal.get_voteable_decisions(dimos_id=1, days=90,
                                                       db=Db(rows=[[decision]], scalars=counts))
        votes = result["decisions"][0]["votes"]
        assert votes["total"] == total
        assert votes["yes"] == (10 if counts == [10, 10, 10] else None)


@pytest.mark.asyncio
async def test_mp_public_breakdown_does_not_reveal_withheld_choice(monkeypatch):
    aggregate(monkeypatch, mp, [39, 10, 10, 1])
    result = await mp.bill_party_breakdown("GR-PRIVACY", db=Db(rows=[[]]))
    assert result["citizen_votes"]["total"] is None
    assert result["citizen_votes"]["yes_pct"] is None
    assert result["citizen_votes"]["majority"] is None
    assert all(p["match_citizens"] is None for p in result["party_votes"])


def test_future_arweave_public_audit_results_are_suppressed():
    result = arweave.build_audit_trail(bill_fixture(), [],
                                     {"yes": 39, "no": 1, "abstain": 10, "unknown": 10, "total": 60}, 0.35)
    assert result["citizen_votes"]["total"] is None
    assert result["citizen_votes"]["yes"] is None
    assert result["divergence_score"] is None


@pytest.mark.asyncio
async def test_public_turnout_counters_exclude_below_threshold_bills(monkeypatch):
    """Execute the real combined-population SQL; do not include small bills in sums."""
    from sqlalchemy import event, text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from services.zk_vote_aggregation import count_public_votes

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def add_concat(connection, _):
        connection.create_function("concat", -1, lambda *args: "".join(str(a) for a in args))

    try:
        async with engine.begin() as connection:
            await connection.execute(text("""CREATE TABLE parliament_bills (
                id TEXT PRIMARY KEY, title_el TEXT, summary_short_el TEXT, summary_long_el TEXT,
                source TEXT, status TEXT, results_visibility TEXT, admin_hidden BOOLEAN)"""))
            await connection.execute(text("""CREATE TABLE citizen_votes (
                id INTEGER PRIMARY KEY, bill_id TEXT, vote TEXT, created_at DATETIME)"""))
            await connection.execute(text("""CREATE TABLE zk_vote_receipts (
                id INTEGER PRIMARY KEY, vote_scope_id TEXT, vote_commitment TEXT, created_at DATETIME)"""))
            await connection.execute(text("""INSERT INTO parliament_bills
                (id, source, status, results_visibility, admin_hidden) VALUES
                ('SAFE', 'PARLIAMENT', 'OPEN_END', 'ALWAYS', 0),
                ('SMALL', 'PARLIAMENT', 'OPEN_END', 'ALWAYS', 0),
                ('DIAV', 'DIAVGEIA', 'OPEN_END', 'ALWAYS', 0),
                ('HIDDEN', 'PARLIAMENT', 'ACTIVE', 'HIDDEN', 0)"""))
            await connection.execute(text("""INSERT INTO citizen_votes (bill_id, vote, created_at)
                VALUES (:bill, 'YES', '2026-10-15 12:00:00')"""),
                [{"bill": b} for b, n in [("SAFE", 9), ("SMALL", 9), ("DIAV", 1), ("HIDDEN", 20)]
                 for _ in range(n)])
            await connection.execute(text("""INSERT INTO zk_vote_receipts
                (vote_scope_id, vote_commitment, created_at)
                VALUES (:scope, 'YES', '2026-10-15 12:00:00')"""),
                [{"scope": "bill:SAFE"}] + [{"scope": "bill:DIAV"}] * 20)
        async with AsyncSession(engine) as db:
            assert await count_public_votes(db) == 0
            assert await count_public_votes(db, since=datetime(2026, 10, 15)) == 0
            assert await count_public_votes(db, since=datetime(2026, 10, 16)) == 0
            monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
            assert await count_public_votes(db) == 20
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_public_stats_and_overview_do_not_publish_small_counters(monkeypatch):
    async def count(*_, **__):
        return 0

    monkeypatch.setattr(public_api, "count_public_votes", count)
    result = await public_api.public_stats(_key=None, db=Db(scalars=[1] * 7))
    assert result["stats"]["total_votes"] is None and result["stats"]["suppressed"] is True
    monkeypatch.setattr(analytics, "count_public_votes", count)
    result = await analytics.analytics_overview(db=Db(scalars=[1] * 3, rows=[[], []]))
    assert all(result["votes"][key] is None for key in ("total", "last_7_days", "today", "avg_per_bill"))


@pytest.mark.asyncio
async def test_future_public_telegram_result_notification_suppresses_small_total(monkeypatch):
    from services import telegram_community
    messages = []

    async def capture(message, **_):
        messages.append(message)

    monkeypatch.setattr(telegram_community, "_send", capture)
    await telegram_community.notify_parliament_voted("GR-PRIVACY", "Test", citizen_votes=9)
    assert "λιγότερες από 10 ψήφοι" in messages[0]
    assert "9 ψήφοι" not in messages[0]


@pytest.mark.asyncio
async def test_future_public_newsletter_does_not_bypass_result_suppression(monkeypatch):
    from services import newsletter_service
    monkeypatch.setattr(newsletter_service, "ensure_reconfirmations_paused", AsyncMock(return_value=True))
    from routers import newsletter
    from tests.test_newsletter_delivery_sync import MemoryRedis
    monkeypatch.setattr(newsletter, "_get_redis", AsyncMock(return_value=MemoryRedis()))
    captured = []

    async def capture(endpoint, data):
        captured.append(data)
        return {"id": 1} if endpoint == "emailCampaigns" else {}

    monkeypatch.setattr(newsletter_service, "_brevo_post", capture)
    db = Db(scalars=[0, 0, 1234567, 0], rows=[[], [], [("GR-PRIVACY", "Private", 987654, 1, 987655)]])
    await newsletter_service.send_monthly_report(db)
    html = captured[0]["htmlContent"]
    assert all(str(number) not in html for number in (1234567, 987654, 987655))


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [None, "0", "invalid", "-1"])
async def test_flag_off_http_results_match_origin_main_bytes(monkeypatch, raw):
    """Bytes captured from main 7e9dba6cc19a5b2e6d329d49c622b454386b0a1a.

    The committed fixture keeps shallow CI checkouts independent of git refs.
    """
    from pathlib import Path
    if raw is None:
        monkeypatch.delenv("PUBLIC_RESULTS_MIN_COUNT")
    else:
        monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", raw)
    aggregate(monkeypatch, voting, [8, 1, 0, 0])
    app = FastAPI()
    app.include_router(voting.router)
    app.dependency_overrides[get_db] = lambda: Db(rows=[[bill_fixture()]])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/vote/GR-PRIVACY/results")
    assert response.status_code == 200
    expected = Path(__file__).with_name("fixtures").joinpath("public_results_main.json").read_bytes()
    assert response.content == expected
    assert "suppressed" not in response.json() and "suppression_k" not in response.json()


@pytest.mark.asyncio
async def test_cplm_one_yes_is_withheld_in_compute_cache_and_http_history(monkeypatch):
    import json
    from services import cplm
    from routers import cplm as cplm_router

    vote = SimpleNamespace(nullifier_hash="one", vote=VoteChoice.YES)
    bill = bill_fixture()
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
    legacy = await cplm.compute_cplm(Db(rows=[[(vote, bill)], []]))
    assert (legacy["total_votes"], legacy["total_voters"], legacy["x"]) == (1, 1, 0.05)
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    computed = await cplm.compute_cplm(Db(rows=[[], [(vote, bill)]]))
    assert computed["x"] is None and computed["total_voters"] is None

    class Redis:
        async def get(self, _):
            return json.dumps(legacy)
        async def lrange(self, *_):
            return [json.dumps(legacy), json.dumps({**legacy, "total_voters": 10})]
        async def aclose(self):
            pass
    monkeypatch.setattr(cplm.aioredis, "from_url", lambda *_, **__: Redis())
    app = FastAPI()
    app.include_router(cplm_router.router)
    app.dependency_overrides[get_db] = lambda: Db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        aggregate_response = (await client.get("/api/v1/cplm/aggregate")).json()
        history = (await client.get("/api/v1/cplm/history")).json()["snapshots"]
    for point in (aggregate_response, history[0]):
        assert point["suppressed"] is True and point["suppression_k"] == 10
        assert all(point[key] is None for key in ("x", "y", "quadrant", "total_votes", "total_voters", "trend"))
    assert history[1]["x"] is None and history[1]["suppressed"] is True


@pytest.mark.asyncio
async def test_platform_timeline_excludes_10_10_10_10_plus_1_0_0_0():
    from datetime import timezone
    day = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = [SimpleNamespace(bill_id=bill, day=day, vote=c.upper(), count=n, zk=0)
            for bill, counts in [("SAFE", [10]*4), ("SMALL", [1, 0, 0, 0])]
            for c, n in zip(CHOICES, counts) if n]
    result = await analytics.votes_timeline(bill_id=None, days=7, db=Db(rows=[rows]))
    assert len(result["timeline"]) == 1
    assert [result["timeline"][0][c] for c in CHOICES] == [10, 10, 10, 10]
    assert result["timeline"][0]["total"] == 40


@pytest.mark.asyncio
async def test_alltime_11_10_10_10_minus_seven_day_10_each_withholds_windows(monkeypatch):
    from datetime import timedelta, timezone
    from services.public_result_windows import load_public_vote_days, public_window_count
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = [SimpleNamespace(bill_id="GR-PRIVACY", day=now, vote=c.upper(), count=10, zk=0)
            for c in CHOICES]
    rows += [SimpleNamespace(bill_id="GR-PRIVACY", day=now-timedelta(days=8), vote="YES", count=1, zk=0)]
    bills = await load_public_vote_days(Db(rows=[rows]))
    assert bills["GR-PRIVACY"]["totals"] == dict(zip(CHOICES, [11,10,10,10]), total=41)
    assert public_window_count(bills) == 41
    assert public_window_count(bills, since=now-timedelta(days=7)) is None
    for days in (7, 30):
        result = await analytics.votes_timeline(bill_id="GR-PRIVACY", days=days, db=Db(rows=[rows]))
        assert result["timeline"]
        assert all(r["total"] is None and all(r[c] is None for c in CHOICES) for r in result["timeline"])

    async def count(_db, *, since=None):
        return public_window_count(bills, since=since)
    monkeypatch.setattr(analytics, "count_public_votes", count)
    result = await analytics.analytics_overview(db=Db(scalars=[1, 0, 0], rows=[[], rows]))
    assert result["votes"]["total"] == 41
    assert result["votes"]["avg_per_bill"] == 41
    assert result["votes"]["today"] is None and result["votes"]["last_7_days"] is None
    assert result["votes"]["suppressed"] is True


@pytest.mark.asyncio
async def test_40_public_zk_receipts_cannot_be_subtracted_from_combined_41(monkeypatch):
    async def fake(*_, **__):
        return VoteTotals(11, 10, 10, 10, 1, 40)
    for module in (voting, public_api, analytics, mp):
        monkeypatch.setattr(module, "aggregate_bill_vote_totals", fake)
    result = await voting.get_results("GR-PRIVACY", db=Db(rows=[[bill_fixture()]]))
    assert result.total_votes is None and result.yes_count is None
    result = await voting.get_latest_result(db=Db(rows=[[], [bill_fixture()]]))
    assert result["total_votes"] is None and result["yes_pct"] is None
    result = await public_api.public_bill_results("GR-PRIVACY", _key=None, db=Db())
    assert result["citizen_votes"]["total"] is None and result["divergence_score"] is None
    result = await analytics.bill_analytics("GR-PRIVACY", db=Db(rows=[[]]))
    assert result["votes"]["total"] is None and result["divergence"]["score"] is None
    result = await mp.bill_party_breakdown("GR-PRIVACY", db=Db(rows=[[]]))
    assert result["citizen_votes"]["total"] is None
    result = arweave.build_audit_trail(bill_fixture(), [], dict(zip(CHOICES, [11,10,10,10]), total=41, zk_total=40), 0.1)
    assert result["citizen_votes"]["total"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("ordinary,counts,hidden", [
    ([], [0]*4, True), ([], [1,0,0,0], True), ([], [39,1,10,10], True),
    ([], [10]*4, False), ([1,10,10,10], [10]*4, True),
    ([10]*4, [39,1,10,10], True), ([10]*4, [10]*4, False),
])
async def test_zk_receipt_enumeration_gates_scope_before_pagination(monkeypatch, ordinary, counts, hidden):
    from routers import zk
    async def public(*_):
        pass
    monkeypatch.setattr(zk, "_ensure_scope_public_or_safe_canary", public)
    monkeypatch.setattr(zk, "build_public_zk_receipt_from_storage", lambda _: {"choice": "YES"})
    db = Db(rows=[list(zip(VoteChoice, ordinary)), list(zip([c.value for c in VoteChoice], counts)), [object()]])
    app = FastAPI()
    app.include_router(zk.router)
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/zk/receipts/bill:GR-PRIVACY?offset=100&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert data["receipts"] == (None if hidden else [{"choice": "YES"}])
    assert data["suppressed"] is hidden
    assert len(db.queries) == (2 if hidden else 3)


@pytest.mark.asyncio
@pytest.mark.parametrize("ordinary,counts", [([], [1,0,0,0]), ([], [39,1,10,10]), ([1,10,10,10], [10]*4)])
async def test_zk_arweave_withholds_small_choice_before_any_publication(monkeypatch, ordinary, counts):
    from services import zk_arweave_publisher as publisher
    monkeypatch.setenv("ZK_ARWEAVE_PUBLICATION_ENABLED", "true")
    monkeypatch.setenv("ZK_CANARY_ENABLED", "false")
    monkeypatch.setenv("ZK_ARWEAVE_SCOPE_ALLOWLIST", "bill:GR-PRIVACY")
    async def public(*_):
        pass
    monkeypatch.setattr(publisher, "ensure_public_parliament_scope", public)
    db = Db(rows=[list(zip(VoteChoice, ordinary)), list(zip([c.value for c in VoteChoice], counts))])
    with pytest.raises(publisher.ZkArweavePublicationError, match="withheld"):
        await publisher.publish_pending_zk_receipts_for_scope(db, vote_scope_id="bill:GR-PRIVACY")
    assert len(db.queries) == 2
    assert all("arweave_pending" not in str(q) for q in db.queries)


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["platform", "windows", "sources", "source_windows", "source_cells", "zk_choice"])
async def test_exact_reproductions_execute_real_public_aggregate_sql(scenario):
    from datetime import timedelta
    from sqlalchemy import event, text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from services.public_result_windows import load_public_vote_days, public_daily_series
    from services.zk_vote_aggregation import count_public_votes

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    @event.listens_for(engine.sync_engine, "connect")
    def concat(connection, _):
        connection.create_function("concat", -1, lambda *a: "".join(str(x) for x in a))
    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d 12:00:00")
    old = (now-timedelta(days=8)).strftime("%Y-%m-%d 12:00:00")
    try:
        async with engine.begin() as connection:
            for sql in [
                "CREATE TABLE parliament_bills (id TEXT PRIMARY KEY, title_el TEXT, summary_short_el TEXT, summary_long_el TEXT, source TEXT, status TEXT, results_visibility TEXT, admin_hidden BOOLEAN)",
                "CREATE TABLE citizen_votes (id INTEGER PRIMARY KEY, bill_id TEXT, vote TEXT, created_at DATETIME)",
                "CREATE TABLE zk_vote_receipts (id INTEGER PRIMARY KEY, vote_scope_id TEXT, vote_commitment TEXT, created_at DATETIME)",
                "INSERT INTO parliament_bills (id,source,status,results_visibility,admin_hidden) VALUES ('SAFE','PARLIAMENT','OPEN_END','ALWAYS',0),('SMALL','PARLIAMENT','OPEN_END','ALWAYS',0)",
            ]:
                await connection.execute(text(sql))
            if scenario in ("sources", "source_windows", "source_cells", "zk_choice"):
                await connection.execute(text("INSERT INTO zk_vote_receipts (vote_scope_id,vote_commitment,created_at) VALUES ('bill:SAFE',:vote,:day)"),
                                         [{"vote": c.upper(), "day": today} for c, n in zip(CHOICES, [39,1,10,10] if scenario == "zk_choice" else [10]*4) for _ in range(n)])
                tier = [{"bill": "SAFE", "vote": "YES", "day": today}]
                if scenario == "source_cells":
                    tier += [{"bill": "SAFE", "vote": c.upper(), "day": today} for c in CHOICES[1:] for _ in range(10)]
                if scenario == "zk_choice":
                    tier = []
                if scenario == "source_windows":
                    tier += [{"bill": "SAFE", "vote": c.upper(), "day": old} for c in CHOICES for _ in range(10)]
            else:
                tier = [{"bill": "SAFE", "vote": c.upper(), "day": today} for c in CHOICES for _ in range(10)]
                tier += [{"bill": "SMALL" if scenario == "platform" else "SAFE", "vote": "YES", "day": today if scenario == "platform" else old}]
            if tier:
                await connection.execute(text("INSERT INTO citizen_votes (bill_id,vote,created_at) VALUES (:bill,:vote,:day)"), tier)
        async with AsyncSession(engine) as db:
            from services.zk_vote_aggregation import aggregate_bill_vote_totals, zk_scope_publishable
            totals = await aggregate_bill_vote_totals(db, "SAFE", include_zk=True)
            assert totals.publishable is (scenario not in ("sources", "source_cells", "zk_choice"))
            assert await zk_scope_publishable(db, "bill:SAFE") is totals.publishable
            total = await count_public_votes(db)
            assert total == {"platform": 40, "windows": 41, "sources": 0, "source_windows": 81, "source_cells": 0, "zk_choice": 0}[scenario]
            window = await count_public_votes(db, since=now-timedelta(days=7))
            assert window == {"platform": 40, "windows": None, "sources": 0, "source_windows": None, "source_cells": 0, "zk_choice": 0}[scenario]
            bills = await load_public_vote_days(db)
            timeline = public_daily_series(bills, since=now-timedelta(days=7), platform=True)
            if scenario == "platform":
                assert [timeline[0][c] for c in CHOICES] == [10]*4
                assert timeline[0]["total"] == 40
            else:
                assert timeline == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_representation_totals_exclude_hidden_source_complements(monkeypatch):
    safe = bill_fixture()
    safe.id = "SAFE"
    async def aggregate(_db, bill_id, **_):
        return VoteTotals(10, 10, 10, 10, 40, 0) if bill_id == "SAFE" else VoteTotals(11, 10, 10, 10, 1, 40)
    monkeypatch.setattr(analytics, "aggregate_bill_vote_totals", aggregate)
    result = await analytics.compute_cumulative_representation(Db(rows=[[safe, bill_fixture()]]))
    assert result["total_citizen_votes"] == 40


@pytest.mark.asyncio
async def test_lifecycle_notification_cannot_publish_41_minus_40_receipts(monkeypatch):
    from services import bill_lifecycle, telegram_community
    messages = []
    async def capture(message, **_):
        messages.append(message)
    async def aggregate(*_, **__):
        return VoteTotals(11, 10, 10, 10, 1, 40)
    monkeypatch.setattr(telegram_community, "_send", capture)
    monkeypatch.setattr(bill_lifecycle, "aggregate_bill_vote_totals", aggregate)
    bill = bill_fixture()
    bill.governance_level = None
    await bill_lifecycle._hook_telegram_community(bill, BillStatus.PARLIAMENT_VOTED, db=Db())
    assert len(messages) == 1 and "— ψήφοι" in messages[0]
    assert "41" not in messages[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("ordinary,zk_counts", [([1,0,0,0], [0]*4), ([1,10,10,10], [10]*4)])
async def test_cplm_safe_economic_plus_one_social_vote_never_enters_compute_cache_history(monkeypatch, ordinary, zk_counts):
    import json
    from services import cplm
    safe, small = bill_fixture(), bill_fixture()
    safe.id, small.id = 'SAFE', 'SMALL'
    small.title_en = 'social'
    days = [SimpleNamespace(bill_id=b.id, day=datetime(2026,10,15), vote=c.value, count=n, zk=zk)
            for b, zk, counts in [(safe, 0, [10]*4), (small, 0, ordinary), (small, 1, zk_counts)]
            for c, n in zip(VoteChoice, counts) if n]
    votes = [(SimpleNamespace(nullifier_hash=f'{c}-{i}', vote=c), safe)
             for c in VoteChoice for i in range(10)]
    votes += [(SimpleNamespace(nullifier_hash=f'small-{c}-{i}', vote=c), small)
              for c, n in zip(VoteChoice, ordinary) for i in range(n)]
    computed = await cplm.compute_cplm(Db(rows=[days, votes, []]))
    assert computed['total_votes'] == computed['total_voters'] == 40
    assert computed['x'] == computed['y'] == 0 and computed['suppressed'] is False
    keys = []
    class Redis:
        async def get(self, key):
            keys.append(key)
            return cplm._store_snapshot(computed, 10)
        async def lrange(self, key, *_):
            keys.append(key)
            return [cplm._store_snapshot(computed, 10), json.dumps({**computed, 'total_votes': 41, 'y': .0012})]
        async def aclose(self):
            pass
    monkeypatch.setattr(cplm.aioredis, 'from_url', lambda *_, **__: Redis())
    assert await cplm.get_cplm_cached(Db()) == computed
    history = await cplm.get_cplm_history()
    assert history[0] == computed
    assert history[1]['total_votes'] is None and history[1]['y'] is None
    assert all(':publishable-v1:k10' in key for key in keys)


@pytest.mark.asyncio
@pytest.mark.parametrize('min_votes', [0, 40, 41, 42, 71, 72])
@pytest.mark.parametrize('ordinary', [[1,0,0,0], [1,10,10,10]])
async def test_export_source_choice_suppression_precedes_min_votes_and_divergence_csv(min_votes, ordinary):
    bill = bill_fixture()
    rows = [SimpleNamespace(bill_id=bill.id, day=datetime(2026,10,15), vote=c.value, count=n, zk=zk)
            for zk, counts in [(0, ordinary), (1, [10]*4)]
            for c, n in zip(VoteChoice, counts)]
    assert await export.get_all_results(Db(rows=[[bill], rows]), min_votes=min_votes) == []
    response = await export.export_divergence_csv(min_votes=min_votes, db=Db(rows=[[bill], rows]))
    body = ''.join([chunk async for chunk in response.body_iterator])
    assert bill.id not in body


@pytest.mark.asyncio
async def test_milestone_total_alone_cannot_authorize_a_suppressed_bill(monkeypatch):
    from routers import notifications
    published = []
    async def capture(*args):
        published.append(args)
    monkeypatch.setattr(notifications, 'publish_bill_event', capture)
    await notifications.publish_vote_milestone('GR-PRIVACY', 100)
    await notifications.publish_vote_milestone('GR-PRIVACY', 100, db=Db(rows=[[]]))
    assert published == []
    monkeypatch.setenv('PUBLIC_RESULTS_MIN_COUNT', '0')
    await notifications.publish_vote_milestone('GR-PRIVACY', 100)
    assert len(published) == 1
