import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services import discourse_sync
from services.diavgeia_scraper import _clean_org_label


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        data: dict | None = None,
        text: str = "",
        headers: dict | None = None,
    ):
        self.status_code = status_code
        self._data = data or {}
        self.text = text
        self.headers = headers or {}

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


@pytest.mark.parametrize("raw,expected", [
    (None, None),
    ("", None),
    ("   ", None),
    ("unknown", None),
    ("[unknown:99999]", None),
    ("ΕΦΚΑ", "ΕΦΚΑ"),
    ("  ΥΠΕΞ  ", "ΥΠΕΞ"),
])
def test_clean_org_label(raw, expected):
    """NEA-268: _clean_org_label filters bad values."""
    assert _clean_org_label(raw) == expected


def test_unique_title_suffix_prefers_ada_and_preserves_limit():
    bill = SimpleNamespace(id="DIAV-123", diavgeia_ada="ΨΙΗΕ465ΕΦ5-Λ")
    title = "[Φορέας] " + "Α" * 280

    result = discourse_sync._with_unique_title_suffix(title, bill)

    assert result.endswith(" — ΨΙΗΕ465ΕΦ5-Λ")
    assert len(result) == 255


def test_topic_body_uses_analysis_el_not_summary_long_as_analysis():
    """GH#103/GH#105: forum body must render distinct analysis_el, not summary_long_el."""
    bill = SimpleNamespace(
        id="GR-TEST",
        title_el="Δοκιμαστικό νομοσχέδιο",
        summary_short_el="Σύντομη σύνοψη.",
        analysis_el="Ξεχωριστή ανάλυση από το νέο πεδίο.",
        pill_el=None,
        summary_long_el="Νομοθετική Διαδικασία BOILERPLATE ΠΟΥ ΔΕΝ ΠΡΕΠΕΙ ΝΑ ΕΜΦΑΝΙΣΤΕΙ",
        ai_summary_reviewed=True,
        status=SimpleNamespace(value="OPEN_END"),
        governance_level=SimpleNamespace(value="NATIONAL"),
        source="PARLIAMENT",
        diavgeia_ada=None,
        parliament_url=None,
        official_source_url=None,
        forum_topic_id=123,
        forum_topic_url="https://pnyx.ekklesia.gr/t/123",
        periferia_id=None,
        dimos_id=None,
    )

    body = discourse_sync._build_topic_body(bill)

    assert "## Περίληψη\nΣύντομη σύνοψη." in body
    assert "## Ανάλυση\nΞεχωριστή ανάλυση από το νέο πεδίο." in body
    assert "BOILERPLATE" not in body


def test_topic_body_renders_clean_official_text_as_own_section():
    """GH#103: official text/PDF links belong in their own section, never in analysis."""
    bill = SimpleNamespace(
        id="GR-TEST",
        title_el="Δοκιμαστικό νομοσχέδιο",
        summary_short_el="Σύντομη σύνοψη.",
        analysis_el="Ξεχωριστή ανάλυση.",
        pill_el=None,
        summary_long_el=(
            "### Αιτιολογική Έκθεση — κύρια σημεία\n"
            "Σκοπός του νόμου είναι η δοκιμή.\n\n"
            "### Πλήρη έγγραφα\n"
            "- [Αιτιολογική Έκθεση](https://www.hellenicparliament.gr/UserFiles/x/test.pdf)"
        ),
        ai_summary_reviewed=False,
        status=SimpleNamespace(value="OPEN_END"),
        governance_level=SimpleNamespace(value="NATIONAL"),
        source="PARLIAMENT",
        diavgeia_ada=None,
        parliament_url=None,
        official_source_url=None,
        forum_topic_id=123,
        forum_topic_url="https://pnyx.ekklesia.gr/t/123",
        periferia_id=None,
        dimos_id=None,
    )

    body = discourse_sync._build_topic_body(bill)

    assert "## Ανάλυση\nΞεχωριστή ανάλυση." in body
    assert "## Επίσημο κείμενο και έγγραφα" in body
    assert "[Αιτιολογική Έκθεση](https://www.hellenicparliament.gr/UserFiles/x/test.pdf)" in body


