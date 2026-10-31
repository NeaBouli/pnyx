"""Privacy routing stays scoped to the platform and preserves other intents."""

import unicodedata

import pytest

from routers import agent


# Includes every quoted review example and the equivalent Greek linkage question.
PAYMENT_CASES = [
    ("en", "Can I make an anonymous donation?"),
    ("en", "Can I donate anonymously?"),
    ("en", "Can I anonymously donate?"),
    ("en", "Can I make an anonymous donation to your project?"),
    ("el", "Μπορώ να κάνω ανώνυμη δωρεά;"),
    ("el", "Μπορώ να κάνω μια ανώνυμη δωρεά στην πλατφόρμα;"),
    ("el", "Μπορώ να κάνω δωρεά ανώνυμα;"),
]

DELETION_CASES = [
    ("el", "διαγραφή προσωπικών δεδομένων"),
    ("en", "How do I request deletion of my personal information?"),
    ("en", "request deletion of my personal information"),
    ("en", "personal data deletion"),
    ("en", "How can I delete my data?"),
    ("en", "Can I erase my personal information after HLR verification?"),
    ("en", "Request deletion of our personal info"),
    ("en", "How do I request deletion of personal data?"),
    ("en", "How do I request deletion of all of my personal information?"),
    ("el", "Πώς ζητώ διαγραφή των προσωπικών δεδομένων μου;"),
    ("el", "Θέλω διαγραφή των προσωπικών μου δεδομένων"),
    ("el", "Διαγραφή προσωπικών στοιχείων μετά την επαλήθευση HLR"),
    ("el", "Πώς μπορώ να διαγράψω τα προσωπικά δεδομένα μου;"),
    ("el", unicodedata.normalize("NFD", "ΔΙΑΓΡΑΦΗ ΠΡΟΣΩΠΙΚΩΝ ΔΕΔΟΜΕΝΩΝ")),
    ("en", "Delete my personal data: can anyone link my vote to me?"),
    ("el", "Διαγραφή προσωπικών δεδομένων: ποιος βλέπει την ψήφο μου;"),
]

ANONYMITY_CASES = [
    ("en", "Can anyone link my vote to me after HLR verification?"),
    ("el", "Μπορεί κάποιος να συνδέσει την ψήφο μου με εμένα μετά την επαλήθευση HLR;"),
    ("en", "Can my vote be linked to my identity after HLR verification?"),
    ("en", "Can my identity be linked to my vote after HLR verification?"),
    ("en", "Can the operators associate my vote with my phone number?"),
    ("el", "Μπορεί η ψήφος μου να συνδεθεί με την ταυτότητά μου μετά την επαλήθευση HLR;"),
    ("el", "Μπορεί η ταυτότητά μου να συνδεθεί με την ψήφο μου;"),
    ("el", "Μπορούν οι διαχειριστές να συσχετίσουν την ψήφο μου με εμένα;"),
    ("el", unicodedata.normalize("NFD", "ΜΠΟΡΕΙ ΚΑΠΟΙΟΣ ΝΑ ΣΥΝΔΕΣΕΙ ΤΗΝ ΨΗΦΟ ΜΟΥ ΜΕ ΕΜΕΝΑ ΜΕΤΑ ΤΗΝ ΕΠΑΛΗΘΕΥΣΗ HLR;")),
    ("en", "Who can see my vote after HLR verification?"),
    ("el", "Ποιος βλέπει την ψήφο μου μετά την επαλήθευση HLR;"),
    ("en", "Are votes anonymous?"),
    ("el", "Είναι οι ψήφοι ανώνυμες;"),
    ("en", "Is my vote private?"),
    ("en", "What personal data is stored by the platform?"),
    ("en", "Do you collect personal information?"),
    ("el", "Ποια προσωπικά δεδομένα αποθηκεύει η πλατφόρμα;"),
    ("en", "How does this platform protect privacy?"),
    ("el", "Πώς προστατεύεται η ιδιωτικότητα στην πλατφόρμα;"),
    ("en", "Is my vote on this bill anonymous?"),
    ("el", "Είναι η ψήφος μου στο νομοσχέδιο ανώνυμη;"),
]

VERIFICATION_CASES = [
    ("en", "How does HLR verification work?", ["verification"]),
    ("en", "Do I need SMS for phone verification?", ["verification"]),
    ("en", "Is my phone number stored after HLR verification?", ["verification"]),
    ("en", "Is my public key linked to my identity after HLR verification?", ["verification"]),
    ("en", "How do I verify before casting my vote?", ["verification", "voting"]),
    ("el", "Πώς γίνεται η επαλήθευση HLR;", ["verification"]),
    ("el", "Αποθηκεύεται ο αριθμός τηλεφώνου μετά την επαλήθευση;", ["verification"]),
    ("el", "Πώς επαληθεύομαι πριν δώσω την ψήφο μου;", ["verification", "voting"]),
]

BILL_CASES = [
    ("en", "What does the privacy bill change?"),
    ("en", "What does the privacy bill change about my vote?"),
    ("en", "privacy bill"),
    ("el", "νομοσχέδιο για την ιδιωτικότητα"),
    ("el", "Τι λέει το νομοσχέδιο για την ιδιωτικότητα και την ψήφο μου;"),
    ("en", "Does the privacy bill require personal data deletion?"),
    ("en", "Does the bill permit anonymous donations?"),
    ("en", "Does the bill require banks to store personal information?"),
    ("en", "Does the bill make parliamentary votes anonymous?"),
    ("el", "Τι προβλέπει το νομοσχέδιο για τη διαγραφή προσωπικών δεδομένων;"),
    ("el", "Επιτρέπει το νομοσχέδιο ανώνυμες δωρεές;"),
    ("el", "Ποια προσωπικά δεδομένα αποθηκεύουν οι τράπεζες σύμφωνα με το νομοσχέδιο;"),
]

