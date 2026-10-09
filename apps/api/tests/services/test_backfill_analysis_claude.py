import importlib.util
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn
from unittest.mock import AsyncMock, Mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "backfill_analysis_claude.py"
spec = importlib.util.spec_from_file_location("backfill_analysis_claude", SCRIPT_PATH)
assert spec and spec.loader
backfill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backfill)

build_official_text_block = backfill.build_official_text_block
build_documents_block = backfill.build_documents_block
choose_pdfs = backfill.choose_pdfs
classify_pdf = backfill.classify_pdf
display_label = backfill.display_label
extract_pdf_links = backfill.extract_pdf_links
fallback_pdf_candidates = backfill.fallback_pdf_candidates
is_readable_pdf_text = backfill.is_readable_pdf_text
strip_table_of_contents = backfill.strip_table_of_contents


def _unexpected_call(*args: object, **kwargs: object) -> NoReturn:
    pytest.fail("unexpected external call or write", pytrace=False)


def _forbid_budget_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import claude_usage

    for name in ("reserve_budget", "track_usage", "charge_reservation", "release_budget"):
        monkeypatch.setattr(claude_usage, name, _unexpected_call)


@pytest.fixture(autouse=True)
def block_external_access(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncpg
    import redis.asyncio as aioredis

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(backfill, "_read_env_file", _unexpected_call)
    monkeypatch.setattr(backfill, "_http_text", _unexpected_call)
    monkeypatch.setattr(backfill.urllib.request, "urlopen", _unexpected_call)
    monkeypatch.setattr(backfill, "call_claude", _unexpected_call)
    monkeypatch.setattr(asyncpg, "connect", _unexpected_call)
    monkeypatch.setattr(aioredis, "from_url", _unexpected_call)


@pytest.fixture
def dummy_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-key-not-a-secret")


def test_extract_pdf_links_prefers_jina_image_alt_label():
    markdown = """
    [![Image 18: Αιτιολογική-Εισηγητική Έκθεση](https://www.hellenicparliament.gr/assets/pdf.png)](https://www.hellenicparliament.gr/UserFiles/a/13319369.pdf)
    [![Image 19: Διατάξεις Σχεδίου ή Πρότασης Νόμου](https://www.hellenicparliament.gr/assets/pdf.png)](https://www.hellenicparliament.gr/UserFiles/a/13319370.pdf)
    """

    links = extract_pdf_links(markdown)

    assert links == [
        {
            "label": "Αιτιολογική-Εισηγητική Έκθεση",
            "url": "https://www.hellenicparliament.gr/UserFiles/a/13319369.pdf",
        },
        {
            "label": "Διατάξεις Σχεδίου ή Πρότασης Νόμου",
            "url": "https://www.hellenicparliament.gr/UserFiles/a/13319370.pdf",
        },
    ]


def test_choose_pdfs_separates_analysis_from_official_text():
    links = [
        {"label": "Το φωτοτυπημένο σ/ν ή π/ν", "url": "https://example.test/scan.pdf"},
        {"label": "Αιτιολογική-Εισηγητική Έκθεση", "url": "https://example.test/analysis.pdf"},
        {"label": "Διατάξεις Σχεδίου ή Πρότασης Νόμου", "url": "https://example.test/full.pdf"},
    ]

    analysis_pdf, official_pdf = choose_pdfs(links)

    assert classify_pdf("Το φωτοτυπημένο σ/ν ή π/ν") == "skip"
    assert analysis_pdf == links[1]
    assert official_pdf == links[2]


def test_build_official_text_block_keeps_full_text_heading_and_pdf_links():
    chosen = {
        "label": "Διατάξεις Σχεδίου ή Πρότασης Νόμου",
        "url": "https://www.hellenicparliament.gr/UserFiles/a/full.pdf",
    }
    links = [
        chosen,
        {
            "label": "Αιτιολογική-Εισηγητική Έκθεση",
            "url": "https://www.hellenicparliament.gr/UserFiles/a/analysis.pdf",
        },
    ]
    official_text = "Άρθρο 1\nΣκοπός του νόμου.\n\nΆρθρο 2\nΑντικείμενο του νόμου."

    block = build_official_text_block(official_text, links, chosen)

    assert "### Διατάξεις Σχεδίου ή Πρότασης Νόμου" in block
    assert "Άρθρο 1" in block
    assert "[Διατάξεις Σχεδίου ή Πρότασης Νόμου](https://www.hellenicparliament.gr/UserFiles/a/full.pdf)" in block
    assert "[Αιτιολογική-Εισηγητική Έκθεση](https://www.hellenicparliament.gr/UserFiles/a/analysis.pdf)" in block


def test_pdf_text_quality_gate_rejects_empty_and_ocr_garbage():
    empty = "Title: file.pdf\n\nMarkdown Content:\n\n"
    garbage = "Markdown Content:\n" + ("ΝΝΕΑ ΔΗ ΟΚ Α1Δ ΚΗ ΛΗ ριΟ Πρω ΗΒΟ ΛΗ " * 80)
    readable = "Markdown Content:\nΑΙΤΙΟΛΟΓΙΚΗ ΕΚΘΕΣΗ\n" + (
        "Προς τη Βουλή των Ελλήνων και για τον σκοπό του νόμου, το άρθρο ρυθμίζει "
        "τη διαδικασία και τις αρμοδιότητες της διοίκησης. "
    ) * 80

    assert not is_readable_pdf_text(empty)
    assert not is_readable_pdf_text(garbage)
    assert is_readable_pdf_text(readable)


def test_documents_block_keeps_download_links_when_text_is_unreadable():
    links = [
        {"label": "Το φωτοτυπημένο σ/ν ή π/ν", "url": "https://example.test/scan.pdf"},
        {"label": "Διατάξεις Σχεδίου ή Πρότασης Νόμου", "url": "https://example.test/full.pdf"},
    ]

    block = build_documents_block(links)

    assert "### Πλήρη έγγραφα" in block
    assert "φωτοτυπημένο" not in block
    assert "[Διατάξεις Σχεδίου ή Πρότασης Νόμου](https://example.test/full.pdf)" in block


def test_unknown_pdf_labels_still_become_document_candidates():
    links = [
        {"label": ".pdf", "url": "https://example.test/13313922.pdf"},
        {"label": "Το φωτοτυπημένο σ/ν ή π/ν", "url": "https://example.test/scan.pdf"},
    ]

    candidates = fallback_pdf_candidates(links)
    block = build_documents_block(links)

    assert candidates == [links[0]]
    assert display_label(links[0], 1) == "Έγγραφο Βουλής 1 (13313922.pdf)"
    assert "[Έγγραφο Βουλής 1 (13313922.pdf)](https://example.test/13313922.pdf)" in block


def test_strip_table_of_contents_prefers_second_article_body():
    text = """
ΣΧΕΔΙΟ ΝΟΜΟΥ
ΠΙΝΑΚΑΣ ΠΕΡΙΕΧΟΜΕΝΩΝ
Άρθρο 1 Σκοπός
Άρθρο 2 Αντικείμενο

ΜΕΡΟΣ Α'
ΚΕΦΑΛΑΙΟ Α'
Άρθρο 1
Σκοπός του παρόντος είναι η ουσιαστική ρύθμιση.
"""

    stripped = strip_table_of_contents(text)

    assert "ΠΙΝΑΚΑΣ ΠΕΡΙΕΧΟΜΕΝΩΝ" not in stripped
    assert stripped.startswith("ΚΕΦΑΛΑΙΟ Α")
    assert "Σκοπός του παρόντος" in stripped


def _day_month() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")


async def test_gated_call_refuses_without_calling_claude_when_budget_exhausted(
    monkeypatch: pytest.MonkeyPatch, dummy_provider_key: None,
) -> None:
    from services.claude_usage import DAILY_TOKEN_LIMIT
    from tests.budget_fakes import BudgetFakeRedis

    calls = []
    monkeypatch.setattr(backfill, "call_claude", lambda *a: calls.append(a))
    day, _ = _day_month()
    redis = BudgetFakeRedis({f"claude:tokens:{day}": str(DAILY_TOKEN_LIMIT)})
    with pytest.raises(backfill.BudgetGateClosed):
        await backfill.gated_call_claude("Τίτλος", "Κείμενο", redis_client=redis)
    assert calls == []


async def test_gated_call_refuses_when_redis_is_down(
    monkeypatch: pytest.MonkeyPatch, dummy_provider_key: None,
) -> None:
    from tests.budget_fakes import BudgetFakeRedis

    calls = []
    monkeypatch.setattr(backfill, "call_claude", lambda *a: calls.append(a))
    with pytest.raises(backfill.BudgetGateClosed):
        await backfill.gated_call_claude("t", "x", redis_client=BudgetFakeRedis(broken=True))
    assert calls == []


@pytest.mark.parametrize("usage", [
    {"input_tokens": 1200, "output_tokens": 300},
    {"input_tokens": 0, "output_tokens": 300},
    {"input_tokens": 1200, "output_tokens": 0},
])
async def test_gated_call_tracks_real_usage_and_releases(
    monkeypatch: pytest.MonkeyPatch, dummy_provider_key: None, usage: dict[str, int],
) -> None:
    from services import claude_usage
    from tests.budget_fakes import BudgetFakeRedis

    provider = Mock(return_value=({"summary_short_el": "ok"}, usage))
    monkeypatch.setattr(backfill, "call_claude", provider)
    monkeypatch.setattr(claude_usage, "charge_reservation", _unexpected_call)
    redis = BudgetFakeRedis()
    result, got = await backfill.gated_call_claude("t", "x", redis_client=redis)
    day, month = _day_month()
    total = sum(usage.values())
    cost = claude_usage.estimate_cost_usd(usage)
    assert result == {"summary_short_el": "ok"} and got is usage
    provider.assert_called_once_with("t", "x")
    assert redis.store[f"claude:tokens:{day}"] == str(total)
    assert redis.store[f"claude:tokens:analysis:{day}"] == str(total)
    assert float(redis.store[f"claude:cost_usd:{month}"]) == pytest.approx(cost)
    assert float(redis.store[f"claude:cost_usd:analysis:{day}"]) == pytest.approx(cost)
    assert int(redis.store[f"claude:reserved_tokens:{day}"]) == 0
    assert float(redis.store[f"claude:reserved_cost_usd:{month}"]) == pytest.approx(0)


async def test_gated_call_books_full_reservation_when_call_fails(
    monkeypatch: pytest.MonkeyPatch, dummy_provider_key: None,
) -> None:
    from services import claude_usage
    from tests.budget_fakes import BudgetFakeRedis

    def boom(*args: object) -> NoReturn:
        raise TimeoutError("timeout after send")

    monkeypatch.setattr(backfill, "call_claude", boom)
    monkeypatch.setattr(claude_usage, "track_usage", _unexpected_call)
    redis = BudgetFakeRedis()
    tokens, cost = claude_usage.reservation_size(
        "", backfill.analysis_prompt("t", "x" * 100), backfill.ANALYSIS_MAX_OUTPUT_TOKENS,
    )
    with pytest.raises(TimeoutError):
        await backfill.gated_call_claude("t", "x" * 100, redis_client=redis)
    day, month = _day_month()
    assert int(redis.store[f"claude:tokens:{day}"]) == tokens
    assert int(redis.store[f"claude:tokens:analysis:{day}"]) == tokens
    assert float(redis.store[f"claude:cost_usd:{month}"]) == pytest.approx(cost)
    assert int(redis.store[f"claude:reserved_tokens:{day}"]) == 0
    assert float(redis.store[f"claude:reserved_cost_usd:{month}"]) == pytest.approx(0)


@pytest.mark.parametrize("usage", [
    pytest.param({}, id="empty"),
    pytest.param(None, id="none"),
    pytest.param([], id="non-dict"),
    pytest.param({"input_tokens": 1200}, id="missing-output"),
    pytest.param({"output_tokens": 300}, id="missing-input"),
    pytest.param({"input_tokens": -1, "output_tokens": 300}, id="negative-input"),
    pytest.param({"input_tokens": 1200, "output_tokens": -1}, id="negative-output"),
    pytest.param({"input_tokens": True, "output_tokens": 300}, id="bool-input"),
    pytest.param({"input_tokens": 1200, "output_tokens": False}, id="bool-output"),
    pytest.param({"input_tokens": 1.2, "output_tokens": 300}, id="float-input"),
    pytest.param({"input_tokens": 1200, "output_tokens": 3.2}, id="float-output"),
    pytest.param({"input_tokens": "1200", "output_tokens": 300}, id="string-input"),
    pytest.param({"input_tokens": 1200, "output_tokens": "300"}, id="string-output"),
    pytest.param({"input_tokens": 0, "output_tokens": 0}, id="zero-total"),
])
async def test_gated_call_books_full_reservation_for_uncertain_usage(
    monkeypatch: pytest.MonkeyPatch, dummy_provider_key: None, usage: Any,
) -> None:
    from services import claude_usage
    from tests.budget_fakes import BudgetFakeRedis

    monkeypatch.setattr(backfill, "call_claude", Mock(return_value=({"ok": True}, usage)))
    monkeypatch.setattr(claude_usage, "track_usage", _unexpected_call)
    redis = BudgetFakeRedis()
    tokens, cost = claude_usage.reservation_size(
        "", backfill.analysis_prompt("t", "x"), backfill.ANALYSIS_MAX_OUTPUT_TOKENS,
    )

    result, got = await backfill.gated_call_claude("t", "x", redis_client=redis)

    day, month = _day_month()
    assert result == {"ok": True} and got is usage
    assert int(redis.store[f"claude:tokens:{day}"]) == tokens
    assert int(redis.store[f"claude:tokens:analysis:{day}"]) == tokens
    assert float(redis.store[f"claude:cost_usd:{month}"]) == pytest.approx(cost)
    assert int(redis.store[f"claude:reserved_tokens:{day}"]) == 0
    assert float(redis.store[f"claude:reserved_cost_usd:{month}"]) == pytest.approx(0)


@pytest.mark.parametrize("raises", [False, True], ids=["zero-booked", "booking-error"])
async def test_gated_call_falls_back_when_real_booking_fails(
    monkeypatch: pytest.MonkeyPatch, dummy_provider_key: None, raises: bool,
) -> None:
    from services import claude_usage
    from tests.budget_fakes import BudgetFakeRedis

    usage = {"input_tokens": 1200, "output_tokens": 300}
    monkeypatch.setattr(backfill, "call_claude", Mock(return_value=({"ok": True}, usage)))
    track = AsyncMock(side_effect=RuntimeError("booking failed")) if raises else AsyncMock(return_value=0)
    monkeypatch.setattr(claude_usage, "track_usage", track)
    redis = BudgetFakeRedis()
    tokens, cost = claude_usage.reservation_size(
        "", backfill.analysis_prompt("t", "x"), backfill.ANALYSIS_MAX_OUTPUT_TOKENS,
    )

    await backfill.gated_call_claude("t", "x", redis_client=redis)

    day, month = _day_month()
    track.assert_awaited_once_with(redis, usage, purpose="analysis")
    assert int(redis.store[f"claude:tokens:{day}"]) == tokens
    assert float(redis.store[f"claude:cost_usd:{month}"]) == pytest.approx(cost)
    assert int(redis.store[f"claude:reserved_tokens:{day}"]) == 0
    assert float(redis.store[f"claude:reserved_cost_usd:{month}"]) == pytest.approx(0)


async def test_gated_call_keeps_both_holds_when_real_and_fallback_booking_fail(
    monkeypatch: pytest.MonkeyPatch, dummy_provider_key: None,
) -> None:
    from services import claude_usage
    from tests.budget_fakes import BudgetFakeRedis

    usage = {"input_tokens": 1200, "output_tokens": 300}
    monkeypatch.setattr(backfill, "call_claude", Mock(return_value=({"ok": True}, usage)))
    track = AsyncMock(wraps=claude_usage.track_usage)
    charge = AsyncMock(wraps=claude_usage.charge_reservation)
    release = AsyncMock(side_effect=_unexpected_call)
    monkeypatch.setattr(claude_usage, "track_usage", track)
    monkeypatch.setattr(claude_usage, "charge_reservation", charge)
    monkeypatch.setattr(claude_usage, "release_budget", release)
    redis = BudgetFakeRedis(fail_writes=True)
    tokens, cost = claude_usage.reservation_size(
        "", backfill.analysis_prompt("t", "x"), backfill.ANALYSIS_MAX_OUTPUT_TOKENS,
    )

    result, got = await backfill.gated_call_claude("t", "x", redis_client=redis)

    day, month = _day_month()
    assert result == {"ok": True} and got is usage
    track.assert_awaited_once_with(redis, usage, purpose="analysis")
    charge.assert_awaited_once()
    reservation = charge.await_args.args[1]
    assert charge.await_args.args[0] is redis
    assert charge.await_args.kwargs == {"purpose": "analysis"}
    assert (reservation.tokens, reservation.cost) == (tokens, cost)
    release.assert_not_awaited()
    assert int(redis.store[f"claude:reserved_tokens:{day}"]) == tokens
    assert float(redis.store[f"claude:reserved_cost_usd:{month}"]) == pytest.approx(cost)
    assert f"claude:tokens:{day}" not in redis.store
    assert f"claude:cost_usd:{month}" not in redis.store


@pytest.mark.parametrize("with_redis", [False, True], ids=["before-client", "before-reserve"])
async def test_gated_call_missing_key_does_not_create_client_or_reserve(
    monkeypatch: pytest.MonkeyPatch, with_redis: bool,
) -> None:
    from tests.budget_fakes import BudgetFakeRedis

    _forbid_budget_calls(monkeypatch)
    redis = BudgetFakeRedis() if with_redis else None
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        await backfill.gated_call_claude("t", "x", redis_client=redis)
    if redis is not None:
        assert redis.store == {}


def test_default_is_offline_dry_run():
    args = backfill.build_parser().parse_args(["--bill-id", "GR-1"])
    assert args.live_calls is False and args.apply is False
    assert backfill.mode_error(args) is None


def test_apply_analysis_requires_live_calls():
    args = backfill.build_parser().parse_args(["--bill-id", "GR-1", "--apply"])
    assert "--live-calls" in backfill.mode_error(args)
    ok = backfill.build_parser().parse_args(["--bill-id", "GR-1", "--apply", "--live-calls"])
    assert backfill.mode_error(ok) is None


def test_official_only_apply_needs_no_paid_calls():
    args = backfill.build_parser().parse_args(["--bill-id", "GR-1", "--apply", "--official-only"])
    assert backfill.mode_error(args) is None


def test_plan_is_offline_and_matches_reservation_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    from services.claude_usage import reservation_size

    _forbid_budget_calls(monkeypatch)
    monkeypatch.setattr(backfill, "gated_call_claude", _unexpected_call)
    plan = backfill.plan_claude_call("Τίτλος", "Κείμενο νόμου")
    prompt = backfill.analysis_prompt("Τίτλος", "Κείμενο νόμου")
    tokens, cost = reservation_size("", prompt, backfill.ANALYSIS_MAX_OUTPUT_TOKENS)
    assert plan == {"prompt_chars": len(prompt), "reserved_tokens_max": tokens, "reserved_cost_usd_max": cost}


FIXTURE_RESULT = {
    "summary_short_el": "Η ρύθμιση προβλέπει σαφείς διαδικασίες για τη δημόσια διοίκηση.",
    "analysis_el": (
        "Το άρθρο καθορίζει τις αρμοδιότητες των υπηρεσιών και περιγράφει τα στάδια "
        "εφαρμογής του νόμου με συγκεκριμένες προθεσμίες για κάθε φορέα. "
    ) * 4,
    "quality_notes": ["fixture analysis"],
}
FIXTURE_USAGE = {"input_tokens": 1200, "output_tokens": 300}
FIXTURE_PDF = "Markdown Content:\nΑΙΤΙΟΛΟΓΙΚΗ ΕΚΘΕΣΗ\nΆρθρο 1\n" + (
    "Προς τη Βουλή των Ελλήνων και για τον σκοπό του νόμου, το άρθρο ρυθμίζει "
    "τη διαδικασία και τις αρμοδιότητες της διοίκησης. "
) * 40
FIXTURE_PAGE = """
[![Image 18: Αιτιολογική-Εισηγητική Έκθεση](https://fixture.invalid/pdf.png)](https://fixture.invalid/analysis.pdf)
[![Image 19: Διατάξεις Σχεδίου ή Πρότασης Νόμου](https://fixture.invalid/pdf.png)](https://fixture.invalid/full.pdf)
"""


class FakeDB:
    def __init__(self, rows: dict[str, dict[str, str]]) -> None:
        self.rows = rows
        self.fetched_ids: list[str] = []
        self.updates: list[tuple[str, tuple[str, ...]]] = []
        self.close_calls = 0

    async def fetchrow(self, query: str, bill_id: str) -> dict[str, str] | None:
        assert "SELECT" in query and "source='PARLIAMENT'" in query
        self.fetched_ids.append(bill_id)
        return self.rows.get(bill_id)

    async def execute(self, query: str, *values: str) -> str:
        assert "UPDATE parliament_bills" in query
        self.updates.append((query, values))
        return "UPDATE 1"

    async def close(self) -> None:
        self.close_calls += 1


@dataclass
class MainHarness:
    connection: FakeDB
    connect: AsyncMock
    gated_call: AsyncMock
    source_urls: list[str]
    env_paths: list[str]
    out_dir: Path


@pytest.fixture
def main_harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> MainHarness:
    import asyncpg

    rows = {
        bill_id: {
            "id": bill_id,
            "title_el": f"Τίτλος {bill_id}",
            "parliament_url": f"https://fixture.invalid/bills/{bill_id}",
            "summary_short_el": "existing summary",
            "analysis_el": "existing analysis",
        }
        for bill_id in ("GR-1", "GR-2")
    }
    connection = FakeDB(rows)
    connect = AsyncMock(return_value=connection)
    gated_call = AsyncMock(return_value=(dict(FIXTURE_RESULT), dict(FIXTURE_USAGE)))
    source_urls: list[str] = []
    env_paths: list[str] = []
    sources = {
        f"{backfill.JINA_BASE}{row['parliament_url']}": FIXTURE_PAGE
        for row in rows.values()
    }
    sources.update({
        f"{backfill.JINA_BASE}https://fixture.invalid/analysis.pdf": FIXTURE_PDF,
        f"{backfill.JINA_BASE}https://fixture.invalid/full.pdf": FIXTURE_PDF,
    })

    def read_fixture_source(url: str, timeout: int = 60) -> str:
        source_urls.append(url)
        assert url in sources, f"unexpected fixture source: {url}"
        return sources[url]

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://fixture.invalid/backfill")
    monkeypatch.setattr(asyncpg, "connect", connect)
    monkeypatch.setattr(backfill, "_read_env_file", env_paths.append)
    monkeypatch.setattr(backfill, "_http_text", read_fixture_source)
    monkeypatch.setattr(backfill, "gated_call_claude", gated_call)
    _forbid_budget_calls(monkeypatch)
    return MainHarness(connection, connect, gated_call, source_urls, env_paths, tmp_path / "previews")


def _set_main_args(
    monkeypatch: pytest.MonkeyPatch,
    harness: MainHarness,
    flags: list[str],
    bill_ids: tuple[str, ...] = ("GR-1",),
) -> None:
    argv = [str(SCRIPT_PATH), "--out-dir", str(harness.out_dir)]
    for bill_id in bill_ids:
        argv.extend(["--bill-id", bill_id])
    monkeypatch.setattr(backfill.sys, "argv", argv + flags)


@pytest.mark.parametrize("apply,live_calls,official_only", [
    pytest.param(False, False, False, id="default-plan"),
    pytest.param(True, False, False, id="invalid-apply"),
    pytest.param(False, True, False, id="live-preview"),
    pytest.param(True, True, False, id="live-apply"),
    pytest.param(False, False, True, id="official-preview"),
    pytest.param(True, False, True, id="official-apply"),
    pytest.param(False, True, True, id="official-preview-with-live-flag"),
    pytest.param(True, True, True, id="official-apply-with-live-flag"),
])
async def test_main_flag_matrix(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    main_harness: MainHarness,
    apply: bool,
    live_calls: bool,
    official_only: bool,
) -> None:
    harness = main_harness
    flags = [
        flag for enabled, flag in (
            (apply, "--apply"), (live_calls, "--live-calls"), (official_only, "--official-only"),
        ) if enabled
    ]
    _set_main_args(monkeypatch, harness, flags)
    if live_calls and not official_only:
        # A mocked env loader supplies the dummy key; no real env file is read.
        def load_fixture_env(path: str) -> None:
            harness.env_paths.append(path)
            monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-key-not-a-secret")

        monkeypatch.setattr(backfill, "_read_env_file", load_fixture_env)
    else:
        harness.gated_call.side_effect = _unexpected_call

    if not live_calls and not official_only:
        monkeypatch.setattr(backfill.os, "makedirs", _unexpected_call)
        monkeypatch.setattr(backfill, "open", _unexpected_call, raising=False)
        if apply:
            with pytest.raises(SystemExit) as exc:
                await backfill.main()
            assert exc.value.code == 2
            assert "--live-calls" in capsys.readouterr().err
            assert harness.env_paths == []
            harness.connect.assert_not_awaited()
            harness.gated_call.assert_not_awaited()
            assert harness.source_urls == []
            assert harness.connection.fetched_ids == []
            assert harness.connection.updates == []
            assert harness.connection.close_calls == 0
            assert not harness.out_dir.exists()
            return

    await backfill.main()

    output = capsys.readouterr()
    assert output.err == ""
    assert len(harness.env_paths) == 2
    harness.connect.assert_awaited_once_with("postgresql://fixture.invalid/backfill")
    assert harness.connection.fetched_ids == ["GR-1"]
    assert harness.connection.close_calls == 1
    assert harness.source_urls == [
        f"{backfill.JINA_BASE}https://fixture.invalid/bills/GR-1",
        f"{backfill.JINA_BASE}https://fixture.invalid/full.pdf",
        f"{backfill.JINA_BASE}https://fixture.invalid/analysis.pdf",
    ]
    if not live_calls and not official_only:
        assert "GR-1: offline dry run, no Claude call:" in output.out
        assert '"reserved_tokens_max":' in output.out
        assert '"reserved_cost_usd_max":' in output.out
        harness.gated_call.assert_not_awaited()
        assert harness.connection.updates == []
        assert not harness.out_dir.exists()
        return

    json_path = harness.out_dir / "claude_analysis_GR-1.json"
    md_path = harness.out_dir / "claude_analysis_GR-1.md"
    preview = json.loads(json_path.read_text(encoding="utf-8"))
    assert md_path.is_file()
    assert "## Επίσημο κείμενο και έγγραφα" in md_path.read_text(encoding="utf-8")
    assert preview["validation_errors"] == []
    assert preview["apply"] is apply
    assert "Άρθρο 1" in preview["official_text_el"]
    if official_only:
        harness.gated_call.assert_not_awaited()
        assert preview["usage"] == {}
        assert preview["result"] == {
            "summary_short_el": "existing summary",
            "analysis_el": "existing analysis",
            "quality_notes": ["official-only refresh"],
        }
    else:
        harness.gated_call.assert_awaited_once()
        assert harness.gated_call.await_args.args[0] == "Τίτλος GR-1"
        assert "Άρθρο 1" in harness.gated_call.await_args.args[1]
        assert preview["result"] == FIXTURE_RESULT
        assert preview["usage"] == FIXTURE_USAGE

    if not apply:
        assert harness.connection.updates == []
        return
    assert len(harness.connection.updates) == 1
    query, values = harness.connection.updates[0]
    assert "summary_long_el=$" in query
    if official_only:
        assert "summary_short_el" not in query
        assert "analysis_el" not in query
        assert values == (preview["official_text_el"], "GR-1")
    else:
        assert "summary_short_el=$1" in query and "analysis_el=$2" in query
        assert values == (
            FIXTURE_RESULT["summary_short_el"].strip(), FIXTURE_RESULT["analysis_el"].strip(),
            preview["official_text_el"], "GR-1",
        )


@pytest.mark.parametrize("apply", [False, True], ids=["preview", "apply"])
async def test_main_invalid_analysis_is_previewed_but_never_applied(
    monkeypatch: pytest.MonkeyPatch,
    main_harness: MainHarness,
    dummy_provider_key: None,
    apply: bool,
) -> None:
    harness = main_harness
    _set_main_args(monkeypatch, harness, ["--live-calls"] + (["--apply"] if apply else []))
    harness.gated_call.return_value = (
        {"summary_short_el": "short", "analysis_el": "short", "quality_notes": []}, FIXTURE_USAGE,
    )

    await backfill.main()

    preview = json.loads((harness.out_dir / "claude_analysis_GR-1.json").read_text(encoding="utf-8"))
    assert preview["validation_errors"]
    assert harness.connection.updates == []
    assert harness.connection.close_calls == 1


@pytest.mark.parametrize("apply", [False, True], ids=["preview", "apply"])
async def test_main_missing_key_exits_before_db_source_http_or_gate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    main_harness: MainHarness,
    apply: bool,
) -> None:
    harness = main_harness
    _set_main_args(monkeypatch, harness, ["--live-calls"] + (["--apply"] if apply else []))

    with pytest.raises(SystemExit) as exc:
        await backfill.main()

    assert exc.value.code == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
    assert len(harness.env_paths) == 2
    harness.connect.assert_not_awaited()
    harness.gated_call.assert_not_awaited()
    assert harness.source_urls == []
    assert harness.connection.fetched_ids == []
    assert harness.connection.updates == []
    assert harness.connection.close_calls == 0
    assert not harness.out_dir.exists()


