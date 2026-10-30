"""Exercise the actual script loops with synthetic results and a mocked DB."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest


ROOT = Path(__file__).resolve().parents[4]
GOOD = "Η ρύθμιση ορίζει τη διαδικασία λειτουργίας των δημόσιων υπηρεσιών."
BAD = "Απάντηση: Για να βρεις την πληροφορία, αναζήτησε το έγγραφο."


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["backfill_summary_short", "backfill_summary_ollama"])
@pytest.mark.parametrize("text", [BAD, GOOD])
async def test_backfill_loop_skips_bad_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, text: str,
) -> None:
    import asyncpg
    from services import representation_cache

    script = _load(name)
    row = {"id": "SYNTH-1", "title_el": "Δοκιμαστικός τίτλος", "summary_long_el": GOOD * 5,
           "summary_short_el": None, "pill_el": None, "source": "PARLIAMENT", "status": "ANNOUNCED"}
    conn = SimpleNamespace(fetch=AsyncMock(return_value=[row]), execute=AsyncMock(), close=AsyncMock())
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/synthetic")
    monkeypatch.setattr(asyncpg, "connect", AsyncMock(return_value=conn))
    invalidate = AsyncMock()
    monkeypatch.setattr(representation_cache, "invalidate_representation_cache", invalidate)
    monkeypatch.setattr(script.sys, "argv", [name, "--apply"])
    csv_path = tmp_path / f"{name}.csv"
    def open_audit(path: str, *args: object, **kwargs: object) -> object:
        assert str(path).startswith("/tmp/backfill_")
        return csv_path.open(*args, **kwargs)
    monkeypatch.setattr(script, "open", open_audit, raising=False)
    if name == "backfill_summary_short":
        monkeypatch.setattr(script, "generate_short_summary", lambda *a: text)
        monkeypatch.setattr(script, "generate_pill", lambda *a: GOOD)
    else:
        monkeypatch.setattr(script, "call_ollama", lambda *a: {"summary_short_el": text, "pill_el": GOOD})
        monkeypatch.setattr(script.time, "sleep", lambda *a: None)
    await script.main()
    conn.close.assert_awaited_once()
    if text == BAD:
        conn.execute.assert_not_awaited()
        invalidate.assert_not_awaited()
        assert BAD not in csv_path.read_text()
    else:
        conn.execute.assert_awaited_once()
        invalidate.assert_awaited_once()
        args = conn.execute.await_args.args
        assert args[1] == GOOD
        assert "summary_short_el" in json.loads(args[-1])


@pytest.mark.parametrize("text", ["Tôi xin lỗi, nhưng tôi không thể cung cấp thông tin.", BAD, "≈ÀÀ«Õ… « ƒ«Ãœ —"])
def test_model_backfill_validation_uses_shared_gate(text: str) -> None:
    script = _load("backfill_summary_ollama")
    assert script.validate_output(GOOD, text, "Δοκιμαστικός τίτλος")


def test_backfill_accepts_greek_with_url() -> None:
    script = _load("backfill_summary_ollama")
    text = GOOD + " Δείτε https://example.test/source."
    assert script.validate_output(GOOD, text, "Δοκιμαστικός τίτλος") is None


def test_model_backfill_rejects_bad_pill_with_good_summary() -> None:
    script = _load("backfill_summary_ollama")
    assert script.validate_output(BAD, GOOD, "Δοκιμαστικός τίτλος") == "refusal_or_meta"
