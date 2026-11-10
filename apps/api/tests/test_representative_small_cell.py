"""Representative endpoints use public small-cell rules for citizen signals."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from database import get_db
from models import BillStatus
from routers import representative
from services.zk_vote_aggregation import VoteTotals


class Result:
    def __init__(self, rows=(), scalar=None):
        self.rows = list(rows)
        self.scalar = scalar

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)


class RepresentativeDb:
    def __init__(self, bill, timeline=()):
        self.bill = bill
        self.timeline = list(timeline)
        self.calls = 0

    async def execute(self, *_args, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return Result(rows=[self.bill], scalar=self.bill)
        if self.calls == 2:
            return Result(rows=self.timeline)
        return Result(rows=[self.bill])


def bill_fixture(*, consensus_count=3, consensus_score=4.5):
    return SimpleNamespace(
        id="REP-SMALL-CELL",
        title_el="Δοκιμαστικό νομοσχέδιο",
        status=BillStatus.OPEN_END,
        source="PARLIAMENT",
        governance_level=None,
        party_votes_parliament={"Α": "YES", "Β": "NO"},
        parliament_vote_date=None,
        consensus_count=consensus_count,
        consensus_score=consensus_score,
    )


def app_for(db):
    app = FastAPI()
    app.include_router(representative.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[representative.verify_rep_token] = lambda: {"role": "Βουλευτής"}
    return app


def totals_below_k():
    return VoteTotals(1, 0, 0, 0, 1, 0, sources=((1, 0, 0, 0),))


def totals_publishable():
    return VoteTotals(10, 10, 10, 10, 40, 0, sources=((10, 10, 10, 10),))


def totals_small_zk_partition():
    # Combined and Tier-1 choices meet k, but one present ZK source cell does not.
    return VoteTotals(
        11, 10, 10, 10, 40, 1,
        sources=((10, 10, 10, 10), (1, 0, 0, 0)),
    )


async def call_endpoint(monkeypatch, *, path, totals, db):
    async def aggregate(*_args, **_kwargs):
        return totals

    monkeypatch.setattr(representative, "aggregate_bill_vote_totals", aggregate)
    monkeypatch.setattr(representative, "is_bill_visible_for_token", lambda *_: True)
    monkeypatch.setattr(representative, "include_zk_for_bill", lambda _bill: True)
    app = app_for(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["results", "divergence"])
async def test_representative_one_vote_is_suppressed(monkeypatch, endpoint):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    db = RepresentativeDb(bill_fixture())
    data = await call_endpoint(
        monkeypatch,
        path=f"/api/v1/rep/{endpoint}/REP-SMALL-CELL",
        totals=totals_below_k(),
        db=db,
    )

    assert data["suppressed"] is True
    assert data["suppression_k"] == 10
    if endpoint == "results":
        for key in (
            "yes", "no", "abstain", "unknown", "total", "tier1_total", "zk_total",
            "yes_pct", "no_pct", "abstain_pct", "unknown_pct",
        ):
            assert data[key] is None
        assert data["timeline"] == []
    else:
        assert data["citizen"] == {
            "yes_pct": None, "total": None, "tier1_total": None, "zk_total": None,
        }
        assert data["divergence_pct"] is None
        assert data["parliament"]["total"] == 2
        assert data["parliament"]["yes_pct"] == 50


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["results", "divergence"])
async def test_representative_publishable_bill_keeps_values(monkeypatch, endpoint):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    data = await call_endpoint(
        monkeypatch,
        path=f"/api/v1/rep/{endpoint}/REP-SMALL-CELL",
        totals=totals_publishable(),
        db=RepresentativeDb(bill_fixture(consensus_count=10)),
    )
    assert data["suppressed"] is False
    assert data["suppression_k"] == 10
    if endpoint == "results":
        assert (data["yes"], data["no"], data["total"]) == (10, 10, 40)
        assert data["yes_pct"] == 25
    else:
        assert data["citizen"]["yes_pct"] == 25
        assert data["citizen"]["total"] == 40
        assert data["divergence_pct"] == 25


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["results", "divergence"])
async def test_representative_small_zk_source_suppresses_complete_result(monkeypatch, endpoint):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    data = await call_endpoint(
        monkeypatch,
        path=f"/api/v1/rep/{endpoint}/REP-SMALL-CELL",
        totals=totals_small_zk_partition(),
        db=RepresentativeDb(bill_fixture()),
    )
    assert data["suppressed"] is True
    if endpoint == "results":
        assert all(data[key] is None for key in (
            "yes", "no", "abstain", "unknown", "total", "tier1_total", "zk_total",
            "yes_pct", "no_pct", "abstain_pct", "unknown_pct",
        ))
        assert data["timeline"] == []
    else:
        assert all(data["citizen"][key] is None for key in (
            "yes_pct", "total", "tier1_total", "zk_total",
        ))
        assert data["divergence_pct"] is None


@pytest.mark.asyncio
async def test_representative_legacy_payload_is_unchanged_when_k_is_zero(monkeypatch):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
    hour = datetime(2026, 11, 10, 10, tzinfo=timezone.utc)
    rows = [(hour, "YES", 1)]
    totals = totals_below_k()
    db = RepresentativeDb(bill_fixture(), timeline=rows)
    results = await call_endpoint(
        monkeypatch, path="/api/v1/rep/results/REP-SMALL-CELL", totals=totals, db=db,
    )
    assert results == {
        "bill_id": "REP-SMALL-CELL",
        "title_el": "Δοκιμαστικό νομοσχέδιο",
        "status": "OPEN_END",
        "yes": 1, "no": 0, "abstain": 0, "unknown": 0, "total": 1,
        "tier1_total": 1, "zk_total": 0,
        "yes_pct": 100, "no_pct": 0, "abstain_pct": 0, "unknown_pct": 0,
        "consensus_score": 4.5, "consensus_count": 3,
        "party_votes": {"Α": "YES", "Β": "NO"},
        "timeline": [{
            "hour": hour.isoformat(), "yes": 1, "no": 0, "abstain": 0, "unknown": 0,
        }],
    }

    divergence = await call_endpoint(
        monkeypatch, path="/api/v1/rep/divergence/REP-SMALL-CELL", totals=totals,
        db=RepresentativeDb(bill_fixture()),
    )
    assert divergence == {
        "bill_id": "REP-SMALL-CELL",
        "title_el": "Δοκιμαστικό νομοσχέδιο",
        "citizen": {"yes_pct": 100, "total": 1, "tier1_total": 1, "zk_total": 0},
        "parliament": {
            "yes_pct": 50, "total": 2, "parties": {"Α": "YES", "Β": "NO"},
        },
        "divergence_pct": 50,
        "governance_level": "NATIONAL",
    }


@pytest.mark.asyncio
async def test_representative_bill_list_legacy_payload_is_unchanged_when_k_is_zero(monkeypatch):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "0")
    data = await call_endpoint(
        monkeypatch, path="/api/v1/rep/bills", totals=totals_publishable(),
        db=RepresentativeDb(bill_fixture()),
    )
    assert data == [{
        "id": "REP-SMALL-CELL",
        "title_el": "Δοκιμαστικό νομοσχέδιο",
        "status": "OPEN_END",
        "source": "PARLIAMENT",
        "governance_level": "NATIONAL",
        "parliament_vote_date": None,
        "consensus_score": 4.5,
        "consensus_count": 3,
    }]


@pytest.mark.asyncio
async def test_publishable_bill_hides_small_hourly_timeline_partition(monkeypatch):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    hour = datetime(2026, 11, 10, 10, tzinfo=timezone.utc)
    rows = [(hour, "YES", 1), (hour, "NO", 12)]
    data = await call_endpoint(
        monkeypatch,
        path="/api/v1/rep/results/REP-SMALL-CELL",
        totals=totals_publishable(),
        db=RepresentativeDb(bill_fixture(consensus_count=10), timeline=rows),
    )
    assert data["yes"] == 10
    assert data["timeline"]
    assert all(
        row[key] is None
        for row in data["timeline"]
        for key in ("yes", "no", "abstain", "unknown", "total")
    )


@pytest.mark.asyncio
async def test_timeline_hidden_when_votes_before_window_form_a_small_cell(monkeypatch):
    # Every 48h bucket meets k, but published totals minus the window would
    # reveal 5 older YES votes (and 0 older others).
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    hour = datetime(2026, 11, 10, 10, tzinfo=timezone.utc)
    rows = [(hour, "YES", 15), (hour, "NO", 20), (hour, "ABSTAIN", 20), (hour, "UNKNOWN", 20)]
    data = await call_endpoint(
        monkeypatch,
        path="/api/v1/rep/results/REP-SMALL-CELL",
        totals=VoteTotals(20, 20, 20, 20, 80, 0, sources=((20, 20, 20, 20),)),
        db=RepresentativeDb(bill_fixture(consensus_count=10), timeline=rows),
    )
    assert data["yes"] == 20
    assert all(row["yes"] is None and row["total"] is None for row in data["timeline"])


@pytest.mark.asyncio
async def test_timeline_visible_when_window_holds_all_votes_and_cells_meet_k(monkeypatch):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    hour = datetime(2026, 11, 10, 10, tzinfo=timezone.utc)
    rows = [(hour, "YES", 20), (hour, "NO", 20), (hour, "ABSTAIN", 20), (hour, "UNKNOWN", 20)]
    data = await call_endpoint(
        monkeypatch,
        path="/api/v1/rep/results/REP-SMALL-CELL",
        totals=VoteTotals(20, 20, 20, 20, 80, 0, sources=((20, 20, 20, 20),)),
        db=RepresentativeDb(bill_fixture(consensus_count=10), timeline=rows),
    )
    assert [(r["yes"], r["no"], r["total"]) for r in data["timeline"]] == [(20, 20, 80)]


@pytest.mark.asyncio
async def test_representative_consensus_signals_are_suppressed_below_k(monkeypatch):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    data = await call_endpoint(
        monkeypatch,
        path="/api/v1/rep/results/REP-SMALL-CELL",
        totals=totals_publishable(),
        db=RepresentativeDb(bill_fixture(consensus_count=1)),
    )
    assert data["consensus_score"] is None and data["consensus_count"] is None
    assert data["consensus_suppressed"] is True


@pytest.mark.asyncio
async def test_representative_bill_list_suppresses_small_consensus_signal(monkeypatch):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    bill = bill_fixture(consensus_count=1)
    db = RepresentativeDb(bill)
    data = await call_endpoint(
        monkeypatch, path="/api/v1/rep/bills", totals=totals_publishable(), db=db,
    )
    assert len(data) == 1
    assert data[0]["consensus_score"] is None and data[0]["consensus_count"] is None
    assert data[0]["consensus_suppressed"] is True
