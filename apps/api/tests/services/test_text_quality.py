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
    swapped = check_generated_greek(text.swapcase(), field="summary_long_el")
    # The Latin-run heuristic intentionally requires lowercase-dominant prose.
    case_sensitive_language_signals = {"english_clause", "foreign_word"}
    assert (set(result.reasons) - case_sensitive_language_signals
            == set(swapped.reasons) - case_sensitive_language_signals) or reason == "mojibake"


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


@pytest.mark.parametrize("text", [
    "The policy sets min 200 words as the required length for the review.",
    "This notice allows max 120 chars for the account identifier.",
])
def test_ordinary_english_prompt_constraints_are_not_prompt_echo(text: str) -> None:
    assert check_generated_text(text, field="summary_long_en").ok


@pytest.mark.parametrize("field,fragment", [
    ("pill_en", "1 sentence max 120 chars"),
    ("summary_short_en", "3 paragraphs with main points"),
    ("summary_long_en", "Full analysis min 200 words"),
])
def test_english_prompt_template_echo_is_rejected(field: str, fragment: str) -> None:
    assert check_generated_text(fragment, field=field).reasons == ("prompt_echo",)


@pytest.mark.parametrize("text,reason", [
    ("Δυστυχώς, δεν μπορώ να παράσχω σύνοψη…", "refusal_or_meta"),
    ("Δεν έχω πρόσβαση στο έγγραφο…", "refusal_or_meta"),
    ("Παρακαλώ, δώστε μου το κείμενο για να το αναλύσω.", "refusal_or_meta"),
    ("**Απάντηση**: Η ρύθμιση αφορά τις υπηρεσίες.", "refusal_or_meta"),
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


@pytest.mark.parametrize("text", [
    "Η " + "«" * 99_998, "Η " + "\n \t" * 33_334, "A" * 100_000, "COVID-" + "9" * 99_993 + "a",
    "α" * 99_999 + "r", "λέξη " * 20_000,
], ids=["unclosed-quotes", "blank-lines", "latin-word", "alphanumeric-token", "mixed-word", "many-words"])
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


@pytest.mark.parametrize("text", [
    "ΕΛΛΗΝΙΚΗ ΔΗΜΟΚΡΑΤΙΑ\nΔΗΜΟΣ ΔΟΚΙΜΗΣ\nΔιεύθυνση Διοικητικών Υπηρεσιών\n"
    "Ταχ. Διεύθυνση: Οδός Δοκιμής 12, ΤΚ 12345\nΑριθ. Πρωτ.: 1234/31-10-2026\n"
    "Πληροφορίες: Γραμματεία\ne-mail: info@example.test\n"
    "ΑΠΟΣΠΑΣΜΑ ΠΡΑΚΤΙΚΟΥ 42\nΤο δημοτικό συμβούλιο εγκρίνει τη συντήρηση του κτιρίου.",
    "ΔΙΟΙΚΗΤΙΚΟ ΣΥΜΒΟΥΛΙΟ ΓΕΝΙΚΟΥ ΝΟΣΟΚΟΜΕΙΟΥ ΔΟΚΙΜΗΣ\n"
    "Τμήμα Γραμματείας, Οδός Παραδείγματος 15, ΤΚ 54321\nΑρ. Πρωτ. 987/2026\n"
    "Ημερομηνία: 31/10/2026\nΤο συμβούλιο εγκρίνει την προμήθεια εξοπλισμού.",
    "Αποδοχή δωρεάς οχημάτων TOYOTA HILUX CRUISER 4X4 από την εταιρεία HELLENiQ ENERGY "
    "για τις ανάγκες των δημοτικών υπηρεσιών και της πολιτικής προστασίας.",
    "Έγκριση παραχώρησης του δημοτικού χώρου για τη διοργάνωση της εκδήλωσης "
    "Colibri Spirit Festival σύμφωνα με τους όρους της παρούσας απόφασης.",
    "Έγκριση συμμετοχής του δήμου στο πρόγραμμα Market Place Digital Programme "
    "για την ενίσχυση των τοπικών επιχειρήσεων και την ανάπτυξη της περιοχής.",
    "Η αιτιολογική έκθεση εξετάζει τη συνεργασία των φορέων και αναφέρεται στις μελέτες "
    "των José René και Jesús για τη βελτίωση της δημόσιας διοίκησης και των υπηρεσιών της.",
    "Η μίσθωση αφορά μηχάνημα CATERPILLAR 100HP με σύστημα Microsoft Teams για τις υπηρεσίες.",
])
@pytest.mark.parametrize("field", ["summary_short_el", "summary_long_el"])
def test_synthetic_official_text_is_accepted(text: str, field: str) -> None:
    assert check_generated_greek(text, field=field).ok
    assert check_generated_greek(unicodedata.normalize("NFD", text), field=field).ok


@pytest.mark.parametrize("phrase", [
    "Société Générale", "Banco Español", "São Paulo", "Crédit Agricole",
    "réélection", "déclaration", "Générale", "José", "Martí",
])
def test_accented_foreign_names_and_terms_are_preserved(phrase: str) -> None:
    text = f"Η γνωμοδότηση αναφέρεται στη {phrase} και στην αρμόδια ελληνική εποπτική αρχή."
    assert check_generated_text(text, field="summary_long_el").ok


@pytest.mark.parametrize("sign", ["\u02b9", "\u0374", "\u0375", "\u02b0", "\u02e0", "\u0640", "€", "℃"])
def test_numeral_signs_modifiers_and_symbols_are_not_foreign_prose(sign: str) -> None:
    text = f"Η απόφαση δημοσιεύεται στο τεύχος Α{sign} και ορίζει τη διαδικασία."
    assert check_generated_greek(text, field="summary_long_el").ok


@pytest.mark.parametrize("letter", list("ABCEHIKMNOPTXYZaceiopuvxy"))
def test_homoglyph_typos_do_not_count_as_mixed_words(letter: str) -> None:
    assert check_generated_greek(f"{letter}πόφαση {letter}πόφαση {letter}πόφαση", field="summary_long_el").ok


def test_latin_a_in_official_decision_is_accepted() -> None:
    assert check_generated_greek("Aπόφαση για τη λειτουργία των δημοτικών υπηρεσιών.", field="summary_short_el").ok


@pytest.mark.parametrize("text", [
    "Για να βridge το προβλήμα", "του κίνδυnu", "διαβέrez", "ενημερωsem",
    "Η διαδικασία rυθμίζεται κανονικά.", "Η διαδικασία ρυθμίzεται κανονικά.",
])
def test_non_homoglyph_latin_inside_greek_word_is_rejected(text: str) -> None:
    assert check_generated_greek(text, field="summary_short_el").reasons == ("mixed_script",)


@pytest.mark.parametrize("words,mixed,rejected", [
    (199, 1, True), (200, 1, True), (201, 1, False),
    (201, 2, True), (401, 2, True), (1_000, 2, True),
    (200, 0, False), (1_000, 0, False),
])
def test_mixed_word_count_and_density_thresholds(words: int, mixed: int, rejected: bool) -> None:
    # A single suspect word is tolerated only in long prose; repeated suspect
    # words fail even when aggregate density is below one per 200 words.
    text = " ".join(["ενημερωsem"] * mixed + ["διαδικασία"] * (words - mixed))
    result = check_generated_greek(text, field="summary_long_el")
    assert result.reasons == (("mixed_script",) if rejected else ())


def test_brands_quotes_and_urls_do_not_create_mixed_words() -> None:
    text = 'Η απόφαση αφορά τα API PDF GDPR και το "Very Long Latin Programme Name". https://example.test/ενημερωsem'
    assert check_generated_greek(text, field="summary_short_el").ok
    assert check_generated_greek('Η απόφαση αφορά «ενημερωsem».', field="summary_short_el").reasons == ("mixed_script",)


@pytest.mark.parametrize("fragment", [
    "theo quy định", "ăđơư", "ẮỘỴ", "правила", "规则", "ひらがな", "カタカナ", "ｶﾀｶﾅ", "한글", "ﾡ",
    "नियम", "নিয়ম", "ਨਿਯਮ", "નિયમ", "ନିୟମ", "விதி", "నియమం", "ನಿಯಮ", "നിയമം", "නියමය",
    "قانون", "חוק", "กฎ",
])
def test_explicit_foreign_script_fragments_are_rejected(fragment: str) -> None:
    text = f"Η απόφαση καθορίζει τη διαδικασία των δημοτικών υπηρεσιών και αναφέρει «{fragment}»."
    assert "foreign_script" in check_generated_greek(text, field="summary_long_el").reasons


@pytest.mark.parametrize("text", [
    "Η ρύθμιση ορίζει ως μοντέλο τεχνητής νοημοσύνης το σύστημα που παράγει προβλέψεις.",
    "Ως μοντέλο τεχνητής νοημοσύνης νοείται το σύστημα που παράγει προβλέψεις.",
    "Ως γλωσσικό μοντέλο νοείται το σύστημα επεξεργασίας της φυσικής γλώσσας.",
    "«Δεν έχω πρόσβαση στα στοιχεία»",
    "«Κατά την εξέταση δήλωσε:\nΔεν έχω πρόσβαση στα στοιχεία\nΠαρακαλώ να μου στείλετε το έγγραφο»",
    "Η κατάθεση αναφέρει «Λυπάμαι, αλλά δεν μπορώ να δώσω τα στοιχεία».",
    'Ο μάρτυρας δήλωσε "Δεν διαθέτω πρόσβαση στο έγγραφο" κατά την εξέταση.',
    "“Παρακαλώ να μου στείλετε το έγγραφο”, δήλωσε ο πολίτης.",
    "1. Απάντηση του Υπουργείου σε ερώτηση για τη διαδικασία αδειοδότησης.",
    "23) Απάντηση του Υπουργείου σε ερώτηση για τη λειτουργία των υπηρεσιών.",
    "• Απάντηση του Υπουργείου σε ερώτηση για την εφαρμογή της απόφασης.",
    "Η απόφαση αφορά τους φορείς New Rules Foundation και Digital Services Programme για τη βελτίωση των δημόσιων υπηρεσιών και την ενίσχυση της διαφάνειας στη διοίκηση.",
    "Η απόφαση αφορά τα API PDF GDPR και τη συνεργασία με τους José René και Jesús.",
    'Η έκθεση παραθέτει "introduces new requirements" ως όρο της συμφωνίας.',
    "Η κατάθεση αναφέρει «Please provide the document so I can summarize it» ως παράδειγμα.",
    "Η κατάθεση αναφέρει “provides new rules” ως παράδειγμα ξενόγλωσσης διατύπωσης.",
])
@pytest.mark.parametrize("field", ["summary_short_el", "summary_long_el", "analysis_el"])
def test_round_three_legislative_preservation(text: str, field: str) -> None:
    assert check_generated_text(text, field=field).ok
    assert check_generated_text(unicodedata.normalize("NFD", text), field=field).ok


@pytest.mark.parametrize("fragment", [
    "introduces new requirements", "provides new rules", "establishes additional obligations",
    "Please provide the document so I can summarize it.",
    "Please send me your text so I can analyse it.",
])
@pytest.mark.parametrize("position", ["before", "within", "after"])
def test_english_clause_cannot_hide_in_greek_padding(fragment: str, position: str) -> None:
    greek = "Η ρύθμιση αφορά τη λειτουργία των δημόσιων υπηρεσιών και τη διαδικασία αδειοδότησης. " * 3
    text = {"before": fragment + " " + greek, "within": greek + fragment + " " + greek,
            "after": greek + fragment}[position]
    assert check_generated_text(text, field="summary_short_el").reasons == ("english_clause",)


@pytest.mark.parametrize("text,reason", [
    ("The regulation sets out new requirements for applicants.", "english_clause"),
    ("Applicants must submit the signed form before the deadline.", "english_clause"),
    ("stellte fest, dass die neue Regelung für alle Behörden gilt", "foreign_word"),
    ("La commission a adopté la nouvelle règle pour tous les citoyens", "foreign_word"),
    ("La autoridad aplica la nueva norma para todos los ciudadanos", "foreign_word"),
    ("La commissione ha approvato la nuova norma per tutti i cittadini", "foreign_word"),
    ("A comissão aprovou a proposta para os novos serviços", "foreign_word"),
])
def test_lowercase_latin_sentence_runs_are_reported(text: str, reason: str) -> None:
    assert reason in check_generated_text(text, field="summary_short_el").reasons


@pytest.mark.parametrize("text", [
    "Η σύμβαση αφορά το έργο με τίτλο PREserving BIOdiversity in coastal DUNEs from tourism pressure της περιφέρειας.",
    "Ε Λ Λ Η Ν Ι Κ Η Δ Η Μ Ο Κ Ρ Α Τ Ι Α e m a i l : s e c r . d i r e c t o r της υπηρεσίας του έργου.",
])
def test_long_official_fields_do_not_judge_latin_sentence_runs(text: str) -> None:
    # Production comparison 2026-11-13: in summary_long_el the run rule hit
    # unquoted EU project titles and OCR-spaced letters (54 false positives).
    reasons = check_generated_text(text, field="summary_long_el").reasons
    assert "english_clause" not in reasons and "foreign_word" not in reasons


@pytest.mark.parametrize("fragment", ["Mykoníaikí", "Åëåõóßíáò", "ÁÊÑÉÂÅÓ"])
def test_greek_transliteration_and_mojibake_signatures_are_reported(fragment: str) -> None:
    text = f"Η απόφαση ορίζει τη διαδικασία και αναφέρει το {fragment} ως παράδειγμα."
    assert "foreign_word" in check_generated_text(text, field="summary_long_el").reasons


@pytest.mark.parametrize("text", [
    'Η απόφαση παραθέτει "The regulation sets out new requirements for applicants." ως τίτλο.',
    "Η απόφαση παραθέτει de facto, a priori, ad hoc, per capita και et al. ως νομικούς όρους "
    "σύμφωνα με τις αρμόδιες υπηρεσίες και τις διατάξεις της απόφασης.",
    "Η απόφαση αναφέρει τη Microsoft Teams για τις υπηρεσίες και το CATERPILLAR 100HP "
    "σύμφωνα με τις αρμόδιες υπηρεσίες και τις διατάξεις της απόφασης.",
    "Η απόφαση παραπέμπει στο info@example.test και στη διεύθυνση https://example.test/english-sentence "
    "σύμφωνα με τις αρμόδιες υπηρεσίες και τις διατάξεις της απόφασης.",
    "Η απόφαση αναφέρει το ακρωνύμιο EU και το API για τη διαδικασία.",
])
def test_latin_run_preserves_titles_brands_urls_emails_and_legal_phrases(text: str) -> None:
    assert check_generated_text(text, field="summary_long_el").ok


@pytest.mark.parametrize("prefix", ["1. ", "23) ", "• ", "‣ ", "◦ ", "⁃ ", "∙ ", "● ", "▪ ", "▫ ", "> 1. ", "1. 2) "])
def test_formatted_meta_answers_are_rejected(prefix: str) -> None:
    result = check_generated_text(prefix + "Απάντηση: Για να βρεις την πληροφορία, αναζήτησε το έγγραφο.",
                                  field="summary_short_el")
    assert result.reasons == ("refusal_or_meta", "meta_answer")


def test_plain_and_list_prefixed_answer_heads_have_equal_legacy_eligibility_signal() -> None:
    answer = "Απάντηση: Η υπηρεσία εγκρίνει την αίτηση."
    plain = check_generated_text(answer, field="summary_short_el")
    prefixed = check_generated_text("• " + answer, field="summary_short_el")
    assert "refusal_or_meta" in plain.reasons
    assert "refusal_or_meta" in prefixed.reasons
    assert ("refusal_or_meta" in plain.reasons) == ("refusal_or_meta" in prefixed.reasons)
    assert "meta_answer" not in plain.reasons and "meta_answer" in prefixed.reasons


@pytest.mark.parametrize("text", [
    "η απάντηση είναι η ακόλουθη: Η υπηρεσία εγκρίνει την αίτηση.",
    "Βεβαίως, η απάντηση είναι η ακόλουθη: Η υπηρεσία εγκρίνει την αίτηση.",
    "Παρακάτω παρατίθεται η απάντηση: Η υπηρεσία εγκρίνει την αίτηση.",
    "Βεβαίως, παρακάτω παρατίθεται η απάντηση: Η υπηρεσία εγκρίνει την αίτηση.",
])
def test_answer_introductions_are_rejected(text: str) -> None:
    assert check_generated_text(text, field="summary_short_el").reasons == ("refusal_or_meta", "meta_answer")


@pytest.mark.parametrize("heading", ["Περίληψη:", "Συνοπτικά:"])
def test_official_decision_summary_headings_are_preserved(heading: str) -> None:
    assert check_generated_text(heading + " Η ρύθμιση εγκρίνει την αίτηση.", field="summary_short_el").ok


@pytest.mark.parametrize("prefix", ["1. ", "23) ", "• ", "‣ ", "◦ ", "⁃ ", "∙ ", "● ", "▪ ", "▫ "])
def test_formatted_summary_labels_are_rejected(prefix: str) -> None:
    result = check_generated_text(prefix + "Σύνοψη: Η ρύθμιση αφορά τη λειτουργία των υπηρεσιών.",
                                  field="summary_short_el")
    assert result.reasons == ("refusal_or_meta", "meta_answer")


@pytest.mark.parametrize("fragment", [
    "Πλήρης ανάλυση min 200 λέξεις",
    "1 πρόταση max 120 χαρακτήρες",
    "3 παράγραφοι με τα κύρια σημεία",
    "min 200 words",
    "max 120 chars",
])
def test_prompt_template_echo_is_rejected(fragment: str) -> None:
    text = f"Η απόφαση αφορά τη διοίκηση των δημόσιων υπηρεσιών. {fragment}"
    assert check_generated_text(text, field="summary_long_el").reasons == ("prompt_echo",)


@pytest.mark.parametrize("text", [
    "Η μίσθωση eines (1) μηχανήματος καλύπτεται από τους όρους της απόφασης.",
    "Η απόφαση αφορά τον σύλλογο Mykoníaikí Aelleleghy και τη λειτουργία του.",
    "Η έκθεση αναφέρει «eines» ως παράδειγμα και παραθέτει \"Mykoníaikí\" ως τίτλο.",
])
def test_foreign_function_words_and_latin_transliteration(text: str) -> None:
    result = check_generated_text(text, field="summary_short_el")
    if "eines (1)" in text:
        assert result.reasons == ("foreign_word",)
    elif "Mykoníaikí Aelleleghy" in text:
        assert result.reasons == ("foreign_word",)
    else:
        assert result.ok


@pytest.mark.parametrize("word", ["der", "avec", "una", "della"])
def test_common_foreign_function_words_in_greek_prose_are_rejected(word: str) -> None:
    text = f"Η μίσθωση {word} (1) μηχανήματος καλύπτεται από τους όρους της απόφασης."
    assert check_generated_text(text, field="summary_short_el").reasons == ("foreign_word",)


@pytest.mark.parametrize("text", [
    "1) Η απόφαση εγκρίνει την προμήθεια εξοπλισμού.",
    "α) Η διαδικασία εφαρμόζεται από τις αρμόδιες υπηρεσίες.",
    "Άρθρο 1. Η απόφαση καθορίζει τους όρους εφαρμογής.",
    "Η ρύθμιση αφορά τα ΦΕΚ, τον Ν. 123/2026 και την ΚΥΑ 45/2026.",
    "Η απόφαση παραθέτει «Die Neue Ordnung» και \"Framework Agreement\" ως τίτλους.",
    "Η απόφαση παραθέτει «Πλήρης ανάλυση min 200 λέξεις» και \"max 120 chars\" ως τίτλους.",
    "Η απόφαση δημοσιεύεται στη διεύθυνση https://example.test/min-200-words.",
    "Η εταιρεία La Poste συνεργάζεται με Microsoft Teams και προμηθεύεται CATERPILLAR 100HP "
    "για την υλοποίηση της δράσης, τη διατήρηση των υποδομών και την παροχή υπηρεσιών "
    "στους πολίτες και στις αρμόδιες δημοτικές υπηρεσίες.",
])
def test_preserved_legal_formatting_titles_and_urls(text: str) -> None:
    assert check_generated_text(text, field="summary_short_el").ok


def test_english_fields_are_not_run_through_greek_language_detectors() -> None:
    text = "The rule introduces new requirements for Microsoft Teams and CATERPILLAR 100HP equipment."
    assert check_generated_text(text, field="summary_short_en").ok


# Exercise every word boundary in the refusal/meta lead-ins, with a failed
# suffix so regex engines must explore their nonmatching paths too.
_META_LEADS = (
    "Tôi", "Tôi xin", "Tôi không", "I'm", "I", "I am", "I can't", "As", "As an", "As an AI,",
    "As a language", "As a language model,", "Λυπάμαι", "Λυπάμαι,", "Λυπάμαι, αλλά",
    "Δυστυχώς", "Δυστυχώς,", "Δυστυχώς, αλλά", "Δεν", "Δεν μπορώ", "Δεν μπορώ να",
    "Δεν έχω", "Δεν διαθέτω", "Χρειάζομαι", "Χρειάζομαι το", "Χρειάζομαι το πλήρες",
    "Χρειάζομαι περισσότερες", "Παρακαλώ", "Παρακαλώ,", "Παρακαλώ να", "Παρακαλώ να μου",
    "Μπορείτε", "Μπορείτε να", "Μπορείτε να μου", "Ως", "Ως γλωσσικό", "Ως μοντέλο",
    "Ως μοντέλο τεχνητής", "Ως μοντέλο τεχνητής νοημοσύνης", "Απάντηση", "Για", "Για να",
    "Για να βρεις", "Για να βρεις την", "Δώστε", "Δώσε", "Στείλτε", "Στείλε", "Παραθέστε", "Παραθέσε",
    "Δώστε μου", "Δώστε μου το", "Here", "Here is", "Here's", "Summary", "You", "You are", "You are a",
    "You are a Greek", "You are a Greek legislation", "Write", "Write only", "Return", "Return only",
    "Return only valid", "Summarize", "Summarize this", "Summarize this Greek", "Respond", "Respond only",
    "Respond only in", "Επέστρεψε", "Επέστρεψε μόνο", "Επέστρεψε μόνο έγκυρο", "Ανάλυσε", "Ανάλυσε αυτό",
    "Ανάλυσε αυτό το", "Ανάλυσε αυτό το ελληνικό", "System", "User", "Assistant", "Prompt", "Title", "Text",
    "Τίτλος", "Κείμενο", "Please", "Please provide", "Please provide the", "Please provide the document",
    "Please provide the document so", "Please provide the document so I", "Please provide the document so I can",
)


@pytest.mark.parametrize("lead", _META_LEADS)
@pytest.mark.parametrize("whitespace", [" ", "\t", " \t"], ids=["spaces", "tabs", "mixed"])
def test_every_meta_lead_with_100k_horizontal_whitespace_is_fast(lead: str, whitespace: str) -> None:
    from time import perf_counter

    text = lead + (whitespace * 100_000)[:100_000] + "η απόφαση ορίζει τη νόμιμη διαδικασία."
    started = perf_counter()
    check_generated_text(text, field="summary_long_el")
    assert perf_counter() - started < 0.5


@pytest.mark.parametrize("lead", ["Παρακαλώ", "Λυπάμαι", "Δυστυχώς"])
@pytest.mark.parametrize("length", [10_000, 100_000])
@pytest.mark.parametrize("matching", [False, True])
def test_review_backtracking_reproduction(lead: str, length: int, matching: bool) -> None:
    from time import perf_counter

    suffix = (", δώστε μου το κείμενο." if lead == "Παρακαλώ" else ", αλλά δεν μπορώ να αναλύσω το κείμενο.")
    text = lead + " " * length + (suffix if matching else "η απόφαση ορίζει τη νόμιμη διαδικασία.")
    started = perf_counter()
    result = check_generated_text(text, field="summary_long_el")
    assert perf_counter() - started < 0.5
    assert ("refusal_or_meta" in result.reasons) == matching


def test_whitespace_compaction_preserves_original_mojibake_density() -> None:
    text = "Η απόφαση αναφέρει τους συμβολισμούς ≈ÀÕ≈ÀÕ≈ÀÕ≈ÀÕ." + "\t" * 100_000 + " Η διαδικασία καθορίζεται αναλυτικά."
    assert check_generated_text(text, field="summary_long_el").ok



@pytest.mark.parametrize("text", [
    "Η απόφαση αναφέρει τη déclaration της εταιρείας για το έργο της περιφέρειας.",
    "Ο Martí ορίζεται υπεύθυνος του έργου για τη συντήρηση του δικτύου.",
    "Στην παράγραφο é του εγγράφου περιγράφεται η διαδικασία του διαγωνισμού.",
])
def test_single_accent_latin_words_in_official_greek_text_are_preserved(text):
    # Production comparison 2026-11-13: one-accent Latin tokens were the only
    # false positives of the new foreign_word rule in 32,530 stored texts.
    assert "foreign_word" not in check_generated_text(text, field="summary_long_el").reasons


def test_repeated_accent_transliteration_and_mojibake_are_rejected():
    assert "foreign_word" in check_generated_text(
        "Συναυλία σε συνεργασία με τον σύλλογο Mykoníaikí Aelleleghy της πόλης.", field="summary_short_el").reasons
