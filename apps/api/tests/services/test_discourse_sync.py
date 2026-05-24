import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services import discourse_sync


class FakeResponse:
    def __init__(self, status_code: int, data: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self) -> dict:
        return self._data


class FakeAsyncClient:
    posts: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url: str, json: dict, headers: dict):
        self.posts.append(json)
        if len(self.posts) == 1:
            return FakeResponse(422, text="Τίτλος έχει ήδη χρησιμοποιηθεί")
        return FakeResponse(200, {"topic_id": 987})


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_unique_title_suffix_prefers_ada_and_preserves_limit():
    bill = SimpleNamespace(id="DIAV-123", diavgeia_ada="ΨΙΗΕ465ΕΦ5-Λ")
    title = "[Φορέας] " + "Α" * 280

    result = discourse_sync._with_unique_title_suffix(title, bill)

    assert result.endswith(" — ΨΙΗΕ465ΕΦ5-Λ")
    assert len(result) == 255


@pytest.mark.asyncio
async def test_create_topic_retries_with_stable_suffix_when_duplicate_search_misses(monkeypatch):
    FakeAsyncClient.posts = []
    bill = SimpleNamespace(
        id="DIAV-123",
        title_el="ΑΝΑΘΕΣΗ ΕΡΓΟΥ",
        summary_short_el="Σύνοψη",
        pill_el=None,
        summary_long_el=None,
        status=SimpleNamespace(value="ACTIVE"),
        governance_level=SimpleNamespace(value="INSTITUTIONAL"),
        source="DIAVGEIA",
        diavgeia_ada="ΨΙΗΕ465ΕΦ5-Λ",
        periferia_id=None,
        dimos_id=None,
    )

    async def fake_resolve_category(_bill, _db):
        return 42

    async def fake_search(_title):
        return None

    monkeypatch.setattr(discourse_sync, "_resolve_category", fake_resolve_category)
    monkeypatch.setattr(discourse_sync, "_search_existing_topic", fake_search)
    monkeypatch.setattr(discourse_sync.httpx, "AsyncClient", FakeAsyncClient)

    topic_id = await discourse_sync.create_discourse_topic(bill, db=None)

    assert topic_id == 987
    assert len(FakeAsyncClient.posts) == 2
    assert FakeAsyncClient.posts[0]["title"] == "[Φορέας] ΑΝΑΘΕΣΗ ΕΡΓΟΥ"
    assert FakeAsyncClient.posts[1]["title"] == "[Φορέας] ΑΝΑΘΕΣΗ ΕΡΓΟΥ — ΨΙΗΕ465ΕΦ5-Λ"
