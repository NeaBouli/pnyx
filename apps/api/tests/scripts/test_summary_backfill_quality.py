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
@pytest.mark.parametrize("existing_pill", [None, "Επίσημη περιγραφή"])
async def test_backfill_loop_skips_bad_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, text: str, existing_pill: str | None,
) -> None:
    import asyncpg
    from services import representation_cache

    script = _load(name)
    row = {"id": "SYNTH-1", "title_el": "Δοκιμαστικός τίτλος", "summary_long_el": GOOD * 5,
           "summary_short_el": None, "pill_el": existing_pill, "source": "PARLIAMENT", "status": "ANNOUNCED"}
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
    if text == BAD and name != "backfill_summary_short":
        conn.execute.assert_not_awaited()
        invalidate.assert_not_awaited()
        assert BAD not in csv_path.read_text()
    else:
        conn.execute.assert_awaited_once()
        invalidate.assert_awaited_once()
        args = conn.execute.await_args.args
        assert args[1] == text
        if name == "backfill_summary_short":
            assert "generated_content_provenance" not in args[0]
        else:
            assert "NULLIF(generated_content_provenance, 'null'::jsonb)" in args[0]
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



def _script(name: str):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


QUOTE = "«Λυπάμαι, αλλά δεν μπορώ να δώσω τα στοιχεία»"


def test_ollama_backfill_accepts_quoted_refusal_speech() -> None:
    module = _script("backfill_summary_ollama")
    short = f"Ο Υπουργός απάντησε στη Βουλή {QUOTE} και ανακοίνωσε νέα ρύθμιση για τα δημόσια έργα."
    assert module.validate_output("Νέα ρύθμιση δημόσιων έργων", short, "Ρύθμιση για τα δημόσια έργα") is None
    assert module.validate_output("Νέα ρύθμιση", "Λυπάμαι, αλλά δεν μπορώ να δώσω σύνοψη για αυτό το έγγραφο.",
                                  "Τίτλος") is not None


def test_analysis_backfill_accepts_quoted_refusal_speech() -> None:
    module = _script("backfill_analysis_claude")
    short = "Η ρύθμιση αλλάζει τη διαδικασία ενημέρωσης των πολιτών για τα δημόσια έργα της περιφέρειας."
    analysis = ("Κατά τη συζήτηση ο αρμόδιος υπηρεσιακός παράγοντας δήλωσε " + QUOTE + ", γεγονός που "
                "ανέδειξε την ανάγκη για σαφέστερους κανόνες διαφάνειας. Η πρόταση προβλέπει υποχρεωτική "
                "δημοσίευση των στοιχείων, προθεσμίες απάντησης και έλεγχο από ανεξάρτητη αρχή, ώστε οι "
                "πολίτες να ενημερώνονται έγκαιρα για την πορεία των έργων και των δαπανών.")
    errors = module.validate_result({"summary_short_el": short, "analysis_el": analysis}, "απόσπασμα")
    assert "AI disclaimer leaked" not in errors
    refusal = analysis.replace(QUOTE, "κάτι") + " Ως AI δεν μπορώ να κρίνω περισσότερα."
    assert "AI disclaimer leaked" in module.validate_result({"summary_short_el": short, "analysis_el": refusal}, "x")
