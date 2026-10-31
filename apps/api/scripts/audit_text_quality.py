#!/usr/bin/env python3
"""Audit bill prose without printing it. Default: database reads only.

Apply requires an unreviewed row and either an exact generation ownership digest
or explicit legacy source/reason eligibility.
Legacy fields without provenance are reported but only cleared when an operator
names their source with --include-legacy after reviewing a dry run: their
ownership cannot be distinguished from human edits or official text otherwise.
Legacy clearing defaults to refusal_or_meta, reader_metadata, mojibake and
error_page; language/script signals are report-only unless explicitly selected
with --legacy-reasons (which replaces the defaults).
The exclusive, mode-0600 CSV backup is flushed to disk before any UPDATE.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from itertools import islice
from pathlib import Path
from typing import Any, Iterable, Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.content_provenance import contains_sensitive_marker, content_sha256
from services.public_bill_index import SENSITIVE_PATTERN
from services.text_quality import GENERATED_TEXT_FIELDS, GREEK_FIELDS, check_generated_text


# Legacy fields may hold extracted official text. Official documents contain
# homoglyph quirks (Greek capitals inside brand names, Cyrillic look-alikes),
# so only structural failures are cleared by default; script signals report only.
DEFAULT_LEGACY_REASONS = frozenset({"refusal_or_meta", "reader_metadata", "mojibake", "error_page"})
LEGACY_REASON_CHOICES = DEFAULT_LEGACY_REASONS | {"foreign_script", "mixed_script", "non_greek"}


PAGE_LIKE_MAX_CHARS = 1500
PAGE_LIKE_MIN_MARKUP_SHARE = 0.5


def page_like(value: str) -> bool:
    """Block pages are short or mostly markup; long legislative prose never is.

    A structural bound for legacy clearing: an error-page heuristic hit inside a
    long official text stays report-only, whatever the regexes match.
    """
    if len(value) < PAGE_LIKE_MAX_CHARS:
        return True
    from services.error_pages import _TAG

    markup = sum(len(match) for match in _TAG.findall(value))
    return markup / len(value) > PAGE_LIKE_MIN_MARKUP_SHARE


def _ownership(row: Any) -> dict[str, str]:
    value = row["generated_content_provenance"]
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, dict) else {}


def write_backup(path: Path, failures: Iterable[tuple[str, str, str]]) -> None:
    """Fail closed if the backup already exists or cannot be made durable."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as backup:
        os.fchmod(backup.fileno(), 0o600)
        writer = csv.writer(backup)
        writer.writerow(("id", "field", "old_value"))
        writer.writerows(failures)
        backup.flush()
        os.fsync(backup.fileno())


