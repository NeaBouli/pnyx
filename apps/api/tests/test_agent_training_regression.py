"""Regression checks for the landing-chat training questions captured by Codex.

The tracked fixture holds only id/lang/category/question; captured answers,
endpoints and timestamps stay in the private agent-bridge dataset.
"""

import json
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from routers import agent
from routers.agent import _canonical_response, _safety_response, _should_include_bills


DATASET = Path(__file__).resolve().parent / "fixtures" / "landing_chat_training_questions.jsonl"
FIXTURE_FIELDS = {"id", "lang", "category", "question"}


def _records() -> list[dict[str, Any]]:
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_training_dataset_has_25_entries_with_retry() -> None:
    records = _records()

    assert len(records) == 25
    assert len({r["id"] for r in records}) == 25
    assert all(set(r) == FIXTURE_FIELDS for r in records)
    assert {r["id"] for r in records} >= {"EN-005", "EN-005-R1", "EN-011"}


def test_training_dataset_safety_questions_are_filtered() -> None:
    for record in _records():
        if record["category"] != "adversarial":
            continue
        response = _safety_response(record["question"], record["lang"])
        assert response is not None
        assert response["model"] == "safety-filter"
        assert response["sources"] == []


def test_training_dataset_high_priority_knowledge_has_canonical_answers() -> None:
    expected = {
        "EL-009": "cplm",
        "EL-006": "private_key",
        "EL-012": "govgr",
        "EN-005": "nullifier_hash",
        "EN-005-R1": "nullifier_hash",
        "EN-006": "private_key",
        "EN-008": "municipal",
    }

    by_id = {r["id"]: r for r in _records()}
    for record_id, topic in expected.items():
        response = _canonical_response(by_id[record_id]["question"], by_id[record_id]["lang"])
        assert response is not None
        assert response["model"] == "knowledge-base"
        assert response["sources"] == [{"type": "knowledge_base", "topic": topic}]


def test_training_dataset_general_questions_do_not_attach_bill_sources() -> None:
    for record in _records():
        if record["category"] in {"identity", "legal", "privacy", "crypto", "limits"}:
            assert _should_include_bills(record["question"]) is False


PAYMENT_PROMPTS = [
    ("en", "How can I donate to ekklesia?"),
    ("en", "Can I pay with Stripe?"),
    ("en", "Where is the PayPal donate link?"),
    ("en", "I want to support the project financially"),
    ("en", "How can I support ekklesia?"),
    ("en", "Do you accept payments or sponsorship?"),
    ("el", "Πώς μπορώ να κάνω δωρεά;"),
    ("el", "Μπορώ να πληρώσω με PayPal;"),
    ("el", "Υπάρχει σύνδεσμος Stripe για δωρεές;"),
    ("el", "Πώς μπορώ να στηρίξω την εκκλησία;"),
    ("el", "Θέλω να δώσω οικονομική στήριξη στην πλατφόρμα"),
    ("el", "Δέχεστε χορηγίες ή εισφορές;"),
    ("en", "Do you accept donations?"),
    ("en", "Is there an IBAN for donations?"),
    ("el", "Θέλω να στηρίξω οικονομικά την πλατφόρμα"),
    ("el", "Υπάρχει σύνδεσμος για δωρεές;"),
    # accent-less, upper-case and decomposed (NFD) spellings
    ("el", "ΠΩΣ ΜΠΟΡΩ ΝΑ ΚΑΝΩ ΔΩΡΕΑ;"),
    ("el", "πως μπορω να στηριξω την εκκλησια"),
    ("el", unicodedata.normalize("NFD", "Πώς μπορώ να κάνω δωρεά;")),
    # natural first-person intents (Codex review #400, second round)
    ("en", "Can I donate?"),
    ("en", "Where can I donate?"),
    ("en", "I want to donate"),
    ("en", "Can I make a payment to ekklesia?"),
    ("el", "Πώς μπορώ να σας στηρίξω;"),
    ("el", "Θέλω να κάνω δωρεά στο ekklesia.gr"),
    ("el", "Πώς μπορώ να στηρίξω το ekklesia;"),
]


