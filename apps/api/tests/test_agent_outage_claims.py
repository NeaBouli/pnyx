"""BUG-CHAT-20261013-01: invented platform outage/maintenance claims are replaced."""
import pytest

from routers import agent
from routers.agent import _claims_platform_outage

# The answer from Gio's screenshot (12.10.2026) and typical variants.
OUTAGE_CLAIMS = [
    "Η πλατφόρμα δεν ανταποκρίνεται προς το παρόν στα αιτήματα των χρηστών.",
    "Η πλατφόρμα βρίσκεται σε συντήρηση και θα επανέλθει σύντομα.",
    "Η εφαρμογή είναι προσωρινά εκτός λειτουργίας.",
    "Ο ιστότοπος ekklesia.gr είναι υπό συντήρηση.",
    "The platform is currently under maintenance.",
    "The ekklesia.gr website is down for maintenance right now.",
    "The app is not responding at the moment.",
    "The platform is experiencing an outage.",
    # T-9113 Codex review: accents/case, inflections, temporary wording.
    "Η πλατφόρμα είναι ΣΕ ΣΥΝΤΗΡΗΣΗ.",
    "Η πλατφορμα ειναι εκτος λειτουργιας.",
    "Η πλατφόρμα συντηρείται αυτή τη στιγμή.",
    "Η πλατφόρμα δεν λειτουργεί προσωρινά.",
    "The platform is temporarily unavailable.",
    # Round 2 review.
    "Η πλατφόρμα δεν λειτουργεί αυτή τη στιγμή.",
    "Η πλατφόρμα δεν είναι διαθέσιμη αυτή τη στιγμή.",
    "The platform isn't responding at the moment.",
    "Δυστυχώς, η πλατφόρμα βρίσκεται σε συντήρηση.",
    # Round 3 review.
    "Η πλατφόρμα\nδεν ανταποκρίνεται προς το παρόν.",
    "**Η πλατφόρμα είναι σε συντήρηση.**",
    "Ενημέρωση:\n- Η πλατφόρμα είναι εκτός λειτουργίας",
    "Δυστυχώς, αυτή τη στιγμή η πλατφόρμα δεν ανταποκρίνεται.",
    "Το ekklesia.gr είναι προσωρινά εκτός λειτουργίας.",
    "The platform isn't working right now.",
]

# Legitimate answers that must stay untouched.
LEGITIMATE = [
    "Οι πληρωμές είναι προσωρινά σε παύση.",
    "Η εφαρμογή για iOS δεν είναι ακόμη διαθέσιμη.",
    "The iOS app is not available yet.",
    "Από 03/10/2026 η ZK ψηφοφορία βρίσκεται σε παύση για έλεγχο ασφαλείας.",
    "Το νομοσχέδιο αφορά εργασίες συντήρησης του οδικού δικτύου.",
    "Η εκκλησία του χωριού χρειάζεται συντήρηση σύμφωνα με την απόφαση.",
    "Η πλατφόρμα λειτουργεί κανονικά.",
    "The decision covers scheduled maintenance of school buildings.",
    # T-9113 Codex review: denials, other subjects, downloads.
    "The platform is not under maintenance.",
    "Η πλατφόρμα δεν είναι σε συντήρηση.",
    "Η εφαρμογή της απόφασης αφορά κτίριο που είναι σε συντήρηση.",
    "Η πλατφόρμα λειτουργεί, αλλά το σχολείο είναι σε συντήρηση.",
    "The app is currently downloading an update.",
    # Round 2 review.
    "The platform isn't under maintenance.",
    "Δεν ισχύει ότι η πλατφόρμα είναι σε συντήρηση.",
    "If the platform is under maintenance, try again later.",
    "Η πλατφόρμα λειτουργεί· το σχολείο είναι σε συντήρηση.",
    "The platform reports a school is under maintenance.",
    "Η πλατφόρμα της ΑΑΔΕ είναι σε συντήρηση.",
    "The iOS app is temporarily unavailable because it has not launched yet.",
    "Η εφαρμογή  της απόφασης αφορά κτίριο σε συντήρηση.",
    "Η εφαρμογή\tτης απόφασης αφορά κτίριο σε συντήρηση.",
    "The platform breaks this down into clear steps.",
    # Round 3 review.
    "Δεν ισχύει ότι\nη πλατφόρμα είναι σε συντήρηση.",
    "Η εφαρμογή δεν είναι διαθέσιμη για iOS ακόμη.",
    "The app is not available on iOS yet.",
    "Η πλατφόρμα συντηρείται από εθελοντές.",
]


@pytest.mark.parametrize("text", OUTAGE_CLAIMS)
def test_outage_claims_are_detected(text: str) -> None:
    assert _claims_platform_outage(text) is True


@pytest.mark.parametrize("text", LEGITIMATE)
def test_legitimate_answers_are_not_flagged(text: str) -> None:
    assert _claims_platform_outage(text) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("lang", ["el", "en"])
async def test_ollama_outage_answer_is_replaced_with_honest_fallback(monkeypatch: pytest.MonkeyPatch, lang: str) -> None:
    async def fake_context(question: str, lang: str, db: object):
        return [], [], False, []

    async def fake_available() -> bool:
        return True

    async def fake_answer(question: str, context: list, lang: str) -> str:
        return OUTAGE_CLAIMS[0] if lang == "el" else OUTAGE_CLAIMS[4]

    async def no_claude(*args: object, **kwargs: object) -> None:
        raise AssertionError("the outage guard must answer before any Claude call")

    monkeypatch.setattr(agent, "_build_context", fake_context)
    monkeypatch.setattr(agent, "ollama_available", fake_available)
    monkeypatch.setattr(agent, "answer_citizen_question", fake_answer)
    monkeypatch.setattr(agent, "_claude_answer", no_claude)
    monkeypatch.setattr(agent, "_is_answer_poor", lambda answer: False)
    monkeypatch.setattr(agent, "_sources", lambda *args, **kwargs: [{"type": "knowledge_base", "topic": "kept"}])

    response = await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question="Πώς ψηφίζω;" if lang == "el" else "How do I vote?", lang=lang), db=object(),
    )

    assert response["model"] == "outage-guard"
    assert "δεν ανταποκρίνεται" not in response["answer"] and "under maintenance" not in response["answer"]
    assert ("επιβεβαιωμένη" if lang == "el" else "no confirmed information") in response["answer"]
    assert "λειτουργεί κανονικά" not in response["answer"] and "working normally" not in response["answer"]
    assert response["sources"] == [{"type": "knowledge_base", "topic": "kept"}]


@pytest.mark.asyncio
async def test_claude_outage_answer_is_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_context(question: str, lang: str, db: object):
        return [], [], False, []

    async def unavailable() -> bool:
        return False

    async def claude(question: str, context: list, lang: str) -> str:
        return "The platform is currently under maintenance."

    monkeypatch.setattr(agent, "_build_context", fake_context)
    monkeypatch.setattr(agent, "ollama_available", unavailable)
    monkeypatch.setattr(agent, "_claude_answer", claude)

    response = await agent.ask_agent.__wrapped__(
        object(), agent.AskRequest(question="How do I vote?", lang="en"), db=object(),
    )

    assert response["model"] == "outage-guard"
    assert "under maintenance" not in response["answer"]
