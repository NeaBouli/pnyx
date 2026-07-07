#!/usr/bin/env python3
"""Deterministic metadata backfill for old PARLIAMENT beta rows.

This script fills only missing ``summary_short_el`` and/or ``pill_el`` values
for PARLIAMENT bills. It never calls AI, never overwrites non-empty fields, and
does not touch votes, forum IDs, Arweave IDs, source URLs, or official document
blocks.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


DEFAULT_AUDIT_CSV = "/tmp/backfill_parliament_metadata_audit.csv"


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def has_text(value: str | None) -> bool:
    return bool(normalize_text(value))


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 1:
        return value[:limit]
    return value[: limit - 1].rstrip() + "…"


def format_el_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    text = str(value)
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{day}/{month}/{year}"


def build_metadata_summary(
    *,
    title_el: str,
    submitted_date: Any = None,
    vote_date: Any = None,
) -> str:
    title = normalize_text(title_el)
    lines = [f"Η Βουλή δημοσίευσε εγγραφή για: {title}."]

    facts: list[str] = []
    submitted = format_el_date(submitted_date)
    if submitted:
        facts.append(f"Ημερομηνία κατάθεσης: {submitted}")
    voted = format_el_date(vote_date)
    if voted:
        facts.append(f"Ημερομηνία συζήτησης/ψήφισης: {voted}")
    if facts:
        lines.append("; ".join(facts) + ".")

    lines.append("Για το πλήρες περιεχόμενο δείτε τα επίσημα έγγραφα της Βουλής.")
    return "\n".join(lines)


def build_metadata_pill(*, title_el: str) -> str:
    return truncate(normalize_text(title_el), 200)


def database_url_from_env() -> str:
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    return db_url.replace("postgresql+asyncpg://", "postgresql://")


def row_action(row: Any) -> tuple[bool, bool]:
    return (not has_text(row["summary_short_el"]), not has_text(row["pill_el"]))


async def fetch_candidates(conn: Any, *, limit: int, bill_id: str | None) -> list[Any]:
    where = [
        "source = 'PARLIAMENT'",
        "((summary_short_el IS NULL OR btrim(summary_short_el) = '') "
        "OR (pill_el IS NULL OR btrim(pill_el) = ''))",
    ]
    params: list[Any] = []
    if bill_id:
        params.append(bill_id)
        where.append(f"id = ${len(params)}")

    query = f"""
        SELECT id, title_el, summary_short_el, pill_el, source, status,
               submitted_date, parliament_vote_date, parliament_url
        FROM parliament_bills
        WHERE {' AND '.join(where)}
        ORDER BY GREATEST(
            COALESCE(submitted_date, '1900-01-01'::timestamp),
            COALESCE(parliament_vote_date, '1900-01-01'::timestamp),
            COALESCE(created_at, '1900-01-01'::timestamp)
        ) DESC
    """
    if limit > 0:
        params.append(limit)
        query += f" LIMIT ${len(params)}"
    return list(await conn.fetch(query, *params))


async def apply_update(conn: Any, row: Any, summary: str, pill: str) -> str:
    result = await conn.execute(
        """
        UPDATE parliament_bills
        SET
          summary_short_el = CASE
            WHEN summary_short_el IS NULL OR btrim(summary_short_el) = '' THEN $1
            ELSE summary_short_el
          END,
          pill_el = CASE
            WHEN pill_el IS NULL OR btrim(pill_el) = '' THEN $2
            ELSE pill_el
          END
        WHERE id = $3
          AND source = 'PARLIAMENT'
          AND (
            summary_short_el IS NULL OR btrim(summary_short_el) = ''
            OR pill_el IS NULL OR btrim(pill_el) = ''
          )
        """,
        summary,
        pill,
        row["id"],
    )
    return result


async def run(args: argparse.Namespace) -> int:
    import asyncpg

    conn = await asyncpg.connect(database_url_from_env())
    try:
        rows = await fetch_candidates(conn, limit=args.limit, bill_id=args.bill_id)
        audit_path = Path(args.audit_csv)
        with audit_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(
                [
                    "bill_id",
                    "status",
                    "fill_summary_short_el",
                    "fill_pill_el",
                    "summary_short_el",
                    "pill_el",
                    "action",
                ]
            )

            updated = 0
            skipped = 0
            print(f"{'APPLY' if args.apply else 'DRY-RUN'} mode — PARLIAMENT metadata backfill")
            print(f"Candidates: {len(rows)}")

            for row in rows:
                title = normalize_text(row["title_el"])
                fill_summary, fill_pill = row_action(row)
                if not title:
                    writer.writerow([row["id"], row["status"], fill_summary, fill_pill, "", "", "SKIP_NO_TITLE"])
                    skipped += 1
                    continue

                summary = build_metadata_summary(
                    title_el=title,
                    submitted_date=row["submitted_date"],
                    vote_date=row["parliament_vote_date"],
                )
                pill = build_metadata_pill(title_el=title)
                action = "UPDATE" if args.apply else "DRY_RUN"
                writer.writerow([row["id"], row["status"], fill_summary, fill_pill, summary, pill, action])

                if args.apply:
                    await apply_update(conn, row, summary, pill)
                updated += 1

        print(f"Results: {updated} {'updated' if args.apply else 'would update'}, {skipped} skipped")
        print(f"CSV audit: {audit_path}")
        return 0
    finally:
        await conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill old PARLIAMENT metadata summaries safely")
    parser.add_argument("--apply", action="store_true", help="Write to DB; default is dry-run")
    parser.add_argument("--limit", type=int, default=0, help="Limit rows; 0 means all")
    parser.add_argument("--bill-id", default=None, help="Restrict to one bill id")
    parser.add_argument("--audit-csv", default=DEFAULT_AUDIT_CSV, help="CSV audit output path")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
