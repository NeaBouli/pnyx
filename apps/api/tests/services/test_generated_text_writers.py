"""No external services or bill data: exercise the generation boundaries."""

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from models import BillStatus
from routers import parliament, scraper
from services import ollama_service
from services.content_provenance import apply_generated_content, content_sha256


GOOD = "Η ρύθμιση ορίζει τη διαδικασία λειτουργίας των δημόσιων υπηρεσιών."
BAD = "Απάντηση: Για να βρεις την πληροφορία, αναζήτησε το έγγραφο."


def _summary(text: str = GOOD) -> dict[str, str]:
    return {"pill_el": GOOD, "summary_short_el": GOOD, "summary_long_el": text,
            "summary_short_en": "The regulation defines a procedure."}


@pytest.mark.parametrize("hf_bad", [False, True])
async def test_provider_fallthrough(monkeypatch: pytest.MonkeyPatch, hf_bad: bool) -> None:
    first = AsyncMock(return_value=_summary(BAD))
    second = AsyncMock(return_value=_summary(BAD if hf_bad else GOOD))
    monkeypatch.setattr(scraper, "summarize_ollama", first)
    monkeypatch.setattr(scraper, "summarize_huggingface", second)
    result = await scraper.generate_summaries(GOOD * 10, "Δοκιμαστικός τίτλος", bill_id="SYNTH-1")
    assert result["_provider"] == ("rule_based" if hf_bad else "huggingface")
    assert BAD not in result.values()
    first.assert_awaited_once()
    second.assert_awaited_once()


async def test_bad_rule_output_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scraper, "summarize_ollama", AsyncMock(return_value=None))
    monkeypatch.setattr(scraper, "summarize_huggingface", AsyncMock(return_value=None))
    result = await scraper.generate_summaries(BAD, "Δοκιμαστικός τίτλος", bill_id="SYNTH-1")
    assert result["summary_long_el"] is None


def test_existing_value_survives_rejection_without_text_in_log(caplog: pytest.LogCaptureFixture) -> None:
    bill = SimpleNamespace(id="SYNTH-1", summary_short_el=GOOD, ai_summary_reviewed=False,
                           generated_content_provenance={"summary_short_el": content_sha256(GOOD)})
    assert not apply_generated_content(bill, "summary_short_el", BAD)
    assert bill.summary_short_el == GOOD
    assert "SYNTH-1" in caplog.text and "refusal_or_meta" in caplog.text
    assert BAD not in caplog.text and GOOD not in caplog.text


@pytest.mark.parametrize("translation", ["", BAD, "English text instead of Greek.", GOOD])
async def test_summary_translation_gate_and_fallback(monkeypatch: pytest.MonkeyPatch, translation: str) -> None:
    monkeypatch.setattr(ollama_service, "ollama_available", AsyncMock(return_value=True))
    monkeypatch.setattr(ollama_service, "ollama_generate", AsyncMock(return_value="The synthetic regulation defines how public services operate and process applications."))
    monkeypatch.setattr(ollama_service, "deepl_translate", AsyncMock(return_value=translation))
    result = await ollama_service.summarize_bill("Δοκιμαστικός τίτλος", GOOD * 20, bill_id="SYNTH-1")
    assert result == GOOD if translation == GOOD else "Δοκιμαστικός τίτλος" in result
    assert BAD not in result


async def test_refusal_is_rejected_before_translation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ollama_service, "ollama_available", AsyncMock(return_value=True))
    monkeypatch.setattr(ollama_service, "ollama_generate", AsyncMock(return_value="I'm sorry, I cannot provide a summary of this synthetic document."))
    translate = AsyncMock()
    monkeypatch.setattr(ollama_service, "deepl_translate", translate)
    result = await ollama_service.summarize_bill("Δοκιμαστικός τίτλος", GOOD * 20, bill_id="SYNTH-1")
    assert "Δοκιμαστικός τίτλος" in result
    translate.assert_not_awaited()


