"""No external services or bill data: exercise the generation boundaries."""

import inspect
from typing import Any
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


def _summary(text: str = GOOD) -> dict[str, Any]:
    return {"pill_el": GOOD, "summary_short_el": GOOD, "summary_long_el": text,
            "pill_en": "Synthetic procedure", "summary_short_en": "The regulation defines a procedure.",
            "summary_long_en": "The synthetic regulation defines a procedure for public services."}


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


async def test_rule_output_keeps_official_excerpt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scraper, "summarize_ollama", AsyncMock(return_value=None))
    monkeypatch.setattr(scraper, "summarize_huggingface", AsyncMock(return_value=None))
    result = await scraper.generate_summaries(BAD, "Δοκιμαστικός τίτλος", bill_id="SYNTH-1")
    assert result["summary_long_el"] == BAD


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


async def test_import_writer_keeps_official_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    added: list[object] = []
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)), add=added.append)
    monkeypatch.setattr(scraper, "commit_and_invalidate_representation", AsyncMock())
    req = scraper.BillImportRequest(bills=[scraper.BillImportItem(
        bill_id="SYNTH-1", title_el="Δοκιμαστικός τίτλος", pill_el=BAD, summary_short_el=BAD,
        submitted_date="2026-01-01", url="https://example.test/bill",
    )])
    await inspect.unwrap(scraper.import_parliament_bills)(req, _auth=True, db=db, request=None)
    assert len(added) == 1
    assert added[0].pill_el == BAD and added[0].summary_short_el == BAD
    assert added[0].generated_content_provenance is None


@pytest.mark.parametrize("subject,label", [
    ("Προμήθεια anti-virus Example Endpoint Package for synthetic office", "SYNTHETIC TIMING SYSTEMS AE"),
    ("ΑΠΟΦΑΣΗ ΑΝΑΘΕΣΗΣ ΣΤΗΝ SYNTHETIC TIMING SYSTEMS AE", "[unknown:123]"),
])
async def test_diavgeia_conversion_keeps_official_fields(monkeypatch: pytest.MonkeyPatch, subject: str, label: str) -> None:
    from services import diavgeia_scraper

    added: list[object] = []
    row = ("SYNTH-1", subject, "Α.2", label,
           "https://example.test/bill", "OTHER", None, None, None)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(fetchall=lambda: [row])),
                         add=added.append, flush=AsyncMock())
    monkeypatch.setattr(diavgeia_scraper, "_sync_existing_decision_bill_scopes", AsyncMock(return_value=0))
    monkeypatch.setattr(diavgeia_scraper, "commit_and_invalidate_representation", AsyncMock())
    result = await diavgeia_scraper.convert_decisions_to_bills(db)
    assert result["created"] == 1
    assert added[0].pill_el == f"Διαύγεια: {label}"
    assert added[0].summary_short_el == added[0].title_el == subject
    assert added[0].generated_content_provenance is None


async def test_automatic_org_resolution_keeps_official_latin_label(monkeypatch: pytest.MonkeyPatch) -> None:
    from routers import admin
    from services import diavgeia_org_lookup

    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(fetchall=lambda: [("SYNTH-1", "Διαύγεια: [unknown:123]")])))
    monkeypatch.setattr(diavgeia_org_lookup, "resolve_unknown_label", AsyncMock(return_value="SYNTHETIC TIMING SYSTEMS AE"))
    monkeypatch.setattr(admin, "commit_and_invalidate_representation", AsyncMock())
    result = await inspect.unwrap(admin.admin_resolve_orgs)(_key=True, db=db, request=None)
    assert result["resolved"] == 1
    assert db.execute.await_count == 2
    assert db.execute.await_args.args[1]["pill"] == "Διαύγεια: SYNTHETIC TIMING SYSTEMS AE"


