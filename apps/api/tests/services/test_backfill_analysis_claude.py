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
extract_pdf_links = backfill.extract_pdf_links
is_readable_pdf_text = backfill.is_readable_pdf_text


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
