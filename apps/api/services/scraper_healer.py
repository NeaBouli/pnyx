"""
Auto-Healing Scraper Service
Uses Ollama to analyze HTML structure changes and generate new selectors.
Triggered when a scraper fails to extract expected data.
"""
import asyncio
import logging
from typing import Optional

from .ollama_service import ollama_generate, ollama_available

logger = logging.getLogger(__name__)

HEALED_SELECTOR_KEY = "scraper:healed:{scraper_name}:{field}"


def _looks_like_css_selector(selector: str) -> bool:
    """Reject prose, multi-line answers, and obviously invalid selector output."""
    if not selector or len(selector) > 200 or "\n" in selector:
        return False
    lowered = selector.lower()
    if lowered.startswith(("i ", "the ", "here", "css selector")):
        return False
    if any(token in selector for token in ["<", ">", "{", "}", ";"]):
        return False
    return any(prefix in selector for prefix in [".", "#", "[", ":", " "]) or selector.isidentifier()


async def analyze_html_structure(
    html_snippet: str,
    field_name: str,
    expected_content: str,
    scraper_name: str,
) -> Optional[str]:
    """Ask Ollama to analyze HTML and suggest a new CSS selector."""
    prompt = (
        "You are an expert web scraper developer.\n"
        f"The CSS selector for '{field_name}' on a Greek government site stopped working.\n"
        f"Expected content type: {expected_content}\n"
        f"Scraper: {scraper_name}\n\n"
        f"HTML snippet (first 2000 chars):\n{html_snippet[:2000]}\n\n"
        f"Find the CSS selector that extracts '{field_name}' from this HTML.\n"
        "Respond with ONLY the CSS selector string, nothing else.\n"
        "CSS selector:"
    )
    try:
        result = await ollama_generate(prompt, max_tokens=50)
        selector = result.strip().strip('"').strip("'").strip()
        if _looks_like_css_selector(selector):
            logger.info("Ollama suggested selector for %s/%s: %s", scraper_name, field_name, selector)
            return selector
    except Exception as e:
        logger.error("Ollama healer failed: %s", e)
    return None


async def test_selector(html: str, selector: str) -> bool:
    """Test if a CSS selector finds non-empty content in HTML."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        results = soup.select(selector)
        return len(results) > 0 and results[0].get_text(strip=True) != ""
    except Exception:
        return False


async def heal_scraper(
    scraper_name: str,
    field_name: str,
    failed_html: str,
    expected_content: str,
    redis_client=None,
) -> Optional[str]:
    """
    Main healing function:
    1. Ask Ollama for new selector (up to 3 attempts)
    2. Test selector against failed HTML
    3. Cache in Redis if successful
    """
    if not await ollama_available():
        logger.warning("Auto-healing skipped: Ollama unavailable")
        return None

    logger.warning("Auto-healing triggered: %s/%s", scraper_name, field_name)

    for attempt in range(3):
        selector = await analyze_html_structure(
            failed_html, field_name, expected_content, scraper_name
        )
        if not selector:
            continue

        if await test_selector(failed_html, selector):
            logger.info("Auto-healing SUCCESS: %s/%s → %s", scraper_name, field_name, selector)
            if redis_client:
                key = HEALED_SELECTOR_KEY.format(scraper_name=scraper_name, field=field_name)
                try:
                    await redis_client.set(key, selector, ex=86400 * 7)
                except Exception:
                    pass
            return selector

        await asyncio.sleep(2)

    logger.error("Auto-healing FAILED after 3 attempts: %s/%s", scraper_name, field_name)
    return None


async def get_healed_selector(
    scraper_name: str,
    field_name: str,
    redis_client=None,
) -> Optional[str]:
    """Retrieve a previously healed selector from Redis."""
    if not redis_client:
        return None
    try:
        key = HEALED_SELECTOR_KEY.format(scraper_name=scraper_name, field=field_name)
        result = await redis_client.get(key)
        if isinstance(result, bytes):
            return result.decode()
        return result
    except Exception:
        return None
