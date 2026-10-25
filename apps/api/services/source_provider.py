"""Optional deployment-supplied source metadata over a local Unix socket.

The application owns validation and ingestion. A provider supplies only public
source metadata and receives no application credentials or database access.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 20
TIMEOUT_SECONDS = 120


def configured_socket() -> str | None:
    value = os.getenv("SOURCE_PROVIDER_SOCKET", "")
    if not value:
        return None
    if not value.startswith("/") or "\0" in value or len(value.encode()) > 100:
        return None
    return value


def _date(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("Invalid source date")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _text(value: object, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid source text")
    value = " ".join(value.split())
    if len(value) > 2000 or any(ord(char) < 32 or ord(char) == 127 for char in value) or (required and len(value) < 10):
        raise ValueError("Invalid source text length")
    return value


def validate_payload(payload: object, *, limit: int, require_dates: bool) -> list[dict]:
    """Reject malformed envelopes/identities; never accept provider-generated content."""
    if type(limit) is not int or not 1 <= limit <= MAX_ROWS:
        raise ValueError("Invalid source limit")
    if not isinstance(payload, dict) or (
        type(payload.get("schema_version")) is not int
        or payload["schema_version"] != 1
        or payload.get("source") != "PARLIAMENT"
        or payload.get("source_status") != "ok"
    ):
        raise ValueError("Invalid source envelope")
    captured = payload.get("captured_at")
    if not isinstance(captured, str):
        raise ValueError("Missing source capture time")
    captured_at = datetime.fromisoformat(captured.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if captured_at.tzinfo is None or not now - timedelta(minutes=15) <= captured_at <= now + timedelta(minutes=2):
        raise ValueError("Invalid source capture time")
    rows = payload.get("bills")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError("Invalid source rows")
    seen: set[str] = set()
    result: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("law_id"), str):
            raise ValueError("Missing source identity")
        identifier = UUID(row["law_id"])
        law_id = str(identifier)
        if identifier.int == 0 or law_id in seen:
            raise ValueError("Invalid or duplicate source identity")
        seen.add(law_id)
        url = row.get("url")
        if not isinstance(url, str) or any(ord(char) < 32 for char in url):
            raise ValueError("Invalid source URL")
        parsed = urlsplit(url)
        ids = parse_qs(parsed.query, keep_blank_values=True).get("law_id", [])
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"hellenicparliament.gr", "www.hellenicparliament.gr"}
            or parsed.port not in {None, 443}
            or parsed.username or parsed.password or parsed.fragment
            or not parsed.path.startswith("/Nomothetiko-Ergo/")
            or len(ids) != 1 or ids[0].lower() != law_id
        ):
            raise ValueError("Unbound source URL")
        date, submitted_date = _date(row.get("date")), _date(row.get("submitted_date"))
        title = _text(row.get("title_el"), required=True)
        optional = {key: _text(row.get(key)) for key in ("type", "ministry", "phase")}
        if require_dates and not (date or submitted_date):
            continue
        result.append({
            "title_el": title, "url": url, "law_id": law_id,
            "date": date, "submitted_date": submitted_date, **optional,
        })
    return result[:limit]


async def collect_source_rows(*, limit: int, require_dates: bool) -> list[dict]:
    socket_path = configured_socket()
    if socket_path is None:
        return []
    try:
        transport = httpx.AsyncHTTPTransport(uds=socket_path, retries=0)
        async with asyncio.timeout(TIMEOUT_SECONDS):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://source-provider",
                timeout=httpx.Timeout(TIMEOUT_SECONDS, connect=2, pool=2, write=2),
                trust_env=False, follow_redirects=False,
            ) as client:
                async with client.stream(
                    "POST", "/v1/collect",
                    json={"source": "PARLIAMENT", "limit": limit, "require_dates": require_dates},
                    headers={"Accept": "application/json", "Accept-Encoding": "identity"},
                ) as response:
                    if response.status_code != 200:
                        raise ValueError("Source provider unavailable")
                    if response.headers.get("content-type", "").split(";")[0].strip() != "application/json":
                        raise ValueError("Invalid source content type")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise ValueError("Unsupported source encoding")
                    body = bytearray()
                    async for chunk in response.aiter_raw():
                        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise ValueError("Source response too large")
                        body.extend(chunk)
        return validate_payload(json.loads(body), limit=limit, require_dates=require_dates)
    except (httpx.HTTPError, OSError, ValueError, TypeError, OverflowError, RecursionError, TimeoutError):
        # Do not expose private deployment paths, response bodies or transport details.
        logger.warning("Configured source provider unavailable")
        return []
