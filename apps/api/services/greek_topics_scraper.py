"""
Greek News Topics Scraper for Discourse Forum
Fetches RSS feeds from major Greek news outlets, classifies topics,
and auto-creates discussion threads on pnyx.ekklesia.gr.
Deduplication via Redis. Runs every 6 hours via APScheduler.
"""
import os
import logging
import hashlib
import re
from datetime import datetime, timezone
from dataclasses import dataclass

import httpx
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

DISCOURSE_API_KEY = os.getenv("DISCOURSE_API_KEY", "")
DISCOURSE_API_URL = os.getenv("DISCOURSE_API_URL", "https://pnyx.ekklesia.gr")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
GREEK_SCRAPER_ENABLED = os.getenv("GREEK_SCRAPER_ENABLED", "false").lower() == "true"

# RSS Feeds — major Greek news outlets (politics sections)
FEEDS: list[dict] = [
    {"name": "Kathimerini", "url": "https://www.kathimerini.gr/rss/politics", "lang": "el"},
    {"name": "Protothema", "url": "https://www.protothema.gr/feeds/politics.xml", "lang": "el"},
    {"name": "iefimerida", "url": "https://www.iefimerida.gr/rss/politiki", "lang": "el"},
    {"name": "in.gr", "url": "https://www.in.gr/feed/category/politiki/", "lang": "el"},
    {"name": "News247", "url": "https://www.news247.gr/rss/politiki.xml", "lang": "el"},
]

# Category classification keywords → Discourse category
CATEGORY_MAP: dict[str, list[str]] = {
    "Βουλή": ["βουλή", "κοινοβούλιο", "νομοσχέδιο", "ψηφοφορία", "τροπολογία", "ψήφισ", "νομοθεσ"],
    "Κυβέρνηση": ["πρωθυπουργ", "κυβέρνηση", "υπουργ", "μαξίμου", "μέγαρο"],
    "Οικονομία": ["οικονομ", "φόρ", "φορολ", "προϋπολογισμ", "ΑΕΠ", "πληθωρισμ", "μισθ", "σύνταξ"],
    "Εκπαίδευση": ["εκπαίδευσ", "πανεπιστήμ", "σχολεί", "φοιτητ", "δάσκαλ", "εκπαιδευτικ"],
    "Υγεία": ["υγεί", "νοσοκομεί", "ΕΣΥ", "γιατρ", "φάρμακ", "ασθεν"],
    "Τοπική Αυτοδιοίκηση": ["δήμος", "δήμαρχ", "περιφέρει", "δημοτικ", "αυτοδιοίκησ"],
    "Εξωτερική Πολιτική": ["εξωτερικ", "NATO", "ΕΕ", "τουρκ", "κύπρ", "ευρωπαϊκ"],
    "Δικαιοσύνη": ["δικαστ", "δικαιοσύν", "εισαγγελ", "ποιν", "καταδίκ", "αθώ"],
}

# Default Discourse category for uncategorized news
DEFAULT_CATEGORY = "Επικαιρότητα"

# Redis key prefix for dedup
REDIS_PREFIX = "forum:news:"
REDIS_TTL = 86400 * 30  # 30 days dedup window


@dataclass
class NewsItem:
    title: str
    link: str
    description: str
    source: str
    pub_date: str
    category: str = ""


def _article_hash(title: str, link: str) -> str:
    """Generate dedup hash from title + link."""
    raw = f"{title.strip().lower()}|{link.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _classify_topic(title: str, description: str) -> str:
    """Classify news into a Discourse category based on keywords."""
    text = f"{title} {description}".lower()
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_MAP.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[category] = score
    if scores:
        return max(scores, key=scores.get)  # type: ignore
    return DEFAULT_CATEGORY


def _parse_rss_items(xml_text: str, source_name: str) -> list[NewsItem]:
    """Minimal RSS XML parser — no external XML lib needed."""
    items: list[NewsItem] = []
    # Split by <item> tags
    item_blocks = re.findall(r"<item>(.*?)</item>", xml_text, re.DOTALL)
    for block in item_blocks[:10]:  # Max 10 per feed
        title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.DOTALL)
        link_m = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", block, re.DOTALL)
        desc_m = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", block, re.DOTALL)
        pubdate_m = re.search(r"<pubDate>(.*?)</pubDate>", block)

        title = title_m.group(1).strip() if title_m else ""
        link = link_m.group(1).strip() if link_m else ""
        description = desc_m.group(1).strip() if desc_m else ""
        pub_date = pubdate_m.group(1).strip() if pubdate_m else ""

        # Strip HTML tags from description
        description = re.sub(r"<[^>]+>", "", description).strip()[:500]

        if title and link:
            category = _classify_topic(title, description)
            items.append(NewsItem(
                title=title,
                link=link,
                description=description,
                source=source_name,
                pub_date=pub_date,
                category=category,
            ))
    return items


