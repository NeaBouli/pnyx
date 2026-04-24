"""
One-time fetch of all Diavgeia organizations → JSON snapshot.
Respects 5s rate limit. Resume-safe via .partial.json temp file.

Usage:
    cd apps/api && python -m scripts.fetch_diavgeia_orgs_snapshot
"""
import asyncio
import gzip
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_PATH = DATA_DIR / "diavgeia_orgs_snapshot.json"
SNAPSHOT_GZ_PATH = DATA_DIR / "diavgeia_orgs_snapshot.json.gz"
PARTIAL_PATH = DATA_DIR / ".diavgeia_orgs_partial.json"
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


async def fetch_all_orgs() -> list[dict]:
    from services.diavgeia_client import DiavgeiaClient

    # Resume from partial if exists
    existing_orgs: list[dict] = []
    start_page = 0
    if PARTIAL_PATH.exists():
        try:
            with open(PARTIAL_PATH, "r", encoding="utf-8") as f:
                partial = json.load(f)
            existing_orgs = partial.get("organizations", [])
            start_page = partial.get("next_page", 0)
            logger.info("Resuming from partial: %d orgs, page %d", len(existing_orgs), start_page)
        except (json.JSONDecodeError, KeyError):
            logger.warning("Corrupt partial file, starting fresh")

    all_orgs = list(existing_orgs)

    async with DiavgeiaClient() as client:
        page = start_page
        while True:
            data = await client.list_organizations(page=page, size=500)
            orgs = data.get("organizations", [])
            if not orgs:
                break

            for org in orgs:
                all_orgs.append({
                    "uid": str(org.get("uid", "")),
                    "label": org.get("label", ""),
                    "category": org.get("category"),
                    "parent_uid": str(org.get("parentUid", "")) if org.get("parentUid") else None,
                    "status": org.get("status", "active"),
                })

            page += 1

            if page % 10 == 0:
                logger.info("Progress: page %d, %d orgs so far", page, len(all_orgs))
                # Save partial for resume
                with open(PARTIAL_PATH, "w", encoding="utf-8") as f:
                    json.dump({"organizations": all_orgs, "next_page": page}, f, ensure_ascii=False)

            if len(orgs) < 500:
                break

    # Cleanup partial
    if PARTIAL_PATH.exists():
        PARTIAL_PATH.unlink()

    return all_orgs


async def main() -> None:
    logger.info("Fetching all Diavgeia organizations...")
    start = time.monotonic()

    orgs = await fetch_all_orgs()
    elapsed = time.monotonic() - start

    snapshot = {
        "metadata": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_count": len(orgs),
            "source_url": "https://diavgeia.gov.gr/luminapi/opendata/organizations.json",
            "api_version_hint": "luminapi-v1",
            "script_version": "1.0",
            "fetch_duration_seconds": round(elapsed, 1),
        },
        "organizations": orgs,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Write JSON first to check size
    raw = json.dumps(snapshot, ensure_ascii=False, indent=1)
    raw_bytes = raw.encode("utf-8")

    if len(raw_bytes) > MAX_SIZE_BYTES:
        logger.info("Snapshot is %d MB — compressing with gzip", len(raw_bytes) // (1024 * 1024))
        with gzip.open(SNAPSHOT_GZ_PATH, "wt", encoding="utf-8") as f:
            f.write(raw)
        final_size = SNAPSHOT_GZ_PATH.stat().st_size
        logger.info("Written to %s (%d KB)", SNAPSHOT_GZ_PATH, final_size // 1024)
        # Remove uncompressed if exists
        if SNAPSHOT_PATH.exists():
            SNAPSHOT_PATH.unlink()
    else:
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            f.write(raw)
        final_size = SNAPSHOT_PATH.stat().st_size
        logger.info("Written to %s (%d KB)", SNAPSHOT_PATH, final_size // 1024)
        # Remove gzip if exists
        if SNAPSHOT_GZ_PATH.exists():
            SNAPSHOT_GZ_PATH.unlink()

    logger.info("=" * 50)
    logger.info("SNAPSHOT COMPLETE")
    logger.info("  Total orgs:      %d", len(orgs))
    logger.info("  Fetch duration:  %.0fs", elapsed)
    logger.info("  File size:       %d KB", final_size // 1024)
    municipality_count = sum(1 for o in orgs if o.get("category") == "MUNICIPALITY")
    logger.info("  Municipalities:  %d", municipality_count)
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
