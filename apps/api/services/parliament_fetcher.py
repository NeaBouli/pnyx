"""
Parliament Bill Text Fetcher — 3-Kanal Pipeline (NEA-199 Ultimativ)

Kanal 1: Jina.ai Markdown (primär, kostenlos)
Kanal 2: Jina.ai Raw HTML → Regex-Extraktion
Kanal 3: Ollama llama3.2:3b — extrahiert Text aus rohem HTML

Jeder Kanal: 2 Retries, 30s Timeout.
Logging: welcher Kanal erfolgreich war.
"""
import asyncio
import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)

JINA_URL = "https://r.jina.ai/"
USER_AGENT = "ekklesia.gr/1.0 (civic-tech; +https://ekklesia.gr/wiki/api.html)"

# Boilerplate patterns that indicate Parliament navigation/chrome, not bill text
_BAD_TEXT_PATTERNS = [
    "Μετάβαση στο κύριο περιεχόμενο",
    "Ενεργοποίηση προσβασιμότητας",
    "Ανοίξτε το μενού προσβασιμότητας",
    "Νομοθετική Διαδικασία",
    "Ημερ. Διάταξη Ολομέλειας",
    "Εβδομαδιαίο Δελτίο",
    "Κατατεθέντα Σ/Ν ή Π/Ν",
    "Επεξεργασία στις Επιτροπές",
    "Συζητήσεις & Ψήφιση",
    "Ψηφισθέντα Σ/Ν",
    "Εμφανίζονται τα σχέδια ή οι προτάσεις",
    "Εμφανίζονται τα ψηφισθέντα",
]


def _is_bad_parliament_text(text: str) -> bool:
    """Return True if text is Parliament navigation boilerplate, not real bill content."""
    if not text or len(text.strip()) < 200:
        return True
    # Check for boilerplate markers
    matches = sum(1 for pat in _BAD_TEXT_PATTERNS if pat in text)
    if matches >= 1:
        return True
    # Mostly Markdown links/images/nav menus
    lines = text.strip().split("\n")
    markdown_noise = sum(
        1 for line in lines
        if line.strip().startswith(("*", "#", "![", "["))
        or ("http" in line and len(line.strip()) < 160)
    )
    if len(lines) > 3 and markdown_noise / len(lines) > 0.3:
        return True
    return False
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
MIN_TEXT_LENGTH = 200
MAX_TEXT_LENGTH = 8000
MAX_RETRIES = 2
TIMEOUT = 30


# ─── Kanal 1: Jina Markdown ─────────────────────────────────────────────────

async def _channel_jina_markdown(url: str) -> str:
    """Jina Reader — returns Markdown, we extract content lines."""
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(
                    f"{JINA_URL}{url}",
                    headers={"Accept": "text/plain", "User-Agent": USER_AGENT},
                )
                if resp.status_code != 200:
                    logger.warning("[CH1] Jina MD attempt %d: HTTP %d", attempt + 1, resp.status_code)
                    continue

                text = _extract_markdown_content(resp.text)
                if len(text) >= MIN_TEXT_LENGTH:
                    return text[:MAX_TEXT_LENGTH]

                logger.info("[CH1] Jina MD: too short (%d chars)", len(text))
        except Exception as e:
            logger.warning("[CH1] Jina MD attempt %d error: %s", attempt + 1, e)
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(3)
    return ""


def _extract_markdown_content(raw: str) -> str:
    """Extract meaningful content from Jina Markdown output."""
    lines = raw.split("\n")
    content_lines = []
    in_content = False
    for line in lines:
        if line.startswith("Title:") or line.startswith("URL Source:"):
            continue
        if line.startswith("Markdown Content:"):
            in_content = True
            continue
        if in_content and line.strip():
            if line.startswith("*") and "http" in line:
                continue
            if line.startswith("[") and "](" in line:
                continue
            if line.startswith("!["):
                continue
            if len(line.strip()) > 30:
                content_lines.append(line.strip())
    return "\n".join(content_lines)


# ─── Kanal 2: Jina Raw HTML → Regex ─────────────────────────────────────────

async def _channel_jina_html(url: str) -> str:
    """Jina Reader with X-Return-Format: html, then regex extraction."""
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(
                    f"{JINA_URL}{url}",
                    headers={
                        "X-Return-Format": "html",
                        "User-Agent": USER_AGENT,
                    },
                )
                if resp.status_code != 200:
                    logger.warning("[CH2] Jina HTML attempt %d: HTTP %d", attempt + 1, resp.status_code)
                    continue

                text = _extract_text_from_html(resp.text)
                if len(text) >= MIN_TEXT_LENGTH:
                    return text[:MAX_TEXT_LENGTH]

                logger.info("[CH2] Jina HTML: too short (%d chars)", len(text))
        except Exception as e:
            logger.warning("[CH2] Jina HTML attempt %d error: %s", attempt + 1, e)
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(3)
    return ""


