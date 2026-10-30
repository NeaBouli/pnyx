#!/usr/bin/env python3
"""Audit bill prose without printing it. Default: database reads only.

Apply requires both an unreviewed row and an exact generation ownership digest.
Legacy fields without provenance are reported but only cleared when an operator
names their source with --include-legacy after reviewing a dry run: their
ownership cannot be distinguished from human edits or official text otherwise.
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
) -> int:
    """Print aggregate counts and IDs; return number of fields cleared."""
    if not fields or any(field not in GENERATED_TEXT_FIELDS for field in fields):
        raise ValueError("Unsupported audit fields")
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")
    if apply and backup_path is None:
        raise ValueError("--apply requires --backup-csv")
    fields = tuple(dict.fromkeys(fields))
    counts: Counter[tuple[str, str, str]] = Counter()
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
                    for reason in reasons:
                        key = (row["source"] or "UNKNOWN", field, reason)
                        counts[key] += 1
                        if len(samples[key]) < sample_limit:
                            samples[key].append(row["id"])
                    if sensitive or not reasons or row["ai_summary_reviewed"]:
                        continue
                    source = None
                    if ownership.get(field) == content_sha256(value):
                        generated_count += 1
                    elif field not in ownership and row["source"] in legacy_sources:
                        legacy_count += 1
                        source = row["source"]
                    else:
                        continue
                    if apply:
                        candidates.write(json.dumps((row["id"], field, value, source)) + "\n")
        print("source\tfield\treason\tcount\tsample_ids")
        for key, count in sorted(counts.items()):
            print("\t".join((*key, str(count), ",".join(samples[key]))))
        print(f"{'APPLY' if apply else 'DRY-RUN'}: {row_count} rows; {generated_count} failing fields with generation ownership; "
              f"{legacy_count} failing legacy fields without provenance in {sorted(legacy_sources) or 'no named source'}")
        if not apply or not (generated_count or legacy_count):
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


def _candidates(stream: TextIO) -> Iterator[tuple[str, str, str, str | None]]:
    stream.seek(0)
    for line in stream:
        bill_id, field, value, source = json.loads(line)
        yield bill_id, field, value, source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fields", nargs="+", choices=GENERATED_TEXT_FIELDS, default=list(GREEK_FIELDS))
    parser.add_argument("--samples", type=int, default=5, help="Maximum sample IDs per source/field/reason")
    parser.add_argument("--apply", action="store_true", help="Clear only unreviewed, provably generated failures")
    parser.add_argument("--backup-csv", type=Path, help="New private CSV file, required with --apply")
    parser.add_argument("--include-legacy", metavar="SOURCE", action="append", default=[],
                        help="Also clear failing unreviewed fields without provenance for this bill source")
    args = parser.parse_args()
    if args.samples < 0:
        parser.error("--samples must be non-negative")
    if args.apply and args.backup_csv is None:
        parser.error("--apply requires --backup-csv")
    return args


async def main() -> None:
    import asyncpg

    args = parse_args()
    db_url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    try:
        if args.apply:
            await audit(conn, fields=tuple(args.fields), sample_limit=args.samples,
                        apply=True, backup_path=args.backup_csv,
                        legacy_sources=frozenset(args.include_legacy))
        else:
            await audit(conn, fields=tuple(args.fields), sample_limit=args.samples,
                        legacy_sources=frozenset(args.include_legacy))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
