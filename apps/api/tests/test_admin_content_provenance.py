from types import SimpleNamespace

import pytest

from routers.admin import (
    BillUpdateRequest,
    admin_review_summary,
    admin_update_bill,
)
from services.content_provenance import content_sha256, record_generated_content


class _FakeDb:
    def __init__(self, bill):
        self.bill = bill
        self.committed = False

    async def get(self, *_args):
        return self.bill

    async def commit(self):
        self.committed = True


def _bill():
    bill = SimpleNamespace(
        pill_el="Αυτόματο pill",
        summary_short_el="Αυτόματη σύνοψη",
        generated_content_provenance=None,
        ai_summary_reviewed=False,
    )
    record_generated_content(bill, "pill_el", bill.pill_el)
    record_generated_content(bill, "summary_short_el", bill.summary_short_el)
    return bill


@pytest.mark.asyncio
async def test_admin_summary_edit_revokes_only_that_field_ownership():
    bill = _bill()
    db = _FakeDb(bill)

    result = await admin_update_bill(
        "GR-TEST",
        BillUpdateRequest(summary_short_el="Χειροκίνητη σύνοψη"),
        _key=True,
        db=db,
    )

    assert result["updated"] == ["summary_short_el"]
    assert bill.summary_short_el == "Χειροκίνητη σύνοψη"
    assert bill.generated_content_provenance == {
        "pill_el": content_sha256("Αυτόματο pill")
    }
    assert db.committed is True


@pytest.mark.asyncio
async def test_review_approval_revokes_all_summary_ownership():
    bill = _bill()
    db = _FakeDb(bill)

    result = await admin_review_summary("GR-TEST", approved=True, _key=True, db=db)

    assert result["reviewed"] is True
    assert bill.ai_summary_reviewed is True
    assert bill.generated_content_provenance is None
    assert db.committed is True
