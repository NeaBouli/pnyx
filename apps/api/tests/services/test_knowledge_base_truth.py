from routers.agent import _canonical_response
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


def test_private_key_seed_matches_canonical_platform_split() -> None:
    key_entry = _entry("What if I lose my private key?")

    for lang, content in (("el", key_entry[3]), ("en", key_entry[4])):
        response = _canonical_response(key_entry[2], lang)
        assert response is not None
        assert response["answer"].startswith(content)
    assert "Web Beta: it is kept in the browser's localStorage" in key_entry[4]
    assert "not iOS Keychain or Android Keystore" in key_entry[4]
    assert "Expo SecureStore" in key_entry[4]


def test_seed_does_not_claim_keychain_for_web_or_offer_payment_processors() -> None:
    anonymity_entry = _entry("How is my anonymity protected?")
    all_content = " ".join(str(value) for entry in ENTRIES for value in entry[3:5]).lower()

    assert "web beta: browser localstorage; mobile app: expo securestore" in anonymity_entry[4].lower()
    assert "stored only on your device" not in all_content
    assert "stripe" not in all_content and "paypal" not in all_content
