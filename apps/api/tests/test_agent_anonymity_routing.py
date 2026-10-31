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


# Round 2 review, including the abbreviated ballot prompt in full.
ROUND2_ANONYMITY_CASES = [
    ("en", "Am I anonymous after HLR verification?"),
    ("el", "Είμαι ανώνυμος μετά την επαλήθευση HLR;"),
    ("en", "Is my ballot anonymous after HLR verification?"),
]
ROUND2_DELETION_CASES = [
    ("el", "Πώς μπορώ να διαγράψω τα προσωπικά μου δεδομένα;"),
    ("en", "How do I delete personal data?"),
]
ROUND2_BILL_CASES = [
    ("en", "Does the law require anonymous voting?"),
    ("el", "Ο νόμος επιτρέπει ανώνυμη ψηφοφορία;"),
]
ROUND2_FORUM_CASES = [("en", "Is the forum on this platform anonymous?")]
ROUND2_FEEDBACK_CASES = [
    ("en", "Can I leave anonymous feedback on your platform?"),
    ("el", "Μπορώ να κάνω ανώνυμη καταγγελία στην πλατφόρμα;"),
]

NEW_ANONYMITY_CASES = [
    ("en", "Can anyone trace my ballot to me after verification?"),
    ("en", "Who sees my ballot after HLR?"),
    ("en", "Is my platform account anonymous after HLR verification?"),
    ("en", "Can my account be traced to me after HLR verification?"),
    ("en", "Who sees my personal data after HLR verification?"),
    ("el", "Μπορούν τα προσωπικά μου δεδομένα να συνδεθούν με την ταυτότητά μου;"),
    ("el", "Είμαι ανώνυμη μετά την επαλήθευση;"),
    ("el", "Ποιος μπορεί να δει την ψήφο μου μετά το HLR;"),
    ("el", unicodedata.normalize("NFD", "Είμαι ανώνυμος μετά την επαλήθευση HLR;".upper())),
]
NEW_DELETION_CASES = [
    ("en", "Please erase the personal data after HLR verification"),
    ("en", "Delete my account: am I anonymous after HLR?"),
    ("en", "Delete my personal data: can my vote on this bill be linked to me after HLR?"),
    ("en", "Can my vote be linked to me after HLR, and how do I delete my personal data?"),
    ("en", "How can I delete my data under privacy law?"),
    ("el", "Θέλω να σβήσω τα προσωπικά μας δεδομένα"),
    ("el", "Θέλω διαγραφή των προσωπικών μου πληροφοριών"),
    ("el", unicodedata.normalize("NFD", "Πώς μπορώ να διαγράψω τα προσωπικά μου δεδομένα;".upper())),
]
NEW_BILL_CASES = [
    ("en", "Does legislation permit anonymous ballots?"),
    ("en", "Does the law require personal data deletion?"),
    ("en", "Does the privacy law make my vote anonymous?"),
    ("el", "Η νομοθεσία επιτρέπει ανώνυμη ψηφοφορία;"),
    ("el", "Ο νόμος απαιτεί διαγραφή των προσωπικών μου δεδομένων;"),
    ("el", "Επιτρέπεται ανώνυμη ψηφοφορία σύμφωνα με τον νόμο;"),
    ("el", unicodedata.normalize("NFD", "Ο νόμος επιτρέπει ανώνυμη ψηφοφορία;".upper())),
]
NEW_FORUM_CASES = [
    ("el", "Είναι το φόρουμ στην πλατφόρμα ανώνυμο;"),
    ("en", "Is my forum account anonymous after HLR verification?"),
    ("en", "Does this platform keep forum comments anonymous?"),
    ("en", "How do I delete a forum comment containing personal data?"),
]
NEW_FEEDBACK_CASES = [
    ("en", "Can I submit an anonymous complaint on this platform?"),
    ("el", "Μπορώ να στείλω ανώνυμα παράπονα στην πλατφόρμα;"),
    ("en", "anonymous feedback"),
    ("el", "ανώνυμη καταγγελία"),
    ("en", "complaint"),
    ("en", "feedback"),
    ("en", "Can I leave anonymous feedback after HLR verification?"),
    ("en", "How do I delete feedback containing my personal data?"),
]
NEW_VERIFICATION_CASES = [
    ("en", "How does HLR work for ballot verification?", ["verification"]),
    ("en", "How is my account verified with HLR?", ["verification"]),
    ("el", "Πώς λειτουργεί η επαλήθευση HLR;", ["verification"]),
    ("el", "δεδομένα κινητού", ["verification"]),
]
NEW_UNRELATED_CASES = [
    ("en", "Where is the link to cast my ballot?"),
    ("en", "Where can I see my ballot history?"),
    ("en", "How can I delete my vote?"),
    ("en", "Can my ballot be erased after HLR verification?"),
    ("en", "Do banks delete personal data?"),
    ("el", "Οι τράπεζες διαγράφουν προσωπικά δεδομένα;"),
    ("en", "How do I delete a forum comment containing personal data?"),
    ("en", "How do I delete feedback containing my personal data?"),
    ("en", "What is an anonymous account in a hospital app?"),
]
NEW_BARE_CASES = [
    ("en", "complaint", []),
    ("en", "feedback", []),
    ("en", "forum", ["forum"]),
    ("el", "δεδομένα κινητού", ["verification"]),
]

