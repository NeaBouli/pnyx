"""
Discourse Bill Sync Service
Syncs ACTIVE parliament bills to pnyx.ekklesia.gr Discourse forum.
Creates one topic per bill, stores forum_topic_id back in DB.
"""
import os
import re
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
        "Api-Username": os.getenv("DISCOURSE_API_USERNAME", "ekklesia"),
        "Content-Type": "application/json",
    }


async def get_or_create_category(name: str, parent_id: int | None = None) -> int:
    """Get or create a Discourse category by name. Searches all categories incl. subcategories."""
    cache_key = f"{parent_id}:{name}"
    if cache_key in _category_cache:
        return _category_cache[cache_key]

    async with httpx.AsyncClient(timeout=15) as client:
        # Fetch all categories including subcategories
        r = await client.get(
            f"{DISCOURSE_API_URL}/categories.json",
            params={"include_subcategories": "true"},
            headers=_headers(),
        )
        if r.status_code == 200:
            data = r.json().get("category_list", {}).get("categories", [])
            for cat in data:
                if cat["name"] == name and (parent_id is None or cat.get("parent_category_id") == parent_id):
                    _category_cache[cache_key] = cat["id"]
                    return cat["id"]
                # Check subcategories
                for sub in cat.get("subcategory_ids", []):
                    pass  # IDs only, need name match from top-level
                for sub in cat.get("subcategory_list", []):
                    if sub["name"] == name and (parent_id is None or sub.get("parent_category_id") == parent_id):
                        _category_cache[cache_key] = sub["id"]
                        return sub["id"]

        # Not found — create
        payload: dict = {"name": name, "color": "2563eb", "text_color": "FFFFFF"}
        if parent_id:
            payload["parent_category_id"] = parent_id

        r = await client.post(
            f"{DISCOURSE_API_URL}/categories.json", json=payload, headers=_headers()
        )
        resp = r.json()
        if "category" in resp:
            cat_id = resp["category"]["id"]
            _category_cache[cache_key] = cat_id
            return cat_id

        # Category might already exist (race condition or name conflict)
        logger.warning("Could not create category %s: %s", name, r.text[:200])
        raise RuntimeError(f"Failed to get/create category '{name}'")


async def _resolve_category(bill: ParliamentBill, db: AsyncSession) -> int:
    """Resolve Discourse category based on governance level + source."""
    gov = bill.governance_level.value if bill.governance_level else "NATIONAL"
    source = getattr(bill, "source", "PARLIAMENT") or "PARLIAMENT"

    # Diavgeia: route by governance level
    if source == "DIAVGEIA":
        parent = await get_or_create_category("Διαύγεια")
        if gov == "INSTITUTIONAL":
            return await get_or_create_category("Φορείς & Οργανισμοί", parent)
        if gov == "NATIONAL":
            return await get_or_create_category("Κεντρική Διοίκηση", parent)
        if gov == "REGIONAL":
            return await get_or_create_category("Περιφέρειες", parent)
        if gov == "MUNICIPAL":
            return await get_or_create_category("Δήμοι", parent)
        return await get_or_create_category("Άλλα", parent)

    if gov == "NATIONAL":
        parent = await get_or_create_category("Βουλή")
        return await get_or_create_category("Νομοσχέδια", parent)

    # Local governance: max 2 levels (Discourse limit)
    if gov == "REGIONAL" and bill.periferia_id:
        parent = await get_or_create_category("Τοπική Αυτοδιοίκηση")
        periferia = await db.get(Periferia, bill.periferia_id)
        name = f"Περιφέρεια {periferia.name_el}" if periferia else "Περιφέρεια"
        return await get_or_create_category(name, parent)

    if gov == "MUNICIPAL" and bill.dimos_id:
        # Flat: Τοπική Αυτοδιοίκηση → Δήμος X (no 3rd level via Periferia)
        parent = await get_or_create_category("Τοπική Αυτοδιοίκηση")
        dimos = await db.get(Dimos, bill.dimos_id)
        name = f"Δήμος {dimos.name_el}" if dimos else "Δήμος"
        return await get_or_create_category(name, parent)

    parent = await get_or_create_category("Βουλή")
    return await get_or_create_category("Νομοσχέδια", parent)


