"""
Discourse Bill Sync Service
Syncs ACTIVE parliament bills to pnyx.ekklesia.gr Discourse forum.
Creates one topic per bill, stores forum_topic_id back in DB.
"""
import os
import logging
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ParliamentBill, BillStatus, Periferia, Dimos

logger = logging.getLogger(__name__)

DISCOURSE_API_KEY = os.getenv("DISCOURSE_API_KEY", "")
DISCOURSE_API_URL = os.getenv("DISCOURSE_API_URL", "https://pnyx.ekklesia.gr")
FORUM_SYNC_ENABLED = os.getenv("FORUM_SYNC_ENABLED", "false").lower() == "true"
FORUM_SYNC_BATCH = int(os.getenv("FORUM_SYNC_BATCH_SIZE", "20"))

_category_cache: dict[str, int] = {}


def _headers() -> dict:
    return {
        "Api-Key": DISCOURSE_API_KEY,
        "Api-Username": "system",
        "Content-Type": "application/json",
    }


async def get_or_create_category(name: str, parent_id: int | None = None) -> int:
    """Get or create a Discourse category by name."""
    cache_key = f"{parent_id}:{name}"
    if cache_key in _category_cache:
        return _category_cache[cache_key]

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{DISCOURSE_API_URL}/categories.json", headers=_headers())
        if r.status_code == 200:
            for cat in r.json().get("category_list", {}).get("categories", []):
                if cat["name"] == name:
                    _category_cache[cache_key] = cat["id"]
                    return cat["id"]

        payload: dict = {"name": name, "color": "2563eb", "text_color": "FFFFFF"}
        if parent_id:
            payload["parent_category_id"] = parent_id

        r = await client.post(
            f"{DISCOURSE_API_URL}/categories.json", json=payload, headers=_headers()
        )
        cat_id = r.json()["category"]["id"]
        _category_cache[cache_key] = cat_id
        return cat_id


async def _resolve_category(bill: ParliamentBill, db: AsyncSession) -> int:
    """Resolve Discourse category based on governance level."""
    gov = bill.governance_level.value if bill.governance_level else "NATIONAL"

    if gov == "NATIONAL":
        # Post into Βουλή → Νομοσχέδια subcategory
        parent = await get_or_create_category("Βουλή")
        return await get_or_create_category("Νομοσχέδια", parent)

    if gov == "REGIONAL" and bill.periferia_id:
        parent = await get_or_create_category("Τοπική Αυτοδιοίκηση")
        periferia = await db.get(Periferia, bill.periferia_id)
        name = f"Περιφέρεια {periferia.name_el}" if periferia else "Περιφέρεια"
        return await get_or_create_category(name, parent)

    if gov == "MUNICIPAL" and bill.dimos_id:
        # Find periferia parent, then create dimos subcategory on-demand
        dimos = await db.get(Dimos, bill.dimos_id)
        if dimos and dimos.periferia_id:
            periferia = await db.get(Periferia, dimos.periferia_id)
            local_parent = await get_or_create_category("Τοπική Αυτοδιοίκηση")
            periferia_cat = await get_or_create_category(
                f"Περιφέρεια {periferia.name_el}" if periferia else "Περιφέρεια",
                local_parent,
            )
            return await get_or_create_category(dimos.name_el, periferia_cat)
        parent = await get_or_create_category("Τοπική Αυτοδιοίκηση")
        return await get_or_create_category("Δήμος", parent)

    parent = await get_or_create_category("Βουλή")
    return await get_or_create_category("Νομοσχέδια", parent)


async def create_discourse_topic(bill: ParliamentBill, db: AsyncSession) -> int:
    """Create a Discourse topic for a bill. Returns topic_id."""
    category_id = await _resolve_category(bill, db)
    ekklesia_url = f"https://ekklesia.gr/el/bills/{bill.id}"

    body = (
        f"## {bill.title_el}\n\n"
        f"{bill.summary_short_el or bill.pill_el or ''}\n\n"
        "---\n\n"
        f"{bill.summary_long_el or ''}\n\n"
        "---\n\n"
        f"> 🗳️ **[Ψηφίστε στο ekklesia.gr →]({ekklesia_url})**\n>\n"
        f"> Κατηγορία: `{bill.governance_level.value if bill.governance_level else 'NATIONAL'}` "
        f"| ID: `{bill.id}`\n"
        "> Αυτό το θέμα δημιουργήθηκε αυτόματα από το σύστημα ekklesia.\n"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DISCOURSE_API_URL}/posts.json",
            json={
                "title": bill.title_el[:255],
                "raw": body,
                "category": category_id,
                "tags": ["ekklesia", (bill.governance_level.value if bill.governance_level else "national").lower()],
            },
            headers=_headers(),
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Discourse API error {r.status_code}: {r.text[:200]}")
        return r.json()["topic_id"]


async def sync_new_bills_to_forum(db: AsyncSession) -> None:
    """
    APScheduler job — every 10 min.
    Finds ACTIVE bills without forum_topic_id → creates Discourse topic.
    Idempotent: forum_topic_id is set after creation.
    """
    if not FORUM_SYNC_ENABLED:
        return
    if not DISCOURSE_API_KEY:
        logger.warning("DISCOURSE_API_KEY not set — skipping forum sync")
        return

    result = await db.execute(
        select(ParliamentBill)
        .where(
            ParliamentBill.status.in_([BillStatus.ACTIVE, BillStatus.WINDOW_24H]),
            ParliamentBill.forum_topic_id.is_(None),
        )
        .limit(FORUM_SYNC_BATCH)
    )
    bills = result.scalars().all()

    if not bills:
        return

    logger.info("Forum sync: %d bills to create", len(bills))

    for bill in bills:
        try:
            topic_id = await create_discourse_topic(bill, db)
            bill.forum_topic_id = topic_id
            await db.commit()
            logger.info("Forum topic %d ← bill %s", topic_id, bill.id)
        except Exception as e:
            logger.error("Forum sync failed for bill %s: %s", bill.id, e)
            await db.rollback()
