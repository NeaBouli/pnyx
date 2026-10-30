"""Synthetic connection: no production data, database, filesystem, or network."""

import csv
import importlib.util
import json
import stat
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock

import pytest

from services.content_provenance import content_sha256


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit_text_quality.py"
spec = importlib.util.spec_from_file_location("audit_text_quality", SCRIPT)
assert spec and spec.loader
audit_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_script)
BAD = "Απάντηση: Δεν παρέχεται σύνοψη του δοκιμαστικού εγγράφου."
GOOD = "Η ρύθμιση ορίζει τη διαδικασία των δημόσιων υπηρεσιών."


def _row(bill_id: str, *, reviewed: bool | None = False, owned: bool = True, value: str = BAD) -> dict[str, Any]:
    return {"id": bill_id, "source": "SYNTHETIC", "ai_summary_reviewed": reviewed,
            "generated_content_provenance": {"summary_long_el": content_sha256(value)} if owned else {},
            "summary_long_el": value}


class Connection:
    def __init__(self, rows: list[dict[str, Any]], backup: Path) -> None:
        self.rows = rows
        self.backup = backup
        self.writes: list[tuple[str, tuple[Any, ...]]] = []
        self.race = False

    async def cursor(self, query: str, *, prefetch: int) -> AsyncIterator[dict[str, Any]]:
        assert query.startswith("SELECT ") and prefetch == 100
        for row in self.rows:
            yield row

    @asynccontextmanager
    async def transaction(self, **kwargs: Any) -> AsyncIterator[None]:
        yield

    async def execute(self, query: str, *values: Any) -> str:
        # The complete, private backup must already exist before the first write.
        assert stat.S_IMODE(self.backup.stat().st_mode) == 0o600
        with self.backup.open(newline="", encoding="utf-8") as stream:
            records = list(csv.DictReader(stream))
        assert records[0] == {"id": "SYNTH-1", "field": "summary_long_el", "old_value": BAD}
        assert "ai_summary_reviewed IS NOT TRUE" in query
        assert "summary_long_el = $2" in query
        assert "generated_content_provenance ->> $3::text = $4" in query
        assert BAD not in query
        self.writes.append((query, values))
        return "UPDATE 0" if self.race else "UPDATE 1"


@pytest.fixture
def invalidate(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    from services import representation_cache

    mock = AsyncMock()
    monkeypatch.setattr(representation_cache, "invalidate_representation_cache", mock)
    return mock


async def test_dry_run_counts_and_ids_only(tmp_path: Path, capsys: pytest.CaptureFixture[str], invalidate: AsyncMock) -> None:
    backup = tmp_path / "backup.csv"
    rows = [_row("SYNTH-1"), _row("SYNTH-2", owned=False), _row("SYNTH-3", value=GOOD)]
    conn = Connection(rows, backup)
    assert await audit_script.audit(conn, fields=("summary_long_el",), sample_limit=1, backup_path=backup) == 0
    output = capsys.readouterr().out
    assert "SYNTHETIC\tsummary_long_el\trefusal_or_meta\t2\tSYNTH-1" in output
    assert "SYNTH-2" not in output
    assert BAD not in output and GOOD not in output
    assert not conn.writes and not backup.exists()
    invalidate.assert_not_awaited()


async def test_apply_only_unreviewed_owned_failures(tmp_path: Path, invalidate: AsyncMock, capsys: pytest.CaptureFixture[str]) -> None:
    backup = tmp_path / "backup.csv"
    changed = _row("SYNTH-EDIT")
    changed["generated_content_provenance"] = {"summary_long_el": content_sha256(GOOD)}
    rows = [_row("SYNTH-1", reviewed=None), _row("SYNTH-REVIEWED", reviewed=True),
            _row("SYNTH-MANUAL", owned=False), changed, _row("SYNTH-GOOD", value=GOOD)]
    rows[0]["generated_content_provenance"] = json.dumps(rows[0]["generated_content_provenance"])
    conn = Connection(rows, backup)
    assert await audit_script.audit(conn, fields=("summary_long_el",), apply=True, backup_path=backup) == 1
    assert len(conn.writes) == 1
    assert conn.writes[0][1] == ("SYNTH-1", BAD, "summary_long_el", content_sha256(BAD), audit_script.SENSITIVE_PATTERN)
    invalidate.assert_awaited_once()
    assert BAD not in capsys.readouterr().out


async def test_existing_backup_prevents_all_writes(tmp_path: Path, invalidate: AsyncMock) -> None:
    backup = tmp_path / "backup.csv"
    backup.write_text("keep", encoding="utf-8")
    conn = Connection([_row("SYNTH-1")], backup)
    with pytest.raises(FileExistsError):
        await audit_script.audit(conn, fields=("summary_long_el",), apply=True, backup_path=backup)
    assert backup.read_text() == "keep" and not conn.writes
    invalidate.assert_not_awaited()


async def test_failed_backup_prevents_all_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalidate: AsyncMock) -> None:
    conn = Connection([_row("SYNTH-1")], tmp_path / "backup.csv")
    def fail_sync(fd: int) -> None:
        raise OSError("synthetic disk failure")
    monkeypatch.setattr(audit_script.os, "fsync", fail_sync)
    with pytest.raises(OSError, match="synthetic disk failure"):
        await audit_script.audit(conn, fields=("summary_long_el",), apply=True, backup_path=conn.backup)
    assert not conn.writes
    invalidate.assert_not_awaited()


