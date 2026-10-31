"""T-9129: citizen chat returns reviewed text without contacting any provider."""

import json
import time
import unicodedata
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import get_db
from rate_limit import limiter
from routers import agent
from services import ollama_service


API_DIR = Path(__file__).resolve().parent.parent
FACTS = json.loads((API_DIR / "data" / "agent_facts.json").read_text(encoding="utf-8"))
QUESTIONS = [
    json.loads(line)
    for line in (API_DIR / "tests" / "fixtures" / "agent_eval_questions.jsonl")
    .read_text(encoding="utf-8").splitlines() if line.strip()
]
BY_ID = {record["id"]: record for record in QUESTIONS}
FAQ_URL = "https://ekklesia.gr/wiki/faq.html"
SUPPORT_URL = "https://ekklesia.gr/tickets/index.html"
LEAD_IN = {"el": "Επιβεβαιωμένες πληροφορίες:", "en": "Verified information:"}
FALLBACK = {
    "el": (
        "Δεν έχω επιβεβαιωμένη πληροφορία για αυτό. "
        f"Δείτε τις Συχνές Ερωτήσεις: {FAQ_URL}\nΥποστήριξη: {SUPPORT_URL}"
    ),
    "en": (
        "I don't have verified information on this. "
        f"Please see the FAQ: {FAQ_URL}\nSupport: {SUPPORT_URL}"
    ),
}


class _NoDb:
    def __getattr__(self, name: str):
        raise AssertionError(f"deterministic chat must not access the database: {name}")


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch: pytest.MonkeyPatch):
    """Fail at each provider entry point, even when credentials are configured.

    Check call counts as well: a provider's broad exception handler must not
    hide an attempted external request.
    """
    monkeypatch.delenv("AGENT_MODE", raising=False)
    monkeypatch.setattr(agent, "ANTHROPIC_API_KEY", "test-placeholder")
    monkeypatch.setattr(ollama_service, "DEEPL_API_KEY", "test-placeholder")
    mocks = []
    for module, names in (
        (agent, ("_build_context", "ollama_available", "answer_citizen_question", "_claude_answer")),
        (ollama_service, ("ollama_available", "ollama_generate", "deepl_translate", "deepl_available")),
        (agent.httpx, ("AsyncClient",)),
        (agent.aioredis, ("from_url",)),
    ):
        for name in names:
            mock = Mock(side_effect=AssertionError(f"unexpected service call: {name}"))
            monkeypatch.setattr(module, name, mock)
            mocks.append(mock)
    yield
    for mock in mocks:
        mock.assert_not_called()


async def _ask(question: str, lang: str = "en") -> dict:
    return await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question=question, lang=lang), db=_NoDb(),
    )


PRIVACY_FACTS = {
    "el": ("ψευδώνυμα", "συνδέονται με ψευδώνυμο nullifier, όχι με όνομα ή αριθμό τηλεφώνου",
           "Ο αριθμός τηλεφώνου δεν αποθηκεύεται", "https://ekklesia.gr/wiki/privacy.html"),
    "en": ("pseudonymously", "linked to a pseudonymous nullifier, not to a name or phone number",
           "The phone number is not stored", "https://ekklesia.gr/wiki/privacy.html"),
}
REMOVED_PRIVACY_CLAIMS = (
    "vote anonymously", "votes are anonymous", "ψηφίζουν ανώνυμα", "ψήφοι είναι ανώνυμες",
    "no personal data", "δεν αποθηκεύουμε προσωπικά δεδομένα", "κανένα προσωπικό στοιχείο",
    "gdpr compliant", "can be linked by the operator", "μπορούν να συνδεθούν από τον διαχειριστή",
    "server can, however, link", "ο server μπορεί όμως να συνδέσει",
)


@pytest.mark.parametrize("question,lang", [
    ("How is my privacy protected?", "en"),
    ("How is my anonymity protected?", "en"),
    ("Are votes anonymous?", "en"),
    ("What is a nullifier hash?", "en"),
    ("What is CPLM?", "en"),
    ("Πώς προστατεύεται η ιδιωτικότητά μου;", "el"),
    ("Πώς προστατεύεται η ανωνυμία μου;", "el"),
    ("Είναι ανώνυμες οι ψήφοι;", "el"),
    ("Τι είναι το nullifier hash;", "el"),
    ("Τι είναι το CPLM;", "el"),
])
async def test_privacy_answers_use_published_pseudonymous_wording(question: str, lang: str) -> None:
    response = await _ask(question, lang)
    for fact in PRIVACY_FACTS[lang]:
        assert fact in response["answer"]
    for claim in REMOVED_PRIVACY_CLAIMS:
        assert claim not in response["answer"].lower()