async def test_human_admin_edits_remain_ungated(monkeypatch: pytest.MonkeyPatch) -> None:
    from routers import admin

    bill = SimpleNamespace(summary_short_el=GOOD, generated_content_provenance={"summary_short_el": content_sha256(GOOD)})
    db = SimpleNamespace(get=AsyncMock(return_value=bill))
    monkeypatch.setattr(admin, "commit_and_invalidate_representation", AsyncMock())
    await inspect.unwrap(admin.admin_update_bill)("SYNTH-1", admin.BillUpdateRequest(summary_short_el=BAD),
                                                _key=True, db=db, request=None)
    assert bill.summary_short_el == BAD
    assert bill.generated_content_provenance is None


@pytest.mark.parametrize("empty", [None, "", " \n\t"])
@pytest.mark.parametrize("field", ["pill_el", "summary_short_el", "summary_long_el",
                                    "pill_en", "summary_short_en", "summary_long_en"])
async def test_empty_mandatory_provider_field_falls_through(
    monkeypatch: pytest.MonkeyPatch, empty: str | None, field: str,
) -> None:
    response = _summary()
    response[field] = empty
    monkeypatch.setattr(scraper, "summarize_ollama", AsyncMock(return_value=response))
    second = AsyncMock(return_value=_summary())
    monkeypatch.setattr(scraper, "summarize_huggingface", second)
    result = await scraper.generate_summaries(GOOD * 10, "Συνθετικός τίτλος")
    assert result["_provider"] == "huggingface"
    second.assert_awaited_once()


async def test_import_deterministic_latin_metadata_has_no_generated_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    added: list[object] = []
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)), add=added.append)
    monkeypatch.setattr(scraper, "commit_and_invalidate_representation", AsyncMock())
    title = "SYNTHETIC TIMING SYSTEMS AE Example Endpoint Package"
    req = scraper.BillImportRequest(bills=[scraper.BillImportItem(
        bill_id="SYNTH-1", title_el=title, submitted_date="2026-01-01", url="https://example.test/bill",
    )])
    await inspect.unwrap(scraper.import_parliament_bills)(req, _auth=True, db=db, request=None)
    assert title in added[0].summary_short_el
    assert title in added[0].pill_el
    assert added[0].generated_content_provenance is None


def test_sensitive_generated_summary_survives_rejected_replacement() -> None:
    from services.bill_visibility import is_public_bill

    value = BAD + " ΑΜΚΑ συνθετικό στοιχείο"
    bill = SimpleNamespace(id="SYNTH-1", source="DIAVGEIA", title_el="Συνθετικός τίτλος",
                           summary_short_el=value, summary_long_el=None, ai_summary_reviewed=False,
                           generated_content_provenance={"summary_short_el": content_sha256(value)})
    assert not is_public_bill(bill)
    for candidate in (BAD, GOOD):
        assert not apply_generated_content(bill, "summary_short_el", candidate)
        assert bill.summary_short_el == value
        assert not is_public_bill(bill)


async def test_rule_based_storage_preserves_latin_excerpt_without_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    added: list[Any] = []
    official = "Ανάθεση στη SYNTHETIC TIMING SYSTEMS AE για το Example Endpoint Package. " * 8
    monkeypatch.setattr(scraper, "summarize_ollama", AsyncMock(return_value=None))
    monkeypatch.setattr(scraper, "summarize_huggingface", AsyncMock(return_value=None))
    monkeypatch.setattr(scraper, "fetch_with_fallback", AsyncMock(return_value=official))
    monkeypatch.setattr(scraper, "extract_bill_text", lambda _: official)
    monkeypatch.setattr(scraper, "commit_and_invalidate_representation", AsyncMock())
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)), add=added.append)
    await inspect.unwrap(scraper.fetch_and_store)(url="https://example.test/synthetic", title_el=official[:150],
                                                bill_id="SYNTH-1", _auth=True, db=db, request=None)
    assert added[0].summary_long_el == official
    assert added[0].generated_content_provenance is None