async def test_concurrent_review_or_edit_skips_update(tmp_path: Path, invalidate: AsyncMock) -> None:
    conn = Connection([_row("SYNTH-1")], tmp_path / "backup.csv")
    conn.race = True
    assert await audit_script.audit(conn, fields=("summary_long_el",), apply=True, backup_path=conn.backup) == 0
    invalidate.assert_not_awaited()


async def test_unknown_field_rejected_before_sql(tmp_path: Path) -> None:
    conn = Connection([], tmp_path / "backup.csv")
    with pytest.raises(ValueError, match="Unsupported"):
        await audit_script.audit(conn, fields=("summary_long_el; DROP TABLE parliament_bills",))


async def test_apply_requires_backup(tmp_path: Path) -> None:
    conn = Connection([], tmp_path / "backup.csv")
    with pytest.raises(ValueError, match="requires"):
        await audit_script.audit(conn, apply=True)


class LegacyConnection:
    def __init__(self, rows: list[dict[str, Any]], backup: Path) -> None:
        self.rows, self.backup = rows, backup
        self.writes: list[tuple[str, tuple[Any, ...]]] = []

    async def cursor(self, query: str, *, prefetch: int) -> AsyncIterator[dict[str, Any]]:
        assert prefetch == 100
        for row in self.rows:
            yield row

    @asynccontextmanager
    async def transaction(self, **kwargs: Any) -> AsyncIterator[None]:
        yield

    async def execute(self, query: str, *values: Any) -> str:
        assert stat.S_IMODE(self.backup.stat().st_mode) == 0o600
        self.writes.append((query, values))
        return "UPDATE 1"


def _legacy(bill_id: str, *, source: str = "DIAVGEIA", reviewed: bool | None = False,
            value: str = BAD) -> dict[str, Any]:
    return {"id": bill_id, "source": source, "ai_summary_reviewed": reviewed,
            "generated_content_provenance": None, "summary_long_el": value}


@pytest.mark.asyncio
async def test_legacy_fields_need_an_explicit_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "services.representation_cache",
                        type("M", (), {"invalidate_representation_cache": AsyncMock()}))
    backup = tmp_path / "legacy.csv"
    conn = LegacyConnection([_legacy("L-1")], backup)
    cleared = await audit_script.audit(conn, fields=("summary_long_el",), apply=True, backup_path=backup)
    assert cleared == 0 and conn.writes == [] and not backup.exists()


