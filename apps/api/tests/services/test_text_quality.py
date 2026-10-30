"""Synthetic examples of generation failures and useful Greek typography."""

import unicodedata

import pytest

from services.text_quality import check_generated_greek, check_generated_text


@pytest.mark.parametrize("text,reason", [
    ("This proposed regulation changes the synthetic process.", "non_greek"),
    ("Tôi xin lỗi, nhưng tôi không thể viết bản tóm tắt.", "refusal_or_meta"),
    ("I'm sorry, this request cannot be completed.", "refusal_or_meta"),
    ("I cannot summarize this document.", "refusal_or_meta"),
    ("As an AI, I have no access to this text.", "refusal_or_meta"),
    ("I can't provide this summary.", "refusal_or_meta"),
    ("Λυπάμαι, αλλά δεν μπορώ να αναλύσω το κείμενο.", "refusal_or_meta"),
    ("Ως μοντέλο δεν έχω πρόσβαση στο έγγραφο.", "refusal_or_meta"),
    ("ΑΠΑΝΤΗΣΗ: Το σχέδιο περιλαμβάνει αλλαγές.", "refusal_or_meta"),
    ("Για να βρεις την πληροφορία, αναζήτησε το έγγραφο.", "refusal_or_meta"),
    ("Επέστρεψε ΜΟΝΟ έγκυρο JSON: Τίτλος: δοκιμή", "refusal_or_meta"),
    ("You are a Greek legislation expert. Write ONLY in English.", "refusal_or_meta"),
    ("Summarize this Greek law in JSON format. Title: Δοκιμή. Text: Δοκιμαστικό κείμενο.", "refusal_or_meta"),
    ("Τίτλος: Δοκιμή\nΚείμενο: Αυτό είναι ένα δοκιμαστικό κείμενο.", "refusal_or_meta"),
    ('{"summary_short_el": "Η ρύθμιση αφορά τη διαδικασία."}', "refusal_or_meta"),
    ("```markdown\nΗ ρύθμιση αφορά τη διαδικασία.\n```", "refusal_or_meta"),
    ("~~~\nΗ ρύθμιση αφορά τη διαδικασία.\n~~~", "refusal_or_meta"),
    ("Title: %CE%94\nURL Source: https://example.test/source\nΚείμενο", "reader_metadata"),
    ("Title: Έγγραφο\nMarkdown Content:\nΚείμενο", "reader_metadata"),
    ("≈ÀÀ«Õ… « ƒ«Ãœ — ≈ÀÀ«Õ…", "mojibake"),
    ("Î•Î»Î»Î·Î½Î¹ÎºÏŒ", "mojibake"),
    ("Ã© Ã± Ã¼", "mojibake"),
    ("Η ρύθμιση ορίζει τη διαδικασία ăđơư.", "foreign_script"),
    ("Η ρύθμιση ορίζει τη διαδικασία ẮỘỴ.", "foreign_script"),
    ("12345 — …", "non_greek"),
])
def test_rejection_codes(text: str, reason: str) -> None:
    result = check_generated_greek(text, field="summary_long_el")
    assert not result.ok
    assert reason in result.reasons
    assert result == check_generated_greek(text.swapcase(), field="summary_long_el") or reason == "mojibake"


@pytest.mark.parametrize("text", [
    "Η ρύθμιση αφορά τη διοίκηση του ΕΣΥ και τη συνεργασία με την ΕΕ.",
    "Η νέα διαδικασία τηρεί τον GDPR και χρησιμοποιεί API και PDF για τα έγγραφα.",
    "Δείτε το επίσημο κείμενο: https://example.test/very/long/english/document-name?title=english.",
    "Η ρύθμιση δημοσιεύεται στο ΦΕΚ Α΄ 123/2026 σύμφωνα με τον ν. 9999/2026.",
    'Η ρύθμιση κυρώνει το κείμενο "Framework Agreement for Public Administration and Digital Services".',
    "Το σχέδιο αφορά το «Digital Services Framework» και τη διαδικασία εφαρμογής του.",
    "Η διαδικασία — με σαφείς όρους — αφορά «τις υπηρεσίες»… και «τους φορείς»…",
    "### Πλήρη έγγραφα\n- [PDF](https://example.test/a-long-english-document.pdf)",
    "Η λέξη Title: αποτελεί παράδειγμα χωρίς μεταδεδομένα ανάγνωσης.",
    "Ἡ νέα ρύθμισις αφορά τη δημόσια διοίκηση και τις υπηρεσίες της.",
])
@pytest.mark.parametrize("field", ["pill_el", "summary_short_el", "summary_long_el", "analysis_el"])
def test_legitimate_greek(text: str, field: str) -> None:
    assert check_generated_greek(text, field=field).ok
    assert check_generated_greek(unicodedata.normalize("NFD", text), field=field).ok