PRIVATE_KEY_CASES = [
    ("en", "Where is my private key used to sign my vote stored?"),
    ("el", "Πού αποθηκεύεται το ιδιωτικό κλειδί για την ψήφο μου;"),
    ("en", "Where is my private key stored?"),
    ("en", "Is my private key secret?"),
    ("el", "Είναι μυστικό το ιδιωτικό κλειδί μου;"),
]


# Round 4 review: a reference prompt pins each existing canonical answer.
ROUND4_CASES = [
    ("en", "For bill GR-2026-1234, who can see my vote?", "anonymity", "Are votes anonymous?"),
    ("en", "How should I vote on the privacy bill?", None, None),
    ("en", "Can anyone see the vote results before voting ends?", "results_visibility", "Why are results hidden?"),
    ("en", "Can you send me a link to vote?", None, None),
    ("en", "Can you send me a link to the Android app?", "android_download", "Download the Android app"),
    ("en", "Is my vote secret?", "anonymity", "Are votes anonymous?"),
    ("el", "Είναι μυστική η ψήφος μου;", "anonymity", "Είναι οι ψήφοι ανώνυμες;"),
    ("el", "Ειναι μυστικη η ψηφος μου;", "anonymity", "Είναι οι ψήφοι ανώνυμες;"),
    ("en", "Is my vote anonimous?", "anonymity", "Are votes anonymous?"),
    ("en", "Can I revoke my verification?", "data_deletion", "How can I delete my data?"),
]