@pytest.mark.asyncio
async def test_include_legacy_clears_only_named_unreviewed_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalidate = AsyncMock()
    monkeypatch.setitem(__import__("sys").modules, "services.representation_cache",
                        type("M", (), {"invalidate_representation_cache": invalidate}))
    backup = tmp_path / "legacy.csv"
    rows = [
        _legacy("L-bad"),
        _legacy("L-other-source", source="PARLIAMENT"),
        _legacy("L-reviewed", reviewed=True),
        _legacy("L-good", value=GOOD),
    ]
    conn = LegacyConnection(rows, backup)
    cleared = await audit_script.audit(
        conn, fields=("summary_long_el",), apply=True, backup_path=backup,
        legacy_sources=frozenset({"DIAVGEIA"}),
    )
    assert cleared == 1
    with backup.open(newline="", encoding="utf-8") as stream:
        assert list(csv.DictReader(stream)) == [{"id": "L-bad", "field": "summary_long_el", "old_value": BAD}]
    [(query, values)] = conn.writes
    assert values == ("L-bad", BAD, "DIAVGEIA", "summary_long_el", audit_script.SENSITIVE_PATTERN)
    for guard in ("summary_long_el = $2", "ai_summary_reviewed IS NOT TRUE", "source = $3", "? $4::text"):
        assert guard in query
    assert BAD not in query
    invalidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_include_legacy_dry_run_writes_nothing(tmp_path: Path) -> None:
    backup = tmp_path / "legacy.csv"
    conn = LegacyConnection([_legacy("L-bad")], backup)
    cleared = await audit_script.audit(conn, fields=("summary_long_el",), legacy_sources=frozenset({"DIAVGEIA"}))
    assert cleared == 0 and conn.writes == [] and not backup.exists()


@pytest.mark.parametrize("owned", [False, True])
@pytest.mark.parametrize("marker", ["ΑΜΚΑ", "Α.Μ.Κ.Α", "amka", "ασθεν", "ΕΟΠΥΥ", "eopyy"])
async def test_sensitive_failure_is_skipped_and_bill_stays_hidden(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], owned: bool, marker: str,
) -> None:
    from types import SimpleNamespace
    from services.bill_visibility import is_public_bill

    value = BAD + " " + marker
    row = _row("SYNTH-SENSITIVE", owned=owned, value=value)
    row.update(source="DIAVGEIA", title_el="Συνθετικός τίτλος", summary_short_el=None)
    assert not is_public_bill(SimpleNamespace(**row))
    conn = LegacyConnection([row], tmp_path / "sensitive.csv")
    assert await audit_script.audit(conn, fields=("summary_long_el",), apply=True, backup_path=conn.backup,
                                    legacy_sources=frozenset({"DIAVGEIA"})) == 0
    assert "skipped_sensitive\t1\tSYNTH-SENSITIVE" in capsys.readouterr().out
    assert not conn.writes and not conn.backup.exists()
    assert not is_public_bill(SimpleNamespace(**row))


@pytest.mark.parametrize("apply", [False, True])
async def test_legacy_fields_restrict_counting_backup_and_apply(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], invalidate: AsyncMock, apply: bool,
) -> None:
    row = _legacy("SYNTH-FIELDS")
    row.update(pill_el="ERROR", summary_short_el="English summary that must remain untouched.")

    class FieldsConnection(LegacyConnection):
        async def cursor(self, query: str, *, prefetch: int) -> AsyncIterator[dict[str, Any]]:
            assert "summary_short_el" not in query and "pill_el" not in query
            yield row

        async def execute(self, query: str, *values: Any) -> str:
            assert "lower(summary_long_el) ~ $5" in query
            assert values[-1] == audit_script.SENSITIVE_PATTERN
            row["summary_long_el"] = None
            return await super().execute(query, *values)

    conn = FieldsConnection([row], tmp_path / "fields.csv")
    assert await audit_script.audit(conn, fields=("summary_long_el",), apply=apply, backup_path=conn.backup,
                                    legacy_sources=frozenset({"DIAVGEIA"})) == int(apply)
    output = capsys.readouterr().out
    assert "summary_short_el" not in output and "pill_el" not in output
    assert "summary_long_el\trefusal_or_meta\t1" in output
    assert row["pill_el"] == "ERROR" and row["summary_short_el"].startswith("English")
    if apply:
        assert row["summary_long_el"] is None
        with conn.backup.open(newline="", encoding="utf-8") as stream:
            assert [entry["field"] for entry in csv.DictReader(stream)] == ["summary_long_el"]
    else:
        assert not conn.writes and not conn.backup.exists()