UNRELATED_CASES = [
    ("en", "What is anonymization?"),
    ("en", "Who wrote this anonymous article?"),
    ("en", "Can I make an anonymous donation to my local hospital?"),
    ("en", "How do I delete an anonymous forum comment?"),
    ("en", "Where can I see my vote history?"),
    ("en", "Where is the link to cast my vote?"),
    ("en", "How do I link my phone to my account?"),
    ("en", "What personal information do banks store?"),
    ("en", "Do hospitals collect personal data?"),
    ("en", "Does a hospital app store personal information?"),
    ("en", "What is an anonymous phone call?"),
    ("el", "Ποιος έγραψε το ανώνυμο άρθρο;"),
    ("el", "Πώς διαγράφω ένα ανώνυμο σχόλιο στο forum;"),
    ("el", "Πού βλέπω το ιστορικό με τις ψήφους μου;"),
    ("el", "Αποθηκεύουν οι τράπεζες προσωπικά δεδομένα;"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["deterministic", "hybrid"])
@pytest.mark.parametrize("topic,lang,question", [
    *[("payments_paused", lang, q) for lang, q in PAYMENT_CASES],
    *[("data_deletion", lang, q) for lang, q in DELETION_CASES],
    *[("anonymity", lang, q) for lang, q in ANONYMITY_CASES],
])
async def test_scoped_canonical_routing(
    monkeypatch: pytest.MonkeyPatch, mode: str, topic: str, lang: str, question: str,
) -> None:
    monkeypatch.setenv("AGENT_MODE", mode)

    async def unexpected(*args, **kwargs):
        raise AssertionError("Canonical routing must precede database/model calls")

    for name in ("_build_context", "ollama_available", "answer_citizen_question", "_claude_answer"):
        monkeypatch.setattr(agent, name, unexpected)

    response = await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question=question, lang=lang), db=object(),
    )
    assert response["sources"] == [{"type": "knowledge_base", "topic": topic}]
    if topic == "anonymity":
        expected = agent._with_disclaimer(agent._FACTS[topic][lang], lang)
    elif topic == "payments_paused":
        expected = agent._payments_paused_response(question, lang)["answer"]
        assert ("paused and unavailable" if lang == "en" else "έχουν προσωρινά ανασταλεί") in expected
    else:
        # Compare the entire answer with an existing, unambiguous deletion prompt.
        expected = agent._canonical_response("How can I delete my data?", lang)["answer"]
    assert response["answer"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("lang,question,topics", VERIFICATION_CASES)
async def test_verification_only_keeps_existing_answer(
    monkeypatch: pytest.MonkeyPatch, lang: str, question: str, topics: list[str],
) -> None:
    monkeypatch.setenv("AGENT_MODE", "deterministic")
    assert agent._canonical_response(question, lang) is None
    response = await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question=question, lang=lang), db=object(),
    )
    assert response["sources"] == [{"type": "knowledge_base", "topic": topic} for topic in topics]
    faq_label = "Συχνές Ερωτήσεις" if lang == "el" else "FAQ"
    expected = "\n\n".join([
        agent._FAQ_LEAD_IN[lang],
        *(agent._FACTS[topic][lang] for topic in topics),
        f"{faq_label}: {agent._FAQ_URL}",
    ])
    assert response["answer"] == agent._with_disclaimer(expected, lang)


@pytest.mark.parametrize("lang,question", BILL_CASES + UNRELATED_CASES)
def test_other_intents_do_not_select_voting_privacy(lang: str, question: str) -> None:
    assert agent._canonical_response(question, lang) is None
    assert "anonymity" not in agent._select_fact_blocks(question)


@pytest.mark.parametrize("lang,question", [
    ("en", "Where is my private key used to sign my vote stored?"),
    ("el", "Πού αποθηκεύεται το ιδιωτικό κλειδί για την ψήφο μου;"),
])
def test_private_key_for_voting_keeps_existing_answer(lang: str, question: str) -> None:
    response = agent._canonical_response(question, lang)
    assert response["sources"] == [{"type": "knowledge_base", "topic": "private_key"}]
    assert response["answer"] == agent._with_disclaimer(agent._FACTS["private_key"][lang], lang)


@pytest.mark.asyncio
@pytest.mark.parametrize("lang,question", BILL_CASES)
async def test_bill_content_keeps_normal_retrieval(
    monkeypatch: pytest.MonkeyPatch, lang: str, question: str,
) -> None:
    monkeypatch.setenv("AGENT_MODE", "hybrid")
    assert agent._should_include_bills(question)

    class BillRetrievalReached(Exception):
        pass

    async def context(actual_question, actual_lang, db):
        assert (actual_question, actual_lang) == (question, lang)
        raise BillRetrievalReached

    monkeypatch.setattr(agent, "_build_context", context)
    with pytest.raises(BillRetrievalReached):
        await agent.ask_agent.__wrapped__(
            object(), agent.AskRequest(question=question, lang=lang), db=object(),
        )