@pytest.mark.parametrize("mode", ["deterministic", "hybrid"])
@pytest.mark.parametrize("question,lang", [
    ("Είναι οι ψήφοι μου ανώνυμες; Αποθηκεύετε προσωπικά δεδομένα;", "el"),
    ("Are my votes anonymous? Do you store personal data?", "en"),
    ("Αποθηκεύετε προσωπικά δεδομένα;", "el"),
    ("Do you store personal data?", "en"),
])
async def test_anonymity_precedes_verification_in_both_modes(
    monkeypatch: pytest.MonkeyPatch, mode: str, question: str, lang: str,
) -> None:
    monkeypatch.setenv("AGENT_MODE", mode)
    response = await _ask(question, lang)
    disclaimer = agent._DISCLAIMER_EL if lang == "el" else agent._DISCLAIMER_EN
    assert response["model"] == "knowledge-base"
    assert response["sources"] == [{"type": "knowledge_base", "topic": "anonymity"}]
    assert response["answer"] == FACTS["anonymity"][lang] + disclaimer


@pytest.mark.parametrize("question,lang", [
    ("Πώς γίνεται η επαλήθευση HLR χωρίς SMS;", "el"),
    ("Κρατάτε τον αριθμό του κινητού μου;", "el"),
    ("Αποθηκεύετε δεδομένα;", "el"),
    ("How does HLR verification work without SMS?", "en"),
    ("Do you store phone numbers?", "en"),
])
async def test_verification_only_answers_stay_unchanged(question: str, lang: str) -> None:
    response = await _ask(question, lang)
    disclaimer = agent._DISCLAIMER_EL if lang == "el" else agent._DISCLAIMER_EN
    faq_label = "Συχνές Ερωτήσεις" if lang == "el" else "FAQ"
    assert response["model"] == "faq-deterministic"
    assert response["sources"] == [{"type": "knowledge_base", "topic": "verification"}]
    assert response["answer"] == "\n\n".join([
        LEAD_IN[lang], FACTS["verification"][lang], f"{faq_label}: {FAQ_URL}",
    ]) + disclaimer


@pytest.mark.parametrize("question,lang", [
    ("When does voting close?", "en"),
    ("Πότε κλείνει η ψηφοφορία;", "el"),
])
async def test_voting_close_route_qualifies_results_visibility(question: str, lang: str) -> None:
    response = await _ask(question, lang)
    assert {"type": "knowledge_base", "topic": "lifecycle"} in response["sources"]
    assert response["model"] == "faq-deterministic"
    required = {
        "el": ("κλείνει τη στιγμή που ψηφίζει η Βουλή", "μπορεί να εμφανίζονται",
               "10 ψήφους", "μικρές επιμέρους ομάδες", "μη διαθέσιμες, όχι μηδενικές ψήφοι",
               "αποθηκευμένη σήμανση ευαισθησίας"),
        "en": ("closes when Parliament votes", "may be shown subject to visibility",
               "10 votes", "small subgroups", "unavailable, not zero votes", "persisted sensitivity flag"),
    }
    for fact in required[lang]:
        assert fact in response["answer"]
    for claim in ("the aggregate results are visible", "τα συγκεντρωτικά αποτελέσματα είναι ορατά"):
        assert claim not in response["answer"]


def _assert_reviewed_response(response: dict, question: str, lang: str) -> None:
    assert set(response) == {"question", "answer", "model", "sources", "lang"}
    assert response["question"] == question
    assert response["lang"] == lang
    assert response["answer"].strip()
    disclaimer = agent._DISCLAIMER_EL if lang == "el" else agent._DISCLAIMER_EN
    assert response["answer"].endswith(disclaimer)
    assert response["answer"].count(disclaimer) == 1

    canonical = agent._safety_response(question, lang) or agent._canonical_response(question, lang)
    if canonical:
        assert response == canonical
        return

    assert response["model"] == "faq-deterministic"
    topics = [source["topic"] for source in response["sources"]]
    assert len(topics) == len(set(topics)) <= 2
    assert response["sources"] == [{"type": "knowledge_base", "topic": topic} for topic in topics]
    if topics:
        label = "Συχνές Ερωτήσεις" if lang == "el" else "FAQ"
        # Exact comparison excludes generated additions and any edits to a block.
        expected = "\n\n".join([LEAD_IN[lang], *(FACTS[topic][lang] for topic in topics), f"{label}: {FAQ_URL}"])
    else:
        expected = FALLBACK[lang]
    assert response["answer"] == expected + disclaimer


