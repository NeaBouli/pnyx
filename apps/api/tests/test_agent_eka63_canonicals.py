"""EKA-63: deterministic MOD-22 answers for data deletion/revocation, guarded
ZK/Semaphore, representative verification and result visibility.

These facts must return from `_canonical_response` before database retrieval
or Ollama/Claude generation (docs/architecture/MAP.md, EKA-63 hop A4→A5).
"""

import pytest

from routers import agent
from routers.agent import _DISCLAIMER_EL, _DISCLAIMER_EN, _canonical_response
from services.agent_prompt import is_unsafe_model_output

# (topic, lang, question) — at least two natural questions per topic/language.
POSITIVE_CASES: list[tuple[str, str, str]] = [
    ("data_deletion", "en", "How can I delete my data?"),
    ("data_deletion", "en", "How do I delete my account?"),
    ("data_deletion", "en", "Can I revoke my identity?"),
    ("data_deletion", "en", "Is there identity revocation?"),
    ("data_deletion", "el", "Πώς μπορώ να διαγράψω τα δεδομένα μου;"),
    ("data_deletion", "el", "Διαγραφή λογαριασμού, πώς γίνεται;"),
    ("data_deletion", "el", "Μπορώ να ανακαλέσω την ταυτότητά μου;"),
    ("data_deletion", "el", "πως γινεται η ανακληση του κλειδιου;"),
    ("zk_semaphore", "en", "What is ZK voting?"),
    ("zk_semaphore", "en", "Does the platform use Semaphore zero-knowledge proofs?"),
    ("zk_semaphore", "en", "Is zero knowledge voting available for every bill?"),
    ("zk_semaphore", "el", "Τι είναι η ψηφοφορία ZK;"),
    ("zk_semaphore", "el", "Χρησιμοποιείτε αποδείξεις μηδενικής γνώσης;"),
    ("zk_semaphore", "el", "Πώς λειτουργεί το Semaphore;"),
    ("representative_verification", "en", "How do representatives get verified?"),
    ("representative_verification", "en", "How can a mayor register on the platform?"),
    ("representative_verification", "en", "Where do I get an invite code?"),
    ("representative_verification", "el", "Πώς γίνεται η επαλήθευση εκπροσώπων;"),
    ("representative_verification", "el", "Πώς μπορεί ένας δήμαρχος να εγγραφεί;"),
    ("representative_verification", "el", "Ως δημοτικός σύμβουλος, πώς πιστοποιούμαι;"),
    ("representative_verification", "el", "Πού βρίσκω κωδικό πρόσκλησης;"),
    ("results_visibility", "en", "Why are the results hidden?"),
    ("results_visibility", "en", "When will the results be visible?"),
    ("results_visibility", "en", "Can I see the results before voting ends?"),
    ("results_visibility", "en", "Why do the vote results show zero?"),
    ("results_visibility", "el", "Γιατί τα αποτελέσματα είναι κρυφά;"),
    ("results_visibility", "el", "Πότε θα γίνουν ορατά τα αποτελέσματα;"),
    ("results_visibility", "el", "Γιατί τα αποτελεσματα εμφανιζονται μηδενικα;"),
]

# Facts each answer must carry (EL, EN), grounded in the mapped source symbols.
REQUIRED_FACTS: dict[str, dict[str, tuple[str, ...]]] = {
    "data_deletion": {
        "el": ("REVOKED", "nullifier hash", "δεν είναι γενική διαγραφή",
               "δεν προσφέρουν κουμπί", "μόνο στη συσκευή"),
        "en": ("REVOKED", "nullifier hash", "not a general deletion",
               "do not offer a revocation", "only on your device"),
    },
    "zk_semaphore": {
        "el": ("δεν είναι γενικά διαθέσιμη", "ρητά", "δημόσια νομοσχέδια της Βουλής",
               "ACTIVE, WINDOW_24H ή OPEN_END", "απορρίπτεται", "Arweave"),
        "en": ("not generally available", "explicitly enabled",
               "public Parliament bills", "ACTIVE, WINDOW_24H or OPEN_END",
               "rejected", "Arweave"),
    },
    "representative_verification": {
        "el": ("κωδικό πρόσκλησης", "δεν έχει χρησιμοποιηθεί", "δεν έχει λήξει",
               "ΑΔΑ", "Διαύγεια", "μόνος του δεν αρκεί", "24 ωρών"),
        "en": ("admin-issued invite code", "unused", "not expired", "ADA",
               "Diavgeia", "alone is not enough", "24-hour"),
    },
    "results_visibility": {
        "el": ("ACTIVE", "μηδενικές", "κρυφές", "WINDOW_24H", "PARLIAMENT_VOTED",
               "OPEN_END", "δεν είναι δημόσια"),
        "en": ("ACTIVE", "zero", "hidden", "WINDOW_24H", "PARLIAMENT_VOTED",
               "OPEN_END", "not public"),
    },
}

# Claims the answers must never make (brief constraints / map §5).
FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "gdpr", "compliant", "permanently deleted", "all your data is deleted",
    "always available", "available for all", "ada alone is enough",
    "minimum-k", "k-anonym", "live", "allowlist", "zk_", "demo-123",
)

TOPICS = tuple(REQUIRED_FACTS)
LANGS = ("el", "en")