def test_topic_body_hides_access_denial_but_keeps_parliament_documents():
    bill = SimpleNamespace(
        id="GR-DENIED",
        title_el="Δοκιμαστικό νομοσχέδιο",
        summary_short_el="Σύντομη σύνοψη.",
        analysis_el=None,
        pill_el=None,
        summary_long_el=(
            "You don't have permission to access '/' on this server. "
            "Reference #18.63c7cf17.1783640051.9520c14\n\n"
            "### Πλήρη έγγραφα\n"
            "- [Έγγραφο Βουλής](https://www.hellenicparliament.gr/UserFiles/x/test.pdf)"
        ),
        ai_summary_reviewed=False,
        status=SimpleNamespace(value="OPEN_END"),
        governance_level=SimpleNamespace(value="NATIONAL"),
        source="PARLIAMENT",
        diavgeia_ada=None,
        parliament_url=None,
        official_source_url=None,
        forum_topic_id=123,
        forum_topic_url="https://pnyx.ekklesia.gr/t/123",
        periferia_id=None,
        dimos_id=None,
    )

    body = discourse_sync._build_topic_body(bill)

    assert "permission to access" not in body
    assert "Reference #" not in body
    assert "[Έγγραφο Βουλής](https://www.hellenicparliament.gr/UserFiles/x/test.pdf)" in body


def test_diavgeia_topic_body_renders_document_link():
    """DIAVGEIA forum topics must expose the decision document, not only the ADA page."""
    bill = SimpleNamespace(
        id="DIAV-98Κ3469Β7Δ-Α",
        title_el="Ανάκληση απόφασης",
        summary_short_el="Σύντομη περίληψη.",
        analysis_el=None,
        pill_el=None,
        summary_long_el=None,
        ai_summary_reviewed=False,
        status=SimpleNamespace(value="OPEN_END"),
        governance_level=SimpleNamespace(value="INSTITUTIONAL"),
        source="DIAVGEIA",
        diavgeia_ada="98Κ3469Β7Δ-ΑΥΦ",
        parliament_url="https://diavgeia.gov.gr/doc/98Κ3469Β7Δ-ΑΥΦ",
        official_source_url=None,
        forum_topic_id=1104,
        forum_topic_url="https://pnyx.ekklesia.gr/t/1104",
        periferia_id=None,
        dimos_id=None,
    )

    body = discourse_sync._build_topic_body(bill)

    assert "## Περίληψη\nΣύντομη περίληψη." in body
    assert "| **ΑΔΑ** | [98Κ3469Β7Δ-ΑΥΦ](https://diavgeia.gov.gr/decision/view/98Κ3469Β7Δ-ΑΥΦ) |" in body
    assert "## Πλήρες έγγραφο" in body
    assert "[Κατεβάστε/διαβάστε την απόφαση στη Διαύγεια →](https://diavgeia.gov.gr/doc/98Κ3469Β7Δ-ΑΥΦ)" in body


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
    assert bill.generated_content_provenance.get("forum_body")


@pytest.mark.asyncio
@pytest.mark.parametrize("body_matches", [True, False])
async def test_duplicate_topic_adopts_only_identical_generated_body(monkeypatch, body_matches):
    bill = _forum_bill("Αυτόματη σύνοψη.")
    generated_body = discourse_sync._build_topic_body(bill)

    async def fake_request(_client, method, url, **_kwargs):
        if method == "get" and "/t/321.json" in url:
            return FakeResponse(200, {"post_stream": {"posts": [{"id": 654}]}})
        if method == "get" and "/posts/654.json" in url:
            raw = generated_body if body_matches else "Χειροκίνητη παρέμβαση"
            return FakeResponse(200, {"raw": raw})
        raise AssertionError((method, url))

    monkeypatch.setattr(discourse_sync, "_request_discourse", fake_request)

    await discourse_sync._record_matching_existing_topic_body(
        object(),
        321,
        bill,
        generated_body,
    )

    provenance = getattr(bill, "generated_content_provenance", None) or {}
    assert bool(provenance.get("forum_body")) is body_matches


def _forum_bill(summary: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="GR-PROVENANCE",
        title_el="Δοκιμή προέλευσης",
        summary_short_el=summary,
        analysis_el=None,
        pill_el=None,
        summary_long_el=(
            "### Πλήρη έγγραφα\n"
            "- [Έγγραφο](https://www.hellenicparliament.gr/UserFiles/x/test.pdf)"
        ),
        ai_summary_reviewed=False,
        status=SimpleNamespace(value="ACTIVE"),
        governance_level=SimpleNamespace(value="NATIONAL"),
        source="PARLIAMENT",
        diavgeia_ada=None,
        parliament_url="https://www.hellenicparliament.gr/test",
        official_source_url=None,
        forum_topic_id=123,
        forum_topic_url="https://pnyx.ekklesia.gr/t/123",
        periferia_id=None,
        dimos_id=None,
        generated_content_provenance=None,
    )


