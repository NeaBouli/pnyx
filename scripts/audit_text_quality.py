#!/usr/bin/env python3
"""Audit bill prose without printing it. Default: database reads only.

Apply requires both an unreviewed row and an exact generation ownership digest.
Legacy fields without provenance are reported but never automatically cleared:
their ownership cannot be distinguished from human edits or official text.
The exclusive, mode-0600 CSV backup is flushed to disk before any UPDATE.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from services.content_provenance import content_sha256
from services.text_quality import GENERATED_TEXT_FIELDS, GREEK_FIELDS, check_generated_text


def _ownership(row: Any) -> dict[str, str]:
    value = row["generated_content_provenance"]
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, dict) else {}


def write_backup(path: Path, failures: list[tuple[str, str, str]]) -> None:
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
) -> int:
    """Print aggregate counts and IDs; return number of fields cleared."""
    if not fields or any(field not in GENERATED_TEXT_FIELDS for field in fields):
        raise ValueError("Unsupported audit fields")
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")
    if apply and backup_path is None:
        raise ValueError("--apply requires --backup-csv")
    fields = tuple(dict.fromkeys(fields))
    rows = await conn.fetch(
        "SELECT id, source, ai_summary_reviewed, generated_content_provenance, "
        + ", ".join(fields) + " FROM parliament_bills ORDER BY id"
    )
    counts: Counter[tuple[str, str, str]] = Counter()
    samples: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    generated: list[tuple[str, str, str]] = []
    for row in rows:
        ownership = _ownership(row)
        for field in fields:
            value = row[field]
            quality = check_generated_text(value, field=field)
            for reason in quality.reasons:
                key = (row["source"] or "UNKNOWN", field, reason)
                counts[key] += 1
                if len(samples[key]) < sample_limit:
                    samples[key].append(row["id"])
            if (
                not quality.ok and not row["ai_summary_reviewed"]
                and ownership.get(field) == content_sha256(value)
            ):
                generated.append((row["id"], field, value))
    print("source\tfield\treason\tcount\tsample_ids")
    for key, count in sorted(counts.items()):
        print("\t".join((*key, str(count), ",".join(samples[key]))))
    print(f"{'APPLY' if apply else 'DRY-RUN'}: {len(rows)} rows; {len(generated)} failing fields with generation ownership")
    if not apply or not generated:
        return 0
    assert backup_path is not None
    write_backup(backup_path, generated)
    updated = 0
    async with conn.transaction():
        for bill_id, field, value in generated:
            # Identifiers are allowlisted above. All values are parameters;
            # recheck ownership, review status and value against concurrent edits.
            status = await conn.execute(
                f"UPDATE parliament_bills SET {field} = NULL, "
                "generated_content_provenance = generated_content_provenance - $3::text "
                f"WHERE id = $1 AND {field} = $2 AND ai_summary_reviewed IS NOT TRUE "
                "AND generated_content_provenance ->> $3::text = $4",
                bill_id, value, field, content_sha256(value),
            )
            updated += int(status.split()[-1])
    if updated:
        from services.representation_cache import invalidate_representation_cache

        await invalidate_representation_cache()
    print(f"Cleared {updated} fields; backup: {backup_path}")
    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fields", nargs="+", choices=GENERATED_TEXT_FIELDS, default=list(GREEK_FIELDS))
    parser.add_argument("--samples", type=int, default=5, help="Maximum sample IDs per source/field/reason")
    parser.add_argument("--apply", action="store_true", help="Clear only unreviewed, provably generated failures")
    parser.add_argument("--backup-csv", type=Path, help="New private CSV file, required with --apply")
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
                        apply=True, backup_path=args.backup_csv)
        else:
            async with conn.transaction(readonly=True):
                await audit(conn, fields=tuple(args.fields), sample_limit=args.samples)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