@pytest.mark.parametrize(("topic", "lang", "question"), POSITIVE_CASES)
def test_eka63_questions_return_canonical_answer(topic: str, lang: str, question: str) -> None:
    response = _canonical_response(question, lang)

    assert response is not None, question
    assert response["model"] == "knowledge-base"
    assert response["sources"] == [{"type": "knowledge_base", "topic": topic}]
    assert response["lang"] == lang
    assert response["question"] == question
    disclaimer = _DISCLAIMER_EL if lang == "el" else _DISCLAIMER_EN
    assert response["answer"].endswith(disclaimer)
    assert response["answer"].count("---") == 1


def test_positive_matrix_has_two_questions_per_topic_and_language() -> None:
    for topic in TOPICS:
        for lang in LANGS:
            count = sum(1 for t, lng, _ in POSITIVE_CASES if t == topic and lng == lang)
            assert count >= 2, (topic, lang)


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("lang", LANGS)
def test_eka63_answers_carry_grounded_facts_only(topic: str, lang: str) -> None:
    question = next(q for t, lng, q in POSITIVE_CASES if t == topic and lng == lang)
    response = _canonical_response(question, lang)
    assert response is not None

    answer = response["answer"]
    for fact in REQUIRED_FACTS[topic][lang]:
        assert fact in answer, (topic, lang, fact)
    lowered = answer.lower()
    for claim in FORBIDDEN_CLAIMS:
        assert claim not in lowered, (topic, lang, claim)


@pytest.mark.parametrize("topic", TOPICS)
def test_eka63_answer_language_follows_request_lang(topic: str) -> None:
    question = next(q for t, lng, q in POSITIVE_CASES if t == topic and lng == "en")

    el = _canonical_response(question, "el")
    en = _canonical_response(question, "en")

    assert el is not None and en is not None
    assert el["sources"] == en["sources"]
    assert el["answer"].endswith(_DISCLAIMER_EL)
    assert en["answer"].endswith(_DISCLAIMER_EN)
    assert el["answer"] != en["answer"]


@pytest.mark.parametrize(("question", "lang"), [
    # Ordinary bill questions near the new topics.
    ("What are the results of bill GR-2024-0012?", "en"),
    ("Show me the results for the pension bill", "en"),
    ("Does the new bill delete old tax debts?", "en"),
    ("Does the bill let banks delete my account data?", "en"),
    ("How did my representative vote on the housing bill?", "en"),
    ("Ποια είναι τα αποτελέσματα για το νομοσχέδιο της στέγασης;", "el"),
    ("Το νομοσχέδιο προβλέπει διαγραφή λογαριασμού σε τράπεζες;", "el"),
    ("Τι ψήφισε ο βουλευτής μου για το νομοσχέδιο;", "el"),
    # Ambiguous generic wording containing a topic word but no topic phrase.
    ("delete", "en"),
    ("results", "en"),
    ("representative", "en"),
    ("proof", "en"),
    ("vote", "en"),
    ("What is the proof of residence requirement?", "en"),
    ("Who is my representative in parliament?", "en"),
    ("How do I remove a comment in the forum?", "en"),
    ("αποτελέσματα", "el"),
    ("διαγραφή", "el"),
    ("Ποιος είναι ο εκπρόσωπος της περιοχής μου;", "el"),
])
def test_nearby_questions_do_not_match_eka63_topics(question: str, lang: str) -> None:
    assert _canonical_response(question, lang) is None


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("lang", LANGS)
def test_eka63_answers_do_not_trip_output_guard(topic: str, lang: str) -> None:
    for t, _, question in POSITIVE_CASES:
        if t != topic:
            continue
        response = _canonical_response(question, lang)
        assert response is not None
        assert is_unsafe_model_output(response["answer"]) is False


def test_existing_canonical_topics_keep_their_precedence() -> None:
    cases = {
        "What happens if I lose my private key?": "private_key",
        "What is a nullifier hash?": "nullifier_hash",
        "Diavgeia municipal votes?": "municipal",
        "Can I change my vote?": "vote_correction",
    }
    for question, topic in cases.items():
        response = _canonical_response(question, "en")
        assert response is not None
        assert response["sources"][0]["topic"] == topic


@pytest.mark.asyncio
@pytest.mark.parametrize(("topic", "lang", "question"), POSITIVE_CASES)
async def test_eka63_route_skips_context_and_language_models(
    monkeypatch: pytest.MonkeyPatch, topic: str, lang: str, question: str,
) -> None:
    async def unexpected(*args: object, **kwargs: object) -> None:
        raise AssertionError("EKA-63 canonical answers must not reach RAG or a model")

    monkeypatch.setattr(agent, "_build_context", unexpected)
    monkeypatch.setattr(agent, "ollama_available", unexpected)
    monkeypatch.setattr(agent, "answer_citizen_question", unexpected)
    monkeypatch.setattr(agent, "_claude_answer", unexpected)

    response = await agent.ask_agent.__wrapped__(
        object(),
        agent.AskRequest(question=question, lang=lang),
        db=object(),
    )

    assert response["model"] == "knowledge-base"
    assert response["sources"] == [{"type": "knowledge_base", "topic": topic}]
    assert response["lang"] == lang
