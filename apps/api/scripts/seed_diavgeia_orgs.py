"""
Seed dimos_diavgeia_orgs mapping table by fuzzy-matching Diavgeia organizations
against local dimos records.

Usage:
    cd apps/api && python -m scripts.seed_diavgeia_orgs
"""
import asyncio
import csv
import logging
import sys
import os
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "apps", "api"))

from sqlalchemy import select
from rapidfuzz import fuzz

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REVIEW_CSV_PATH = "/tmp/diavgeia_mapping_review.csv"
MATCH_THRESHOLD = 85


def normalize_greek(text: str) -> str:
    """Strip accents, uppercase, remove 'ΔΗΜΟΣ ' prefix for comparison."""
    # NFD decomposition → remove combining marks → NFC recompose
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    result = stripped.upper().strip()
    for prefix in ("ΔΗΜΟΣ ", "ΔΗΜΟΥ ", "ΔΗΜΟΙ "):
        if result.startswith(prefix):
            result = result[len(prefix):]
    return result


async def main() -> None:
    # Late imports — need sys.path set first
    from database import AsyncSessionLocal
    from models import Dimos, DimosDiavgeiaOrg
    from services.diavgeia_client import DiavgeiaClient

    # 1. Fetch all organizations from Diavgeia
    logger.info("Fetching organizations from Diavgeia...")
    all_orgs: list[dict] = []
    async with DiavgeiaClient() as client:
        page = 0
        while True:
            data = await client.list_organizations(page=page, size=500)
            orgs = data.get("organizations", [])
            if not orgs:
                break
            all_orgs.extend(orgs)
            page += 1
            if len(orgs) < 500:
                break

    logger.info("Fetched %d organizations total", len(all_orgs))

    # 2. Filter municipalities
    municipality_orgs = [o for o in all_orgs if o.get("category") == "MUNICIPALITY"]
    other_orgs = [o for o in all_orgs if o.get("category") != "MUNICIPALITY"]
    logger.info("Municipality orgs: %d, Other orgs: %d", len(municipality_orgs), len(other_orgs))

    # Pre-normalize org labels
    norm_municipality = [(o, normalize_greek(o.get("label", ""))) for o in municipality_orgs]
    norm_other = [(o, normalize_greek(o.get("label", ""))) for o in other_orgs]

    # 3. Load dimoi from DB
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Dimos))
        dimoi = result.scalars().all()

    logger.info("Loaded %d dimoi from database", len(dimoi))

    stats = {"total": len(dimoi), "auto_matched": 0, "needs_review": 0, "unmatched": 0}
    csv_rows: list[dict] = []
    mappings_to_insert: list[dict] = []

    for dimos in dimoi:
        dimos_norm = normalize_greek(dimos.name_el)

        # 3a. Primary match: find best municipality match
        best_score = 0.0
        best_org = None
        candidates: list[tuple[dict, float]] = []

        for org, org_norm in norm_municipality:
            score = fuzz.token_set_ratio(dimos_norm, org_norm) / 100.0
            if score >= MATCH_THRESHOLD / 100.0:
                candidates.append((org, score))
            if score > best_score:
                best_score = score
                best_org = org

        needs_review = False
        if best_org and best_score >= MATCH_THRESHOLD / 100.0:
            tied = [c for c in candidates if abs(c[1] - best_score) < 0.01]
            needs_review = best_score < 0.95 or len(tied) > 1

            mappings_to_insert.append({
                "dimos_id": dimos.id,
                "diavgeia_uid": best_org["uid"],
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

            # 3d. Also auto-link subsidiaries containing the dimos name
            for org, org_norm in norm_other:
                if dimos_norm in org_norm and len(dimos_norm) >= 4:
                    mappings_to_insert.append({
                        "dimos_id": dimos.id,
                        "diavgeia_uid": org["uid"],
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

    # 4. Insert into DB
    async with AsyncSessionLocal() as db:
        for m in mappings_to_insert:
            db.add(DimosDiavgeiaOrg(**m))
        await db.commit()
        logger.info("Inserted %d mapping rows", len(mappings_to_insert))

    # 5. Write review CSV
    with open(REVIEW_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "dimos_id", "dimos_name_el", "matched_org_uid",
            "matched_org_label", "match_confidence", "needs_review",
        ])
        writer.writeheader()
        writer.writerows(csv_rows)

    logger.info("Review CSV written to %s", REVIEW_CSV_PATH)

    # 6. Summary
    logger.info("=" * 50)
    logger.info("SEED SUMMARY")
    logger.info("  Total dimoi:    %d", stats["total"])
    logger.info("  Auto-matched:   %d", stats["auto_matched"])
    logger.info("  Needs review:   %d", stats["needs_review"])
    logger.info("  Unmatched:      %d", stats["unmatched"])
    logger.info("  Total mappings: %d (incl. subsidiaries)", len(mappings_to_insert))
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
