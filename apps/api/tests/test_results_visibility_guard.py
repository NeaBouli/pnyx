"""T-599: no public surface publishes interim counts of a running (ACTIVE, HIDDEN) vote.

routers.voting.get_results already zeroes ACTIVE bills with hidden results. The public API,
bill analytics, the MP breakdown, the landing feeds (latest / in-progress) and the monthly
newsletter must apply the same rule through services.bill_visibility.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from models import BillStatus
from routers import analytics, mp, public_api, voting
from services import cplm, newsletter_service
from services.bill_visibility import results_hidden, results_visible_filter, results_visible_raw_sql
from services.zk_vote_aggregation import VoteTotals


@pytest.mark.parametrize(("status", "visibility", "hidden"), [
    (BillStatus.ACTIVE, None, True),
    (BillStatus.ACTIVE, "HIDDEN", True),
    (BillStatus.ACTIVE, "WINDOW", False),
    (BillStatus.ACTIVE, "ALWAYS", False),
    (BillStatus.WINDOW_24H, "HIDDEN", False),
    (BillStatus.PARLIAMENT_VOTED, "HIDDEN", False),
    (BillStatus.OPEN_END, None, False),
    (SimpleNamespace(value="ACTIVE"), None, True),
    (SimpleNamespace(value="OPEN_END"), "HIDDEN", False),
])
def test_results_hidden_matches_get_results_rule(status, visibility, hidden):
    assert results_hidden(SimpleNamespace(status=status, results_visibility=visibility)) is hidden


def test_sql_forms_express_the_same_rule():
    compiled = str(results_visible_filter().compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True},
    ))
    assert "parliament_bills.status = 'ACTIVE'" in compiled
    assert "coalesce(parliament_bills.results_visibility, 'HIDDEN') = 'HIDDEN'" in compiled
    assert compiled.startswith("NOT (")
    assert results_visible_raw_sql("b") == (
        "NOT (b.status::text = 'ACTIVE' AND COALESCE(b.results_visibility, 'HIDDEN') = 'HIDDEN')"
    )
    with pytest.raises(ValueError):
        results_visible_raw_sql("b; DROP TABLE x")


def _bill(status, visibility=None, **overrides):
    values = dict(
        id="GR-T599", title_el="Νομοσχέδιο", title_en=None, status=status,
        results_visibility=visibility, party_votes_parliament={"ΝΔ": "ΝΑΙ"}, arweave_tx_id=None,
        admin_hidden=False, source="PARLIAMENT",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class _GetDb:
    def __init__(self, bill):
        self.bill = bill

    async def get(self, _model, _bill_id):
        return self.bill

    async def execute(self, *_args, **_kwargs):
        raise AssertionError("hidden results must not query vote events")


async def _no_aggregate(*_args, **_kwargs):
    raise AssertionError("hidden results must not be aggregated")


def _counting_aggregate(calls):
    async def aggregate(_db, _bill_id, *, include_zk):
        calls.append(include_zk)
        return VoteTotals(yes=3, no=2, abstain=0, unknown=0, tier1_total=5, zk_total=0)
    return aggregate


@pytest.mark.asyncio
async def test_public_results_hide_a_running_vote(monkeypatch):
    monkeypatch.setattr(public_api, "aggregate_bill_vote_totals", _no_aggregate)
    result = await public_api.public_bill_results("GR-T599", _key=True, db=_GetDb(_bill(BillStatus.ACTIVE)))
    assert result["results_hidden"] is True
    assert result["citizen_votes"]["total"] == 0
    assert result["citizen_votes"]["yes_pct"] == 0.0
    assert result["divergence_score"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [BillStatus.WINDOW_24H, BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END])
async def test_public_results_show_closed_or_window_votes(monkeypatch, status):
    calls = []
    monkeypatch.setattr(public_api, "aggregate_bill_vote_totals", _counting_aggregate(calls))
    result = await public_api.public_bill_results("GR-T599", _key=True, db=_GetDb(_bill(status, "HIDDEN")))
    assert calls == [True]
    assert result["results_hidden"] is False
    assert result["citizen_votes"]["total"] == 5


@pytest.mark.asyncio
async def test_public_results_still_404_for_non_public_bills(monkeypatch):
    monkeypatch.setattr(public_api, "aggregate_bill_vote_totals", _no_aggregate)
    with pytest.raises(HTTPException) as exc:
        await public_api.public_bill_results(
            "GR-T599", _key=True, db=_GetDb(_bill(BillStatus.ACTIVE, admin_hidden=True)),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_bill_analytics_hides_a_running_vote(monkeypatch):
    monkeypatch.setattr(analytics, "aggregate_bill_vote_totals", _no_aggregate)
    result = await analytics.bill_analytics("GR-T599", db=_GetDb(_bill(BillStatus.ACTIVE)))
    assert result["results_hidden"] is True
    assert result["votes"]["total"] == 0
    assert result["by_weekday"] == []
    assert result["divergence"]["available"] is False


@pytest.mark.asyncio
async def test_mp_breakdown_hides_the_citizen_majority_of_a_running_vote(monkeypatch):
    async def no_majority(*_args, **_kwargs):
        raise AssertionError("hidden results must not count citizen votes")

    async def party_map(_db):
        return {}

    monkeypatch.setattr(mp, "citizen_majority_for", no_majority)
    monkeypatch.setattr(mp, "get_party_map", party_map)
    result = await mp.bill_party_breakdown("GR-T599", db=_GetDb(_bill(BillStatus.ACTIVE)))
    assert result["results_hidden"] is True
    assert result["citizen_votes"]["total"] == 0
    assert result["citizen_votes"]["majority"] is None
    assert all(p["match_citizens"] is None for p in result["party_votes"])


class _CaptureDb:
    def __init__(self):
        self.statements = []

    async def execute(self, statement, params=None):
        self.statements.append(statement)
        return SimpleNamespace(
            scalar_one_or_none=lambda: None,
            mappings=lambda: [],
        )


@pytest.mark.asyncio
async def test_latest_result_feed_excludes_running_votes():
    db = _CaptureDb()
    assert await voting.get_latest_result(db=db) == {"bill_id": None, "total_votes": 0}
    compiled = str(db.statements[0].compile(dialect=postgresql.dialect()))
    assert "coalesce(parliament_bills.results_visibility" in compiled


@pytest.mark.asyncio
async def test_in_progress_feed_excludes_running_votes():
    db = _CaptureDb()
    await voting.get_votes_in_progress(db=db)
    assert results_visible_raw_sql("b") in str(db.statements[0])


def test_newsletter_top_votes_apply_the_guard():
    import inspect
    source = inspect.getsource(newsletter_service)
    assert "AND {results_visible_raw_sql('b')}" in source


class _CplmDb:
    def __init__(self):
        self.statement = None

    async def execute(self, statement, *_args, **_kwargs):
        self.statement = self.statement or statement
        return SimpleNamespace(all=lambda: [])


@pytest.mark.asyncio
async def test_cplm_counts_only_votes_with_visible_results():
    db = _CplmDb()
    result = await cplm.compute_cplm(db)
    assert result["total_votes"] == 0
    compiled = str(db.statement.compile(dialect=postgresql.dialect()))
    assert "coalesce(parliament_bills.results_visibility" in compiled


# ── Re-review (Codex #456): export, timeline, turnout counters, newsletter total, CPLM cache ──

from models import VoteChoice  # noqa: E402
from routers import export  # noqa: E402
from services import zk_vote_aggregation  # noqa: E402

_VISIBILITY_MATRIX = [
    ("GR-HIDDEN", BillStatus.ACTIVE, "HIDDEN", True),
    ("GR-NULL", BillStatus.ACTIVE, None, True),
    ("GR-WINDOW", BillStatus.ACTIVE, "WINDOW", False),
    ("GR-ALWAYS", BillStatus.ACTIVE, "ALWAYS", False),
    ("GR-CLOSED", BillStatus.OPEN_END, "HIDDEN", False),
]


class _ExportDb:
    def __init__(self, bills):
        self.bills = bills
        self.calls = 0

    async def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: self.bills))
        rows = [(bill.id, VoteChoice.YES, 3) for bill in self.bills]
        return SimpleNamespace(all=lambda: rows)


@pytest.mark.asyncio
async def test_export_omits_counts_of_running_votes():
    bills = [
        _bill(status, visibility, id=bill_id, title_en=None, categories=[], parliament_vote_date=None,
              party_votes_parliament=None)
        for bill_id, status, visibility, _hidden in _VISIBILITY_MATRIX
    ]
    rows = {row["bill_id"]: row for row in await export.get_all_results(_ExportDb(bills))}
    for bill_id, _status, _visibility, hidden in _VISIBILITY_MATRIX:
        assert rows[bill_id]["citizen_total"] == (0 if hidden else 3), bill_id
        assert rows[bill_id]["citizen_yes"] == (0 if hidden else 3), bill_id


@pytest.mark.asyncio
@pytest.mark.parametrize(("bill_id", "status", "visibility", "hidden"), _VISIBILITY_MATRIX)
async def test_bill_timeline_is_empty_while_results_are_hidden(bill_id, status, visibility, hidden):
    class _TimelineDb(_GetDb):
        executed = False

        async def execute(self, *_args, **_kwargs):
            _TimelineDb.executed = True
            return SimpleNamespace(all=lambda: [])

    db = _TimelineDb(_bill(status, visibility, id=bill_id))
    result = await analytics.votes_timeline(bill_id=bill_id, days=30, db=db)
    assert result["timeline"] == []
    assert result.get("results_hidden", False) is hidden
    assert _TimelineDb.executed is (not hidden)


@pytest.mark.asyncio
async def test_global_timeline_excludes_running_votes():
    db = _CaptureDb()

    async def execute(statement, params=None):
        db.statements.append(statement)
        return SimpleNamespace(all=lambda: [])

    db.execute = execute
    await analytics.votes_timeline(bill_id=None, days=30, db=db)
    compiled = str(db.statements[0].compile(dialect=postgresql.dialect()))
    assert compiled.count("coalesce(parliament_bills.results_visibility") == 2  # Tier-1 and ZK


@pytest.mark.asyncio
async def test_global_turnout_counters_exclude_running_votes():
    statements = []

    class _ScalarDb:
        async def scalar(self, statement):
            statements.append(str(statement.compile(dialect=postgresql.dialect())))
            return 0

    assert await zk_vote_aggregation.count_public_votes(_ScalarDb()) == 0
    assert len(statements) == 2
    assert all("coalesce(parliament_bills.results_visibility" in s for s in statements)


def test_newsletter_monthly_total_applies_the_guard():
    import inspect
    assert ".where(public_bill_filter(), results_visible_filter())" in inspect.getsource(newsletter_service)


def test_cplm_cache_key_is_versioned_for_the_filtered_aggregate():
    assert cplm.CACHE_KEY == "cplm:aggregate:v2"


from services import zk_arweave_publisher  # noqa: E402


@pytest.mark.parametrize(("bill_id", "status", "visibility", "hidden"), _VISIBILITY_MATRIX)
def test_zk_arweave_publication_waits_for_visible_results(bill_id, status, visibility, hidden):
    bill = _bill(status, visibility, id=bill_id)
    assert zk_arweave_publisher._is_public_parliament_bill_scope(bill) is (not hidden)


@pytest.mark.asyncio
async def test_zk_arweave_pending_scopes_query_excludes_running_votes():
    db = _CaptureDb()

    async def execute(statement, params=None):
        db.statements.append(statement)
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    db.execute = execute
    assert await zk_arweave_publisher.list_pending_public_parliament_scopes(db) == set()
    compiled = str(db.statements[0].compile(dialect=postgresql.dialect()))
    assert "coalesce(parliament_bills.results_visibility" in compiled
