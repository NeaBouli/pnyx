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


@pytest.mark.asyncio
async def test_admin_creation_preserves_parliament_workflow_without_claiming_attribution(monkeypatch):
    from routers import admin, parliament
    from models import ParliamentBill
    from unittest.mock import AsyncMock

    # Both administrative endpoints must continue to inherit the workflow default.
    for module, request_type, create in (
        (admin, admin.BillCreateRequest, admin.admin_create_bill),
        (parliament, parliament.BillCreateRequest, parliament.create_bill),
    ):
        added = []
        db = SimpleNamespace(
            get=AsyncMock(return_value=None),
            execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
            add=added.append,
        )
        monkeypatch.setattr(module, 'commit_and_invalidate_representation', AsyncMock())
        await create(request_type(id='ADMIN-PROPOSAL', title_el='Τοπική πρόταση'), db=db)
        assert len(added) == 1
        # SQLAlchemy applies the default on insert; the routes must not override it.
        assert added[0].source is None
        assert added[0].parliament_url is None
        assert added[0].title_el == 'Τοπική πρόταση'
    # Importers continue to inherit the existing model default. No data migration.
    assert ParliamentBill.__table__.c.source.default.arg == 'PARLIAMENT'


@pytest.mark.asyncio
async def test_single_url_import_retains_parliament_provenance(monkeypatch):
    from routers import scraper
    from unittest.mock import AsyncMock

    added = []
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        add=added.append,
    )
    monkeypatch.setattr(scraper, 'fetch_with_fallback', AsyncMock(return_value='<p>Επίσημο κείμενο</p>'))
    monkeypatch.setattr(scraper, 'extract_bill_text', lambda _: 'Επίσημο κείμενο')
    monkeypatch.setattr(scraper, 'generate_summaries', AsyncMock(return_value={'pill_el': 'Σύνοψη'}))
    monkeypatch.setattr(scraper, 'commit_and_invalidate_representation', AsyncMock())
    url = 'https://www.hellenicparliament.gr/bill/123'
    await scraper.fetch_and_store(url=url, title_el='Τίτλος', bill_id='GR-IMPORTED', _auth=True, db=db)
    assert added[0].parliament_url == url
    assert added[0].title_el == 'Τίτλος'
    assert added[0].source is None


def test_no_code_compares_against_removed_bill_source():
    from pathlib import Path
    import re
    import subprocess

    removed_source = "LO" + "CAL"
    literal = rf"['\"]{removed_source}['\"]"
    comparison = re.compile(rf"(?:==|!=|===|!==)\s*{literal}|{literal}\s*(?:==|!=|===|!==)")
    root = Path(__file__).resolve().parents[3]
    paths = subprocess.check_output(
        ["git", "ls-files"], cwd=root, text=True,
    ).splitlines()
    matches = []
    for path in paths:
        if Path(path).suffix not in {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs"}:
            continue
        content = (root / path).read_text()
        for match in comparison.finditer(content):
            line_number = content.count("\n", 0, match.start()) + 1
            matches.append(f"{path}:{line_number}: {match.group()}")
    assert not matches, "\n".join(matches)
