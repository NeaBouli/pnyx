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

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        assert query.startswith("SELECT ")
        return self.rows

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
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
    assert conn.writes[0][1] == ("SYNTH-1", BAD, "summary_long_el", content_sha256(BAD))
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

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        return self.rows

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
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
    assert values == ("L-bad", BAD, "DIAVGEIA", "summary_long_el")
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
