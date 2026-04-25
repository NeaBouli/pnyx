"""
Seed dimos_diavgeia_orgs mapping table by fuzzy-matching Diavgeia organizations
against local dimos records.

Default mode: loads from pre-fetched snapshot (< 30s).
Use --refresh-cache to re-fetch from live API first.

Usage:
    cd apps/api && python -m scripts.seed_diavgeia_orgs [OPTIONS]

Options:
    --snapshot PATH              Snapshot file (default: data/diavgeia_orgs_snapshot.json[.gz])
    --refresh-cache              Re-fetch orgs from live API before matching
    --dry-run                    No DB writes, print summary + CSV only
    --stale-days N               Warn if snapshot older than N days (default: 180)
    --confidence-threshold F     Minimum fuzzy score (default: 0.85)
    --output-csv PATH            CSV output path (default: /tmp/diavgeia_mapping_review.csv)
"""
import argparse
import asyncio
import csv
import gzip
import json
import logging
import os
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select
from rapidfuzz import fuzz

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_SNAPSHOT = DATA_DIR / "diavgeia_orgs_snapshot.json"
DEFAULT_SNAPSHOT_GZ = DATA_DIR / "diavgeia_orgs_snapshot.json.gz"


def normalize_greek(text: str) -> str:
    """Strip accents, uppercase, remove 'ΔΗΜΟΣ ' prefix for comparison."""
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    result = stripped.upper().strip()
    for prefix in ("ΔΗΜΟΣ ", "ΔΗΜΟΥ ", "ΔΗΜΟΙ "):
        if result.startswith(prefix):
            result = result[len(prefix):]
    return result


def load_snapshot(path: Path | None) -> dict:
    """Load org snapshot from JSON or gzip file. Returns full snapshot dict."""
    # Resolve path
    if path and path.exists():
        snapshot_path = path
    elif DEFAULT_SNAPSHOT.exists():
        snapshot_path = DEFAULT_SNAPSHOT
    elif DEFAULT_SNAPSHOT_GZ.exists():
        snapshot_path = DEFAULT_SNAPSHOT_GZ
    else:
        raise FileNotFoundError(
            f"Snapshot not found at {DEFAULT_SNAPSHOT} or {DEFAULT_SNAPSHOT_GZ}.\n"
            "Run: python -m scripts.fetch_diavgeia_orgs_snapshot\n"
            "Or use: --refresh-cache to fetch live."
        )

    logger.info("Loading snapshot from %s", snapshot_path)
    if snapshot_path.suffix == ".gz":
        with gzip.open(snapshot_path, "rt", encoding="utf-8") as f:
            data = json.load(f)
    else:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            data = json.load(f)

    # Validate structure
    if "metadata" not in data or "organizations" not in data:
        raise ValueError(f"Malformed snapshot: missing 'metadata' or 'organizations' keys in {snapshot_path}")

    if not isinstance(data["organizations"], list):
        raise ValueError(f"Malformed snapshot: 'organizations' is not a list in {snapshot_path}")

    return data