@pytest.mark.parametrize("lang,question", PAYMENT_PROMPTS)
def test_payment_prompts_get_deterministic_paused_answer(lang: str, question: str) -> None:
    response = _canonical_response(question, lang)

    assert response is not None
    assert response["model"] == "knowledge-base"
    assert response["sources"] == [{"type": "knowledge_base", "topic": "payments_paused"}]
    answer = response["answer"]
    if lang == "el":
        assert "έχουν προσωρινά ανασταλεί" in answer
        assert "δεν παραπέμπει σε Stripe, PayPal" in answer
    else:
        assert "paused and unavailable" in answer
        assert "does not refer you to Stripe, PayPal" in answer
    lowered = answer.lower()
    for forbidden in ("http", "stripe.com", "paypal.me", "paypal.com", "refund", "tax", "will be activated"):
        assert forbidden not in lowered


@pytest.mark.parametrize("lang,question", [
    ("el", "Είναι δωρεάν η εφαρμογή;"),
    ("el", "Πρέπει να πληρώσω για να ψηφίσω;"),
    ("en", "Does the app support iOS?"),
    ("en", "Do I have to pay to vote?"),
    ("el", "Ποιες πληροφορίες αποθηκεύετε;"),
    ("en", "What is ekklesia.gr and who operates it?"),
    # EKA-60 review: bill topics that share vocabulary with payments
    ("en", "Who is the sponsor of this bill?"),
    ("en", "Does the bill change social security contributions?"),
    ("en", "How are pensions paid under the new law?"),
    ("en", "Does the law fund public hospitals?"),
    ("en", "Will the state support us farmers financially?"),
    ("en", "How are donations to charities taxed?"),
    ("en", "Is organ donation covered by the bill?"),
    ("en", "Can I pay my taxes on the platform?"),
    ("el", "Ποιος είναι ο χορηγός του νομοσχεδίου;"),
    ("el", "Αλλάζουν οι ασφαλιστικές εισφορές;"),
    ("el", "Τι προβλέπει το νομοσχέδιο για τις συντάξεις και τις εισφορές;"),
    ("el", "Πότε γίνεται η πληρωμή των συντάξεων;"),
    ("el", "Πώς θα στηρίξει ο νόμος τους αγρότες;"),
    ("el", "Υπάρχει χρηματοδότηση για τα σχολεία;"),
    ("el", "Φορολογούνται οι δωρεές στην Εκκλησία;"),
    ("el", "Μπορώ να κάνω δωρεά οργάνων;"),
    ("el", "Πώς ενισχύεται οικονομικά η τοπική αυτοδιοίκηση;"),
    ("en", "Can I donate organs under the new law?"),
    ("en", "Where can I donate blood?"),
    ("en", "I want to donate to my local hospital"),
    ("el", "Πώς θα σας στηρίξει το κράτος;"),
])
def test_non_payment_prompts_do_not_hit_paused_answer(lang: str, question: str) -> None:
    response = _canonical_response(question, lang)

    assert response is None or response["sources"][0]["topic"] != "payments_paused"


@pytest.mark.parametrize("lang,question", [
    ("en", "Where is my private key stored?"),
    ("en", "What happens if I lose my private key?"),
    ("en", "Is my signing key in the iOS Keychain?"),
    ("el", "Πού αποθηκεύεται το ιδιωτικό κλειδί μου;"),
    ("el", "Τι γίνεται αν χάσω το ιδιωτικό μου κλειδί;"),
])
def test_private_key_answer_separates_web_local_storage_from_mobile_secure_store(
    lang: str, question: str,
) -> None:
    response = _canonical_response(question, lang)

    assert response is not None
    assert response["sources"] == [{"type": "knowledge_base", "topic": "private_key"}]
    answer = response["answer"]
    web, mobile = answer.split("Mobile app:" if lang == "en" else "Εφαρμογή κινητού:", 1)
    assert "Web Beta" in web and "localStorage" in web
    assert ("not iOS Keychain or Android Keystore" if lang == "en" else "όχι iOS Keychain ή Android Keystore") in web
    assert "Expo SecureStore" in mobile and "Android Keystore" in mobile and "iOS Keychain" in mobile
    assert ("implemented iOS code path" if lang == "en" else "υλοποιημένη διαδρομή κώδικα iOS") in mobile
    assert ("does not store it and cannot recover it later" if lang == "en" else "δεν το αποθηκεύει") in mobile
    assert ("server creates the key pair once" if lang == "en" else "δημιουργεί το ζεύγος κλειδιών μία φορά") in mobile


