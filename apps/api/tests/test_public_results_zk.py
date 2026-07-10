from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers import public_api
from services.zk_vote_aggregation import VoteTotals


class FakeDb:
    def __init__(self, bill):
        self.bill = bill

    async def get(self, _model, _bill_id):
        return self.bill

    async def scalar(self, *_args, **_kwargs):
        raise AssertionError("public results must use aggregate_bill_vote_totals")


def _bill(**overrides):
    values = {
        "id": "GR-d4c62ed4",
        "title_el": "Κύρωση Κώδικα Χωροταξίας - Πολεοδομίας",
        "status": SimpleNamespace(value="OPEN_END"),
        "party_votes_parliament": None,
        "arweave_tx_id": None,
        "admin_hidden": False,
        "source": "PARLIAMENT",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_public_bill_results_aggregate_zk_receipts(monkeypatch):
    async def fake_aggregate(_db, bill_id):
        assert bill_id == "GR-d4c62ed4"
        return VoteTotals(
            yes=1,
            no=0,
            abstain=1,
            unknown=0,
            tier1_total=1,
            zk_total=1,
        )

    monkeypatch.setattr(public_api, "is_public_bill", lambda _bill: True)
    monkeypatch.setattr(public_api, "aggregate_bill_vote_totals", fake_aggregate)

    result = await public_api.public_bill_results(
        "GR-d4c62ed4",
        _key=True,
        db=FakeDb(_bill()),
    )

    assert result["citizen_votes"] == {
        "yes": 1,
        "no": 0,
        "abstain": 1,
        "unknown": 0,
        "total": 2,
        "tier1_total": 1,
        "zk_total": 1,
        "yes_pct": 50.0,
        "no_pct": 0.0,
        "abstain_pct": 50.0,
    }


@pytest.mark.asyncio
async def test_public_bill_results_hidden_bill_does_not_aggregate(monkeypatch):
    async def fake_aggregate(_db, _bill_id):
        raise AssertionError("hidden bills must not aggregate results")

    monkeypatch.setattr(public_api, "is_public_bill", lambda _bill: False)
    monkeypatch.setattr(public_api, "aggregate_bill_vote_totals", fake_aggregate)

    with pytest.raises(HTTPException) as exc:
        await public_api.public_bill_results(
            "GR-hidden",
            _key=True,
            db=FakeDb(_bill(admin_hidden=True)),
        )

    assert exc.value.status_code == 404