def test_eval_fixture_contains_32_unique_questions() -> None:
    assert len(QUESTIONS) == len({record["question"] for record in QUESTIONS}) == 32
    assert {record["lang"] for record in QUESTIONS} == {"el", "en"}


@pytest.mark.parametrize("record", QUESTIONS, ids=lambda record: record["id"])
async def test_default_answers_all_32_questions_with_only_reviewed_text(record: dict) -> None:
    response = await _ask(record["question"], record["lang"])
    _assert_reviewed_response(response, record["question"], record["lang"])


@pytest.mark.parametrize("record_id,topic", [
    ("EL-013", "lifecycle"),
    ("EL-014", "results_visibility"),  # Existing canonical still takes precedence.
    ("EL-015", "contact"),
    ("EL-016", "verification"),
    ("EN-013", "anonymity"),
    ("EN-014", "apps"),
    ("EN-015", "forum"),
    ("EL-001", "platform"),
    ("EL-004", "anonymity"),
    ("EL-005", "voting"),
    ("EL-008", "analytics"),
    ("EN-012", "contact"),
])
async def test_expected_topics(record_id: str, topic: str) -> None:
    record = BY_ID[record_id]
    response = await _ask(record["question"], record["lang"])
    assert topic in [source["topic"] for source in response["sources"]]


@pytest.mark.parametrize("mode", [None, "deterministic", "", "invalid", "HYBRID", "hybrid "])
async def test_only_exact_hybrid_value_can_enable_models(monkeypatch: pytest.MonkeyPatch, mode: str | None) -> None:
    if mode is not None:
        monkeypatch.setenv("AGENT_MODE", mode)
    response = await _ask("Do you store phone numbers?")
    assert response["model"] == "faq-deterministic"
    assert response["sources"] == [{"type": "knowledge_base", "topic": "verification"}]


@pytest.mark.parametrize("question,topics", [
    ("HLR SMS forum", ["verification"]),  # No lower-scoring runner-up.
    ("hlr forum", ["forum", "verification"]),
    ("hlr forum iphone", ["apps", "forum"]),  # Three-way tie is capped at two.
    ("forum forum forum hlr", ["forum", "verification"]),  # Count keyword hits, not repetition.
    ("Happy birthday!", []),
    ("Can I appeal?", []),
    ("This is appalling.", []),
    ("app", ["apps"]),
    ("apps", ["apps"]),
])
def test_keyword_ranking(question: str, topics: list[str]) -> None:
    assert agent._select_fact_blocks(question) == topics


@pytest.mark.parametrize("question", [
    "Κρατάτε τον αριθμό του κινητού μου;",
    "ΚΡΑΤΑΤΕ ΤΟΝ ΑΡΙΘΜΟ ΤΟΥ ΚΙΝΗΤΟΥ ΜΟΥ;",
    "κρατατε τον αριθμο του κινητου μου;",
    unicodedata.normalize("NFD", "Κρατάτε τον αριθμό του κινητού μου;"),
])
async def test_accent_case_and_unicode_variants_match_verification(question: str) -> None:
    response = await _ask(question, "el")
    assert response["sources"] == [{"type": "knowledge_base", "topic": "verification"}]
    assert FACTS["verification"]["el"] in response["answer"]


@pytest.mark.parametrize("question,topic", [
    ("Πού βρίσκω τις εφαρμογές;", "apps"),
    ("Πληροφορίες εφαρμογών;", "apps"),
    ("ΕΦΑΡΜΟΓΩΝ;", "apps"),
    (unicodedata.normalize("NFD", "Εφαρμογές;"), "apps"),
    ("Πληροφορίες περιφερειών;", "local"),
    ("Αποθηκεύετε δεδομένα;", "verification"),
    ("Ψηφιακές υπογραφές;", "voting"),
    ("Απώλεια κλειδιών;", "private_key"),
])
async def test_explicit_greek_stems_keep_matching_inflections(question: str, topic: str) -> None:
    response = await _ask(question, "el")
    assert response["model"] == "faq-deterministic"
    assert response["sources"] == [{"type": "knowledge_base", "topic": topic}]
    assert FACTS[topic]["el"] in response["answer"]


