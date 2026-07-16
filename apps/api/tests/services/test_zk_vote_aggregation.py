import pytest

from models import VoteChoice
from services.zk_vote_aggregation import aggregate_bill_vote_totals, count_public_votes


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, results):
        self.results = list(results)
        self.executed = []

    async def execute(self, statement):
        self.executed.append(statement)
        return _RowsResult(self.results.pop(0))


class _ScalarDb:
    def __init__(self, values):
        self.values = list(values)
        self.statements = []

    async def scalar(self, statement):
        self.statements.append(statement)
        return self.values.pop(0)


@pytest.mark.asyncio
async def test_aggregate_bill_vote_totals_combines_tier1_and_zk_votes() -> None:
    db = _FakeDb(
        [
            [(VoteChoice.YES, 2), (VoteChoice.NO, 1)],
            [("YES", 1), ("ABSTAIN", 3), ("UNKNOWN", 1)],
        ]
    )

    totals = await aggregate_bill_vote_totals(
        db,
        "GR-0490a766",
        include_zk=True,
    )

    assert totals.yes == 3
    assert totals.no == 1
    assert totals.abstain == 3
    assert totals.unknown == 1
    assert totals.tier1_total == 3
    assert totals.zk_total == 5
    assert totals.total == 8
    assert len(db.executed) == 2


@pytest.mark.asyncio
async def test_aggregate_bill_vote_totals_handles_zk_only_bill() -> None:
    db = _FakeDb(
        [
            [],
            [("YES", 1)],
        ]
    )

    totals = await aggregate_bill_vote_totals(
        db,
        "GR-0490a766",
        include_zk=True,
    )

    assert totals.yes == 1
    assert totals.total == 1


@pytest.mark.asyncio
async def test_aggregate_bill_vote_totals_skips_zk_for_diavgeia_bill() -> None:
    db = _FakeDb(
        [
            [(VoteChoice.YES, 2), (VoteChoice.ABSTAIN, 1)],
        ]
    )

    totals = await aggregate_bill_vote_totals(
        db,
        "DIAV-Ρ9Ζ546ΜΤΛΒ-Η",
        include_zk=False,
    )

    assert totals.yes == 2
    assert totals.abstain == 1
    assert totals.tier1_total == 3
    assert totals.zk_total == 0
    assert totals.total == 3
    assert len(db.executed) == 1


@pytest.mark.asyncio
async def test_count_public_votes_combines_tier1_and_zk_with_visibility_guards() -> None:
    db = _ScalarDb([7, 3])
    total = await count_public_votes(db)

    assert total == 10
    assert len(db.statements) == 2
    compiled = " ".join(
        str(statement.compile(compile_kwargs={"literal_binds": True}))
        for statement in db.statements
    )
    assert "admin_hidden" in compiled
    assert "zk_vote_receipts" in compiled
    assert "PARLIAMENT" in compiled
