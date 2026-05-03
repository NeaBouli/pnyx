"""Regression tests for Ollama-backed use cases."""

from types import SimpleNamespace

import pytest

from services import ollama_service
from services.compass_generator import generate_questions_from_bill
from services.scraper_healer import _looks_like_css_selector


def test_ollama_model_matching_accepts_base_name(monkeypatch):
    monkeypatch.setattr(ollama_service, "OLLAMA_MODEL", "llama3.2:3b")

    assert ollama_service._ollama_model_matches(["llama3.2:3b"]) is True
    assert ollama_service._ollama_model_matches(["llama3.2"]) is True
    assert ollama_service._ollama_model_matches(["mistral:latest"]) is False


def test_parse_ollama_json_tolerates_markdown_fences():
    raw = '```json\n{"pill_el": "ok", "categories": ["Νομοθεσία"]}\n```'

    assert ollama_service._parse_ollama_json(raw) == {
        "pill_el": "ok",
        "categories": ["Νομοθεσία"],
    }


@pytest.mark.asyncio
async def test_summarize_bill_falls_back_when_ollama_unavailable(monkeypatch):
    async def unavailable():
        return False

    monkeypatch.setattr(ollama_service, "ollama_available", unavailable)

    summary = await ollama_service.summarize_bill(
        "Τίτλος νόμου",
        "x" * 1200,
        lang="el",
        pill="Σύντομη περιγραφή",
        status="ACTIVE",
        categories=["Παιδεία"],
    )

    assert "Τίτλος νόμου" in summary
    assert "Σύντομη περιγραφή" in summary
    assert "Ανοιχτή ψηφοφορία" in summary


@pytest.mark.asyncio
async def test_scraper_ollama_summary_requires_expected_json(monkeypatch):
    from routers import scraper

    async def valid_json(prompt, max_tokens=500):
        return {
            "pill_el": "Σύντομη πρόταση",
            "pill_en": "Short sentence",
            "summary_short_el": "Σύντομη ανάλυση",
            "summary_short_en": "Short analysis",
            "summary_long_el": "Πλήρης ανάλυση",
            "summary_long_en": "Full analysis",
            "categories": ["Νομοθεσία"],
        }

    monkeypatch.setattr(scraper, "ollama_json_generate", valid_json)

    result = await scraper.summarize_ollama("Κείμενο νομοσχεδίου" * 200, "Τίτλος")

    assert result is not None
    assert result["categories"] == ["Νομοθεσία"]


@pytest.mark.asyncio
async def test_scraper_ollama_summary_rejects_incomplete_json(monkeypatch):
    from routers import scraper

    async def incomplete_json(prompt, max_tokens=500):
        return {"pill_el": "Μόνο ένα πεδίο"}

    monkeypatch.setattr(scraper, "ollama_json_generate", incomplete_json)

    assert await scraper.summarize_ollama("Κείμενο", "Τίτλος") is None


@pytest.mark.asyncio
async def test_scraper_status_uses_central_ollama_availability(monkeypatch):
    from routers import scraper

    async def unavailable():
        return False

    monkeypatch.setattr(scraper, "ollama_available", unavailable)

    status = await scraper.scraper_status()

    assert status["providers"]["ollama"]["status"] == "offline"
    assert status["active_provider"] in {"huggingface", "rule_based"}


def test_scraper_healer_rejects_prose_and_accepts_selectors():
    assert _looks_like_css_selector(".law-list .title") is True
    assert _looks_like_css_selector("main article h2") is True
    assert _looks_like_css_selector("Here is the selector: .title") is False
    assert _looks_like_css_selector(".title\n.explanation") is False


@pytest.mark.asyncio
async def test_compass_generator_uses_json_helper(monkeypatch):
    import services.compass_generator as compass_generator

    async def available():
        return True

    async def json_questions(prompt, max_tokens=500):
        return [
            {
                "text_en": "Public services should be digitized.",
                "category_en": "Technology",
                "explanation_en": "It divides voters on state modernization.",
            }
        ]

    async def translate(text, target_lang, source_lang=""):
        return f"EL:{text}"

    monkeypatch.setattr(compass_generator, "ollama_available", available)
    monkeypatch.setattr(compass_generator, "ollama_json_generate", json_questions)
    monkeypatch.setattr(compass_generator, "deepl_translate", translate)

    bill = SimpleNamespace(
        id="GR-TEST",
        title_en="Digital public services",
        title_el="Ψηφιακές δημόσιες υπηρεσίες",
        categories=["Τεχνολογία & Ψηφιακή Πολιτική"],
    )

    questions = await generate_questions_from_bill(bill, 62.0, db=None)

    assert len(questions) == 1
    assert questions[0]["source_bill_id"] == "GR-TEST"
    assert questions[0]["category"] == "Τεχνολογία & Ψηφιακή Πολιτική"