@pytest.mark.asyncio
async def test_update_topic_refreshes_owned_body_and_keeps_pdf_block(monkeypatch):
    from services.content_provenance import FORUM_BODY_FIELD, record_generated_content

    bill = _forum_bill("Παλιά αυτόματη σύνοψη.")
    old_body = discourse_sync._build_topic_body(bill)
    record_generated_content(bill, FORUM_BODY_FIELD, old_body)
    bill.summary_short_el = "Νέα αυτόματη σύνοψη."
    calls = []

    async def fake_resolve_category(_bill, _db):
        return 42

    async def fake_region(_bill, _db):
        return ""

    async def fake_title(_bill, _db):
        return "[Βουλή] Δοκιμή προέλευσης"

    async def fake_request(_client, method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        if method == "put" and "/t/-/" in url:
            return FakeResponse(200)
        if method == "get" and "/t/123.json" in url:
            return FakeResponse(200, {"post_stream": {"posts": [{"id": 55}]}})
        if method == "get" and "/posts/55.json" in url:
            return FakeResponse(200, {"raw": old_body})
        if method == "put" and "/posts/55.json" in url:
            return FakeResponse(200)
        raise AssertionError((method, url))

    monkeypatch.setattr(discourse_sync, "_resolve_category", fake_resolve_category)
    monkeypatch.setattr(discourse_sync, "_region_name_for_body", fake_region)
    monkeypatch.setattr(discourse_sync, "_build_topic_title", fake_title)
    monkeypatch.setattr(discourse_sync, "_request_discourse", fake_request)
    monkeypatch.setattr(discourse_sync, "DISCOURSE_API_KEY", "test-key")

    result = await discourse_sync.update_discourse_topic(bill, db=None)
    assert result is True, calls

    body_updates = [call for call in calls if call[0] == "put" and "/posts/55.json" in call[1]]
    assert len(body_updates) == 1
    new_body = body_updates[0][2]["post"]["raw"]
    assert "Νέα αυτόματη σύνοψη." in new_body
    assert "https://www.hellenicparliament.gr/UserFiles/x/test.pdf" in new_body


@pytest.mark.asyncio
async def test_scheduled_sync_refreshes_changed_owned_existing_topic(monkeypatch):
    from services.content_provenance import FORUM_BODY_FIELD, record_generated_content

    bill = _forum_bill("Παλιά αυτόματη σύνοψη.")
    record_generated_content(bill, FORUM_BODY_FIELD, discourse_sync._build_topic_body(bill))
    bill.summary_short_el = "Νέα αυτόματη σύνοψη."
    updated: list[str] = []

    class ScalarRows:
        @staticmethod
        def all():
            return [bill]

    class QueryResult:
        @staticmethod
        def scalars():
            return ScalarRows()

    class CountResult:
        @staticmethod
        def scalar_one():
            return 1

    class Db:
        commits = 0
        executes = 0

        async def execute(self, _query):
            self.executes += 1
            if self.executes == 1:
                return CountResult()
            return QueryResult()

        async def commit(self):
            self.commits += 1

    async def fake_region(_bill, _db):
        return ""

    async def fake_update(target, _db):
        updated.append(target.id)
        return True

    monkeypatch.setattr(discourse_sync, "_region_name_for_body", fake_region)
    monkeypatch.setattr(discourse_sync, "update_discourse_topic", fake_update)
    monkeypatch.setattr(discourse_sync, "FORUM_SYNC_TOPIC_DELAY_SECONDS", 0)
    db = Db()

    stats = await discourse_sync.sync_changed_bills_to_forum(db)

    assert stats == {
        "total": 1,
        "offset": 0,
        "scanned": 1,
        "refreshed": 1,
        "failed": 0,
    }
    assert updated == [bill.id]
    assert db.commits == 1


def test_forum_refresh_offset_rotates_first_attempt_across_candidates(monkeypatch):
    monkeypatch.setattr(discourse_sync, "FORUM_REFRESH_SCAN", 40)
    monkeypatch.setattr(discourse_sync, "FORUM_REFRESH_BATCH", 2)
    monkeypatch.setattr(discourse_sync, "FORUM_REFRESH_INTERVAL_SECONDS", 600)

    offsets = [
        discourse_sync._forum_refresh_offset(6, now=slot * 600)
        for slot in range(3)
    ]

    assert offsets == [0, 2, 4]
    attempted = {
        candidate
        for offset in offsets
        for candidate in (offset, (offset + 1) % 6)
    }
    assert attempted == set(range(6))


@pytest.mark.asyncio
@pytest.mark.parametrize("with_provenance", [False, True])
async def test_update_topic_never_overwrites_legacy_or_manually_edited_body(
    monkeypatch, with_provenance
):
    from services.content_provenance import FORUM_BODY_FIELD, record_generated_content

    bill = _forum_bill("Αυτόματη σύνοψη.")
    generated_body = discourse_sync._build_topic_body(bill)
    if with_provenance:
        record_generated_content(bill, FORUM_BODY_FIELD, generated_body)
    current_raw = "Χειροκίνητη παρέμβαση συντονιστή" if with_provenance else generated_body
    calls = []

    async def fake_resolve_category(_bill, _db):
        return 42

    async def fake_region(_bill, _db):
        return ""

    async def fake_title(_bill, _db):
        return "[Βουλή] Δοκιμή προέλευσης"

    async def fake_request(_client, method, url, **kwargs):
        calls.append((method, url))
        if method == "put" and "/t/-/" in url:
            return FakeResponse(200)
        if method == "get" and "/t/123.json" in url:
            return FakeResponse(200, {"post_stream": {"posts": [{"id": 55}]}})
        if method == "get" and "/posts/55.json" in url:
            return FakeResponse(200, {"raw": current_raw})
        raise AssertionError((method, url))

    monkeypatch.setattr(discourse_sync, "_resolve_category", fake_resolve_category)
    monkeypatch.setattr(discourse_sync, "_region_name_for_body", fake_region)
    monkeypatch.setattr(discourse_sync, "_build_topic_title", fake_title)
    monkeypatch.setattr(discourse_sync, "_request_discourse", fake_request)
    monkeypatch.setattr(discourse_sync, "DISCOURSE_API_KEY", "test-key")

    result = await discourse_sync.update_discourse_topic(bill, db=None)
    assert result is True, calls
    assert not any(method == "put" and "/posts/55.json" in url for method, url in calls)
    assert not bill.generated_content_provenance


@pytest.mark.asyncio
async def test_discourse_request_retries_after_rate_limit(monkeypatch):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    class RateLimitedClient:
        def __init__(self):
            self.calls = 0

        async def post(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return FakeResponse(429, {"extras": {"wait_seconds": 1}})
            return FakeResponse(200, {"ok": True})

    monkeypatch.setattr(discourse_sync.asyncio, "sleep", fake_sleep)
    client = RateLimitedClient()

    response = await discourse_sync._request_discourse(
        client, "post", "https://pnyx.ekklesia.gr/posts.json", json={}, headers={}
    )

    assert response.status_code == 200
    assert client.calls == 2
    assert sleeps == [2.0]


@pytest.mark.asyncio
async def test_institutional_title_includes_org_label(monkeypatch):
    """NEA-268: INSTITUTIONAL bills with org_label get [Φορέας X] prefix."""
    bill = SimpleNamespace(
        id="DIAV-456",
        title_el="ΠΡΟΣΛΗΨΗ ΠΡΟΣΩΠΙΚΟΥ",
        summary_short_el=None,
        pill_el=None,
        summary_long_el=None,
        status=SimpleNamespace(value="OPEN_END"),
        governance_level=SimpleNamespace(value="INSTITUTIONAL"),
        source="DIAVGEIA",
        diavgeia_ada="ΩΑΒΓ465ΧΘΩ-ΔΕΖ",
        periferia_id=None,
        dimos_id=None,
        org_label="ΕΦΚΑ",
    )

    title = await discourse_sync._build_topic_title(bill, db=None)

    assert title == "[Φορέας ΕΦΚΑ] ΠΡΟΣΛΗΨΗ ΠΡΟΣΩΠΙΚΟΥ"


@pytest.mark.asyncio
async def test_institutional_title_without_org_label_falls_back(monkeypatch):
    """NEA-268: INSTITUTIONAL bills without org_label still get [Φορέας]."""
    bill = SimpleNamespace(
        id="DIAV-789",
        title_el="ΑΠΟΦΑΣΗ ΔΙΟΙΚΗΤΗ",
        summary_short_el=None,
        pill_el=None,
        summary_long_el=None,
        status=SimpleNamespace(value="OPEN_END"),
        governance_level=SimpleNamespace(value="INSTITUTIONAL"),
        source="DIAVGEIA",
        diavgeia_ada="ΨΩΑΒ465ΧΘΩ-ΗΙΚ",
        periferia_id=None,
        dimos_id=None,
        org_label=None,
    )

    title = await discourse_sync._build_topic_title(bill, db=None)

    assert title == "[Φορέας] ΑΠΟΦΑΣΗ ΔΙΟΙΚΗΤΗ"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_label", [
    "[unknown:99999]",
    "unknown",
    "  ",
    "",
])
async def test_institutional_title_filters_bad_org_labels(bad_label):
    """NEA-268: unknown/blank org_label must not leak into forum titles."""
    bill = SimpleNamespace(
        id="DIAV-BAD",
        title_el="ΑΠΟΦΑΣΗ",
        summary_short_el=None,
        pill_el=None,
        summary_long_el=None,
        status=SimpleNamespace(value="OPEN_END"),
        governance_level=SimpleNamespace(value="INSTITUTIONAL"),
        source="DIAVGEIA",
        diavgeia_ada="ΩΩΩΩ465ΧΘΩ-ΑΒΓ",
        periferia_id=None,
        dimos_id=None,
        org_label=bad_label,
    )

    title = await discourse_sync._build_topic_title(bill, db=None)

    assert title == "[Φορέας] ΑΠΟΦΑΣΗ"