async def test_cursor_spools_complete_backup_before_batched_updates(tmp_path: Path, invalidate: AsyncMock) -> None:
    class StreamingConnection:
        scanned = writes = 0
        transaction_sizes: list[int] = []
        current_writes = 0

        @asynccontextmanager
        async def transaction(self, *, readonly: bool = False) -> AsyncIterator[None]:
            self.current_writes = 0
            yield
            if not readonly:
                self.transaction_sizes.append(self.current_writes)

        async def cursor(self, query: str, *, prefetch: int) -> AsyncIterator[dict[str, Any]]:
            assert prefetch == 100
            for index in range(251):
                self.scanned += 1
                yield _row(f"SYNTH-{index}")

        async def execute(self, query: str, *values: Any) -> str:
            assert self.scanned == 251
            with backup.open(newline="", encoding="utf-8") as stream:
                assert sum(1 for _ in csv.DictReader(stream)) == 251
            self.current_writes += 1
            self.writes += 1
            return "UPDATE 1"

    backup = tmp_path / "streamed.csv"
    conn = StreamingConnection()
    assert await audit_script.audit(conn, fields=("summary_long_el",), apply=True, backup_path=backup) == 251
    assert conn.transaction_sizes == [100, 100, 51]
    assert conn.writes == 251


def test_cli_legacy_source_and_field_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--include-legacy", "DIAVGEIA", "--fields", "summary_long_el"])
    args = audit_script.parse_args()
    assert args.include_legacy == ["DIAVGEIA"] and args.fields == ["summary_long_el"]
    assert frozenset(args.legacy_reasons) == audit_script.DEFAULT_LEGACY_REASONS
    assert "non_greek" not in args.legacy_reasons


@pytest.mark.parametrize("apply", [False, True])
@pytest.mark.parametrize("owned", [False, True])
@pytest.mark.parametrize("explicit_non_greek", [False, True])
async def test_non_greek_legacy_is_report_only_unless_explicitly_selected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], invalidate: AsyncMock,
    apply: bool, owned: bool, explicit_non_greek: bool,
) -> None:
    value = "A synthetic description of the administrative procedure."
    row = _legacy("L-language", value=value)
    if owned:
        row["generated_content_provenance"] = {"summary_long_el": content_sha256(value)}
    reasons = {"legacy_reasons": frozenset({"non_greek"})} if explicit_non_greek else {}
    conn = LegacyConnection([row], tmp_path / "language.csv")
    eligible = owned or explicit_non_greek
    assert await audit_script.audit(
        conn, fields=("summary_long_el",), apply=apply, backup_path=conn.backup,
        legacy_sources=frozenset({"DIAVGEIA"}), **reasons,
    ) == int(apply and eligible)
    output = capsys.readouterr().out
    assert "sample_ids\twould_clear\treport_only" in output
    assert f"\tnon_greek\t1\tL-language\t{int(eligible)}\t{int(not eligible)}" in output
    assert value not in output
    if apply and eligible:
        with conn.backup.open(newline="", encoding="utf-8") as stream:
            assert list(csv.DictReader(stream)) == [{"id": "L-language", "field": "summary_long_el", "old_value": value}]
        assert len(conn.writes) == 1
        invalidate.assert_awaited_once()
    else:
        assert not conn.writes and not conn.backup.exists()
        invalidate.assert_not_awaited()


@pytest.mark.parametrize("value,reason", [
    (BAD, "refusal_or_meta"),
    ("Title: Έγγραφο\nURL Source: https://example.test/source\nΚείμενο", "reader_metadata"),
    ("Î•Î»Î»Î·Î½Î¹ÎºÏŒ", "mojibake"),
    ("<html><title>403 Forbidden</title><body>Access denied</body></html>", "error_page"),
    ("Правила синтетического документа", "foreign_script"),
    ("Για να βridge το προβλήμα", "mixed_script"),
])
@pytest.mark.parametrize("apply", [False, True])
async def test_legacy_default_allows_each_high_precision_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], invalidate: AsyncMock,
    value: str, reason: str, apply: bool,
) -> None:
    conn = LegacyConnection([_legacy("L-precise", value=value)], tmp_path / "precise.csv")
    assert await audit_script.audit(
        conn, fields=("summary_long_el",), apply=apply, backup_path=conn.backup,
        legacy_sources=frozenset({"DIAVGEIA"}),
    ) == int(apply)
    output = capsys.readouterr().out
    assert f"\t{reason}\t1\tL-precise\t1\t0" in output
    if "\tnon_greek\t" in output:
        assert "\tnon_greek\t1\tL-precise\t0\t1" in output
    if apply:
        # Multiple reasons authorize a single field backup/update.
        assert len(conn.writes) == 1
        with conn.backup.open(newline="", encoding="utf-8") as stream:
            assert len(list(csv.DictReader(stream))) == 1
        invalidate.assert_awaited_once()
    else:
        assert not conn.writes and not conn.backup.exists()
        invalidate.assert_not_awaited()


