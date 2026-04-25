"""
Diavgeia OpenData API Client — async, rate-limited, no auth required.
https://diavgeia.gov.gr/luminapi/opendata

Rate limit: 5s between requests (self-imposed politeness).
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://diavgeia.gov.gr/luminapi/opendata"
USER_AGENT = "ekklesia.gr/1.0 (+https://ekklesia.gr)"
REQUEST_DELAY_SECONDS = 5.0
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
            logger.warning("Unparseable Unix timestamp from Diavgeia: %s", raw)
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

    logger.warning("Unparseable timestamp from Diavgeia: %s", raw)
    return None


class DiavgeiaClient:
    """Async HTTP client for Diavgeia OpenData API. Rate-limited, no auth."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._last_request_at: float | None = None

    async def __aenter__(self) -> "DiavgeiaClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._client.aclose()

    async def close(self) -> None:
        await self._client.aclose()

    async def _throttle(self) -> None:
        """Enforce minimum delay between requests."""
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < REQUEST_DELAY_SECONDS:
                await asyncio.sleep(REQUEST_DELAY_SECONDS - elapsed)

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        """Execute HTTP request with throttling and retry on 5xx/429."""
        await self._throttle()

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            start = time.monotonic()
            self._last_request_at = start
            try:
                resp = await self._client.request(method, path, **kwargs)
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.info("Diavgeia %s %s -> %d (%.0fms)", method, path, resp.status_code, elapsed_ms)

                if resp.status_code == 429 or resp.status_code >= 500:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("Diavgeia %d on %s, retry %d/%d in %.1fs",
                                   resp.status_code, path, attempt + 1, MAX_RETRIES, delay)
                    await asyncio.sleep(delay)
                    last_exc = httpx.HTTPStatusError(
                        f"{resp.status_code}", request=resp.request, response=resp
                    )
                    continue

                resp.raise_for_status()
                return resp

            except httpx.TimeoutException as e:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("Diavgeia timeout on %s, retry %d/%d in %.1fs",
                               path, attempt + 1, MAX_RETRIES, delay)
                last_exc = e
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
