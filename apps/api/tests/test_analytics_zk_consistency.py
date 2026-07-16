"""Tier-1 and ZK votes must produce one canonical public statistics view."""
from datetime import datetime
from types import SimpleNamespace

import pytest

from models import BillStatus
from routers import analytics, public_api
from services.zk_vote_aggregation import VoteTotals


class _Scalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _Scalars(self._values)

    def all(self):
        return self._values


class _Db:
    def __init__(self, *, bills=None, scalar_values=None):
        self._bills = bills or []
        self._scalar_values = list(scalar_values or [])

    async def execute(self, _statement):
        return _Result(self._bills)

    async def scalar(self, _statement):
        return self._scalar_values.pop(0)


def _bill():
    return SimpleNamespace(
        id="GR-ZK-1",
        title_el="Δοκιμή",
        source="PARLIAMENT",
        status=BillStatus.PARLIAMENT_VOTED,
        party_votes_parliament={"A": "YES", "B": "YES"},
        admin_hidden=False,
    )


@pytest.mark.asyncio
async def test_divergence_uses_combined_tier1_and_zk_total():
    totals = VoteTotals(
        yes=8,
        no=1,
        abstain=0,
        unknown=1,
        tier1_total=6,
        zk_total=4,
    )
    score = await analytics.compute_divergence(_Db(), "GR-ZK-1", _bill(), totals)
    assert score == 0.2


@pytest.mark.asyncio
async def test_cumulative_representation_includes_zk_votes(monkeypatch):
    async def aggregate(_db, bill_id, *, include_zk):
        assert bill_id == "GR-ZK-1"
        assert include_zk is True
        return VoteTotals(yes=8, no=2, abstain=0, unknown=0, tier1_total=6, zk_total=4)

    monkeypatch.setattr(analytics, "aggregate_bill_vote_totals", aggregate)
    result = await analytics.compute_cumulative_representation(_Db(bills=[_bill()]))

    assert result["total_citizen_votes"] == 10
    assert result["bills"][0]["citizen_votes"] == 10
    assert result["cumulative_representation"] == 80.0


@pytest.mark.asyncio
async def test_public_representation_calls_canonical_analytics(monkeypatch):
    async def compute(_db):
        return {"cumulative_representation": 75.0}

    monkeypatch.setattr(analytics, "compute_cumulative_representation", compute)
    result = await public_api.public_representation(_key=True, db=_Db())
    assert result["cumulative_representation"] == 75.0
    assert result["data_license"] == "CC BY 4.0"


@pytest.mark.asyncio
async def test_public_stats_uses_combined_vote_counter(monkeypatch):
    async def count_votes(_db):
        return 42

    monkeypatch.setattr(public_api, "count_public_votes", count_votes)
    db = _Db(scalar_values=[10, 2, 4, 6, 3, 8, 9])
    result = await public_api.public_stats(_key=True, db=db)
    assert result["stats"]["total_votes"] == 42


@pytest.mark.asyncio
async def test_votes_timeline_exposes_unknown_votes_instead_of_hiding_them():
    row = SimpleNamespace(
        day=datetime(2026, 7, 16),
        vote="UNKNOWN",
        count=2,
    )
    result = await analytics.votes_timeline(
        days=30,
        bill_id=None,
        db=_Db(bills=[row]),
    )

    assert result["timeline"] == [{
        "date": "2026-07-16",
        "yes": 0,
        "no": 0,
        "abstain": 0,
        "unknown": 2,
        "total": 2,
    }]
