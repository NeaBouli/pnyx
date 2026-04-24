"""
Offline batch job for initial historical import of Diavgeia decisions.
NOT an HTTP endpoint — run manually or via cron.

Usage:
    cd apps/api && python -m scripts.backfill_diavgeia_decisions \
        --decision-type-uid "Α.2" --since 2024-01-01

Options:
    --decision-type-uid UID    Required (no default, force explicit)
    --since YYYY-MM-DD         Required start date
    --until YYYY-MM-DD         End date (default: now)
    --organization-uid UID     Filter single org (for testing)
    --max-pages N              Safety limit (default: 10000)
    --batch-size N             DB commit batch size (default: 500)
    --resume                   Continue from last cursor
    --dry-run                  Count only, no DB writes
"""
import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CURSOR_PREFIX = ".backfill_cursor_"

_shutdown_requested = False


def _handle_signal(signum: int, frame: object) -> None:
    global _shutdown_requested
    logger.warning("Received signal %d — will flush current batch and exit", signum)
    _shutdown_requested = True


def cursor_path(type_uid: str) -> Path:
    safe_name = type_uid.replace(".", "_").replace("/", "_")
    return DATA_DIR / f"{CURSOR_PREFIX}{safe_name}.json"


def load_cursor(type_uid: str) -> datetime | None:
    p = cursor_path(type_uid)
    if not p.exists():
        return None
    try:
        with open(p, "r") as f:
            data = json.load(f)
        ts = data.get("last_publish_timestamp")
        if ts:
            return datetime.fromisoformat(ts)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt cursor file %s — ignoring", p)
    return None