def _discourse_headers() -> dict:
    return {
        "Api-Key": DISCOURSE_API_KEY,
        "Api-Username": os.getenv("DISCOURSE_API_USERNAME", "ekklesia"),
        "Content-Type": "application/json",
    }


async def _get_or_create_category(client: httpx.AsyncClient, name: str, parent_name: str | None = None) -> int:
    """Resolve a Discourse category ID by name, creating if needed."""
    from services.discourse_sync import get_or_create_category
    if parent_name:
        parent_id = await get_or_create_category(parent_name)
        return await get_or_create_category(name, parent_id)
    return await get_or_create_category(name)


async def _create_discourse_topic(client: httpx.AsyncClient, item: NewsItem, category_id: int) -> int | None:
    """Create a Discourse topic for a news item. Returns topic_id or None."""
    body = (
        f"## {item.title}\n\n"
        f"{item.description}\n\n"
        "---\n\n"
        f"**Πηγή:** [{item.source}]({item.link})\n\n"
        f"**Ημερομηνία:** {item.pub_date}\n\n"
        "---\n\n"
        "> 💬 Συζητήστε αυτό το θέμα! Τι πιστεύετε;\n>\n"
        "> Αυτό το θέμα δημιουργήθηκε αυτόματα από τον scraper ειδήσεων.\n"
    )

    r = await client.post(
        f"{DISCOURSE_API_URL}/posts.json",
        json={
            "title": item.title[:255],
            "raw": body,
            "category": category_id,
            "tags": ["news", "auto", item.category.lower().replace(" ", "-")[:20]],
        },
        headers=_discourse_headers(),
    )
    if r.status_code in (200, 201):
        return r.json().get("topic_id")
    logger.warning("Failed to create topic '%s': %s %s", item.title[:50], r.status_code, r.text[:200])
    return None


async def scrape_greek_topics() -> dict:
    """
    Main scraper: fetch RSS feeds, dedup, classify, create Discourse topics.
    Returns stats dict.
    """
    if not GREEK_SCRAPER_ENABLED:
        return {"status": "disabled"}
    if not DISCOURSE_API_KEY:
        logger.warning("[GreekScraper] DISCOURSE_API_KEY not set — skipping")
        return {"status": "no_api_key"}

    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    stats = {"feeds_checked": 0, "items_found": 0, "items_new": 0, "topics_created": 0, "errors": 0}

    async with httpx.AsyncClient(timeout=20) as client:
        all_items: list[NewsItem] = []

        # Fetch all feeds
        for feed in FEEDS:
            try:
                resp = await client.get(feed["url"], follow_redirects=True)
                if resp.status_code != 200:
                    logger.warning("[GreekScraper] %s returned %d", feed["name"], resp.status_code)
                    stats["errors"] += 1
                    continue
                items = _parse_rss_items(resp.text, feed["name"])
                all_items.extend(items)
                stats["feeds_checked"] += 1
            except Exception as e:
                logger.error("[GreekScraper] Failed to fetch %s: %s", feed["name"], e)
                stats["errors"] += 1

        stats["items_found"] = len(all_items)

        # Dedup + create topics
        for item in all_items:
            article_hash = _article_hash(item.title, item.link)
            redis_key = f"{REDIS_PREFIX}{article_hash}"

            # Already posted?
            if await r.exists(redis_key):
                continue

            stats["items_new"] += 1

            try:
                # Resolve category
                if item.category in ("Βουλή", "Κυβέρνηση"):
                    parent = "Πολιτική"
                elif item.category == "Τοπική Αυτοδιοίκηση":
                    parent = "Τοπική Αυτοδιοίκηση"
                else:
                    parent = "Επικαιρότητα"

                category_id = await _get_or_create_category(client, item.category, parent)
                topic_id = await _create_discourse_topic(client, item, category_id)

                if topic_id:
                    # Mark as posted in Redis
                    await r.setex(redis_key, REDIS_TTL, str(topic_id))
                    stats["topics_created"] += 1
                    logger.info("[GreekScraper] Created topic %d: %s", topic_id, item.title[:60])
                else:
                    stats["errors"] += 1
            except Exception as e:
                logger.error("[GreekScraper] Error creating topic for '%s': %s", item.title[:50], e)
                stats["errors"] += 1

    await r.aclose()
    logger.info("[GreekScraper] Done — %d feeds, %d items, %d new, %d created, %d errors",
                stats["feeds_checked"], stats["items_found"], stats["items_new"],
                stats["topics_created"], stats["errors"])
    return stats
