import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "backfill_analysis_claude.py"
spec = importlib.util.spec_from_file_location("backfill_analysis_claude", SCRIPT_PATH)
assert spec and spec.loader
backfill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backfill)

build_official_text_block = backfill.build_official_text_block
build_documents_block = backfill.build_documents_block
choose_pdfs = backfill.choose_pdfs
classify_pdf = backfill.classify_pdf
display_label = backfill.display_label
extract_pdf_links = backfill.extract_pdf_links
fallback_pdf_candidates = backfill.fallback_pdf_candidates
is_readable_pdf_text = backfill.is_readable_pdf_text
strip_table_of_contents = backfill.strip_table_of_contents


def test_extract_pdf_links_prefers_jina_image_alt_label():
    markdown = """
    [![Image 18: Αιτιολογική-Εισηγητική Έκθεση](https://www.hellenicparliament.gr/assets/pdf.png)](https://www.hellenicparliament.gr/UserFiles/a/13319369.pdf)
    [![Image 19: Διατάξεις Σχεδίου ή Πρότασης Νόμου](https://www.hellenicparliament.gr/assets/pdf.png)](https://www.hellenicparliament.gr/UserFiles/a/13319370.pdf)
    """

    links = extract_pdf_links(markdown)

    assert links == [
        {
            "label": "Αιτιολογική-Εισηγητική Έκθεση",
            "url": "https://www.hellenicparliament.gr/UserFiles/a/13319369.pdf",
        },
        {
            "label": "Διατάξεις Σχεδίου ή Πρότασης Νόμου",
            "url": "https://www.hellenicparliament.gr/UserFiles/a/13319370.pdf",
        },
    ]


def test_choose_pdfs_separates_analysis_from_official_text():
    links = [
        {"label": "Το φωτοτυπημένο σ/ν ή π/ν", "url": "https://example.test/scan.pdf"},
        {"label": "Αιτιολογική-Εισηγητική Έκθεση", "url": "https://example.test/analysis.pdf"},
        {"label": "Διατάξεις Σχεδίου ή Πρότασης Νόμου", "url": "https://example.test/full.pdf"},
    ]

    analysis_pdf, official_pdf = choose_pdfs(links)

    assert classify_pdf("Το φωτοτυπημένο σ/ν ή π/ν") == "skip"
    assert analysis_pdf == links[1]
    assert official_pdf == links[2]


def test_build_official_text_block_keeps_full_text_heading_and_pdf_links():
    chosen = {
        "label": "Διατάξεις Σχεδίου ή Πρότασης Νόμου",
        "url": "https://www.hellenicparliament.gr/UserFiles/a/full.pdf",
    }
    links = [
        chosen,
        {
            "label": "Αιτιολογική-Εισηγητική Έκθεση",
            "url": "https://www.hellenicparliament.gr/UserFiles/a/analysis.pdf",
        },
    ]
    official_text = "Άρθρο 1\nΣκοπός του νόμου.\n\nΆρθρο 2\nΑντικείμενο του νόμου."

    block = build_official_text_block(official_text, links, chosen)

    assert "### Διατάξεις Σχεδίου ή Πρότασης Νόμου" in block
    assert "Άρθρο 1" in block
    assert "[Διατάξεις Σχεδίου ή Πρότασης Νόμου](https://www.hellenicparliament.gr/UserFiles/a/full.pdf)" in block
    assert "[Αιτιολογική-Εισηγητική Έκθεση](https://www.hellenicparliament.gr/UserFiles/a/analysis.pdf)" in block


def test_pdf_text_quality_gate_rejects_empty_and_ocr_garbage():
    empty = "Title: file.pdf\n\nMarkdown Content:\n\n"
    garbage = "Markdown Content:\n" + ("ΝΝΕΑ ΔΗ ΟΚ Α1Δ ΚΗ ΛΗ ριΟ Πρω ΗΒΟ ΛΗ " * 80)
    readable = "Markdown Content:\nΑΙΤΙΟΛΟΓΙΚΗ ΕΚΘΕΣΗ\n" + (
        "Προς τη Βουλή των Ελλήνων και για τον σκοπό του νόμου, το άρθρο ρυθμίζει "
        "τη διαδικασία και τις αρμοδιότητες της διοίκησης. "
    ) * 80

    assert not is_readable_pdf_text(empty)
    assert not is_readable_pdf_text(garbage)
    assert is_readable_pdf_text(readable)


