from types import SimpleNamespace

import pytest

from services.source_links import official_source_url


def bill(**overrides):
    data = {
        "source": "PARLIAMENT",
        "diavgeia_ada": None,
        "parliament_url": None,
        "summary_long_el": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_parliament_prefers_official_pdf_from_scrape():
    b = bill(
        parliament_url="https://www.hellenicparliament.gr/Nomothetiko-Ergo/blocked",
        summary_long_el=(
            "Κείμενο "
            "https://www.hellenicparliament.gr/UserFiles/c8827c35/file.pdf"
        ),
    )

    assert official_source_url(b) == "https://www.hellenicparliament.gr/UserFiles/c8827c35/file.pdf"


def test_parliament_without_pdf_does_not_fall_back_to_blocked_html():
    b = bill(
        parliament_url="https://www.hellenicparliament.gr/Nomothetiko-Ergo/Anazitisi-Nomothetikou-Ergou?law_id=5294",
        summary_long_el="navigation and boilerplate only",
    )

    assert official_source_url(b) is None


def test_diavgeia_uses_readable_decision_view():
    b = bill(
        source="DIAVGEIA",
        diavgeia_ada="96497ΛΨ-7ΒΩ",
        parliament_url="https://diavgeia.gov.gr/doc/96497ΛΨ-7ΒΩ",
    )

    assert official_source_url(b) == (
        "https://diavgeia.gov.gr/decision/view/96497%CE%9B%CE%A8-7%CE%92%CE%A9"
    )


def test_diavgeia_without_ada_does_not_use_doc_fallback():
    b = bill(source="DIAVGEIA", parliament_url="https://diavgeia.gov.gr/doc/UNKNOWN")

    assert official_source_url(b) is None


def test_attribution_fields_preserve_provenance_date_and_do_not_invent_local_origins():
    from datetime import datetime
    from types import SimpleNamespace
    from services.source_links import parliament_attribution_fields

    imported = SimpleNamespace(source='PARLIAMENT', parliament_url='https://www.hellenicparliament.gr/bill',
                               created_at=datetime(2026, 1, 1, 23, 30), summary_long_el=None)
    assert parliament_attribution_fields(imported) == {
        'source': 'PARLIAMENT', 'parliament_url': imported.parliament_url,
        'official_source_url': None, 'created_at': '2026-01-01T23:30:00',
    }
    local = SimpleNamespace(source='PARLIAMENT', parliament_url=None, created_at=None, summary_long_el=None)
    assert parliament_attribution_fields(local)['parliament_url'] is None
    assert parliament_attribution_fields(local)['created_at'] is None


@pytest.mark.parametrize("source,url,attributed", [
    ("PARLIAMENT", "https://www.hellenicparliament.gr/bill/123", True),
    ("PARLIAMENT", "https://hellenicparliament.gr/bill/123", True),
    ("PARLIAMENT", None, False),  # Admin proposal retains its workflow classification.
    ("DIAVGEIA", "https://diavgeia.gov.gr/decision/view/123", False),
    ("DIAVGEIA", "https://www.hellenicparliament.gr/bill/123", False),
    ("UNKNOWN", "https://www.hellenicparliament.gr/bill/123", False),
    (None, "https://www.hellenicparliament.gr/bill/123", False),
    ("PARLIAMENT", "not a url", False),
    ("PARLIAMENT", "https://evil.example/", False),
    ("PARLIAMENT", "http://www.hellenicparliament.gr/bill", False),
    ("PARLIAMENT", "https://user@www.hellenicparliament.gr/bill", False),
    ("PARLIAMENT", "https://www.hellenicparliament.gr:443/bill", False),
    ("PARLIAMENT", "https://www.hellenicparliament.gr:444/bill", False),
    ("PARLIAMENT", "https://www.hellenicparliament.gr.evil.example/", False),
    ("PARLIAMENT", "https://www.hellenicparliament.gr./", False),
    ("PARLIAMENT", "https://%77ww.hellenicparliament.gr/", False),
    ("PARLIAMENT", "https://www.hellenicparliament.gr\\@evil.example/", False),
    ("PARLIAMENT", "https://www.hellenicparliament.gr\n.evil.example/", False),
])
@pytest.mark.parametrize("as_dict", [False, True])
def test_attribution_classification_preserves_workflow_and_requires_official_https(source, url, attributed, as_dict):
    from services.source_links import parliament_attribution_fields

    b = bill(source=source, parliament_url=url)
    fields = parliament_attribution_fields(vars(b) if as_dict else b)
    assert fields["source"] == source
    assert (fields["source"] == "PARLIAMENT" and bool(
        fields["parliament_url"] or fields["official_source_url"]
    )) is attributed
    if source == "PARLIAMENT" and not attributed:
        assert fields["parliament_url"] is None
        assert fields["official_source_url"] is None
    if source == "DIAVGEIA" and "diavgeia.gov.gr" in url:
        assert fields["official_source_url"] == url


@pytest.mark.parametrize("source", ["DIAVGEIA", "UNKNOWN", None, ""])
def test_parliament_pdf_does_not_override_workflow_classification(source):
    b = bill(source=source, summary_long_el="https://www.hellenicparliament.gr/file.pdf")
    assert official_source_url(b) is None
