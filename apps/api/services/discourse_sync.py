"""
Discourse Bill Sync Service
Syncs ACTIVE parliament bills to pnyx.ekklesia.gr Discourse forum.
Creates one topic per bill, stores forum_topic_id back in DB.
"""
import os
import re
import asyncio
import logging
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ParliamentBill, BillStatus, Periferia, Dimos
from services.bill_visibility import public_bill_filter
from services.source_links import official_source_url

logger = logging.getLogger(__name__)

DISCOURSE_API_KEY = os.getenv("DISCOURSE_API_KEY", "")
DISCOURSE_API_URL = os.getenv("DISCOURSE_API_URL", "https://pnyx.ekklesia.gr")
FORUM_SYNC_ENABLED = os.getenv("FORUM_SYNC_ENABLED", "false").lower() == "true"
FORUM_SYNC_BATCH = int(os.getenv("FORUM_SYNC_BATCH_SIZE", "20"))
FORUM_SYNC_TOPIC_DELAY_SECONDS = float(os.getenv("FORUM_SYNC_TOPIC_DELAY_SECONDS", "8"))
DISCOURSE_RATE_LIMIT_RETRIES = int(os.getenv("DISCOURSE_RATE_LIMIT_RETRIES", "3"))

_category_cache: dict[str, int] = {}


def _headers() -> dict:
    return {
        "Api-Key": DISCOURSE_API_KEY,
        "Api-Username": os.getenv("DISCOURSE_API_USERNAME", "ekklesia"),
        "Content-Type": "application/json",
    }


def _discourse_rate_limit_wait(response: httpx.Response) -> float | None:
    """Return Discourse rate-limit wait seconds when present."""
    if response.status_code != 429:
        return None
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), 1.0)
        except ValueError:
            pass
    try:
        wait = response.json().get("extras", {}).get("wait_seconds")
        if wait is not None:
            return max(float(wait), 1.0)
    except Exception:
        pass
    match = re.search(r'"wait_seconds"\s*:\s*(\d+)', response.text or "")
    if match:
        return max(float(match.group(1)), 1.0)
    return 10.0


