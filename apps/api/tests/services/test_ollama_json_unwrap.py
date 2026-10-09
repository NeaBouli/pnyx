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
