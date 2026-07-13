from types import SimpleNamespace

import pytest

from models import BillStatus
from routers import voting
from services.zk_vote_aggregation import VoteTotals


class _ScalarRows:
    def __init__(self, bills):
        self._bills = bills

    def scalars(self):
        return self

    def all(self):
        return self._bills

    def scalar_one_or_none(self):
        return self._bills[0] if self._bills else None


class _FakeDb:
    def __init__(self, bills):
        self._bills = bills
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _ScalarRows(self._bills)


class _EmptyMappings:
    def mappings(self):
        return []


class _SqlCaptureDb:
    def __init__(self):
        self.statement = None

    async def execute(self, statement, _params):
        self.statement = str(statement)
        return _EmptyMappings()


def _bill(*, bill_id: str, source: str):
    return SimpleNamespace(
        id=bill_id,
        title_el="Test bill",
        title_en=None,
        status=BillStatus.OPEN_END,
        source=source,
    )


def _result_bill(*, bill_id: str, source: str):
    return SimpleNamespace(
        id=bill_id,
        title_el="Test bill",
        title_en=None,
        status=BillStatus.OPEN_END,
        source=source,
        pill_el=None,
        summary_short_el=None,
        summary_long_el=None,
        analysis_el=None,
        ai_summary_reviewed=False,
        parliament_url=None,
        diavgeia_ada="Ρ9Ζ546ΜΤΛΒ-Η" if source == "DIAVGEIA" else None,
        results_visibility="ALWAYS",
        party_votes_parliament=None,
        parliament_vote_date=None,
        admin_hidden=False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bill_id", "source", "expected_include_zk"),
    [
        ("GR-0490a766", "PARLIAMENT", True),
        ("DIAV-Ρ9Ζ546ΜΤΛΒ-Η", "DIAVGEIA", False),
    ],
)
async def test_latest_result_uses_source_specific_vote_aggregation(
    monkeypatch,
    bill_id: str,
    source: str,
    expected_include_zk: bool,
) -> None:
    calls = []

    async def fake_aggregate(_db, received_bill_id, *, include_zk):
        calls.append((received_bill_id, include_zk))
        return VoteTotals(
            yes=2,
            no=1,
            abstain=0,
            unknown=0,
            tier1_total=3,
            zk_total=0,
        )

    monkeypatch.setattr(voting, "aggregate_bill_vote_totals", fake_aggregate)

    result = await voting.get_latest_result(
        db=_FakeDb([_bill(bill_id=bill_id, source=source)]),
    )

    assert calls == [(bill_id, expected_include_zk)]
    assert result["bill_id"] == bill_id
    assert result["total_votes"] == 3


@pytest.mark.asyncio
async def test_latest_result_query_requires_real_tier1_or_parliament_zk_votes() -> None:
    db = _FakeDb([])

    result = await voting.get_latest_result(db=db)

    statement = str(db.statement)
    assert "JOIN (SELECT citizen_votes.bill_id AS bill_id" in statement
    assert "UNION SELECT substring(zk_vote_receipts.vote_scope_id" in statement
    assert "citizen_votes.bill_id = parliament_bills.id" in statement
    assert "zk_vote_receipts.vote_scope_id = concat" in statement.lower()
    assert "coalesce(parliament_bills.source" in statement.lower()
    assert "PARLIAMENT" in db.statement.compile().params.values()
    assert result == {"bill_id": None, "total_votes": 0}


@pytest.mark.asyncio
async def test_bill_result_uses_tier1_only_for_diavgeia(monkeypatch) -> None:
    bill_id = "DIAV-Ρ9Ζ546ΜΤΛΒ-Η"

    async def fake_aggregate(_db, received_bill_id, *, include_zk):
        assert received_bill_id == bill_id
        assert include_zk is False
        return VoteTotals(
            yes=1,
            no=0,
            abstain=0,
            unknown=0,
            tier1_total=1,
            zk_total=0,
        )

    monkeypatch.setattr(voting, "is_public_bill", lambda _bill: True)
    monkeypatch.setattr(voting, "aggregate_bill_vote_totals", fake_aggregate)

    result = await voting.get_results(
        bill_id,
        db=_FakeDb([_result_bill(bill_id=bill_id, source="DIAVGEIA")]),
    )

    assert result.total_votes == 1
    assert result.tier1_vote_count == 1
    assert result.zk_vote_count == 0


@pytest.mark.asyncio
async def test_in_progress_zk_join_is_limited_to_parliament_sources(monkeypatch) -> None:
    monkeypatch.setenv("VOTES_IN_PROGRESS_THRESHOLD", "1")
    db = _SqlCaptureDb()

    result = await voting.get_votes_in_progress(db=db)

    assert "COALESCE(b.source, 'PARLIAMENT') = 'PARLIAMENT'" in db.statement
    assert result["count"] == 0