@pytest.mark.parametrize("text", [None, "", "  \n"])
def test_absent_values_are_not_failures(text: str | None) -> None:
    assert check_generated_greek(text, field="summary_long_el").ok


def test_share_threshold_and_short_pill_acronym() -> None:
    assert check_generated_greek("ααα abc", field="summary_short_el").reasons == ("non_greek",)
    assert check_generated_greek("ααα abc", field="summary_short_el", greek_share=0.5).ok
    assert check_generated_greek("GDPR", field="pill_el").ok
    assert check_generated_greek("Νέο API", field="pill_el").ok
    assert not check_generated_greek("Νέο english", field="pill_el").ok
    assert not check_generated_greek("sorry", field="pill_el").ok
    assert not check_generated_greek('"Entirely English quoted text"', field="summary_short_el").ok


def test_english_fields_require_integrity_without_greek_share() -> None:
    assert check_generated_text("The regulation defines a synthetic procedure.", field="summary_short_en").ok
    assert not check_generated_text("I'm sorry, I cannot provide this.", field="summary_short_en").ok


@pytest.mark.parametrize("text,reason", [
    ("Δυστυχώς, δεν μπορώ να παράσχω σύνοψη…", "refusal_or_meta"),
    ("Δεν έχω πρόσβαση στο έγγραφο…", "refusal_or_meta"),
    ("Παρακαλώ, δώστε μου το κείμενο για να το αναλύσω.", "refusal_or_meta"),
    ("**Απάντηση**: Η ρύθμιση αφορά τις υπηρεσίες.", "refusal_or_meta"),
    ("Η ρύθμιση για τη δημόσια διοίκηση provides new rules για τη διαδικασία.", "non_greek"),
    ("Η ρύθμιση για τη δημόσια διοίκηση содержит новые правила.", "foreign_script"),
    ("Η ρύθμιση για τη δημόσια διοίκηση 包含新规则.", "foreign_script"),
    ("Η «Это русское описание документа» αφορά τη διαδικασία.", "foreign_script"),
    ("Η ρύθμιση â€œαφοράâ€ τη διαδικασία.", "mojibake"),
    ("Η ρύθμιση â€” αφορά τη διαδικασία.", "mojibake"),
    ("Η ρύθμιση â€¦ αφορά τη διαδικασία.", "mojibake"),
    ("ERROR", "refusal_or_meta"),
])
def test_review_failure_regressions(text: str, reason: str) -> None:
    assert reason in check_generated_greek(text, field="pill_el").reasons


@pytest.mark.parametrize("text", [
    "Η Εσθονία χρησιμοποιείται ως μοντέλο για την ψηφιακή διακυβέρνηση.",
    "Η κατάθεση αναφέρει «I cannot endorse this proposal» ως δήλωση του μάρτυρα.",
    "Η ρύθμιση χρησιμοποιεί «γνήσια εισαγωγικά», … και — στη διατύπωση.",
    "COVID-19", "ΕΕ COVID-19", "ΕΕ API", "GDPR", "H1N1", "B2B",
])
def test_review_legitimate_regressions(text: str) -> None:
    assert check_generated_greek(text, field="pill_el").ok


@pytest.mark.parametrize("text", ["Η " + "«" * 99_998, "Η " + "\n \t" * 33_334, "A" * 100_000, "COVID-" + "9" * 99_993 + "a"],
                         ids=["unclosed-quotes", "blank-lines", "latin-word", "alphanumeric-token"])
def test_large_inputs_complete_in_half_second(text: str) -> None:
    from time import perf_counter

    started = perf_counter()
    check_generated_greek(text, field="summary_long_el")
    assert perf_counter() - started < 0.5


@pytest.mark.parametrize("text", [
    "Δεν μπορώ να δημιουργήσω περίληψη χωρίς το έγγραφο.",
    "Χρειάζομαι το πλήρες κείμενο του εγγράφου.",
    "Παρακαλώ να μου στείλετε το έγγραφο.",
    "Μπορείτε να μου παρέχετε το κείμενο;",
])
def test_greek_requests_for_input_are_not_legislative_prose(text: str) -> None:
    assert "refusal_or_meta" in check_generated_greek(text, field="summary_short_el").reasons
