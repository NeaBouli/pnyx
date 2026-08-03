import pytest
from fastapi import HTTPException

from routers.public_api import public_bills


class _Scalars:
    def all(self):
        return []


class _Result:
    def scalars(self):
        return _Scalars()


class _Db:
    def __init__(self, total):
        self.total = total
        self.executed = []

    async def scalar(self, statement):
        self.executed.append(statement)
        return self.total

    async def execute(self, statement):
        self.executed.append(statement)
        return _Result()


@pytest.mark.asyncio
async def test_public_bills_meta_reports_all_matching_rows():
    result = await public_bills(
        status=None,
        governance=None,
        source=None,
        limit=20,
        offset=40,
        _key=True,
        db=_Db(123),
    )
    assert result["data"] == []
    assert result["meta"]["total"] == 123
    assert result["meta"]["limit"] == 20
    assert result["meta"]["offset"] == 40


@pytest.mark.asyncio
async def test_public_bills_rejects_invalid_governance():
    with pytest.raises(HTTPException) as exc:
        await public_bills(
            status=None,
            governance="NOT-A-LEVEL",
            source=None,
            limit=20,
            offset=0,
            _key=True,
            db=_Db(0),
        )
    assert exc.value.status_code == 400
