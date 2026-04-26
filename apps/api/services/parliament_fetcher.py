"""
Parliament Bill Text Fetcher
Tries to extract bill text from hellenicparliament.gr via Jina Reader.
Falls back to template if text unavailable (JS-rendered pages).
"""
import asyncio
import logging
import os
import httpx

logger = logging.getLogger(__name__)

JINA_URL = "https://r.jina.ai/"
USER_AGENT = "ekklesia.gr/1.0 (civic-tech; +https://ekklesia.gr/wiki/api.html)"


async def fetch_bill_text(bill_id: str, parliament_url: str) -> str:
    """
    Fetch bill text from hellenicparliament.gr via Jina Reader.
    Returns extracted text (>200 chars) or empty string.
    """
    if not parliament_url:
        return ""

    # Soft scraping: 5s delay
    await asyncio.sleep(5)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Try Jina Reader (bypasses WAF, renders JS)
            resp = await client.get(
                f"{JINA_URL}{parliament_url}",
                headers={"Accept": "text/plain", "User-Agent": USER_AGENT},
            )
            if resp.status_code != 200:
                logger.warning("Jina fetch failed for %s: HTTP %d", bill_id, resp.status_code)
                return ""

            text = resp.text

            # Extract meaningful content (skip navigation, headers)
            lines = text.split("\n")
            content_lines = []
            in_content = False
            for line in lines:
                # Skip metadata/navigation lines
                if line.startswith("Title:") or line.startswith("URL Source:"):
                    continue
                if line.startswith("Markdown Content:"):
                    in_content = True
                    continue
                if in_content and line.strip():
                    # Skip navigation items and image references
                    if line.startswith("*") and "http" in line:
                        continue
                    if line.startswith("[") and "](" in line:
                        continue
                    if line.startswith("!["):
                        continue
                    if len(line.strip()) > 30:
                        content_lines.append(line.strip())

            result = "\n".join(content_lines)

            # Only return if we got meaningful text (>200 chars of content)
            if len(result) > 200:
                logger.info("Fetched %d chars for %s", len(result), bill_id)
                return result[:5000]

            logger.info("No meaningful content for %s (got %d chars)", bill_id, len(result))
            return ""

    except Exception as e:
        logger.warning("Parliament fetch failed for %s: %s", bill_id, e)
        return ""


async def enrich_bill_with_text(bill_id: str, db, redis=None) -> dict:
    """
    Fetch text for a bill + update DB + clear cached summary.
    Returns {"success": bool, "text_length": int}
    """
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
    if text and len(text) > 200:
        bill.summary_long_el = text
        await db.commit()
        # Clear cached summary so it regenerates with real text
        if redis:
            try:
                await redis.delete(f"bill_summary:{bill_id}:el")
                await redis.delete(f"bill_summary:{bill_id}:en")
            except Exception:
                pass
        return {"success": True, "text_length": len(text)}

    return {"success": False, "error": "No text extracted (JS-rendered page)"}