async def test_on_demand_official_template_bypasses_gate_and_generated_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    import redis.asyncio as redis
    from services.content_provenance import OfficialText

    title = "SYNTHETIC TIMING SYSTEMS AE Example Endpoint Package"
    bill = SimpleNamespace(summary_short_el=None, summary_short_en=None, pill_el=None, pill_en=None,
                           summary_long_el=None, summary_long_en=None, source="PARLIAMENT",
                           title_el=title, status=BillStatus.ACTIVE, categories=[])
    cache = SimpleNamespace(get=AsyncMock(return_value=None), setex=AsyncMock())
    monkeypatch.setattr(redis, "from_url", lambda *a, **k: cache)
    monkeypatch.setattr(parliament, "is_public_bill", lambda _: True)
    monkeypatch.setattr(ollama_service, "ollama_available", AsyncMock(return_value=False))
    summary = await ollama_service.summarize_bill(title, bill_id="SYNTH-1")
    assert isinstance(summary, OfficialText) and title in summary
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: bill)))
    result = await inspect.unwrap(parliament.get_bill_summary)(request=None, bill_id="SYNTH-1", lang="el", db=db)
    assert title in result["summary"] and result["source"] == "fallback"
    cache.setex.assert_not_awaited()


@pytest.mark.parametrize("error_page", [False, True])
async def test_scheduled_metadata_preserves_official_latin_fields(
    monkeypatch: pytest.MonkeyPatch, error_page: bool,
) -> None:
    import ast
    import logging
    import sys
    from pathlib import Path
    from services import bill_lifecycle, representation_cache, scraper_state, telegram_community

    official = "Ανάθεση στη SYNTHETIC TIMING SYSTEMS AE για το Example Endpoint Package"
    full_text = "Access Denied\n" + GOOD * 8 if error_page else official * 8
    rows: list[Any] = []

    class DB:
        async def __aenter__(self) -> "DB":
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def execute(self, statement: Any) -> Any:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []), scalar_one_or_none=lambda: None)

        def add(self, value: Any) -> None:
            rows.append(value)

    monkeypatch.setitem(sys.modules, "database", SimpleNamespace(AsyncSessionLocal=DB))
    monkeypatch.setattr(scraper, "scrape_parliament_bills", AsyncMock(return_value=[{
        "law_num": "SYNTH-1", "title_el": official, "pill_el": official, "summary_short_el": official,
        "summary_long_el": full_text, "date": "2026-01-01", "url": "https://example.test/synthetic",
    }]))
    monkeypatch.setattr(scraper_state, "is_circuit_open", AsyncMock(return_value=False))
    for name in ("record_run", "record_success", "record_failure"):
        monkeypatch.setattr(scraper_state, name, AsyncMock())
    monkeypatch.setattr(representation_cache, "commit_and_invalidate_representation", AsyncMock())
    monkeypatch.setattr(telegram_community, "notify_announced", AsyncMock())
    monkeypatch.setattr(bill_lifecycle, "run_bill_lifecycle", AsyncMock(return_value={}))
    path = Path(__file__).resolve().parents[2] / "main.py"
    node = next(node for node in ast.parse(path.read_text()).body
                if isinstance(node, ast.AsyncFunctionDef) and node.name == "scheduled_scrape")
    namespace: dict[str, Any] = {"logger": logging.getLogger("test.metadata")}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    await namespace["scheduled_scrape"]()
    assert len(rows) == 1
    assert rows[0].pill_el == rows[0].summary_short_el == rows[0].title_el == official
    assert rows[0].summary_long_el == (None if error_page else full_text)
    assert rows[0].generated_content_provenance is None


async def test_provider_cannot_override_generated_field_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _summary(BAD)
    response.update(categories=[], _generated_fields=())
    monkeypatch.setattr(scraper, "ollama_json_generate", AsyncMock(return_value=response))
    second = AsyncMock(return_value=_summary())
    monkeypatch.setattr(scraper, "summarize_huggingface", second)
    result = await scraper.generate_summaries(GOOD * 8, "Συνθετικός τίτλος")
    assert result["_provider"] == "huggingface"
    second.assert_awaited_once()