async def audit(
    conn: Any, *, fields: tuple[str, ...] = GREEK_FIELDS,
    sample_limit: int = 5, apply: bool = False, backup_path: Path | None = None,
    legacy_sources: frozenset[str] = frozenset(),
    legacy_reasons: frozenset[str] = DEFAULT_LEGACY_REASONS,
    plan_path: Path | None = None, expect_from: Path | None = None, max_rows: int | None = None,
) -> int:
    """Print aggregate counts and IDs; return number of fields cleared."""
    if not fields or any(field not in GENERATED_TEXT_FIELDS for field in fields):
        raise ValueError("Unsupported audit fields")
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")
    if not legacy_reasons <= LEGACY_REASON_CHOICES:
        raise ValueError("Unsupported legacy reasons")
    if apply and backup_path is None:
        raise ValueError("--apply requires --backup-csv")
    if apply and (expect_from is None or max_rows is None):
        # An approval covers exactly the reviewed dry-run plan, never whatever a later scan finds.
        raise ValueError("--apply requires --expect-from and --max-rows")
    if max_rows is not None and (type(max_rows) is not int or max_rows < 0):
        raise ValueError("max_rows must be a nonnegative integer")
    expected = read_plan(expect_from) if expect_from is not None else None
    plan_file = _open_private(plan_path) if plan_path is not None else None
    plan_writer = csv.writer(plan_file) if plan_file is not None else None
    if plan_writer is not None:
        plan_writer.writerow(PLAN_HEADER)
    kept = unexpected = 0
    fields = tuple(dict.fromkeys(fields))
    counts: Counter[tuple[str, str, str]] = Counter()
    would_clear: Counter[tuple[str, str, str]] = Counter()
    samples: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    row_count = generated_count = legacy_count = 0
    # The server cursor and disk spool bound memory independently of prose volume.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as candidates:
        async with conn.transaction(readonly=True):
            async for row in conn.cursor(
                "SELECT id, source, ai_summary_reviewed, generated_content_provenance, "
                + ", ".join(fields) + " FROM parliament_bills ORDER BY id", prefetch=100,
            ):
                row_count += 1
                ownership = _ownership(row)
                for field in fields:
                    value = row[field]
                    sensitive = contains_sensitive_marker(value)
                    reasons = ("skipped_sensitive",) if sensitive else check_generated_text(value, field=field).reasons
                    permitted_reasons: tuple[str, ...] = ()
                    source = None
                    if not sensitive and reasons and not row["ai_summary_reviewed"]:
                        if ownership.get(field) == content_sha256(value):
                            generated_count += 1
                            permitted_reasons = reasons
                        elif field not in ownership and row["source"] in legacy_sources:
                            permitted_reasons = tuple(
                                reason for reason in reasons if reason in legacy_reasons
                                and (reason != "error_page" or page_like(value))
                            )
                            if permitted_reasons:
                                legacy_count += 1
                                source = row["source"]
                    for reason in reasons:
                        key = (row["source"] or "UNKNOWN", field, reason)
                        counts[key] += 1
                        if reason in permitted_reasons:
                            would_clear[key] += 1
                        if len(samples[key]) < sample_limit:
                            samples[key].append(row["id"])
                    if not permitted_reasons:
                        continue
                    digest = content_sha256(value)
                    if plan_writer is not None:
                        plan_writer.writerow((row["id"], field, "|".join(permitted_reasons), digest))
                    if apply:
                        if expected is not None and (row["id"], field, digest) not in expected:
                            unexpected += 1
                            continue
                        kept += 1
                        candidates.write(json.dumps((row["id"], field, value, source)) + "\n")
        # Counts describe permission per reason. A field with several permitted
        # reasons is still backed up and cleared only once.
        print("source\tfield\treason\tcount\tsample_ids\twould_clear\treport_only")
        for key, count in sorted(counts.items()):
            print("\t".join((*key, str(count), ",".join(samples[key]), str(would_clear[key]), str(count - would_clear[key]))))
        print(f"{'APPLY' if apply else 'DRY-RUN'}: {row_count} rows; {generated_count} failing fields with generation ownership; "
              f"{legacy_count} eligible failing legacy fields without provenance in {sorted(legacy_sources) or 'no named source'}; "
              f"legacy reasons: {', '.join(sorted(legacy_reasons)) or 'none'}")
        if plan_file is not None:
            plan_file.flush()
            os.fsync(plan_file.fileno())
            plan_file.close()
            print(f"Plan: {plan_path}")
        if not apply:
            return 0
        assert expected is not None and max_rows is not None
        print(f"Approved plan: {len(expected)} entries; matching now: {kept}; "
              f"not in plan (skipped): {unexpected}; plan entries not matched: {len(expected) - kept}")
        if kept > max_rows:
            print(f"ABORT: {kept} matching fields exceed --max-rows {max_rows}; nothing written")
            return 0
        if not kept:
            return 0
        assert backup_path is not None
        write_backup(backup_path, (entry[:3] for entry in _candidates(candidates)))
        updated = 0
        # Replay the durable backup's candidates in bounded transactions.
        entries = _candidates(candidates)
        while True:
            batch = list(islice(entries, 100))
            if not batch:
                break
            batch_updated = 0
            async with conn.transaction():
                for bill_id, field, value, source in batch:
                    # Exact value + sensitivity rechecks preserve suppression even
                    # when a concurrent edit lands between scan and update.
                    if source is None:
                        status = await conn.execute(
                            f"UPDATE parliament_bills SET {field} = NULL, "
                            "generated_content_provenance = generated_content_provenance - $3::text "
                            f"WHERE id = $1 AND {field} = $2 AND ai_summary_reviewed IS NOT TRUE "
                            "AND generated_content_provenance ->> $3::text = $4 "
                            f"AND NOT (lower({field}) ~ $5)",
                            bill_id, value, field, content_sha256(value), SENSITIVE_PATTERN,
                        )
                    else:
                        status = await conn.execute(
                            f"UPDATE parliament_bills SET {field} = NULL "
                            f"WHERE id = $1 AND {field} = $2 AND ai_summary_reviewed IS NOT TRUE AND source = $3 "
                            "AND NOT (coalesce(nullif(generated_content_provenance, 'null'::jsonb), '{}'::jsonb) ? $4::text) "
                            f"AND NOT (lower({field}) ~ $5)",
                            bill_id, value, source, field, SENSITIVE_PATTERN,
                        )
                    batch_updated += int(status.split()[-1])
            updated += batch_updated
            if batch_updated:
                from services.representation_cache import invalidate_representation_cache

                await invalidate_representation_cache()
        print(f"Cleared {updated} fields; backup: {backup_path}")
        return updated