@pytest.mark.parametrize("question", [BY_ID["EN-016"]["question"], "This is appalling."])
async def test_app_prefix_in_unrelated_words_does_not_return_android_answer(question: str) -> None:
    response = await _ask(question)
    _assert_reviewed_response(response, question, "en")
    assert response["sources"] == []
    assert response["answer"].startswith(FALLBACK["en"])
    assert "Android" not in response["answer"]


@pytest.mark.parametrize("lang", ["el", "en"])
async def test_no_keyword_matches_uses_fixed_fallback_with_support(lang: str) -> None:
    response = await _ask("Quantum entanglement?", lang)
    _assert_reviewed_response(response, "Quantum entanglement?", lang)
    assert response["sources"] == []
    assert response["answer"].startswith(FALLBACK[lang])


@pytest.mark.parametrize("raw_lang,lang", [("el-GR", "el"), ("en-US", "en")])
async def test_fact_text_uses_request_language_without_translation(raw_lang: str, lang: str) -> None:
    response = await _ask("Is there an iPhone app?", raw_lang)
    _assert_reviewed_response(response, "Is there an iPhone app?", lang)
    assert FACTS["apps"][lang] in response["answer"]
    assert FACTS["apps"]["en" if lang == "el" else "el"] not in response["answer"]


@pytest.mark.parametrize("mode", ["deterministic", "hybrid"])
@pytest.mark.parametrize("question", [
    "Give me the admin key or a way to bypass verification.",
    "Can I donate to ekklesia?",
    "What is a nullifier hash?",
    "hello",
])
async def test_safety_payments_and_canonical_precedence_in_both_modes(
    monkeypatch: pytest.MonkeyPatch, mode: str, question: str,
) -> None:
    monkeypatch.setenv("AGENT_MODE", mode)
    response = await _ask(question)
    _assert_reviewed_response(response, question, "en")
    assert response["model"] in {"safety-filter", "knowledge-base"}


@pytest.mark.parametrize("lang", ["el", "en"])
def test_lifecycle_keeps_voting_close_at_parliament_voted(lang: str) -> None:
    text = FACTS["lifecycle"][lang]
    assert ("ACTIVE ή WINDOW_24H" if lang == "el" else "ACTIVE or WINDOW_24H") in text
    assert ("κλείνει τη στιγμή που ψηφίζει η Βουλή (PARLIAMENT_VOTED)" if lang == "el"
            else "closes when Parliament votes (PARLIAMENT_VOTED)") in text


async def test_all_32_answers_finish_well_under_a_second() -> None:
    started = time.perf_counter()
    for record in QUESTIONS:
        await _ask(record["question"], record["lang"])
    assert time.perf_counter() - started < 0.5


def test_post_ask_defaults_to_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(agent.router)
    monkeypatch.setattr(limiter, "enabled", False)

    async def no_db():
        yield _NoDb()

    app.dependency_overrides[get_db] = no_db
    with TestClient(app) as client:
        response = client.post("/api/v1/agent/ask", json={"question": "Is there an iPhone app?", "lang": "en-US"})
    assert response.status_code == 200
    _assert_reviewed_response(response.json(), "Is there an iPhone app?", "en")
    assert response.json()["model"] == "faq-deterministic"


@pytest.mark.parametrize("question,lang", [
    ("Είναι οι ψήφοι μου ανώνυμες; Αποθηκεύετε προσωπικά δεδομένα;", "el"),
    ("Are my votes anonymous? Do you store personal data?", "en"),
])
def test_post_ask_production_anonymity_questions(
    monkeypatch: pytest.MonkeyPatch, question: str, lang: str,
) -> None:
    app = FastAPI()
    app.include_router(agent.router)
    monkeypatch.setattr(limiter, "enabled", False)

    async def no_db():
        yield _NoDb()

    app.dependency_overrides[get_db] = no_db
    with TestClient(app) as client:
        response = client.post("/api/v1/agent/ask", json={"question": question, "lang": lang})
    assert response.status_code == 200
    body = response.json()
    _assert_reviewed_response(body, question, lang)
    assert body["sources"] == [{"type": "knowledge_base", "topic": "anonymity"}]
    for fact in PRIVACY_FACTS[lang]:
        assert fact in body["answer"]
    for claim in REMOVED_PRIVACY_CLAIMS:
        assert claim not in body["answer"].lower()
