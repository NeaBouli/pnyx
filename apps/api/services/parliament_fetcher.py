"""Bill text enrichment: direct Diavgeia documents and four Parliament fallbacks.

HTTP attempts share host pacing, Retry-After delays and forbidden cooldowns.
"""
import asyncio
import logging
import os
import re
from asyncio import CancelledError, create_task, timeout as attempt_timeout, timeout_at, wait
from urllib.parse import urlsplit

import httpx

from services.scraper_http import HostCooldown, SCRAPER_HTTP_HOOKS, host_limiter

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

_BAD_TEXT_PREFIXES = [
    "Αναζήτηση Τίτλος",
]

_ACCESS_DENIAL_PATTERNS = (
    "you don't have permission to access",
    "errors.edgesuite.net",
)


_DOCUMENT_BLOCK_HEADING = "### Πλήρη έγγραφα"
_DOCUMENT_BLOCK_LINK_RE = re.compile(
    r"^-\s+\[[^\]]+\]\(https?://(?:www\.)?hellenicparliament\.gr/[^)]+\.pdf[^)]*\)$",
    re.IGNORECASE,
)


def _is_parliament_document_block_only(text: str | None) -> bool:
    """Return True only for the scraper's PDF-only Parliament document fallback block."""
    if not text:
        return False

    stripped = text.strip()
    if not stripped.startswith(_DOCUMENT_BLOCK_HEADING):
        return False

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) < 2 or lines[0] != _DOCUMENT_BLOCK_HEADING:
        return False

    document_links = 0
    for line in lines[1:]:
        if not _DOCUMENT_BLOCK_LINK_RE.match(line):
            return False
        document_links += 1
    return document_links > 0


def _merge_text_with_existing_document_block(text: str, existing_summary: str | None) -> str:
    """Preserve working PDF links when replacing a PDF-only fallback with fetched text."""
    if _is_parliament_document_block_only(existing_summary):
        return f"{text.rstrip()}\n\n{existing_summary.strip()}"
    return text


def _is_bad_parliament_text(text: str | None) -> bool:
    """Return True if text is Parliament navigation boilerplate, not real bill content."""
    if not text or len(text.strip()) < 200:
        return True
    stripped = text.strip()
    lowered = stripped.lower()
    if (
        any(pattern in lowered for pattern in _ACCESS_DENIAL_PATTERNS)
        or ("access denied" in lowered and "reference #" in lowered)
    ):
        return True
    if any(stripped.startswith(prefix) for prefix in _BAD_TEXT_PREFIXES):
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
MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_RETRIES = 2
TIMEOUT = 30
PLAYWRIGHT_TEARDOWN_TIMEOUT = 2


# ─── Kanal 1: Jina Markdown ─────────────────────────────────────────────────