ROUND4_VARIANT_CASES = [
    ("en", "Who can see my vote for bill GR-2026-1234?", "anonymity", "Are votes anonymous?"),
    ("en", "On the privacy bill, is my vote secret?", "anonymity", "Are votes anonymous?"),
    ("en", "For bill GR-2026-1234, is my vote anonymus?", "anonymity", "Are votes anonymous?"),
    ("en", "Is my vote anonimi?", "anonymity", "Are votes anonymous?"),
    ("el", "Ειναι ανωνυμη η ψηφος μου;", "anonymity", "Είναι οι ψήφοι ανώνυμες;"),
    ("el", unicodedata.normalize("NFD", "ΕΙΝΑΙ ΜΥΣΤΙΚΗ Η ΨΗΦΟΣ ΜΟΥ;"), "anonymity", "Είναι οι ψήφοι ανώνυμες;"),
    ("en", "Can anyone link my vote to me?", "anonymity", "Are votes anonymous?"),
    ("en", "Can my phone number be linked to my vote?", "anonymity", "Are votes anonymous?"),
    ("el", "Συνδέεται η ψήφος με το τηλέφωνο;", "anonymity", "Είναι οι ψήφοι ανώνυμες;"),
    ("en", "Can anyone see the results?", "results_visibility", "Why are results hidden?"),
    ("en", "Are the vote results anonymous?", "results_visibility", "Why are results hidden?"),
    ("en", "Are the vote results secret?", "results_visibility", "Why are results hidden?"),
    ("el", "Μπορεί κάποιος να δει τα αποτελέσματα πριν κλείσει η ψηφοφορία;", "results_visibility", "Γιατί τα αποτελέσματα είναι κρυφά;"),
    ("en", "For the privacy bill, how should I vote?", None, None),
    ("en", "Can you send me a link to my vote?", None, None),
    ("en", "Can you send me a link to verify my vote?", None, None),
    ("en", "Can you send me a link to see my vote?", None, None),
    ("en", "Is there verification revocation?", "data_deletion", "How can I delete my data?"),
    ("el", "Μπορώ να ανακαλέσω την επαλήθευση;", "data_deletion", "Πώς διαγράφω τα δεδομένα μου;"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["deterministic", "hybrid"])
@pytest.mark.parametrize("lang,question,topic,reference", ROUND4_CASES + ROUND4_VARIANT_CASES)
async def test_round4_review_routing(monkeypatch, mode, lang, question, topic, reference):
    monkeypatch.setenv("AGENT_MODE", mode)

    async def unexpected(*args, **kwargs):
        raise AssertionError("Canonical/deterministic routing must precede database/model calls")

    for name in ("_build_context", "ollama_available", "answer_citizen_question", "_claude_answer"):
        monkeypatch.setattr(agent, name, unexpected)

    if topic is None:
        assert agent._canonical_response(question, lang) is None
        assert "anonymity" not in agent._select_fact_blocks(question)
        if "bill" in question:
            assert agent._should_include_bills(question)
        if mode == "hybrid":
            class RetrievalReached(Exception):
                pass

            async def context(actual_question, actual_lang, db):
                assert (actual_question, actual_lang) == (question, lang)
                raise RetrievalReached

            monkeypatch.setattr(agent, "_build_context", context)
            with pytest.raises(RetrievalReached):
                await agent.ask_agent.__wrapped__(
                    object(), agent.AskRequest(question=question, lang=lang), db=object(),
                )
            return

    response = await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question=question, lang=lang), db=object(),
    )
    if topic is None:
        assert response["model"] == "faq-deterministic"
        assert "anonymity" not in [source["topic"] for source in response["sources"]]
        assert any(source["topic"] == "voting" for source in response["sources"])
    else:
        assert response == agent._canonical_response(reference, lang) | {"question": question}
        assert response["sources"] == [{"type": "knowledge_base", "topic": topic}]


# Exercise every input in every earlier routing table through the endpoint.
# Noncanonical cases retain their existing broader FAQ/fallback assertions;
# verification, forum and bare probes also pin their exact source topics.
PREVIOUS_ROUND_ROUTING_CASES = [
    *[(lang, q, "payments_paused", None) for lang, q in PAYMENT_CASES],
    *[(lang, q, "data_deletion", None) for lang, q in DELETION_CASES + ROUND2_DELETION_CASES + NEW_DELETION_CASES],
    *[(lang, q, "anonymity", None) for lang, q in ANONYMITY_CASES + ROUND2_ANONYMITY_CASES + NEW_ANONYMITY_CASES],
    *[(lang, q, "private_key", None) for lang, q in PRIVATE_KEY_CASES],
    *[(lang, q, None, topics) for lang, q, topics in VERIFICATION_CASES + NEW_VERIFICATION_CASES + NEW_BARE_CASES],
    *[(lang, q, None, ["forum"]) for lang, q in ROUND2_FORUM_CASES + NEW_FORUM_CASES],
    *[(lang, q, None, None) for lang, q in BILL_CASES + UNRELATED_CASES + ROUND2_BILL_CASES + NEW_BILL_CASES + NEW_UNRELATED_CASES + ROUND2_FEEDBACK_CASES + NEW_FEEDBACK_CASES],
]


@pytest.mark.asyncio
@pytest.mark.parametrize("lang,question,canonical_topic,topics", PREVIOUS_ROUND_ROUTING_CASES)
async def test_every_previous_routing_table_input(monkeypatch, lang, question, canonical_topic, topics):
    monkeypatch.setenv("AGENT_MODE", "deterministic")

    async def unexpected(*args, **kwargs):
        raise AssertionError("Deterministic routing must stay offline")

    for name in ("_build_context", "ollama_available", "answer_citizen_question", "_claude_answer"):
        monkeypatch.setattr(agent, name, unexpected)

    canonical = agent._canonical_response(question, lang)
    response = await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question=question, lang=lang), db=object(),
    )
    if canonical_topic:
        assert response["model"] == "knowledge-base"
        assert response["sources"] == [{"type": "knowledge_base", "topic": canonical_topic}]
    else:
        assert canonical is None
        assert response["model"] == "faq-deterministic"
        assert "anonymity" not in [source["topic"] for source in response["sources"]]
        if topics is not None:
            assert response["sources"] == [{"type": "knowledge_base", "topic": topic} for topic in topics]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["deterministic", "hybrid"])
