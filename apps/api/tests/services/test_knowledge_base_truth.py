import pytest

from routers.agent import _FACTS, _canonical_response
from scripts.seed_knowledge_base import ENTRIES


def test_seed_privacy_claims_use_only_published_pseudonymous_facts() -> None:
    for title in ("What is ekklesia?", "How is my anonymity protected?", "Is the app safe?", "What is CPLM?"):
        entry = _entry(title)
        for lang, content in (("el", entry[3]), ("en", entry[4])):
            assert ("ψευδώνυμα" if lang == "el" else "pseudonymously") in content
            assert ("συνδέονται με ψευδώνυμο nullifier, όχι με όνομα ή αριθμό τηλεφώνου" if lang == "el"
                    else "linked to a pseudonymous nullifier, not to a name or phone number") in content
            assert ("Ο αριθμός τηλεφώνου δεν αποθηκεύεται" if lang == "el"
                    else "The phone number is not stored") in content
            assert "https://ekklesia.gr/wiki/privacy.html" in content
    all_content = " ".join(str(value) for entry in ENTRIES for value in entry[3:5]).lower()
    for claim in ("vote anonymously", "ψηφίζουν ανώνυμα", "no personal data", "δεν αποθηκεύουμε προσωπικά δεδομένα",
                  "gdpr compliant", "only a cryptographic nullifier hash is stored",
                  "can be linked by the operator", "μπορούν να συνδεθούν από τον διαχειριστή"):
        assert claim not in all_content


def _entry(title_en: str) -> tuple:
    return next(entry for entry in ENTRIES if entry[2] == title_en)


@pytest.mark.parametrize("lang,index", [("el", 3), ("en", 4)])
def test_anonymity_seed_uses_the_same_published_answer_as_the_canonical(lang: str, index: int) -> None:
    entry = _entry("How is my anonymity protected?")
    response = _canonical_response(entry[2], lang)
    assert response is not None
    assert entry[index].startswith(_FACTS["anonymity"][lang])
    assert response["answer"].startswith(_FACTS["anonymity"][lang])


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
        web, mobile = content.split("Mobile app:" if lang == "en" else "Εφαρμογή κινητού:", 1)
        assert "WebCrypto" in web and "IndexedDB" in web and "Web Locks" in web
        assert "features.identity_key_check" in web
        assert ("non-extractable" if lang == "en" else "μη εξαγώγιμο") in web
        assert ("off by default" if lang == "en" else "ανενεργό από προεπιλογή") in web
        assert "iOS Keychain" not in web and "Android Keystore" not in web
        assert "Expo SecureStore" in mobile
    assert "deletes the plaintext copy only after successful migration" in key_entry[4]
    assert "plaintext in localStorage until migration completes" in key_entry[4]
    assert "if the feature is off, unsupported or a check fails, the copy remains" in key_entry[4]


def test_seed_does_not_claim_keychain_for_web_or_offer_payment_processors() -> None:
    anonymity_entry = _entry("How is my anonymity protected?")
    all_content = " ".join(str(value) for entry in ENTRIES for value in entry[3:5]).lower()

    for lang, content in (("el", anonymity_entry[3]), ("en", anonymity_entry[4])):
        web, mobile = content.split("Mobile app:" if lang == "en" else "Εφαρμογή κινητού:", 1)
        assert "WebCrypto" in web and "IndexedDB" in web and "Web Locks" in web
        assert "localStorage" in web and "features.identity_key_check" in web
        assert ("non-extractable" if lang == "en" else "μη εξαγώγιμο") in web
        assert ("off by default" if lang == "en" else "ανενεργό από προεπιλογή") in web
        assert "iOS Keychain" not in web and "Android Keystore" not in web
        assert "Expo SecureStore" in mobile
    assert "IndexedDB after successful migration" in anonymity_entry[4]
    assert "plaintext in localStorage until migration completes" in anonymity_entry[4]
    assert "if the feature is off, unsupported or a check fails, the plaintext copy remains" in anonymity_entry[4]
    assert "stored only on your device" not in all_content
    assert "stripe" not in all_content and "paypal" not in all_content