def save_cursor(type_uid: str, last_ts: datetime, page: int, total_committed: int) -> None:
    p = cursor_path(type_uid)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump({
            "last_publish_timestamp": last_ts.isoformat(),
            "page": page,
            "total_committed": total_committed,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }, f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Diavgeia decisions")
    parser.add_argument("--decision-type-uid", required=True, help="Decision type UID (e.g. Α.2)")
    parser.add_argument("--since", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--until", default=None, help="End date YYYY-MM-DD (default: now)")
    parser.add_argument("--organization-uid", default=None, help="Filter by org UID")
    parser.add_argument("--max-pages", type=int, default=10000, help="Max pages to fetch")
    parser.add_argument("--batch-size", type=int, default=500, help="DB commit batch size")
    parser.add_argument("--resume", action="store_true", help="Resume from last cursor")
    parser.add_argument("--dry-run", action="store_true", help="Count only, no writes")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    since = datetime.strptime(args.since, "%Y-%m-%d")
    until = datetime.strptime(args.until, "%Y-%m-%d") if args.until else datetime.now(timezone.utc)

    # Resume cursor
    if args.resume:
        cursor_ts = load_cursor(args.decision_type_uid)
        if cursor_ts:
            since = cursor_ts
            logger.info("Resuming from cursor: %s", since.isoformat())
        else:
            logger.info("No cursor found — starting from %s", since.isoformat())

    from services.diavgeia_client import DiavgeiaClient, parse_timestamp
    from services.diavgeia_scraper import _resolve_dimos
    from models import DiavgeiaDecision
    from database import AsyncSessionLocal
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    total_fetched = 0
    total_committed = 0
    total_skipped = 0
    batch: list[dict] = []
    last_publish_ts = since
    start_time = time.monotonic()

    logger.info("Backfill: type=%s since=%s until=%s org=%s max_pages=%d batch=%d dry_run=%s",
                args.decision_type_uid, since.date(), until.date() if hasattr(until, 'date') else until,
                args.organization_uid or "ALL", args.max_pages, args.batch_size, args.dry_run)

    async with DiavgeiaClient() as client:
        for page in range(args.max_pages):
            if _shutdown_requested:
                logger.warning("Shutdown requested — flushing batch")
                break

            data = await client.search_decisions(
                decision_type_uid=args.decision_type_uid,
                organization_uid=args.organization_uid,
                published_after=since,
                page=page,
                size=100,
            )
            decisions = data.get("decisions", [])
            if not decisions:
                logger.info("No more decisions on page %d — done", page)
                break

            for raw in decisions:
                ada = raw.get("ada")
                if not ada:
                    total_skipped += 1
                    continue

                publish_ts = parse_timestamp(raw.get("issueDate"))
                if not publish_ts:
                    total_skipped += 1
                    continue

                # Check until boundary
                if hasattr(until, 'timestamp') and publish_ts.replace(tzinfo=None) > until.replace(tzinfo=None):
                    continue

                total_fetched += 1

                if publish_ts > last_publish_ts:
                    last_publish_ts = publish_ts

                if not args.dry_run:
                    org_uid = str(raw.get("organizationId", ""))
                    submission_ts = parse_timestamp(raw.get("submissionTimestamp"))

                    batch.append({
                        "ada": ada,
                        "subject": raw.get("subject", ""),
                        "decision_type_uid": raw.get("decisionTypeId", args.decision_type_uid),
                        "decision_type_label": raw.get("decisionTypeId", ""),
                        "organization_uid": org_uid,
                        "organization_label": str(raw.get("organizationId", "")),
                        "document_url": raw.get("documentUrl", ""),
                        "submission_timestamp": submission_ts,
                        "publish_timestamp": publish_ts,
                        "raw_payload": raw,
                    })

            # Commit batch
            if len(batch) >= args.batch_size:
                async with AsyncSessionLocal() as session:
                    # Resolve dimos for each row
                    for row in batch:
                        dimos_id, periferia_id = await _resolve_dimos(session, row["organization_uid"])
                        row["dimos_id"] = dimos_id
                        row["periferia_id"] = periferia_id

                    stmt = pg_insert(DiavgeiaDecision).values(batch)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["ada"],
                        set_={
                            "subject": stmt.excluded.subject,
                            "decision_type_label": stmt.excluded.decision_type_label,
                            "organization_label": stmt.excluded.organization_label,
                            "document_url": stmt.excluded.document_url,
                            "raw_payload": stmt.excluded.raw_payload,
                            "dimos_id": stmt.excluded.dimos_id,
                            "periferia_id": stmt.excluded.periferia_id,
                            "fetched_at": stmt.excluded.fetched_at,
                        },
                    )
                    await session.execute(stmt)
                    await session.commit()

                total_committed += len(batch)
                save_cursor(args.decision_type_uid, last_publish_ts, page, total_committed)
                batch.clear()

            # Progress log every 100 pages
            if (page + 1) % 100 == 0:
                elapsed = time.monotonic() - start_time
                rate = total_fetched / elapsed if elapsed > 0 else 0
                logger.info("[%s] page %d, fetched %d, committed %d, rate %.1f/s",
                            datetime.now().strftime("%H:%M:%S"), page + 1,
                            total_fetched, total_committed, rate)

    # Flush remaining batch
    if batch and not args.dry_run:
        async with AsyncSessionLocal() as session:
            for row in batch:
                dimos_id, periferia_id = await _resolve_dimos(session, row["organization_uid"])
                row["dimos_id"] = dimos_id
                row["periferia_id"] = periferia_id

            stmt = pg_insert(DiavgeiaDecision).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ada"],
                set_={
                    "subject": stmt.excluded.subject,
                    "decision_type_label": stmt.excluded.decision_type_label,
                    "organization_label": stmt.excluded.organization_label,
                    "document_url": stmt.excluded.document_url,
                    "raw_payload": stmt.excluded.raw_payload,
                    "dimos_id": stmt.excluded.dimos_id,
                    "periferia_id": stmt.excluded.periferia_id,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            await session.execute(stmt)
            await session.commit()
        total_committed += len(batch)
        save_cursor(args.decision_type_uid, last_publish_ts, args.max_pages, total_committed)

    elapsed = time.monotonic() - start_time
    logger.info("=" * 60)
    logger.info("BACKFILL COMPLETE" if not _shutdown_requested else "BACKFILL INTERRUPTED")
    logger.info("  Type:        %s", args.decision_type_uid)
    logger.info("  Range:       %s → %s", args.since, args.until or "now")
    logger.info("  Fetched:     %d", total_fetched)
    logger.info("  Committed:   %d", total_committed)
    logger.info("  Skipped:     %d", total_skipped)
    logger.info("  Dry run:     %s", args.dry_run)
    logger.info("  Duration:    %.1fs", elapsed)
    if total_fetched > 0 and elapsed > 0:
        logger.info("  Rate:        %.1f decisions/s", total_fetched / elapsed)
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
