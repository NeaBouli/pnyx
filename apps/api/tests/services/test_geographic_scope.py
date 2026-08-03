import pytest
from fastapi import HTTPException

from services.geographic_scope import validate_region_filter


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _Db:
    def __init__(self, values):
        self._values = list(values)
        self.calls = []

    async def execute(self, statement, params):
        self.calls.append((str(statement), params))
        return _Result(self._values.pop(0))


@pytest.mark.asyncio
async def test_valid_region_pair_passes():
    db = _Db([1, 6])
    await validate_region_filter(db, periferia_id=6, dimos_id=22)
    assert len(db.calls) == 2


@pytest.mark.asyncio
async def test_mismatched_region_pair_is_rejected():
    db = _Db([1, 7])
    with pytest.raises(HTTPException) as exc:
        await validate_region_filter(db, periferia_id=6, dimos_id=22)
    assert exc.value.status_code == 400
    assert exc.value.detail == "dimos_id does not belong to periferia_id"


@pytest.mark.asyncio
async def test_unknown_filter_ids_are_rejected():
    with pytest.raises(HTTPException, match="invalid periferia_id"):
        await validate_region_filter(_Db([None]), periferia_id=999, dimos_id=None)

    with pytest.raises(HTTPException, match="invalid dimos_id"):
        await validate_region_filter(_Db([None]), periferia_id=None, dimos_id=999)
