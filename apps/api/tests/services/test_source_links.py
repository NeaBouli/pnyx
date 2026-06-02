from types import SimpleNamespace

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