def _build_topic_body(bill: ParliamentBill) -> str:
    """Build the Discourse topic body for a bill."""
    ekklesia_url = f"https://ekklesia.gr/el/bills/{bill.id}"

    status_labels = {
        "ANNOUNCED": "📋 Ανακοινώθηκε",
        "ACTIVE": "🗳️ Ενεργή Ψηφοφορία",
        "WINDOW_24H": "⏰ Τελευταίες 24 ώρες",
        "PARLIAMENT_VOTED": "🏛️ Ψηφίστηκε στη Βουλή",
        "OPEN_END": "♾️ Ανοιχτή Ψηφοφορία",
    }
    status_val = bill.status.value if bill.status else "ACTIVE"
    status_badge = status_labels.get(status_val, f"📌 {status_val}")

    gov_labels = {
        "NATIONAL": "🇬🇷 Εθνικό",
        "REGIONAL": "🏛️ Περιφερειακό",
        "MUNICIPAL": "🏘️ Δημοτικό",
        "INSTITUTIONAL": "🏫 Φορέας/Οργανισμός",
    }
    gov_val = bill.governance_level.value if bill.governance_level else "NATIONAL"
    gov_label = gov_labels.get(gov_val, gov_val)

    source = getattr(bill, "source", "PARLIAMENT") or "PARLIAMENT"
    source_badge = "📜 ΒΟΥΛΗ" if source == "PARLIAMENT" else "📋 ΔΙΑΥΓΕΙΑ"

    summary = bill.summary_short_el or bill.pill_el or ""
    long_text = bill.summary_long_el or ""

    # Strip navigation/boilerplate lines scraped from parliament site
    def _clean(text: str) -> str:
        lines = text.split("\n")
        cleaned = [l for l in lines if not re.match(r"^\*?\s*\[.+\]\(https?://", l.strip())
                   and "Μετάβαση στο κύριο" not in l
                   and "προσβασιμότητας" not in l]
        return "\n".join(cleaned).strip()
    summary = _clean(summary)
    long_text = _clean(long_text)

    body = (
        f"# {bill.title_el}\n\n"
        f"| | |\n|---|---|\n"
        f"| **Κατάσταση** | {status_badge} |\n"
        f"| **Πηγή** | {source_badge} |\n"
        f"| **Επίπεδο** | {gov_label} |\n"
        f"| **ID** | `{bill.id}` |\n\n"
        "---\n\n"
    )
    if summary:
        body += f"## Περίληψη\n{summary}\n\n"
    elif source == "DIAVGEIA":
        body += "## Περίληψη\n*Η AI σύνοψη θα είναι σύντομα διαθέσιμη.*\n\n"
    if long_text:
        body += f"## Ανάλυση\n{long_text}\n\n"

    # CTA depends on status
    if status_val == "OPEN_END":
        body += (
            "---\n\n"
            f"### ⚖️ [Αξιολογήστε στο ekklesia.gr →]({ekklesia_url})\n\n"
            "> Χρησιμοποιήστε την κλίμακα συναίνεσης (-5 έως +5) για να εκφράσετε τη γνώμη σας.\n\n"
        )
    else:
        body += (
            "---\n\n"
            f"### 🗳️ [Ψηφίστε τώρα στο ekklesia.gr →]({ekklesia_url})\n\n"
            "> Κατεβάστε την εφαρμογή ekklesia για να ψηφίσετε ανώνυμα.\n"
            "> Η ψήφος σας είναι κρυπτογραφημένη (Ed25519) — κανείς δεν γνωρίζει τι ψηφίσατε.\n\n"
        )
    body += "*Αυτό το θέμα δημιουργήθηκε αυτόματα από το σύστημα ekklesia.*\n"
    return body


def _build_topic_tags(bill: ParliamentBill) -> list[str]:
    return [
        "ekklesia",
        (bill.governance_level.value if bill.governance_level else "national").lower(),
        (getattr(bill, "source", "PARLIAMENT") or "PARLIAMENT").lower(),
        bill.status.value.lower().replace("_", "-") if bill.status else "active",
    ]


async def create_discourse_topic(bill: ParliamentBill, db: AsyncSession) -> int:
    """Create a Discourse topic for a bill. Returns topic_id."""
    category_id = await _resolve_category(bill, db)
    body = _build_topic_body(bill)
    tags = _build_topic_tags(bill)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DISCOURSE_API_URL}/posts.json",
            json={
                "title": bill.title_el[:255],
                "raw": body,
                "category": category_id,
                "tags": tags,
            },
            headers=_headers(),
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Discourse API error {r.status_code}: {r.text[:200]}")
        return r.json()["topic_id"]


async def update_discourse_topic(bill: ParliamentBill, db: AsyncSession) -> bool:
    """Update existing Discourse topic: category + tags + first post body."""
    if not bill.forum_topic_id or not DISCOURSE_API_KEY:
        return False

    try:
        category_id = await _resolve_category(bill, db)
        tags = _build_topic_tags(bill)
        body = _build_topic_body(bill)

        async with httpx.AsyncClient(timeout=15) as client:
            # Update topic category + tags
            r = await client.put(
                f"{DISCOURSE_API_URL}/t/-/{bill.forum_topic_id}.json",
                json={"category_id": category_id, "tags": tags},
                headers=_headers(),
            )
            if r.status_code != 200:
                logger.warning("Topic update failed for %s: HTTP %d", bill.id, r.status_code)
                return False

            # Get first post ID
            t = await client.get(
                f"{DISCOURSE_API_URL}/t/{bill.forum_topic_id}.json",
                headers=_headers(),
            )
            if t.status_code == 200:
                posts = t.json().get("post_stream", {}).get("posts", [])
                if posts:
                    post_id = posts[0]["id"]
                    # Update first post body
                    await client.put(
                        f"{DISCOURSE_API_URL}/posts/{post_id}.json",
                        json={"post": {"raw": body}},
                        headers=_headers(),
                    )

            logger.info("Updated topic %d for bill %s (cat+tags+body)",
                        bill.forum_topic_id, bill.id)
            return True
    except Exception as e:
        logger.error("Topic update error for %s: %s", bill.id, e)
    return False


async def resync_all_topics(db: AsyncSession) -> dict:
    """Re-categorize and re-tag ALL existing forum topics."""
    result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.forum_topic_id.isnot(None))
    )
    bills = result.scalars().all()
    updated = 0
    failed = 0

    for bill in bills:
        ok = await update_discourse_topic(bill, db)
        if ok:
            updated += 1
        else:
            failed += 1

    return {"total": len(bills), "updated": updated, "failed": failed}


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
            ParliamentBill.status.in_([
                BillStatus.ACTIVE, BillStatus.WINDOW_24H,
                BillStatus.ANNOUNCED, BillStatus.OPEN_END,
                BillStatus.PARLIAMENT_VOTED,
            ]),
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
            # Refresh to prevent greenlet_spawn errors after prior commit/rollback
            await db.refresh(bill)
            topic_id = await create_discourse_topic(bill, db)
            bill.forum_topic_id = topic_id
            await db.commit()
            logger.info("Forum topic %d ← bill %s", topic_id, bill.id)
        except Exception as e:
            logger.error("Forum sync failed for bill %s: %s", bill.id, e)
            await db.rollback()