def test_documents_block_keeps_download_links_when_text_is_unreadable():
    links = [
        {"label": "Το φωτοτυπημένο σ/ν ή π/ν", "url": "https://example.test/scan.pdf"},
        {"label": "Διατάξεις Σχεδίου ή Πρότασης Νόμου", "url": "https://example.test/full.pdf"},
    ]

    block = build_documents_block(links)

    assert "### Πλήρη έγγραφα" in block
    assert "φωτοτυπημένο" not in block
    assert "[Διατάξεις Σχεδίου ή Πρότασης Νόμου](https://example.test/full.pdf)" in block


def test_unknown_pdf_labels_still_become_document_candidates():
    links = [
        {"label": ".pdf", "url": "https://example.test/13313922.pdf"},
        {"label": "Το φωτοτυπημένο σ/ν ή π/ν", "url": "https://example.test/scan.pdf"},
    ]

    candidates = fallback_pdf_candidates(links)
    block = build_documents_block(links)

    assert candidates == [links[0]]
    assert display_label(links[0], 1) == "Έγγραφο Βουλής 1 (13313922.pdf)"
    assert "[Έγγραφο Βουλής 1 (13313922.pdf)](https://example.test/13313922.pdf)" in block


def test_strip_table_of_contents_prefers_second_article_body():
    text = """
ΣΧΕΔΙΟ ΝΟΜΟΥ
ΠΙΝΑΚΑΣ ΠΕΡΙΕΧΟΜΕΝΩΝ
Άρθρο 1 Σκοπός
Άρθρο 2 Αντικείμενο

ΜΕΡΟΣ Α'
ΚΕΦΑΛΑΙΟ Α'
Άρθρο 1
Σκοπός του παρόντος είναι η ουσιαστική ρύθμιση.
"""

    stripped = strip_table_of_contents(text)

    assert "ΠΙΝΑΚΑΣ ΠΕΡΙΕΧΟΜΕΝΩΝ" not in stripped
    assert stripped.startswith("ΚΕΦΑΛΑΙΟ Α")
    assert "Σκοπός του παρόντος" in stripped


def _day_month():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")


async def test_gated_call_refuses_without_calling_claude_when_budget_exhausted(monkeypatch):
    import pytest

    from services.claude_usage import DAILY_TOKEN_LIMIT
    from tests.budget_fakes import BudgetFakeRedis

    calls = []
    monkeypatch.setattr(backfill, "call_claude", lambda *a: calls.append(a))
    day, _ = _day_month()
    redis = BudgetFakeRedis({f"claude:tokens:{day}": str(DAILY_TOKEN_LIMIT)})
    with pytest.raises(backfill.BudgetGateClosed):
        await backfill.gated_call_claude("Τίτλος", "Κείμενο", redis_client=redis)
    assert calls == []


async def test_gated_call_refuses_when_redis_is_down(monkeypatch):
    import pytest

    from tests.budget_fakes import BudgetFakeRedis

    calls = []
    monkeypatch.setattr(backfill, "call_claude", lambda *a: calls.append(a))
    with pytest.raises(backfill.BudgetGateClosed):
        await backfill.gated_call_claude("t", "x", redis_client=BudgetFakeRedis(broken=True))
    assert calls == []


async def test_gated_call_tracks_real_usage_and_releases(monkeypatch):
    from tests.budget_fakes import BudgetFakeRedis

    usage = {"input_tokens": 1200, "output_tokens": 300}
    monkeypatch.setattr(backfill, "call_claude", lambda *a: ({"summary_short_el": "ok"}, usage))
    redis = BudgetFakeRedis()
    result, got = await backfill.gated_call_claude("t", "x", redis_client=redis)
    day, _ = _day_month()
    assert result == {"summary_short_el": "ok"} and got is usage
    assert redis.store[f"claude:tokens:analysis:{day}"] == "1500"
    assert int(redis.store[f"claude:reserved_tokens:{day}"]) == 0


async def test_gated_call_books_full_reservation_when_call_fails(monkeypatch):
    import pytest

    from tests.budget_fakes import BudgetFakeRedis

    def boom(*args):
        raise TimeoutError("timeout after send")

    monkeypatch.setattr(backfill, "call_claude", boom)
    redis = BudgetFakeRedis()
    with pytest.raises(TimeoutError):
        await backfill.gated_call_claude("t", "x" * 100, redis_client=redis)
    day, _ = _day_month()
    assert int(redis.store[f"claude:tokens:{day}"]) > backfill.ANALYSIS_MAX_OUTPUT_TOKENS
    assert int(redis.store[f"claude:reserved_tokens:{day}"]) == 0
