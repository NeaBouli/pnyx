from scripts.seed_knowledge_base import ENTRIES


def _entry(title_en: str) -> tuple:
    return next(entry for entry in ENTRIES if entry[2] == title_en)


def test_vote_weight_is_equal_for_every_verification_method() -> None:
    all_content = " ".join(str(value) for entry in ENTRIES for value in entry)
    weight_entry = _entry("How much does my vote weigh?")

    assert "x2" not in all_content.lower()
    assert "Every valid vote has weight x1.0" in weight_entry[4]
    assert "ένα άτομο = μία ψήφος" in weight_entry[3]


def test_govgr_seed_is_alpha_only_and_does_not_equate_qr_with_identity() -> None:
    govgr_entry = _entry("What is gov.gr OAuth?")

    assert "not active in Beta" in govgr_entry[4]
    assert "does not authenticate the person" in govgr_entry[4]
    assert "δεν είναι ενεργός στη Beta" in govgr_entry[3]
    assert "όχι από μόνος του την ταυτότητα" in govgr_entry[3]