class _NoDb:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"canonical answer must not touch the database ({name})")


@pytest.mark.asyncio
@pytest.mark.parametrize("lang,question,topic", [
    *[(lang, question, "payments_paused") for lang, question in PAYMENT_PROMPTS],
    ("en", "Where is my private key stored?", "private_key"),
    ("el", "Πού αποθηκεύεται το ιδιωτικό κλειδί μου;", "private_key"),
])
async def test_canonical_answers_end_before_db_and_models(
    monkeypatch: pytest.MonkeyPatch, lang: str, question: str, topic: str,
) -> None:
    async def unexpected(*args: object, **kwargs: object) -> None:
        raise AssertionError("canonical answer must not reach RAG or a model")

    for name in ("_build_context", "ollama_available", "answer_citizen_question", "_claude_answer"):
        monkeypatch.setattr(agent, name, unexpected)

    response = await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question=question, lang=lang), db=_NoDb(),
    )

    assert response["model"] == "knowledge-base"
    assert response["sources"] == [{"type": "knowledge_base", "topic": topic}]
    assert response["lang"] == lang


PAYMENT_MODEL_ANSWERS = [
    "You can support us at https://www.paypal.com/donate?hosted_button_id=X.",
    "Donate here: https://donate.stripe.com/abc",
    "Send money to IBAN: GR16 0110 1250 0000 0001 2300 695",
    "Use paypal.com/donate/ekklesia to help.",
    "Checkout: buy.stripe.com/test_123",
    "Transfer to GR16 0110 1250 0000 0001 2300 695 please.",
    "ΙΒΑΝ: GR16 0110 1250 0000 0001 2300 695",
]


@pytest.mark.parametrize("answer", [
    "Ο νόμος 4624/2019 (ΦΕΚ Α 137) ρυθμίζει την προστασία δεδομένων.",
    "Bill GR-2026-0001 is open for votes until 2026-10-10.",
    "The Ed25519 public key is stored; the vote id is DIAV-Ψ26Μ46Ψ84Ι-Τ.",
])
def test_payment_output_guard_leaves_normal_answers(answer: str) -> None:
    assert agent._has_payment_link(answer) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("model_answer", PAYMENT_MODEL_ANSWERS)
async def test_claude_answers_with_payment_links_are_replaced(
    monkeypatch: pytest.MonkeyPatch, model_answer: str,
) -> None:
    async def fake_context(*args: object, **kwargs: object):
        return "", [], False, []

    async def no(*args: object, **kwargs: object) -> bool:
        return False

    async def fake_claude(*args: object, **kwargs: object) -> str:
        return model_answer

    monkeypatch.setattr(agent, "_build_context", fake_context)
    monkeypatch.setattr(agent, "ollama_available", no)
    monkeypatch.setattr(agent, "_claude_answer", fake_claude)

    response = await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question="What does the new bill change?", lang="en"), db=_NoDb(),
    )

    assert response["sources"] == [{"type": "knowledge_base", "topic": "payments_paused"}]
    assert "http" not in response["answer"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("model_answer", PAYMENT_MODEL_ANSWERS)
async def test_model_answers_with_payment_links_are_replaced(
    monkeypatch: pytest.MonkeyPatch, model_answer: str,
) -> None:
    async def fake_context(*args: object, **kwargs: object):
        return "", [], False, []

    async def yes(*args: object, **kwargs: object) -> bool:
        return True

    async def fake_answer(*args: object, **kwargs: object) -> str:
        return model_answer

    monkeypatch.setattr(agent, "_build_context", fake_context)
    monkeypatch.setattr(agent, "ollama_available", yes)
    monkeypatch.setattr(agent, "answer_citizen_question", fake_answer)

    response = await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question="What does the new bill change?", lang="en"), db=_NoDb(),
    )

    assert response["sources"] == [{"type": "knowledge_base", "topic": "payments_paused"}]
    assert "http" not in response["answer"].lower()
    assert "iban" not in response["answer"].lower()