def _extract_text_from_html(html: str) -> str:
    """Extract text from HTML using regex (no lxml dependency)."""
    # Remove script/style blocks
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

    # Try to find article/main content first
    main_match = re.search(
        r"<(?:article|main|div[^>]*class=\"[^\"]*(?:content|article|body|text)[^\"]*\")[^>]*>(.*?)</(?:article|main|div)>",
        html, flags=re.DOTALL | re.IGNORECASE,
    )
    if main_match:
        html = main_match.group(1)

    # Strip all tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Decode HTML entities
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')

    # Filter noise: keep only lines with Greek or substantial content
    lines = [l.strip() for l in text.split(".") if len(l.strip()) > 40]
    return ". ".join(lines)


# ─── Kanal 3: Ollama Text-Extraktion ────────────────────────────────────────

async def _channel_ollama_extract(url: str) -> str:
    """Fetch raw HTML, then use Ollama to extract bill text."""
    # First get raw HTML via Jina
    raw_html = ""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{JINA_URL}{url}",
                headers={"X-Return-Format": "html", "User-Agent": USER_AGENT},
            )
            if resp.status_code == 200:
                raw_html = resp.text
    except Exception as e:
        logger.warning("[CH3] HTML fetch for Ollama failed: %s", e)

    if not raw_html or len(raw_html) < 500:
        # Try direct fetch as last resort
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                if resp.status_code == 200:
                    raw_html = resp.text
        except Exception as e:
            logger.warning("[CH3] Direct fetch failed: %s", e)
            return ""

    if not raw_html or len(raw_html) < 500:
        return ""

    # Truncate HTML to fit Ollama context (keep first ~6000 chars of content area)
    html_snippet = _extract_text_from_html(raw_html)[:6000]

    if len(html_snippet) < 100:
        return ""

    prompt = (
        "Είσαι βοηθός εξαγωγής κειμένου. Από το παρακάτω κείμενο μιας ιστοσελίδας "
        "του Ελληνικού Κοινοβουλίου, εξήγαγε ΜΟΝΟ το κείμενο του νομοσχεδίου ή της "
        "απόφασης. Αφαίρεσε πλοήγηση, μενού, headers, footers. "
        "Επέστρεψε ΜΟΝΟ το καθαρό κείμενο στα Ελληνικά, χωρίς σχόλια.\n\n"
        f"ΚΕΙΜΕΝΟ ΙΣΤΟΣΕΛΙΔΑΣ:\n{html_snippet}\n\n"
        "ΚΑΘΑΡΟ ΚΕΙΜΕΝΟ ΝΟΜΟΣΧΕΔΙΟΥ:"
    )

    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": 2000, "temperature": 0.1},
                    },
                )
                resp.raise_for_status()
                result = resp.json().get("response", "").strip()
                if len(result) >= MIN_TEXT_LENGTH:
                    return result[:MAX_TEXT_LENGTH]
                logger.info("[CH3] Ollama: too short (%d chars)", len(result))
        except Exception as e:
            logger.warning("[CH3] Ollama attempt %d error: %s", attempt + 1, e)
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(2)
    return ""


# ─── Kanal 4: Playwright Headless Chromium (Not-Instanz) ─────────────────────

