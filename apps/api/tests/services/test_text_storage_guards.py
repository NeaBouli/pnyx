"""Synthetic transport failures and generated extraction at the storage boundary."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from routers import scraper
from services import parliament_fetcher as fetcher
from services.content_provenance import content_sha256
from services.text_quality import check_generated_text


GOOD = "Οι αρμοδιότητες των δημόσιων υπηρεσιών και οι προϋποθέσεις εφαρμογής περιγράφονται αναλυτικά. " * 8
BAD = "Δυστυχώς, δεν μπορώ να παράσχω σύνοψη του εγγράφου. " + GOOD
ERRORS = (
    'You don\'t have permission to access "http://www.hellenicparliament.gr/synthetic" on this server. Reference #synthetic',
    "Access Denied", "403 Forbidden", "Request Rejected",
    "Attention Required! | Cloudflare\nSorry, you have been blocked\nCloudflare Ray ID: synthetic",
    "Akamai reference #synthetic\nThe requested URL was rejected.",
)


@pytest.mark.parametrize("body", ERRORS)
def test_shared_error_page_reason_and_fetch_detectors(body: str) -> None:
    text = body + "\n" + "Synthetic request information. " * 12
    assert "error_page" in check_generated_text(text, field="summary_long_el").reasons
    assert "error_page" in check_generated_text(text, field="summary_long_en").reasons
    assert scraper._looks_like_access_denied_body(text)
    assert fetcher._is_bad_parliament_text(text)


@pytest.mark.parametrize("bulk", [False, True])
@pytest.mark.parametrize("body", ERRORS)
async def test_official_error_pages_never_reach_enrichment_storage(
    monkeypatch: pytest.MonkeyPatch, body: str, bulk: bool,
) -> None:
    bill = SimpleNamespace(id="SYNTH-1", source="PARLIAMENT", summary_long_el=None,
                           parliament_url="https://example.test/synthetic")
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalar_one_or_none=lambda: bill, scalars=lambda: SimpleNamespace(all=lambda: [bill]),
    )))
    commit = AsyncMock()
    monkeypatch.setattr(fetcher, "commit_and_invalidate_representation", commit)
    monkeypatch.setattr(fetcher, "_fetch_bill_text_result", AsyncMock(return_value=(body + "\n" + GOOD, "fetched")))
    if bulk:
        result = await fetcher.enrich_all_bills(db)
        assert result["enriched"] == 0 and result["failed"] == 1
    else:
        result = await fetcher.enrich_bill_with_text(bill.id, db)
        assert not result["success"]
        commit.assert_not_awaited()
    assert bill.summary_long_el is None


def _channels(monkeypatch: pytest.MonkeyPatch, generated: str, final: str = "") -> AsyncMock:
    for name, text in (("_channel_jina_markdown", ""), ("_channel_jina_html", ""),
                       ("_channel_ollama_extract", generated), ("_channel_playwright", final)):
        mock = AsyncMock(return_value=text)
        mock.__name__ = name
        monkeypatch.setattr(fetcher, name, mock)
    return fetcher._channel_playwright


async def test_rejected_generated_channel_tries_next_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    last = _channels(monkeypatch, BAD, GOOD)
    text, outcome = await fetcher._fetch_bill_text_result("SYNTH-1", "https://example.test/synthetic")
    assert outcome == "fetched" and text == GOOD
    assert not isinstance(text, fetcher.GeneratedExtraction)
    last.assert_awaited_once()


@pytest.mark.parametrize("bulk", [False, True])
async def test_generated_extraction_persists_exact_provenance(monkeypatch: pytest.MonkeyPatch, bulk: bool) -> None:
    last = _channels(monkeypatch, GOOD)
    bill = SimpleNamespace(id="SYNTH-1", source="PARLIAMENT", summary_long_el=None,
                           generated_content_provenance=None, parliament_url="https://example.test/synthetic")
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalar_one_or_none=lambda: bill, scalars=lambda: SimpleNamespace(all=lambda: [bill]),
    )))
    monkeypatch.setattr(fetcher, "commit_and_invalidate_representation", AsyncMock())
    if bulk:
        assert (await fetcher.enrich_all_bills(db))["enriched"] == 1
    else:
        assert (await fetcher.enrich_bill_with_text(bill.id, db))["success"]
    assert bill.generated_content_provenance == {"summary_long_el": content_sha256(GOOD)}
    last.assert_not_awaited()


def test_official_prose_bypasses_language_gate_and_clears_generated_ownership() -> None:
    official = "Η ανάθεση στο Example Endpoint Package από SYNTHETIC TIMING SYSTEMS AE. " * 6
    bill = SimpleNamespace(id="SYNTH-1", summary_long_el=None, generated_content_provenance=None)
    assert not check_generated_text(official, field="summary_long_el").ok
    assert fetcher.store_fetched_text(bill, official)
    assert bill.summary_long_el == official and bill.generated_content_provenance is None


def test_storage_rechecks_generated_rejection_without_removing_sensitive_marker() -> None:
    from services.bill_visibility import is_public_bill

    bill = SimpleNamespace(id="SYNTH-1", source="DIAVGEIA", title_el="Συνθετικός τίτλος",
                           summary_short_el=None, summary_long_el=GOOD + " ΑΜΚΑ", generated_content_provenance=None)
    assert not is_public_bill(bill)
    assert not fetcher.store_fetched_text(bill, fetcher.GeneratedExtraction(BAD))
    assert not is_public_bill(bill)
    empty = SimpleNamespace(id="SYNTH-2", summary_long_el=None)
    assert not fetcher.store_fetched_text(empty, fetcher.GeneratedExtraction(BAD))
    assert empty.summary_long_el is None