@pytest.mark.parametrize("topic,lang,question", [
    *[("payments_paused", lang, q) for lang, q in PAYMENT_CASES],
    *[("data_deletion", lang, q) for lang, q in DELETION_CASES],
    *[("anonymity", lang, q) for lang, q in ANONYMITY_CASES],
    *[("anonymity", lang, q) for lang, q in ROUND2_ANONYMITY_CASES + NEW_ANONYMITY_CASES],
    *[("data_deletion", lang, q) for lang, q in ROUND2_DELETION_CASES + NEW_DELETION_CASES],
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
@pytest.mark.parametrize("lang,question,topics", VERIFICATION_CASES + NEW_VERIFICATION_CASES)
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


@pytest.mark.parametrize("lang,question", BILL_CASES + UNRELATED_CASES + ROUND2_BILL_CASES + NEW_BILL_CASES + NEW_UNRELATED_CASES)
def test_other_intents_do_not_select_voting_privacy(lang: str, question: str) -> None:
    assert agent._canonical_response(question, lang) is None
    assert "anonymity" not in agent._select_fact_blocks(question)


@pytest.mark.parametrize("lang,question", PRIVATE_KEY_CASES)
def test_private_key_for_voting_keeps_existing_answer(lang: str, question: str) -> None:
    response = agent._canonical_response(question, lang)
    assert response["sources"] == [{"type": "knowledge_base", "topic": "private_key"}]
    assert response["answer"] == agent._with_disclaimer(agent._FACTS["private_key"][lang], lang)


@pytest.mark.asyncio
@pytest.mark.parametrize("lang,question", BILL_CASES + ROUND2_BILL_CASES + NEW_BILL_CASES)
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


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["deterministic", "hybrid"])
@pytest.mark.parametrize("lang,question", ROUND2_FORUM_CASES + NEW_FORUM_CASES)
async def test_forum_anonymity_uses_existing_forum_answer(monkeypatch, mode, lang, question):
    monkeypatch.setenv("AGENT_MODE", mode)

    async def unexpected(*args, **kwargs):
        raise AssertionError("Forum privacy must use the reviewed forum FAQ")

    for name in ("_build_context", "ollama_available", "answer_citizen_question", "_claude_answer"):
        monkeypatch.setattr(agent, name, unexpected)
    response = await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question=question, lang=lang), db=object(),
    )
    assert response == agent._deterministic_response("forum", lang) | {"question": question}
    assert response["sources"] == [{"type": "knowledge_base", "topic": "forum"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["deterministic", "hybrid"])
@pytest.mark.parametrize("lang,question", ROUND2_FEEDBACK_CASES + NEW_FEEDBACK_CASES)
async def test_feedback_anonymity_keeps_fallback_or_retrieval(monkeypatch, mode, lang, question):
    monkeypatch.setenv("AGENT_MODE", mode)
    assert agent._canonical_response(question, lang) is None
    assert "anonymity" not in agent._select_fact_blocks(question)

    class RetrievalReached(Exception):
        pass

    async def context(actual_question, actual_lang, db):
        assert (actual_question, actual_lang) == (question, lang)
        raise RetrievalReached

    monkeypatch.setattr(agent, "_build_context", context)
    if mode == "hybrid":
        with pytest.raises(RetrievalReached):
            await agent.ask_agent.__wrapped__(
                object(), agent.AskRequest(question=question, lang=lang), db=object(),
            )
    else:
        response = await agent.ask_agent.__wrapped__(
            object(), agent.AskRequest(question=question, lang=lang), db=object(),
        )
        topics = agent._select_fact_blocks(question)
        assert topics in ([], ["contact"])
        if topics:
            assert agent._FACTS["contact"][lang] in response["answer"]
        else:
            assert response["answer"] == agent._with_disclaimer(agent._FAQ_FALLBACK[lang], lang)


@pytest.mark.parametrize("lang,question,topics", NEW_BARE_CASES)
def test_review_bare_probes_keep_existing_topics(lang, question, topics):
    assert agent._canonical_response(question, lang) is None
    assert agent._select_fact_blocks(question) == topics