async def _channel_playwright(url: str) -> str:
    """Playwright headless Chromium — renders JS fully. Optional, skipped if not installed."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.info("[CH4] Playwright not installed — skipping")
        return ""

    for attempt in range(MAX_RETRIES):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(user_agent=USER_AGENT)
                await page.goto(url, timeout=TIMEOUT * 1000, wait_until="networkidle")
                # Extract all text from body
                content = await page.inner_text("body")
                await browser.close()

                if content and len(content.strip()) >= MIN_TEXT_LENGTH:
                    # Clean up navigation noise
                    lines = [l.strip() for l in content.split("\n") if len(l.strip()) > 40]
                    text = "\n".join(lines)
                    if len(text) >= MIN_TEXT_LENGTH:
                        return text[:MAX_TEXT_LENGTH]

                logger.info("[CH4] Playwright: too short (%d chars)", len(content.strip()) if content else 0)
        except Exception as e:
            logger.warning("[CH4] Playwright attempt %d error: %s", attempt + 1, e)
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(3)
    return ""


# ─── Orchestrator ────────────────────────────────────────────────────────────

async def fetch_bill_text(bill_id: str, parliament_url: str) -> str:
    """
    4-Kanal Text-Extraktion Pipeline.
    Returns extracted text (>200 chars) or empty string.
    Logs which channel succeeded.
    """
    if not parliament_url:
        return ""

    # Polite delay
    await asyncio.sleep(3)

    # Kanal 1: Jina Markdown
    text = await _channel_jina_markdown(parliament_url)
    if text:
        if _is_bad_parliament_text(text):
            logger.info("[SCRAPER] Kanal 1 rejected boilerplate: %s (%d chars)", bill_id, len(text))
        else:
            logger.info("[SCRAPER] Kanal 1 (Jina MD) OK: %s (%d chars)", bill_id, len(text))
            return text

    # Kanal 2: Jina Raw HTML
    await asyncio.sleep(2)
    text = await _channel_jina_html(parliament_url)
    if text:
        if _is_bad_parliament_text(text):
            logger.info("[SCRAPER] Kanal 2 rejected boilerplate: %s (%d chars)", bill_id, len(text))
        else:
            logger.info("[SCRAPER] Kanal 2 (Jina HTML) OK: %s (%d chars)", bill_id, len(text))
            return text

    # Kanal 3: Ollama
    await asyncio.sleep(2)
    text = await _channel_ollama_extract(parliament_url)
    if text:
        if _is_bad_parliament_text(text):
            logger.info("[SCRAPER] Kanal 3 rejected boilerplate: %s (%d chars)", bill_id, len(text))
        else:
            logger.info("[SCRAPER] Kanal 3 (Ollama) OK: %s (%d chars)", bill_id, len(text))
            return text

    # Kanal 4: Playwright (Not-Instanz)
    await asyncio.sleep(2)
    text = await _channel_playwright(parliament_url)
    if text:
        if _is_bad_parliament_text(text):
            logger.info("[SCRAPER] Kanal 4 rejected boilerplate: %s (%d chars)", bill_id, len(text))
        else:
            logger.info("[SCRAPER] Kanal 4 (Playwright) OK: %s (%d chars)", bill_id, len(text))
            return text

    # Alle fehlgeschlagen
    logger.error("[SCRAPER] ALLE 4 KANÄLE FEHLGESCHLAGEN: %s — %s", bill_id, parliament_url)
    return ""


# ─── Enrich All ──────────────────────────────────────────────────────────────

async def enrich_bill_with_text(bill_id: str, db, redis=None) -> dict:
    """Fetch text for a bill + update DB + clear cached summary."""
    from sqlalchemy import select
    from models import ParliamentBill

    result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    bill = result.scalar_one_or_none()
    if not bill:
        return {"success": False, "error": "Bill not found"}
    if not bill.parliament_url:
        return {"success": False, "error": "No parliament_url"}

    text = await fetch_bill_text(bill_id, bill.parliament_url)
    if text and _is_bad_parliament_text(text):
        logger.info("[SCRAPER] Rejected bad parliament text for %s (%d chars, boilerplate)", bill_id, len(text))
        return {"success": False, "error": "Rejected: parliament boilerplate"}
    if text and len(text) >= MIN_TEXT_LENGTH:
        bill.summary_long_el = text
        await db.commit()
        if redis:
            try:
                await redis.delete(f"bill_summary:{bill_id}:el")
                await redis.delete(f"bill_summary:{bill_id}:en")
            except Exception:
                pass
        return {"success": True, "text_length": len(text)}

    return {"success": False, "error": "All channels failed or text too short"}


async def enrich_all_bills(db) -> dict:
    """Enrich all parliament bills that have no summary_long_el."""
    from sqlalchemy import select
    from models import ParliamentBill

    result = await db.execute(
        select(ParliamentBill).where(
            ParliamentBill.summary_long_el.is_(None),
            ParliamentBill.parliament_url.isnot(None),
            ParliamentBill.source == "PARLIAMENT",
        )
    )
    bills = result.scalars().all()

    stats = {"total": len(bills), "enriched": 0, "failed": 0, "channels": {"ch1": 0, "ch2": 0, "ch3": 0}}

    for bill in bills:
        text = await fetch_bill_text(bill.id, bill.parliament_url)
        if text and _is_bad_parliament_text(text):
            logger.info("[ENRICH-ALL] Skipped bad text: %s", bill.id)
            stats["failed"] += 1
            continue
        if text and len(text) >= MIN_TEXT_LENGTH:
            bill.summary_long_el = text
            stats["enriched"] += 1
        else:
            stats["failed"] += 1

    await db.commit()
    logger.info("[ENRICH-ALL] %s", stats)
    return stats