async def test_explicit_legacy_reasons_replace_defaults_and_do_not_restrict_owned_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], invalidate: AsyncMock,
) -> None:
    conn = LegacyConnection([_legacy("L-refusal"), _row("G-refusal")], tmp_path / "selected.csv")
    assert await audit_script.audit(
        conn, fields=("summary_long_el",), apply=True, backup_path=conn.backup,
        legacy_sources=frozenset({"DIAVGEIA"}), legacy_reasons=frozenset({"non_greek"}),
    ) == 1
    output = capsys.readouterr().out
    assert "DIAVGEIA\tsummary_long_el\trefusal_or_meta\t1\tL-refusal\t0\t1" in output
    assert "SYNTHETIC\tsummary_long_el\trefusal_or_meta\t1\tG-refusal\t1\t0" in output
    assert [values[0] for _, values in conn.writes] == ["G-refusal"]


async def test_explicit_legacy_reasons_still_require_source_and_preserve_reviewed_or_edited_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], invalidate: AsyncMock,
) -> None:
    value = "A synthetic description of the administrative procedure."
    edited = _legacy("L-edited", value=value)
    edited["generated_content_provenance"] = {"summary_long_el": content_sha256(GOOD)}
    rows = [_legacy("L-other", source="PARLIAMENT", value=value),
            _legacy("L-reviewed", reviewed=True, value=value), edited]
    conn = LegacyConnection(rows, tmp_path / "protected.csv")
    assert await audit_script.audit(
        conn, fields=("summary_long_el",), apply=True, backup_path=conn.backup,
        legacy_sources=frozenset({"DIAVGEIA"}), legacy_reasons=frozenset({"non_greek"}),
    ) == 0
    output = capsys.readouterr().out
    assert "DIAVGEIA\tsummary_long_el\tnon_greek\t2\tL-reviewed,L-edited\t0\t2" in output
    assert "PARLIAMENT\tsummary_long_el\tnon_greek\t1\tL-other\t0\t1" in output
    assert not conn.writes and not conn.backup.exists()
    invalidate.assert_not_awaited()


@pytest.mark.parametrize("reasons", [
    ["non_greek"], ["mixed_script", "non_greek"], ["error_page", "foreign_script"],
])
def test_cli_accepts_explicit_legacy_reason_list(monkeypatch: pytest.MonkeyPatch, reasons: list[str]) -> None:
    import sys

    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--include-legacy", "DIAVGEIA", "--legacy-reasons", *reasons])
    assert audit_script.parse_args().legacy_reasons == reasons


def test_cli_rejects_unknown_legacy_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--legacy-reasons", "non_grek"])
    with pytest.raises(SystemExit) as error:
        audit_script.parse_args()
    assert error.value.code == 2


async def test_unknown_legacy_reason_rejected_before_sql(tmp_path: Path) -> None:
    conn = LegacyConnection([], tmp_path / "unknown.csv")
    with pytest.raises(ValueError, match="Unsupported legacy reasons"):
        await audit_script.audit(conn, legacy_reasons=frozenset({"non_grek"}))


async def test_clearing_other_fields_cannot_expose_sensitive_bill(tmp_path: Path, invalidate: AsyncMock) -> None:
    from types import SimpleNamespace
    from services.bill_visibility import is_public_bill

    row = _legacy("SYNTH-HIDDEN", value=BAD + " ΑΜΚΑ")
    row.update(title_el="Συνθετικός τίτλος", summary_short_el=BAD)
    assert not is_public_bill(SimpleNamespace(**row))

    class VisibilityConnection(LegacyConnection):
        async def execute(self, query: str, *values: Any) -> str:
            assert "SET summary_short_el = NULL" in query
            row["summary_short_el"] = None
            return await super().execute(query, *values)

    conn = VisibilityConnection([row], tmp_path / "hidden.csv")
    assert await audit_script.audit(conn, fields=("summary_short_el", "summary_long_el"), apply=True,
                                    backup_path=conn.backup, legacy_sources=frozenset({"DIAVGEIA"})) == 1
    assert row["summary_short_el"] is None and "ΑΜΚΑ" in row["summary_long_el"]
    assert not is_public_bill(SimpleNamespace(**row))