async def _channel_jina_markdown(url: str) -> str:
    """Jina Reader — returns Markdown, we extract content lines."""
    for attempt in range(MAX_RETRIES):
        try:
            async with attempt_timeout(TIMEOUT), httpx.AsyncClient(timeout=TIMEOUT, event_hooks=SCRAPER_HTTP_HOOKS) as client:
                resp = await client.get(
                    f"{JINA_URL}{url}",
                    headers={"Accept": "text/plain", "User-Agent": USER_AGENT},
                    extensions={"scraper_source_url": url},
                )
                if resp.status_code != 200:
                    logger.warning("[CH1] Jina MD attempt %d: HTTP %d", attempt + 1, resp.status_code)
                    if resp.status_code == 403:
                        host_limiter.check(str(resp.url))
                else:
                    text = _extract_markdown_content(resp.text)
                    if len(text) >= MIN_TEXT_LENGTH:
                        return text[:MAX_TEXT_LENGTH]
                    logger.info("[CH1] Jina MD: too short (%d chars)", len(text))
        except HostCooldown:
            raise
        except Exception as e:
            logger.warning("[CH1] Jina MD attempt %d error: %s", attempt + 1, type(e).__name__)
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
            async with attempt_timeout(TIMEOUT), httpx.AsyncClient(timeout=TIMEOUT, event_hooks=SCRAPER_HTTP_HOOKS) as client:
                resp = await client.get(
                    f"{JINA_URL}{url}",
                    headers={
                        "X-Return-Format": "html",
                        "User-Agent": USER_AGENT,
                    },
                    extensions={"scraper_source_url": url},
                )
                if resp.status_code != 200:
                    logger.warning("[CH2] Jina HTML attempt %d: HTTP %d", attempt + 1, resp.status_code)
                    if resp.status_code == 403:
                        host_limiter.check(str(resp.url))
                else:
                    text = _extract_text_from_html(resp.text)
                    if len(text) >= MIN_TEXT_LENGTH:
                        return text[:MAX_TEXT_LENGTH]
                    logger.info("[CH2] Jina HTML: too short (%d chars)", len(text))
        except HostCooldown:
            raise
        except Exception as e:
            logger.warning("[CH2] Jina HTML attempt %d error: %s", attempt + 1, type(e).__name__)
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
        async with attempt_timeout(TIMEOUT), httpx.AsyncClient(timeout=TIMEOUT, event_hooks=SCRAPER_HTTP_HOOKS) as client:
            resp = await client.get(
                f"{JINA_URL}{url}",
                headers={"X-Return-Format": "html", "User-Agent": USER_AGENT},
                extensions={"scraper_source_url": url},
            )
            if resp.status_code == 200:
                raw_html = resp.text
    except HostCooldown:
        pass
    except Exception as e:
        logger.warning("[CH3] HTML fetch for Ollama failed: %s", type(e).__name__)

    if not raw_html or len(raw_html) < 500:
        # Try direct fetch as last resort
        try:
            async with attempt_timeout(TIMEOUT), httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, event_hooks=SCRAPER_HTTP_HOOKS) as client:
                resp = await client.get(url, headers={"User-Agent": USER_AGENT}, extensions={"scraper_source_url": url})
                if resp.status_code == 200:
                    raw_html = resp.text
        except HostCooldown:
            raise
        except Exception as e:
            logger.warning("[CH3] Direct fetch failed: %s", type(e).__name__)
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
            async with attempt_timeout(90), httpx.AsyncClient(timeout=90, event_hooks=SCRAPER_HTTP_HOOKS) as client:
                resp = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    extensions={"scraper_source_url": url},
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
        except HostCooldown:
            raise
        except Exception as e:
            logger.warning("[CH3] Ollama attempt %d error: %s", attempt + 1, type(e).__name__)
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(2)
    return ""


# ─── Kanal 4: Playwright Headless Chromium (Not-Instanz) ─────────────────────

async def _teardown_playwright(manager, browser) -> None:
    """Bound both cleanup steps, including after launch or navigation times out."""
    def consume_result(task):
        if not task.cancelled():
            task.exception()

    error = None
    steps = ([browser.close] if browser is not None else []) + [
        lambda: manager.__aexit__(None, None, None),
    ]
    for close in steps:
        task = create_task(close())
        try:
            # wait_for can itself hang while waiting for cancellation to finish.
            done, _ = await wait({task}, timeout=PLAYWRIGHT_TEARDOWN_TIMEOUT)
            if not done:
                raise TimeoutError("Playwright teardown deadline exceeded")
            task.result()
        except (Exception, CancelledError) as exc:
            task.cancel()
            task.add_done_callback(consume_result)
            # Playwright has no public force-stop API. Kill only this manager's
            # driver, including when launch never returned a browser handle.
            connection = getattr(manager, "_connection", None)
            transport = getattr(connection, "_transport", None)
            process = getattr(transport, "_proc", None)
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            if isinstance(exc, CancelledError):
                raise
            error = error or exc
    if error is not None:
        raise error


