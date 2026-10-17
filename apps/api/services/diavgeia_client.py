"""
Diavgeia OpenData API Client — async, rate-limited, no auth required.
https://diavgeia.gov.gr/luminapi/opendata

Rate limit: 5s between requests (self-imposed politeness).
"""
import asyncio
import logging
import time
from asyncio import timeout as attempt_timeout
from datetime import datetime
from typing import AsyncIterator

import httpx

from services.scraper_http import SCRAPER_HTTP_HOOKS

logger = logging.getLogger(__name__)

BASE_URL = "https://diavgeia.gov.gr/luminapi/opendata"
USER_AGENT = "ekklesia.gr/1.0 (+https://ekklesia.gr)"
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


def parse_timestamp(raw: str | int | None) -> datetime | None:
    """Parse Diavgeia timestamps — handles Unix ms, ISO, and DD/MM/YYYY formats."""
    if raw is None:
        return None

    # Unix timestamp in milliseconds (primary format from search API)
    if isinstance(raw, (int, float)):
        try:
            return datetime.utcfromtimestamp(raw / 1000.0)
        except (OSError, ValueError, OverflowError):
            logger.warning("Unparseable Unix timestamp from Diavgeia")
            return None

    raw = str(raw).strip()
    if not raw:
        return None

    # Try as numeric string (Unix ms)
    try:
        ms = int(raw)
        return datetime.utcfromtimestamp(ms / 1000.0)
    except (ValueError, OSError, OverflowError):
        pass

    # ISO 8601
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    # DD/MM/YYYY HH:MM:SS (legacy format)
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    logger.warning("Unparseable timestamp from Diavgeia")
    return None


class DiavgeiaClient:
    """Async HTTP client for Diavgeia OpenData API. Rate-limited, no auth."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._attempt_timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            follow_redirects=True,
            event_hooks=SCRAPER_HTTP_HOOKS,
        )

    async def __aenter__(self) -> "DiavgeiaClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._client.aclose()

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        """Execute HTTP request with throttling and retry on 5xx/429."""
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            start = time.monotonic()
            try:
                async with attempt_timeout(self._attempt_timeout):
                    resp = await self._client.request(method, path, **kwargs)
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.info("Diavgeia response status=%d elapsed_ms=%.0f", resp.status_code, elapsed_ms)

                if resp.status_code == 429 or resp.status_code >= 500:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("Diavgeia status=%d attempt=%d/%d",
                                   resp.status_code, attempt + 1, MAX_RETRIES)
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(delay)
                    last_exc = httpx.HTTPStatusError(
                        f"{resp.status_code}", request=resp.request, response=resp
                    )
                    continue

                resp.raise_for_status()
                return resp

            except (httpx.TimeoutException, TimeoutError) as e:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("Diavgeia timeout attempt=%d/%d", attempt + 1, MAX_RETRIES)
                last_exc = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

    async def list_organizations(self, page: int = 0, size: int = 500) -> dict:
        """Fetch organizations from Diavgeia."""
        resp = await self._request("GET", "/organizations.json", params={
            "page": page,
            "size": size,
        })
        return resp.json()

    async def search_decisions(
        self,
        organization_uid: str | None = None,
        decision_type_uid: str | None = None,
        published_after: datetime | None = None,
        page: int = 0,
        size: int = 100,
        sort: str = "recent",
    ) -> dict:
        """Search decisions with filters."""
        params: dict[str, str | int] = {
            "page": page,
            "size": size,
            "sort": sort,
        }
        if organization_uid:
            params["org"] = organization_uid
        if decision_type_uid:
            params["type"] = decision_type_uid
        if published_after:
            params["from_issue_date"] = published_after.strftime("%Y-%m-%d")

        resp = await self._request("GET", "/search.json", params=params)
        return resp.json()

    async def iter_decisions(
        self,
        max_pages: int = 10,
        **filters: object,
    ) -> AsyncIterator[dict]:
        """Yields individual decisions across all pages, respecting rate limit."""
        for page in range(max_pages):
            data = await self.search_decisions(page=page, **filters)  # type: ignore[arg-type]
            decisions = data.get("decisions", [])
            if not decisions:
                break
            for decision in decisions:
                yield decision