async def _request_discourse(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
    """Call Discourse, respecting 429 wait_seconds before retrying."""
    request = getattr(client, method.lower())
    last_response = None
    for attempt in range(DISCOURSE_RATE_LIMIT_RETRIES + 1):
        response = await request(url, **kwargs)
        wait_seconds = _discourse_rate_limit_wait(response)
        if wait_seconds is None:
            return response
        last_response = response
        if attempt >= DISCOURSE_RATE_LIMIT_RETRIES:
            return response
        sleep_for = wait_seconds + 1.0
        logger.warning("Discourse rate limited (%s %s). Sleeping %.1fs before retry %d/%d",
                       method.upper(), url, sleep_for, attempt + 1, DISCOURSE_RATE_LIMIT_RETRIES)
        await asyncio.sleep(sleep_for)
    assert last_response is not None
    return last_response


async def get_or_create_category(name: str, parent_id: int | None = None) -> int:
    """Get or create a Discourse category by name. Searches all categories incl. subcategories."""
    cache_key = f"{parent_id}:{name}"
    if cache_key in _category_cache:
        return _category_cache[cache_key]

    async with httpx.AsyncClient(timeout=15) as client:
        # Fetch all categories including subcategories
        r = await _request_discourse(client, "get",
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

        r = await _request_discourse(client, "post",
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


async def _build_topic_title(bill: ParliamentBill, db: AsyncSession) -> str:
    """Build topic title with region prefix. Never returns 'unknown'."""
    gov = bill.governance_level.value if bill.governance_level else "NATIONAL"
    source = getattr(bill, "source", "PARLIAMENT") or "PARLIAMENT"

    # Derive a safe title — never unknown
    title = bill.title_el
    if not title or title.strip() == "":
        title = (
            bill.summary_short_el.split(".")[0] if bill.summary_short_el else
            f"Απόφαση Διαύγειας — ΑΔΑ {bill.diavgeia_ada}" if getattr(bill, "diavgeia_ada", None) else
            f"Νομοσχέδιο {bill.id}"
        )

    # Region prefix
    if source == "PARLIAMENT" or gov == "NATIONAL":
        prefix = "Βουλή"
    elif gov == "REGIONAL" and bill.periferia_id:
        periferia = await db.get(Periferia, bill.periferia_id)
        prefix = f"Περιφέρεια {periferia.name_el}" if periferia else "Περιφέρεια"
    elif gov == "MUNICIPAL" and bill.dimos_id:
        dimos = await db.get(Dimos, bill.dimos_id)
        prefix = f"Δήμος {dimos.name_el}" if dimos else "Δήμος"
    elif gov == "INSTITUTIONAL":
        org = getattr(bill, "org_label", None) or ""
        org = org.strip()
        if not org or org.lower() == "unknown" or org.startswith("[unknown:"):
            prefix = "Φορέας"
        else:
            prefix = f"Φορέας {org}"
    else:
        prefix = "Διαύγεια" if source == "DIAVGEIA" else "Βουλή"

    formatted = f"[{prefix}] {title}"
    return formatted[:255]


def _build_topic_body(bill: ParliamentBill, region_name: str = "") -> str:
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

    def _is_bad_summary(val: str | None) -> bool:
        if not val or not val.strip():
            return True
        lower = val.lower()
        if "unknown" in lower:
            return True
        bad_parliament_markers = (
            "Μετάβαση στο κύριο περιεχόμενο",
            "Ενεργοποίηση προσβασιμότητας",
            "Νομοθετική Διαδικασία",
            "Εμφανίζονται τα ψηφισθέντα",
            "Εμφανίζονται τα σχέδια",
        )
        if any(marker in val for marker in bad_parliament_markers):
            return True
        if re.match(r"^διαύγεια:\s*\[", val, re.IGNORECASE):
            return True
        if re.match(r"^διαύγεια:\s*\S+$", val, re.IGNORECASE) and len(val) < 80:
            return True  # Just "Διαύγεια: ORG_NAME" — not a real summary
        return False

    # Strip navigation/boilerplate/parliament links from scraped content
    def _clean(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\[([^\]]*)\]\(https?://[^\)]*hellenicparliament[^\)]*\)", r"\1", text)
        text = re.sub(r"https?://\S*hellenicparliament\S*", "", text)
        lines = text.split("\n")
        cleaned = [l for l in lines
                   if "Μετάβαση στο κύριο" not in l
                   and "προσβασιμότητας" not in l
                   and "Cookies" not in l
                   and not re.match(r"^\s*\*?\s*\[Αρχική\]", l.strip())]
        return "\n".join(cleaned).strip()

    def _clean_official_text(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        lines = text.split("\n")
        cleaned = [l for l in lines
                   if "Μετάβαση στο κύριο" not in l
                   and "προσβασιμότητας" not in l
                   and "Cookies" not in l
                   and not re.match(r"^\s*\*?\s*\[Αρχική\]", l.strip())]
        return "\n".join(cleaned).strip()

    # Build clean summary — never unknown
    summary = ""
    summary_candidates = [bill.summary_short_el, bill.pill_el]
    if source != "PARLIAMENT":
        summary_candidates.append(bill.summary_long_el)
    for candidate in summary_candidates:
        if candidate and not _is_bad_summary(candidate):
            summary = _clean(candidate)
            if summary:
                break

    analysis = ""
    analysis_el = getattr(bill, "analysis_el", None)
    if analysis_el and not _is_bad_summary(analysis_el):
        analysis = _clean(analysis_el)

    official_excerpt = ""
    if source == "PARLIAMENT" and bill.summary_long_el and not _is_bad_summary(bill.summary_long_el):
        official_excerpt = _clean_official_text(bill.summary_long_el)

    diavgeia_document_url = ""
    if source == "DIAVGEIA":
        candidate_url = (getattr(bill, "parliament_url", None) or "").strip()
        if candidate_url.startswith("https://diavgeia.gov.gr/doc/"):
            diavgeia_document_url = candidate_url

    # Safe title for body heading
    title = bill.title_el or f"Απόφαση {bill.id}"

    # Metadata block
    body = f"# {title}\n\n"
    body += "| | |\n|---|---|\n"
    body += f"| **Πηγή** | {source_badge} |\n"
    body += f"| **Επίπεδο** | {gov_label} |\n"
    if region_name:
        body += f"| **Περιοχή** | {region_name} |\n"
    if source == "DIAVGEIA" and getattr(bill, "diavgeia_ada", None):
        body += f"| **ΑΔΑ** | [{bill.diavgeia_ada}](https://diavgeia.gov.gr/decision/view/{bill.diavgeia_ada}) |\n"
    body += f"| **Κατάσταση** | {status_badge} |\n"
    body += f"| **ID** | `{bill.id}` |\n\n"
    body += "---\n\n"

    # Content fallback: summary → analysis_el → reviewed official excerpt → diavgeia ADA → title+link
    if summary:
        body += f"## Περίληψη\n{summary}\n\n"
    if analysis:
        body += f"## Ανάλυση\n{analysis}\n\n"
    if official_excerpt:
        body += f"## Επίσημο κείμενο και έγγραφα\n{official_excerpt}\n\n"
    if diavgeia_document_url:
        body += (
            "## Πλήρες έγγραφο\n"
            f"[Κατεβάστε/διαβάστε την απόφαση στη Διαύγεια →]({diavgeia_document_url})\n\n"
        )
    if not summary and not analysis and not official_excerpt:
        if source == "DIAVGEIA" and getattr(bill, "diavgeia_ada", None):
            body += (
                f"## Πληροφορίες\n"
                f"**Διαύγεια ADA:** {bill.diavgeia_ada}\n\n"
                f"[Δείτε την απόφαση στη Διαύγεια →](https://diavgeia.gov.gr/decision/view/{bill.diavgeia_ada})\n\n"
            )
        elif official_source_url(bill):
            body += (
                f"## Πληροφορίες\n"
                f"[Δείτε το νομοσχέδιο στη Βουλή →]({official_source_url(bill)})\n\n"
            )
        else:
            body += f"## Πληροφορίες\n*Δεν υπάρχει περίληψη ακόμα. Ψηφίστε στο ekklesia.gr.*\n\n"

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
    tags = [
        "ekklesia",
        (bill.governance_level.value if bill.governance_level else "national").lower(),
        (getattr(bill, "source", "PARLIAMENT") or "PARLIAMENT").lower(),
        bill.status.value.lower().replace("_", "-") if bill.status else "active",
    ]
    if bill.periferia_id:
        tags.append(f"periferia-{bill.periferia_id}")
    if bill.dimos_id:
        tags.append(f"dimos-{bill.dimos_id}")
    return tags


def _with_unique_title_suffix(title: str, bill: ParliamentBill) -> str:
    """Append a stable suffix for Discourse duplicate-title fallback."""
    suffix_source = getattr(bill, "diavgeia_ada", None) or bill.id
    suffix = f" — {suffix_source}"
    if title.endswith(suffix):
        return title
    return f"{title[:255 - len(suffix)]}{suffix}"


async def _search_existing_topic(title: str) -> int | None:
    """Search Discourse for an existing topic by title. Returns topic_id or None."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await _request_discourse(client, "get",
                f"{DISCOURSE_API_URL}/search.json",
                params={"q": f'title:"{title[:100]}"'},
                headers=_headers(),
            )
            if r.status_code == 200:
                topics = r.json().get("topics", [])
                if topics:
                    return topics[0]["id"]
    except Exception as e:
        logger.warning("Discourse topic search failed: %s", e)
    return None


async def _region_name_for_body(bill: ParliamentBill, db: AsyncSession) -> str:
    """Build region name string for topic body metadata."""
    gov = bill.governance_level.value if bill.governance_level else "NATIONAL"
    parts = []
    if bill.dimos_id:
        dimos = await db.get(Dimos, bill.dimos_id)
        if dimos:
            parts.append(f"Δήμος {dimos.name_el}")
    if bill.periferia_id:
        periferia = await db.get(Periferia, bill.periferia_id)
        if periferia:
            parts.append(f"Περιφέρεια {periferia.name_el}")
    return ", ".join(parts)


async def create_discourse_topic(bill: ParliamentBill, db: AsyncSession) -> int:
    """Create a Discourse topic for a bill. Returns topic_id."""
    category_id = await _resolve_category(bill, db)
    topic_title = await _build_topic_title(bill, db)
    region_name = await _region_name_for_body(bill, db)
    body = _build_topic_body(bill, region_name=region_name)
    tags = _build_topic_tags(bill)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await _request_discourse(client, "post",
            f"{DISCOURSE_API_URL}/posts.json",
            json={
                "title": topic_title,
                "raw": body,
                "category": category_id,
                "tags": tags,
            },
            headers=_headers(),
        )
        if r.status_code in (200, 201):
            return r.json()["topic_id"]

        # Title already exists — search for existing topic and link it
        if r.status_code == 422 and "χρησιμοποιηθεί" in r.text:
            logger.info("Topic title already exists for %s — searching Discourse", bill.id)
            # Search with new prefixed title first, then raw title
            existing_id = await _search_existing_topic(topic_title)
            if not existing_id and bill.title_el:
                existing_id = await _search_existing_topic(bill.title_el)
            if existing_id:
                logger.info("Found existing topic %d for bill %s", existing_id, bill.id)
                return existing_id
            logger.warning("Title duplicate but search found nothing for %s", bill.id)

            fallback_title = _with_unique_title_suffix(topic_title, bill)
            retry = await _request_discourse(client, "post",
                f"{DISCOURSE_API_URL}/posts.json",
                json={
                    "title": fallback_title,
                    "raw": body,
                    "category": category_id,
                    "tags": tags,
                },
                headers=_headers(),
            )
            if retry.status_code in (200, 201):
                logger.info("Created topic with fallback title for bill %s", bill.id)
                return retry.json()["topic_id"]

        raise RuntimeError(f"Discourse API error {r.status_code}: {r.text[:200]}")


async def update_discourse_topic(bill: ParliamentBill, db: AsyncSession) -> bool:
    """Update existing Discourse topic: category + tags + first post body."""
    if not bill.forum_topic_id or not DISCOURSE_API_KEY:
        return False

    try:
        category_id = await _resolve_category(bill, db)
        tags = _build_topic_tags(bill)
        region_name = await _region_name_for_body(bill, db)
        body = _build_topic_body(bill, region_name=region_name)
        topic_title = await _build_topic_title(bill, db)

        async with httpx.AsyncClient(timeout=15) as client:
            # Update topic category + tags + title
            r = await _request_discourse(client, "put",
                f"{DISCOURSE_API_URL}/t/-/{bill.forum_topic_id}.json",
                json={"category_id": category_id, "tags": tags, "title": topic_title},
                headers=_headers(),
            )
            if r.status_code != 200:
                logger.warning("Topic update failed for %s: HTTP %d", bill.id, r.status_code)
                return False

            # Get first post ID
            t = await _request_discourse(client, "get",
                f"{DISCOURSE_API_URL}/t/{bill.forum_topic_id}.json",
                headers=_headers(),
            )
            if t.status_code == 200:
                posts = t.json().get("post_stream", {}).get("posts", [])
                if posts:
                    post_id = posts[0]["id"]
                    # Update first post body
                    await _request_discourse(client, "put",
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
    """Re-categorize and re-tag ALL existing forum topics. Rate-limited to ~10/min."""
    import asyncio
    result = await db.execute(
        select(ParliamentBill).where(
            ParliamentBill.forum_topic_id.isnot(None),
            public_bill_filter(),
        )
    )
    bills = result.scalars().all()
    updated = 0
    failed = 0

    for i, bill in enumerate(bills):
        ok = await update_discourse_topic(bill, db)
        if ok:
            updated += 1
        else:
            failed += 1
        # Discourse rate limit: ~20 req/min, but update does 3 calls per topic
        if (i + 1) % 5 == 0:
            await asyncio.sleep(15)

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
            public_bill_filter(),
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
            if FORUM_SYNC_TOPIC_DELAY_SECONDS > 0:
                await asyncio.sleep(FORUM_SYNC_TOPIC_DELAY_SECONDS)
        except Exception as e:
            logger.error("Forum sync failed for bill %s: %s", bill.id, e)
            await db.rollback()