@pytest.mark.parametrize("cached", [None, BAD])
async def test_on_demand_rejection_never_cached(monkeypatch: pytest.MonkeyPatch, cached: str | None) -> None:
    import redis.asyncio as redis

    bill = SimpleNamespace(summary_short_el=None, summary_short_en=None, pill_el=None, pill_en=None,
                           summary_long_el=None, summary_long_en=None, source="PARLIAMENT",
                           title_el="Δοκιμαστικός τίτλος", status=BillStatus.ACTIVE, categories=[])
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: bill)))
    cache = SimpleNamespace(get=AsyncMock(return_value=cached), setex=AsyncMock())
    monkeypatch.setattr(redis, "from_url", lambda *a, **k: cache)
    monkeypatch.setattr(parliament, "is_public_bill", lambda bill: True)
    monkeypatch.setattr(ollama_service, "summarize_bill", AsyncMock(return_value=BAD))
    with pytest.raises(HTTPException) as exc:
        await inspect.unwrap(parliament.get_bill_summary)(request=None, bill_id="SYNTH-1", lang="el", db=db)
    assert exc.value.status_code == 503
    cache.setex.assert_not_awaited()


async def test_fetch_writer_checks_result_again(monkeypatch: pytest.MonkeyPatch) -> None:
    added: list[object] = []
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)), add=added.append)
    monkeypatch.setattr(scraper, "fetch_with_fallback", AsyncMock(return_value=GOOD))
    monkeypatch.setattr(scraper, "generate_summaries", AsyncMock(return_value=_summary(BAD)))
    monkeypatch.setattr(scraper, "commit_and_invalidate_representation", AsyncMock())
    await inspect.unwrap(scraper.fetch_and_store)(url="https://example.test/bill", title_el="Δοκιμή",
                                                bill_id="SYNTH-1", _auth=True, db=db, request=None)
    assert added[0].summary_long_el is None
    assert added[0].summary_short_el == GOOD


async def test_import_writer_rejects_generated_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    added: list[object] = []
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)), add=added.append)
    monkeypatch.setattr(scraper, "commit_and_invalidate_representation", AsyncMock())
    req = scraper.BillImportRequest(bills=[scraper.BillImportItem(
        bill_id="SYNTH-1", title_el="Δοκιμαστικός τίτλος", pill_el=BAD, summary_short_el=BAD,
        submitted_date="2026-01-01", url="https://example.test/bill",
    )])
    await inspect.unwrap(scraper.import_parliament_bills)(req, _auth=True, db=db, request=None)
    assert len(added) == 1
    assert added[0].pill_el is None and added[0].summary_short_el is None


async def test_diavgeia_conversion_rejects_generated_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import diavgeia_scraper

    added: list[object] = []
    row = ("SYNTH-1", BAD, "Α.2", "Tôi xin lỗi, nhưng tôi không thể.",
           "https://example.test/bill", "OTHER", None, None, None)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(fetchall=lambda: [row])),
                         add=added.append, flush=AsyncMock())
    monkeypatch.setattr(diavgeia_scraper, "_sync_existing_decision_bill_scopes", AsyncMock(return_value=0))
    monkeypatch.setattr(diavgeia_scraper, "commit_and_invalidate_representation", AsyncMock())
    result = await diavgeia_scraper.convert_decisions_to_bills(db)
    assert result["created"] == 1
    assert added[0].pill_el is None and added[0].summary_short_el is None


async def test_automatic_org_resolution_is_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    from routers import admin
    from services import diavgeia_org_lookup

    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(fetchall=lambda: [("SYNTH-1", "Διαύγεια: [unknown:123]")])))
    monkeypatch.setattr(diavgeia_org_lookup, "resolve_unknown_label", AsyncMock(return_value="Tôi xin lỗi, nhưng tôi không thể."))
    monkeypatch.setattr(admin, "commit_and_invalidate_representation", AsyncMock())
    result = await inspect.unwrap(admin.admin_resolve_orgs)(_key=True, db=db, request=None)
    assert result["failed"] == 1
    assert db.execute.await_count == 1  # SELECT only; no UPDATE.


async def test_human_admin_edits_remain_ungated(monkeypatch: pytest.MonkeyPatch) -> None:
    from routers import admin

    bill = SimpleNamespace(summary_short_el=GOOD, generated_content_provenance={"summary_short_el": content_sha256(GOOD)})
    db = SimpleNamespace(get=AsyncMock(return_value=bill))
    monkeypatch.setattr(admin, "commit_and_invalidate_representation", AsyncMock())
    await inspect.unwrap(admin.admin_update_bill)("SYNTH-1", admin.BillUpdateRequest(summary_short_el=BAD),
                                                _key=True, db=db, request=None)
    assert bill.summary_short_el == BAD
    assert bill.generated_content_provenance is None