async def _channel_playwright(url: str) -> str:
    """Playwright headless Chromium — renders JS fully. Optional, skipped if not installed."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.info("[CH4] Playwright not installed — skipping")
        return ""

    for attempt in range(MAX_RETRIES):
        try:
            manager = async_playwright()
            browser = None
            try:
                async with attempt_timeout(TIMEOUT) as deadline:
                    p = await manager.__aenter__()
                    host_limiter.check(url)
                    browser = await p.chromium.launch(headless=True)

                    async def paced_route(route):
                        try:
                            # Send browser traffic through HTTPX too: Playwright's
                            # routing alone does not intercept every redirect hop.
                            # Route callbacks can run in separate asyncio tasks.
                            async with timeout_at(deadline.when()):
                                response = await browser_http.request(
                                    route.request.method, route.request.url,
                                    headers=await route.request.all_headers(),
                                    content=route.request.post_data_buffer,
                                    extensions={"scraper_source_url": url},
                                )
                                headers = {
                                    key: value for key, value in response.headers.items()
                                    if key not in ("content-encoding", "content-length", "transfer-encoding")
                                }
                                await route.fulfill(status=response.status_code, headers=headers, body=response.content)
                        except (HostCooldown, httpx.RequestError, TimeoutError):
                            await route.abort()

                    page = await browser.new_page(user_agent=USER_AGENT, service_workers="block")
                    # Browser redirects and subresources also need host pacing.
                    await page.route("**/*", paced_route)
                    async with httpx.AsyncClient(
                        timeout=TIMEOUT, follow_redirects=True, event_hooks=SCRAPER_HTTP_HOOKS,
                    ) as browser_http:
                        response = await page.goto(url, timeout=TIMEOUT * 1000, wait_until="networkidle")
                        if response is not None and response.status != 200:
                            host_limiter.check(url)
                            return ""
                        content = await page.inner_text("body")
            finally:
                await _teardown_playwright(manager, browser)

            if content and len(content.strip()) >= MIN_TEXT_LENGTH:
                # Clean up navigation noise
                lines = [l.strip() for l in content.split("\n") if len(l.strip()) > 40]
                text = "\n".join(lines)
                if len(text) >= MIN_TEXT_LENGTH:
                    return text[:MAX_TEXT_LENGTH]

            logger.info("[CH4] Playwright: too short (%d chars)", len(content.strip()) if content else 0)
        except HostCooldown:
            raise
        except Exception as e:
            logger.warning("[CH4] Playwright attempt %d error: %s", attempt + 1, type(e).__name__)
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(3)
    return ""


# ─── Orchestrator ────────────────────────────────────────────────────────────

async def _fetch_diavgeia_document(url: str) -> tuple[str, str]:
    """Stream documentUrl directly; reject PDFs and oversized documents early."""
    for attempt in range(MAX_RETRIES):
        try:
            async with attempt_timeout(TIMEOUT), httpx.AsyncClient(
                timeout=TIMEOUT, follow_redirects=True, event_hooks=SCRAPER_HTTP_HOOKS,
            ) as client:
                async with client.stream(
                    "GET", url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
                    extensions={"scraper_source_url": url},
                ) as resp:
                    if resp.status_code == 403:
                        return "", "skipped"
                    if resp.status_code == 200:
                        content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                        # No PDF library is declared in apps/api/requirements*.txt.
                        if content_type == "application/pdf":
                            logger.info("[DIAVGEIA-TEXT] PDF skipped: no declared PDF parser; source link retained")
                            return "", "skipped"
                        if content_type not in ("text/html", "application/xhtml+xml", "text/plain"):
                            logger.info("[DIAVGEIA-TEXT] Unsupported content type; source link retained")
                            return "", "skipped"
                        # Some servers ignore Accept-Encoding. Skip their encoded
                        # bodies before HTTPX can expand even one transport chunk.
                        if resp.headers.get("content-encoding", "identity").strip().lower() != "identity":
                            logger.info("[DIAVGEIA-TEXT] Encoded document skipped; source link retained")
                            return "", "skipped"
                        body = bytearray()
                        # Identity makes the raw and decoded byte limits identical.
                        async for chunk in resp.aiter_raw():
                            # Do not buffer beyond the signature before checking it,
                            # even when it is split across transport chunks.
                            if len(body) < 5 and (body + chunk[:5])[:5] == b"%PDF-":
                                logger.info("[DIAVGEIA-TEXT] PDF signature detected; source link retained")
                                return "", "skipped"
                            if len(body) + len(chunk) > MAX_DOCUMENT_BYTES:
                                logger.info("[DIAVGEIA-TEXT] Document size limit exceeded; source link retained")
                                return "", "skipped"
                            body.extend(chunk)
                        text = body.decode(resp.encoding or "utf-8", errors="replace")
                        if content_type == "text/plain":
                            return text.strip()[:MAX_TEXT_LENGTH], "fetched"
                        return _extract_text_from_html(text)[:MAX_TEXT_LENGTH], "fetched"
                    logger.warning("[DIAVGEIA-TEXT] status=%d attempt=%d", resp.status_code, attempt + 1)
                    if resp.status_code != 429 and resp.status_code < 500:
                        return "", "failed"
        except HostCooldown:
            raise
        except (httpx.RequestError, TimeoutError) as exc:
            logger.warning("[DIAVGEIA-TEXT] request error=%s", type(exc).__name__)
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(3)
    return "", "failed"


async def _fetch_bill_text_result(
    bill_id: str, parliament_url: str, *, source: str | None = None,
) -> tuple[str, str]:
    """Return text and outcome; emit one privacy-safe count line per fetch run."""
    outcome = "failed"
    try:
        if not parliament_url:
            outcome = "skipped"
            return "", outcome
        host_limiter.check(parliament_url)
        host = (urlsplit(parliament_url).hostname or "").lower()
        if source == "DIAVGEIA" or host == "diavgeia.gov.gr" or host.endswith(".diavgeia.gov.gr"):
            text, outcome = await _fetch_diavgeia_document(parliament_url)
            if outcome == "fetched" and _is_bad_parliament_text(text):
                outcome = "failed"
                text = ""
            return text, outcome

        deferred = False
        for channel in (
            _channel_jina_markdown, _channel_jina_html,
            _channel_ollama_extract, _channel_playwright,
        ):
            try:
                host_limiter.check(parliament_url)
                text = await channel(parliament_url)
            except HostCooldown:
                deferred = True
                continue
            if text and not _is_bad_parliament_text(text):
                logger.info("[TEXT-FETCH] channel=%s chars=%d", channel.__name__, len(text))
                outcome = "fetched"
                return text, outcome
        outcome = "skipped" if deferred else "failed"
        return "", outcome
    except HostCooldown:
        outcome = "skipped"
        return "", outcome
    except Exception as exc:
        logger.warning("[TEXT-FETCH] error=%s", type(exc).__name__)
        return "", outcome
    finally:
        logger.info(
            "[TEXT-FETCH] fetched=%d skipped=%d failed=%d",
            int(outcome == "fetched"), int(outcome == "skipped"), int(outcome == "failed"),
        )


async def fetch_bill_text(bill_id: str, parliament_url: str, *, source: str | None = None) -> str:
    """Fetch inline text, using direct document handling for Diavgeia."""
    text, _ = await _fetch_bill_text_result(bill_id, parliament_url, source=source)
    return text


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

    text, outcome = await _fetch_bill_text_result(bill_id, bill.parliament_url, source=bill.source)
    if outcome == "skipped":
        return {"success": False, "skipped": True, "error": "Text enrichment deferred; source link retained"}
    if text and len(text) >= MIN_TEXT_LENGTH:
        bill.summary_long_el = _merge_text_with_existing_document_block(text, bill.summary_long_el)
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
    """Enrich parliament bills with no real full text.

    Existing PDF-only document blocks are kept as a fallback and appended to fetched text.
    Real text is never selected by this broad job.
    """
    from sqlalchemy import or_, select
    from models import ParliamentBill

    result = await db.execute(
        select(ParliamentBill).where(
            or_(
                ParliamentBill.summary_long_el.is_(None),
                ParliamentBill.summary_long_el.like(f"{_DOCUMENT_BLOCK_HEADING}%"),
            ),
            ParliamentBill.parliament_url.isnot(None),
            ParliamentBill.source == "PARLIAMENT",
        )
    )
    bills = [
        bill for bill in result.scalars().all()
        if bill.summary_long_el is None or _is_parliament_document_block_only(bill.summary_long_el)
    ]

    stats = {"total": len(bills), "enriched": 0, "fetched": 0, "skipped": 0, "failed": 0, "channels": {"ch1": 0, "ch2": 0, "ch3": 0}}

    for bill in bills:
        text, outcome = await _fetch_bill_text_result(bill.id, bill.parliament_url, source=bill.source)
        if outcome == "skipped":
            stats["skipped"] += 1
            continue
        if text and len(text) >= MIN_TEXT_LENGTH:
            bill.summary_long_el = _merge_text_with_existing_document_block(text, bill.summary_long_el)
            stats["enriched"] += 1
            stats["fetched"] += 1
        else:
            stats["failed"] += 1

    await db.commit()
    logger.info("[ENRICH-ALL] %s", stats)
    return stats
