#!/usr/bin/env python3
"""Repair exact DIAVGEIA unknown organization pills. Default: database reads only.

Dry runs resolve public organization UIDs and may warm the Redis label cache.
Apply consumes a reviewed plan without HTTP, requires an explicit row bound and
a new 0600 backup, and rechecks both old columns in each bounded transaction.
No prose, sensitivity fields, overrides, timestamps or decision rows are edited.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.diavgeia_org_lookup import (
    UID_RE, UNKNOWN_PILL_RE, UNKNOWN_PILL_SQL_PATTERN,
    clean_org_label, org_pill, resolve_org_label,
)
from services.representation_cache import invalidate_representation_cache

PLAN_HEADER = ("id", "old_pill_sha256", "old_org_label_sha256", "uid", "new_pill")
BACKUP_HEADER = ("id", "old_pill", "old_org_label_json", "new_pill")
BATCH_SIZE = 100
SELECT_SQL = """SELECT id, pill_el, org_label FROM parliament_bills
    WHERE source = 'DIAVGEIA' AND pill_el ~ $1 ORDER BY id"""
# Assign only these two columns: z904's UPDATE OF sensitivity trigger must not fire.
UPDATE_SQL = """UPDATE parliament_bills SET pill_el = $3, org_label = $5
    WHERE id = $1 AND source = 'DIAVGEIA' AND pill_el = $2
      AND org_label IS NOT DISTINCT FROM $4"""


def pill_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def org_label_sha256(value: str | None) -> str:
    # JSON binds the raw value, distinguishing SQL NULL, empty and literal null.
    return pill_sha256(json.dumps(value, ensure_ascii=False))


def _open_private(path: Path):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    stream = os.fdopen(fd, "w", newline="", encoding="utf-8")
    os.fchmod(stream.fileno(), 0o600)
    return stream


def read_plan(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != PLAN_HEADER:
            raise ValueError("Unexpected plan header")
        expected = {}
        for row in reader:
            if (None in row or any(value is None for value in row.values())
                    or not row["id"] or row["id"] in expected or not UID_RE.fullmatch(row["uid"])):
                raise ValueError("Invalid or duplicate plan entry")
            old_pill = f"Διαύγεια: [unknown:{row['uid']}]"
            if row["old_pill_sha256"] != pill_sha256(old_pill):
                raise ValueError("Plan digest does not match UID")
            if not re.fullmatch(r"[0-9a-f]{64}", row["old_org_label_sha256"]):
                raise ValueError("Invalid old organization label digest")
            new_pill = row["new_pill"]
            if new_pill != "Διαύγεια":
                prefix = "Διαύγεια: "
                if not new_pill.startswith(prefix) or org_pill(new_pill[len(prefix):]) != new_pill:
                    raise ValueError("Invalid new pill in plan")
            expected[row["id"]] = row
    return expected


def _validate(*, apply, backup_path, expect_from, max_rows, plan_path, sample_limit):
    if max_rows is not None and (type(max_rows) is not int or max_rows < 0):
        raise ValueError("max_rows must be a nonnegative integer")
    if type(sample_limit) is not int or sample_limit < 0:
        raise ValueError("sample_limit must be a nonnegative integer")
    if apply and (expect_from is None or max_rows is None or backup_path is None):
        raise ValueError("--apply requires --expect-from, --max-rows and --backup-csv")
    if apply and plan_path is not None:
        raise ValueError("--plan-csv is for dry runs only")


async def backfill(
    conn, *, apply: bool = False, plan_path: Path | None = None,
    expect_from: Path | None = None, max_rows: int | None = None,
    backup_path: Path | None = None, sample_limit: int = 5,
) -> int:
    _validate(apply=apply, backup_path=backup_path, expect_from=expect_from,
              max_rows=max_rows, plan_path=plan_path, sample_limit=sample_limit)
    expected = read_plan(expect_from) if expect_from is not None else None
    labels: dict[str, str | None] = {}
    uids = set()
    candidates = []
    scanned = resolved = neutral = skipped = 0
    samples = []
    # Read-only snapshot; no row locks held across public HTTP requests.
    async with conn.transaction(readonly=True):
        async for row in conn.cursor(SELECT_SQL, UNKNOWN_PILL_SQL_PATTERN, prefetch=BATCH_SIZE):
            match = UNKNOWN_PILL_RE.fullmatch(row["pill_el"] or "")
            if not match:
                continue
            scanned += 1
            uid = match.group(1)
            uids.add(uid)
            digest = pill_sha256(row["pill_el"])
            if expected is not None:
                entry = expected.get(row["id"])
                if entry is None or (
                    entry["uid"], entry["old_pill_sha256"], entry["old_org_label_sha256"]
                ) != (uid, digest, org_label_sha256(row["org_label"])):
                    skipped += 1
                    continue
                new_pill = entry["new_pill"]
            else:
                if uid not in labels:
                    labels[uid] = await resolve_org_label(uid)
                new_pill = org_pill(labels[uid] or clean_org_label(row["org_label"]))
            resolved += int(new_pill != "Διαύγεια")
            neutral += int(new_pill == "Διαύγεια")
            if len(samples) < sample_limit:
                samples.append(row["id"])
            candidates.append((row["id"], row["pill_el"], row["org_label"], uid, new_pill))

    print(f"{'APPLY' if apply else 'DRY-RUN'}: unknown pills={scanned}; "
          f"planned={len(candidates)}; resolved={resolved}; neutral={neutral}; "
          f"unplanned/changed={skipped}; distinct_uids={len(uids)}")
    print("Sample ids: " + ",".join(samples))
    if expected is not None:
        print(f"Plan entries={len(expected)}; not matched={len(expected) - len(candidates)}")
    if plan_path is not None:
        with _open_private(plan_path) as stream:
            writer = csv.writer(stream)
            writer.writerow(PLAN_HEADER)
            writer.writerows((bill_id, pill_sha256(old), org_label_sha256(old_label), uid, new)
                             for bill_id, old, old_label, uid, new in candidates)
            stream.flush()
            os.fsync(stream.fileno())
        print(f"Plan: {plan_path}")
    if not apply:
        return 0
    assert max_rows is not None and backup_path is not None
    if len(candidates) > max_rows:
        raise ValueError(f"ABORT: {len(candidates)} matching rows exceed --max-rows {max_rows}; nothing written")
    if not candidates:
        return 0
    # Back up every attempted old value durably before the first transaction.
    # JSON preserves the difference between SQL NULL and an empty org_label.
    with _open_private(backup_path) as stream:
        writer = csv.writer(stream)
        writer.writerow(BACKUP_HEADER)
        writer.writerows((bill_id, old, json.dumps(old_label, ensure_ascii=False), new)
                         for bill_id, old, old_label, _, new in candidates)
        stream.flush()
        os.fsync(stream.fileno())
    updated = 0
    for start in range(0, len(candidates), BATCH_SIZE):
        batch_updated = 0
        async with conn.transaction():
            for bill_id, old, old_label, _, new in candidates[start:start + BATCH_SIZE]:
                label = clean_org_label(new.removeprefix("Διαύγεια: ")) if new != "Διαύγεια" else None
                label = clean_org_label(old_label) or label
                status = await conn.execute(UPDATE_SQL, bill_id, old, new, old_label, label)
                batch_updated += int(status.split()[-1])
        updated += batch_updated
        if batch_updated:
            await invalidate_representation_cache()
    print(f"Updated={updated}; concurrent changes skipped={len(candidates) - updated}; backup: {backup_path}")
    return updated


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-csv", type=Path, help="New private plan file (dry run only)")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-from", type=Path, help="Reviewed dry-run plan; only exact matching rows are eligible")
    parser.add_argument("--max-rows", type=int, help="Nonnegative bound; exceeding it aborts before backup/writes")
    parser.add_argument("--backup-csv", type=Path, help="New exclusive mode-0600 backup, required for apply")
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        _validate(apply=args.apply, backup_path=args.backup_csv, expect_from=args.expect_from,
                  max_rows=args.max_rows, plan_path=args.plan_csv, sample_limit=args.samples)
    except ValueError as exc:
        parser.error(str(exc))
    return args


async def main():
    import asyncpg

    args = parse_args()
    conn = await asyncpg.connect(os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await backfill(conn, apply=args.apply, plan_path=args.plan_csv, expect_from=args.expect_from,
                       max_rows=args.max_rows, backup_path=args.backup_csv, sample_limit=args.samples)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