async def test_main_closed_gate_exits_nonzero_closes_db_and_stops_before_next_bill(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    main_harness: MainHarness,
    dummy_provider_key: None,
) -> None:
    harness = main_harness
    _set_main_args(monkeypatch, harness, ["--live-calls", "--apply"], ("GR-1", "GR-2"))
    harness.gated_call.side_effect = backfill.BudgetGateClosed("fixture budget exhausted")
    monkeypatch.setattr(backfill.os, "makedirs", _unexpected_call)
    monkeypatch.setattr(backfill, "open", _unexpected_call, raising=False)

    with pytest.raises(SystemExit) as exc:
        await backfill.main()

    assert exc.value.code == 1
    assert "fixture budget exhausted" in capsys.readouterr().err
    harness.gated_call.assert_awaited_once()
    assert harness.connection.fetched_ids == ["GR-1"]
    assert all("GR-2" not in url for url in harness.source_urls)
    assert harness.connection.updates == []
    assert harness.connection.close_calls == 1
    assert not harness.out_dir.exists()


@pytest.mark.parametrize("stage", ["select", "source", "provider", "preview", "update"])
async def test_main_closes_db_when_postconnect_step_raises(
    monkeypatch: pytest.MonkeyPatch,
    main_harness: MainHarness,
    dummy_provider_key: None,
    stage: str,
) -> None:
    harness = main_harness
    _set_main_args(monkeypatch, harness, ["--live-calls", "--apply"])
    error = RuntimeError("fixture postconnect failure")
    if stage == "select":
        monkeypatch.setattr(harness.connection, "fetchrow", AsyncMock(side_effect=error))
    elif stage == "source":
        monkeypatch.setattr(backfill, "_http_text", Mock(side_effect=error))
    elif stage == "provider":
        harness.gated_call.side_effect = error
    elif stage == "preview":
        monkeypatch.setattr(backfill, "open", Mock(side_effect=error), raising=False)
    else:
        monkeypatch.setattr(harness.connection, "execute", AsyncMock(side_effect=error))

    with pytest.raises(RuntimeError, match="fixture postconnect failure"):
        await backfill.main()

    harness.connect.assert_awaited_once()
    assert harness.connection.close_calls == 1
