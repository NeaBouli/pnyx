"""
One-time fetch of Diavgeia organizations → JSON snapshot.
Includes MUNICIPALITY orgs + their subsidiary entities (ΔΕΥΑ, ΝΠΔΔ, Δημοτικές Επιχειρήσεις).

Two-pass approach:
  Pass 1: Collect MUNICIPALITY orgs (primary)
  Pass 2: Match subsidiaries by label keywords (ΔΗΜΟΤΙΚ*, ΔΗΜΟΥ, ΔΕΥΑ, ΚΟΙΝΟΤΗΤ*, ΣΥΝΔΕΣΜ*, ΟΤΑ)

Usage:
    cd apps/api && python -m scripts.fetch_diavgeia_orgs_snapshot
"""
import asyncio
import json
import logging
import os
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_PATH = DATA_DIR / "diavgeia_orgs_snapshot.json"
PARTIAL_PATH = DATA_DIR / ".diavgeia_orgs_partial.json"

# Keywords that identify municipal subsidiary organizations
MUNICIPAL_KEYWORDS = ["ΔΗΜΟΤΙΚ", "ΔΗΜΟΥ ", "ΔΕΥΑ", "ΚΟΙΝΟΤΗΤ", "ΣΥΝΔΕΣΜ"]
MUNICIPAL_CATEGORIES = {"MUNICIPALITY", "DEYA"}


def _normalize(text: str) -> str:
    """Strip accents, uppercase."""
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return stripped.upper().strip()


def _is_municipal_subsidiary(label_norm: str, category: str) -> tuple[bool, str]:
    """Check if an org is a municipal subsidiary. Returns (is_sub, match_method)."""
    if category in MUNICIPAL_CATEGORIES:
        return True, f"category:{category}"
    for kw in MUNICIPAL_KEYWORDS:
        if kw in label_norm:
            return True, f"label_contains:{kw}"
    return False, ""


async def fetch_all_orgs() -> tuple[list[dict], list[dict]]:
    """Fetch orgs. Returns (municipality_orgs, subsidiary_orgs)."""
    from services.diavgeia_client import DiavgeiaClient

    municipality_orgs: list[dict] = []
    municipality_uids: set[str] = set()
    non_muni_buffer: list[dict] = []

    # Resume from partial if exists
    start_page = 0
    if PARTIAL_PATH.exists():
        try:
            with open(PARTIAL_PATH, "r", encoding="utf-8") as f:
                partial = json.load(f)
            for o in partial.get("municipality_orgs", []):
                municipality_orgs.append(o)
                municipality_uids.add(o["uid"])
            non_muni_buffer = partial.get("non_muni_buffer", [])
            start_page = partial.get("next_page", 0)
            logger.info("Resuming from partial: %d muni, %d buffer, page %d",
                        len(municipality_orgs), len(non_muni_buffer), start_page)
        except (json.JSONDecodeError, KeyError):
            logger.warning("Corrupt partial file, starting fresh")

    async with DiavgeiaClient() as client:
        page = start_page
        while True:
            data = await client.list_organizations(page=page, size=500)
            orgs = data.get("organizations", [])
            if not orgs:
                break

            for org in orgs:
                uid = str(org.get("uid", ""))
                label = org.get("label", "")
                category = org.get("category", "")
                parent_uid = str(org.get("parentUid", "")) if org.get("parentUid") else None

                if category == "MUNICIPALITY":
                    municipality_orgs.append({
                        "uid": uid, "label": label, "category": category,
                        "parent_uid": parent_uid, "status": org.get("status", "active"),
                        "is_primary": True, "match_method": "category",
                    })
                    municipality_uids.add(uid)
                else:
                    non_muni_buffer.append({
                        "uid": uid, "label": label, "category": category,
                        "parent_uid": parent_uid, "status": org.get("status", "active"),
                    })

            page += 1

            if page % 10 == 0:
                logger.info("Progress: page %d, %d muni, %d buffer", page, len(municipality_orgs), len(non_muni_buffer))
                with open(PARTIAL_PATH, "w", encoding="utf-8") as f:
                    json.dump({
                        "municipality_orgs": municipality_orgs,
                        "non_muni_buffer": non_muni_buffer,
                        "next_page": page,
                    }, f, ensure_ascii=False)

            if len(orgs) < 100:
                break

    # Pass 2: find subsidiaries from buffer
    logger.info("Pass 2: scanning %d non-MUNICIPALITY orgs for subsidiaries...", len(non_muni_buffer))
    subsidiary_orgs: list[dict] = []
    seen_uids: set[str] = set(municipality_uids)

    for org in non_muni_buffer:
        uid = org["uid"]
        if uid in seen_uids:
            continue

        label_norm = _normalize(org["label"])
        is_sub, method = _is_municipal_subsidiary(label_norm, org["category"])

        if is_sub:
            org["is_primary"] = False
            org["match_method"] = method
            subsidiary_orgs.append(org)
            seen_uids.add(uid)

    # Cleanup partial
    if PARTIAL_PATH.exists():
        PARTIAL_PATH.unlink()

    # Deduplicate municipalities
    muni_seen: set[str] = set()
    unique_muni: list[dict] = []
    for o in municipality_orgs:
        if o["uid"] not in muni_seen:
            muni_seen.add(o["uid"])
            unique_muni.append(o)

    logger.info("Pass 2 complete: %d municipalities, %d subsidiaries", len(unique_muni), len(subsidiary_orgs))
    return unique_muni, subsidiary_orgs


async def main() -> None:
    logger.info("Fetching Diavgeia organizations (MUNICIPALITY + subsidiaries)...")
    start = time.monotonic()

    muni_orgs, sub_orgs = await fetch_all_orgs()
    elapsed = time.monotonic() - start

    all_orgs = muni_orgs + sub_orgs

    snapshot = {
        "metadata": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_count": len(all_orgs),
            "municipality_count": len(muni_orgs),
            "subsidiary_count": len(sub_orgs),
            "source_url": "https://diavgeia.gov.gr/luminapi/opendata/organizations.json",
            "api_version_hint": "luminapi-v1",
            "script_version": "2.0",
            "fetch_duration_seconds": round(elapsed, 1),
            "filter": "MUNICIPALITY + subsidiaries (ΔΗΜΟΤΙΚ*, ΔΗΜΟΥ, ΔΕΥΑ, ΚΟΙΝΟΤΗΤ*, ΣΥΝΔΕΣΜ*)",
        },
        "organizations": all_orgs,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)

    final_size = SNAPSHOT_PATH.stat().st_size
    logger.info("=" * 50)
    logger.info("SNAPSHOT COMPLETE")
    logger.info("  Municipalities:  %d", len(muni_orgs))
    logger.info("  Subsidiaries:    %d", len(sub_orgs))
    logger.info("  Total:           %d", len(all_orgs))
    logger.info("  File size:       %d KB", final_size // 1024)
    logger.info("  Duration:        %.0fs", elapsed)
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
