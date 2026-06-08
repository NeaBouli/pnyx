import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services import discourse_sync
from services.diavgeia_scraper import _clean_org_label


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