PLAN_HEADER = ("id", "field", "reasons", "sha256")


def _open_private(path: Path) -> TextIO:
    """Exclusive 0600 file: never overwrite an earlier plan or backup."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    stream = os.fdopen(fd, "w", newline="", encoding="utf-8")
    os.fchmod(stream.fileno(), 0o600)
    return stream


def read_plan(path: Path) -> frozenset[tuple[str, str, str]]:
    """Approved dry-run entries keyed by id, field and the exact value digest."""
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != PLAN_HEADER:
            raise ValueError("Unexpected plan header")
        return frozenset((row["id"], row["field"], row["sha256"]) for row in reader)


def _candidates(stream: TextIO) -> Iterator[tuple[str, str, str, str | None]]:
    stream.seek(0)
    for line in stream:
        bill_id, field, value, source = json.loads(line)
        yield bill_id, field, value, source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fields", nargs="+", choices=GENERATED_TEXT_FIELDS, default=list(GREEK_FIELDS))
    parser.add_argument("--samples", type=int, default=5, help="Maximum sample IDs per source/field/reason")
    parser.add_argument("--apply", action="store_true", help="Clear eligible unreviewed failures after writing the backup")
    parser.add_argument("--backup-csv", type=Path, help="New private CSV file, required with --apply")
    parser.add_argument("--include-legacy", metavar="SOURCE", action="append", default=[],
                        help="Also clear high-precision failures in unreviewed fields without provenance for this bill source")
    parser.add_argument("--plan-csv", type=Path, help="New private CSV listing every field this run would clear (no text)")
    parser.add_argument("--expect-from", type=Path, help="Approved dry-run plan; --apply clears only matching fields")
    parser.add_argument("--max-rows", type=int, help="Nonnegative integer; abort --apply without writing if more fields match")
    parser.add_argument("--legacy-reasons", nargs="+", choices=sorted(LEGACY_REASON_CHOICES),
                        default=sorted(DEFAULT_LEGACY_REASONS),
                        help="Replace the legacy clearing reasons; defaults to refusal_or_meta, reader_metadata, "
                             "mojibake, error_page; non_greek, mixed_script, foreign_script are report-only")
    args = parser.parse_args()
    if args.samples < 0:
        parser.error("--samples must be non-negative")
    if args.max_rows is not None and args.max_rows < 0:
        parser.error("--max-rows must be a nonnegative integer")
    if args.apply and args.backup_csv is None:
        parser.error("--apply requires --backup-csv")
    if args.apply and (args.expect_from is None or args.max_rows is None):
        parser.error("--apply requires --expect-from and --max-rows")
    return args


async def main() -> None:
    import asyncpg

    args = parse_args()
    db_url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    try:
        await audit(conn, fields=tuple(args.fields), sample_limit=args.samples,
                    apply=args.apply, backup_path=args.backup_csv,
                    legacy_sources=frozenset(args.include_legacy),
                    legacy_reasons=frozenset(args.legacy_reasons),
                    plan_path=args.plan_csv, expect_from=args.expect_from, max_rows=args.max_rows)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
