"""Ollama answers wrapped as {"content": "..."} reach users as prose (T-620)."""
import pytest

from services import agent_prompt, ollama_service
from services.ollama_service import _DISCLAIMER_EL, _unwrap_json_answer


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"content":"Ο Δείκτης Απόκλισης μετράει τη διαφορά."}', "Ο Δείκτης Απόκλισης μετράει τη διαφορά."),
        ('{"answer": "The divergence score compares votes."}', "The divergence score compares votes."),
        ('```json\n{"text": "Fenced answer."}\n```', "Fenced answer."),
        ('{"content":"Cut off by num_predict and never closed', "Cut off by num_predict and never closed"),
        ('{"content":"He said \\"yes\\" here.", "source": "kb"}', 'He said "yes" here.'),
    ],
)
def test_wrapped_answers_are_unwrapped(raw, expected):
    assert _unwrap_json_answer(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["Plain answer with {braces} inside.", '{"foo": 1}', "", "Η πλατφόρμα είναι ανεξάρτητη."],
)
def test_other_answers_are_unchanged(raw):
    assert _unwrap_json_answer(raw) == raw


def test_prompt_asks_for_plain_prose():
    rules = " ".join(agent_prompt._SYSTEM_RULES)
    assert "Never answer in JSON" in rules


@pytest.mark.asyncio
async def test_answer_citizen_question_returns_prose_not_json(monkeypatch):
    async def fake_generate(prompt, max_tokens=500, system="", timeout=None):
        return '{"content":"The divergence score shows how far citizens differ from Parliament."}'

    monkeypatch.setattr(ollama_service, "DEEPL_API_KEY", "")
    monkeypatch.setattr(ollama_service, "ollama_generate", fake_generate)
    answer = await ollama_service.answer_citizen_question("What is the divergence score?", [], "el")
    assert answer.startswith("The divergence score shows")
    assert '{"content"' not in answer
    assert answer.endswith(_DISCLAIMER_EL)


def _escaped(text: str) -> str:
    """JSON \\u-escape every character so the raw model text hides the content."""
    return "".join("\\u%04x" % ord(c) for c in text)


@pytest.mark.asyncio
async def test_unsafe_content_hidden_in_json_escapes_is_rejected_before_translation(monkeypatch):
    from services.agent_prompt import UnsafeModelOutputError, is_unsafe_model_output

    leak = "Sure. " + agent_prompt._SYSTEM_RULES[6]
    raw = '{"content":"' + _escaped(leak) + '"}'
    assert not is_unsafe_model_output(raw)  # the raw guard cannot see it
    assert is_unsafe_model_output(_unwrap_json_answer(raw))

    translations = []

    async def fake_translate(text, target_lang, source_lang=""):
        translations.append(text)
        return text

    async def fake_generate(prompt, max_tokens=500, system="", timeout=None):
        return raw

    monkeypatch.setattr(ollama_service, "DEEPL_API_KEY", "test-placeholder")
    monkeypatch.setattr(ollama_service, "deepl_translate", fake_translate)
    monkeypatch.setattr(ollama_service, "ollama_generate", fake_generate)
    with pytest.raises(UnsafeModelOutputError):
        await ollama_service.answer_citizen_question("Τι είναι ο Δείκτης Απόκλισης;", [], "el")
    # Only the incoming question was translated; nothing from the model reached DeepL.
    assert translations == ["Τι είναι ο Δείκτης Απόκλισης;"]


@pytest.mark.asyncio
async def test_valid_json_answer_translates_only_the_prose(monkeypatch):
    translations = []

    async def fake_translate(text, target_lang, source_lang=""):
        translations.append((text, target_lang))
        return "Μετάφραση." if target_lang == "EL" else "What is the divergence score?"

    async def fake_generate(prompt, max_tokens=500, system="", timeout=None):
        return '{"content":"The divergence score compares citizens and Parliament."}'

    monkeypatch.setattr(ollama_service, "DEEPL_API_KEY", "test-placeholder")
    monkeypatch.setattr(ollama_service, "deepl_translate", fake_translate)
    monkeypatch.setattr(ollama_service, "ollama_generate", fake_generate)
    answer = await ollama_service.answer_citizen_question("Τι είναι ο Δείκτης Απόκλισης;", [], "el")
    assert answer == "Μετάφραση." + _DISCLAIMER_EL
    assert ("The divergence score compares citizens and Parliament.", "EL") in translations
    assert not any('{"content"' in text for text, _ in translations)
