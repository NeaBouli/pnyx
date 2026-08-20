from datetime import datetime
from types import SimpleNamespace

import pytest

from models import BillStatus, VoteChoice
from routers.export import get_all_results


class _ScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _VoteRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Session:
    def __init__(self, bills, votes):
        self._results = [_ScalarRows(bills), _VoteRows(votes)]
        self.execute_count = 0

    async def execute(self, _statement):
        result = self._results[self.execute_count]
        self.execute_count += 1
        return result


def _bill(bill_id: str, party_votes=None):
    return SimpleNamespace(
        id=bill_id,
        title_el=f"Title {bill_id}",
        title_en="",
        categories=[],
        status=BillStatus.OPEN_END,
        parliament_vote_date=datetime(2026, 8, 20),
        party_votes_parliament=party_votes,
        arweave_tx_id=None,
    )


@pytest.mark.asyncio
async def test_get_all_results_aggregates_votes_in_two_queries():
    session = _Session(
        [_bill("with-votes"), _bill("without-votes")],
        [
            ("with-votes", VoteChoice.YES, 2),
            ("with-votes", VoteChoice.NO, 1),
        ],
    )

    rows = await get_all_results(session, min_votes=1)

    assert session.execute_count == 2
    assert [row["bill_id"] for row in rows] == ["with-votes"]
    assert rows[0]["citizen_yes"] == 2
    assert rows[0]["citizen_no"] == 1
    assert rows[0]["citizen_total"] == 3
    assert rows[0]["yes_pct"] == 66.7


@pytest.mark.asyncio
async def test_get_all_results_preserves_zero_vote_export_default():
    session = _Session([_bill("without-votes")], [])

    rows = await get_all_results(session)

    assert len(rows) == 1
    assert rows[0]["citizen_total"] == 0


@pytest.mark.asyncio
async def test_get_all_results_uses_canonical_divergence_and_counts_unknown():
    session = _Session(
        [_bill("canonical", {"A": "ΝΑΙ", "B": "ΟΧΙ"})],
        [
            ("canonical", VoteChoice.YES, 1),
            ("canonical", VoteChoice.UNKNOWN, 1),
        ],
    )

    rows = await get_all_results(session, min_votes=2)

    assert rows[0]["citizen_unknown"] == 1
    assert rows[0]["citizen_total"] == 2
    assert rows[0]["parliament_result"] == "REJECTED"
    assert rows[0]["divergence_score"] == 0.5