def check_staleness(metadata: dict, stale_days: int) -> None:
    """Warn if snapshot is older than stale_days."""
    fetched_at_str = metadata.get("fetched_at", "")
    if not fetched_at_str:
        logger.warning("Snapshot has no fetched_at timestamp — cannot check staleness")
        return

    try:
        fetched_at = datetime.fromisoformat(fetched_at_str)
        age_days = (datetime.now(timezone.utc) - fetched_at).days
        if age_days > stale_days:
            logger.warning(
                "Snapshot is %d days old (threshold: %d). Consider --refresh-cache.",
                age_days, stale_days,
            )
        else:
            logger.info("Snapshot age: %d days (threshold: %d) — OK", age_days, stale_days)
    except (ValueError, TypeError):
        logger.warning("Cannot parse fetched_at: %s", fetched_at_str)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed dimos-Diavgeia org mapping")
    parser.add_argument("--snapshot", type=Path, default=None, help="Path to snapshot file")
    parser.add_argument("--refresh-cache", action="store_true", help="Re-fetch from live API first")
    parser.add_argument("--dry-run", action="store_true", help="No DB writes")
    parser.add_argument("--stale-days", type=int, default=180, help="Warn if snapshot older than N days")
    parser.add_argument("--confidence-threshold", type=float, default=0.85, help="Min fuzzy match score")
    parser.add_argument("--output-csv", type=str, default="/tmp/diavgeia_mapping_review.csv", help="CSV output")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    # Refresh cache if requested
    if args.refresh_cache:
        logger.info("Refreshing org cache from live API...")
        from scripts.fetch_diavgeia_orgs_snapshot import main as fetch_main
        await fetch_main()
        logger.info("Cache refreshed. Proceeding with matching.")

    # Load orgs from snapshot
    start = time.monotonic()
    snapshot = load_snapshot(args.snapshot)
    check_staleness(snapshot["metadata"], args.stale_days)

    all_orgs = snapshot["organizations"]
    logger.info("Loaded %d organizations from snapshot", len(all_orgs))

    # Split into primary (MUNICIPALITY) and subsidiary orgs
    municipality_orgs = [o for o in all_orgs if o.get("is_primary", False) or o.get("category") == "MUNICIPALITY"]
    subsidiary_orgs = [o for o in all_orgs if not (o.get("is_primary", False) or o.get("category") == "MUNICIPALITY")]
    logger.info("Municipality orgs: %d, Subsidiary orgs: %d", len(municipality_orgs), len(subsidiary_orgs))

    # Pre-normalize org labels
    norm_municipality = [(o, normalize_greek(o.get("label", ""))) for o in municipality_orgs]
    norm_subsidiary = [(o, normalize_greek(o.get("label", ""))) for o in subsidiary_orgs]

    # Load dimoi from DB
    from database import AsyncSessionLocal
    from models import Dimos, DimosDiavgeiaOrg

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Dimos))
        dimoi = result.scalars().all()

    logger.info("Loaded %d dimoi from database", len(dimoi))

    threshold = args.confidence_threshold
    stats = {"total": len(dimoi), "auto_matched": 0, "needs_review": 0, "unmatched": 0}
    csv_rows: list[dict] = []
    mappings_to_insert: list[dict] = []

    for dimos in dimoi:
        dimos_norm = normalize_greek(dimos.name_el)
        best_score = 0.0
        best_org = None
        candidates: list[tuple[dict, float]] = []

        for org, org_norm in norm_municipality:
            score = fuzz.token_set_ratio(dimos_norm, org_norm) / 100.0
            if score >= threshold:
                candidates.append((org, score))
            if score > best_score:
                best_score = score
                best_org = org

        needs_review = False
        if best_org and best_score >= threshold:
            tied = [c for c in candidates if abs(c[1] - best_score) < 0.01]
            needs_review = best_score < 0.95 or len(tied) > 1

            mappings_to_insert.append({
                "dimos_id": dimos.id,
                "diavgeia_uid": str(best_org["uid"]),
                "org_label": best_org.get("label", ""),
                "org_category": "MUNICIPALITY",
                "is_primary": True,
                "match_confidence": round(best_score, 3),
            })

            csv_rows.append({
                "dimos_id": dimos.id,
                "dimos_name_el": dimos.name_el,
                "matched_org_uid": best_org["uid"],
                "matched_org_label": best_org.get("label", ""),
                "match_confidence": f"{best_score:.3f}",
                "needs_review": "TRUE" if needs_review else "FALSE",
            })

            if needs_review:
                stats["needs_review"] += 1
            else:
                stats["auto_matched"] += 1

            # Auto-link subsidiaries containing the dimos name
            for org, org_norm in norm_subsidiary:
                if dimos_norm in org_norm and len(dimos_norm) >= 4:
                    mappings_to_insert.append({
                        "dimos_id": dimos.id,
                        "diavgeia_uid": str(org["uid"]),
                        "org_label": org.get("label", ""),
                        "org_category": org.get("category", ""),
                        "is_primary": False,
                        "match_confidence": None,
                    })
        else:
            stats["unmatched"] += 1
            csv_rows.append({
                "dimos_id": dimos.id,
                "dimos_name_el": dimos.name_el,
                "matched_org_uid": "",
                "matched_org_label": "",
                "match_confidence": f"{best_score:.3f}" if best_org else "0.000",
                "needs_review": "TRUE",
            })

    # Write to DB (unless dry-run)
    if not args.dry_run:
        async with AsyncSessionLocal() as db:
            for m in mappings_to_insert:
                db.add(DimosDiavgeiaOrg(**m))
            await db.commit()
            logger.info("Inserted %d mapping rows", len(mappings_to_insert))
    else:
        logger.info("[DRY RUN] Would insert %d mapping rows", len(mappings_to_insert))

    # Write review CSV
    with open(args.output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "dimos_id", "dimos_name_el", "matched_org_uid",
            "matched_org_label", "match_confidence", "needs_review",
        ])
        writer.writeheader()
        writer.writerows(csv_rows)

    elapsed = time.monotonic() - start
    logger.info("Review CSV written to %s", args.output_csv)
    logger.info("=" * 50)
    logger.info("SEED SUMMARY (%.1fs)", elapsed)
    logger.info("  Total dimoi:    %d", stats["total"])
    logger.info("  Auto-matched:   %d", stats["auto_matched"])
    logger.info("  Needs review:   %d", stats["needs_review"])
    logger.info("  Unmatched:      %d", stats["unmatched"])
    logger.info("  Total mappings: %d (incl. subsidiaries)", len(mappings_to_insert))
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
