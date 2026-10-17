import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import diavgeia_scraper as scraper


@pytest.mark.parametrize("fail", [False, True])
async def test_diavgeia_run_counts_are_logged_on_success_and_failure(monkeypatch, caplog, fail):
    caplog.set_level(logging.INFO)

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def iter_decisions(self, **kwargs):
            if fail:
                raise RuntimeError("private-person https://private-url/?secret=value")
            yield {"subject": "private-person"}
            yield {"ada": "id", "issueDate": "private-person"}
            yield {"ada": "id", "issueDate": "2026-10-01T00:00:00Z", "subject": "private-person"}

    monkeypatch.setattr(scraper, "DiavgeiaClient", Client)
    monkeypatch.setattr(scraper, "_resolve_org", AsyncMock(return_value=(None, None, "OTHER")))
    monkeypatch.setattr(scraper, "get_org_label", lambda uid: "Organization")
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)))
    if fail:
        with pytest.raises(RuntimeError):
            await scraper.scrape_decisions(db, decision_type_uids=["Α.2"], dry_run=True)
        assert "fetched=0 skipped=0 failed=1" in caplog.text
    else:
        result = await scraper.scrape_decisions(db, decision_type_uids=["Α.2"], dry_run=True)
        assert result.fetched == 3 and result.skipped == 2 and result.inserted == 1
        assert "fetched=3 skipped=2 failed=0" in caplog.text
    assert "private-person" not in caplog.text and "secret=value" not in caplog.text
