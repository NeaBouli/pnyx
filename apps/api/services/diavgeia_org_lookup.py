"""Municipal geography snapshot and shared, persistent organization labels.

Live labels never enter the municipal snapshot: it is a geographic allowlist.
Per-UID Redis hashes expire independently (30 days positive, 1 day negative),
so new imports and repairs share labels without a database migration.
"""
import asyncio
import gzip
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import redis.asyncio as aioredis

from config import settings
from services import scraper_http
from services.diavgeia_client import MAX_RETRIES, RETRY_BASE_DELAY, USER_AGENT
from services.scraper_http import SCRAPER_HTTP_HOOKS

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_PATH = DATA_DIR / "diavgeia_orgs_snapshot.json"
SNAPSHOT_GZ_PATH = DATA_DIR / "diavgeia_orgs_snapshot.json.gz"

_org_cache: dict[str, dict] | None = None
LABEL_CACHE_PREFIX = "diavgeia:org-label:v1:"
LABEL_RATE_KEY = "diavgeia:org-label:request-slot"
POSITIVE_TTL = 30 * 86400
NEGATIVE_TTL = 86400
LOOKUP_TIMEOUT = 10.0
ORGANIZATIONS_URL = "https://diavgeia.gov.gr/opendata/organizations"
UID_RE = re.compile(r"[0-9]{1,16}\Z")
UNKNOWN_PILL_RE = re.compile(r"Διαύγεια: \[unknown:([0-9]{1,16})\]\Z")
UNKNOWN_PILL_SQL_PATTERN = r"^Διαύγεια: \[unknown:[0-9]{1,16}\]$"
ORG_LABEL_MISSING_SQL = """(org_label IS NULL OR btrim(org_label) = ''
    OR lower(btrim(org_label)) = 'unknown'
    OR lower(btrim(org_label)) LIKE '[unknown:%'
    OR lower(btrim(org_label)) LIKE '[no-label:%')"""
DECISION_LABEL_MISSING_SQL = ORG_LABEL_MISSING_SQL.replace("org_label", "organization_label")


def clean_org_label(label: object) -> str | None:
    """Validate display metadata, independently of generated prose quality."""
    if not isinstance(label, str):
        return None
    label = label.strip()
    if (not label or label.lower() == "unknown" or label.isdecimal()
            or label.lower().startswith(("[unknown:", "[no-label:"))):
        return None
    return label


def org_pill(label: str | None) -> str:
    label = clean_org_label(label)
    return f"Διαύγεια: {label}" if label else "Διαύγεια"


@asynccontextmanager
async def _redis():
    async with aioredis.from_url(
        settings.redis_url, decode_responses=True,
        socket_connect_timeout=1, socket_timeout=1,
    ) as cache:
        yield cache


async def _pace_label_request(request: httpx.Request) -> None:
    """Atomic shared 500ms slot, including retries and redirects across workers.

    Existing scraper hooks additionally enforce host pacing and cooldowns.
    Fail closed during Redis outages so worker count cannot amplify traffic.
    The enclosing attempt deadline bounds contention as well as HTTP time.
    """
    while True:
        async with _redis() as cache:
            if await cache.set(LABEL_RATE_KEY, "1", nx=True, px=500):
                return
        await asyncio.sleep(0.5)


async def _cache_label(uid: str, label: str | None) -> None:
    try:
        async with _redis() as cache:
            async with cache.pipeline(transaction=True) as pipe:
                pipe.hset(LABEL_CACHE_PREFIX + uid, mapping={"label": label or ""})
                pipe.expire(LABEL_CACHE_PREFIX + uid, POSITIVE_TTL if label else NEGATIVE_TTL)
                await pipe.execute()
    except Exception as exc:
        logger.warning("Diavgeia label cache write unavailable error=%s", type(exc).__name__)


def _load_snapshot() -> dict[str, dict]:
    """Load snapshot and return uid→org dict."""
    for path in (SNAPSHOT_PATH, SNAPSHOT_GZ_PATH):
        if path.exists():
            opener = gzip.open if path.suffix == ".gz" else open
            with opener(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
            orgs = {str(o["uid"]): o for o in data.get("organizations", [])}
            logger.info("Loaded %d orgs from snapshot %s", len(orgs), path.name)
            return orgs
    logger.warning("No org snapshot found at %s", SNAPSHOT_PATH)
    return {}


def get_org_cache() -> dict[str, dict]:
    """Get or initialize the org cache."""
    global _org_cache
    if _org_cache is None:
        _org_cache = _load_snapshot()
    return _org_cache


def reload() -> int:
    """Reload snapshot from disk. Returns new cache size."""
    global _org_cache
    _org_cache = _load_snapshot()
    return len(_org_cache)


def get_label(uid: str) -> str:
    """Get org label by UID. Returns '[unknown:{uid}]' if not found."""
    cache = get_org_cache()
    org = cache.get(str(uid))
    if org:
        return org.get("label", f"[no-label:{uid}]")
    return f"[unknown:{uid}]"


async def resolve_org_label(uid: str) -> str | None:
    """Snapshot → persistent label/negative cache → public organization API.

    Only a numeric public organization UID leaves this process. Transient
    failures are logged by status/type and are never cached as missing orgs.
    """
    uid = str(uid).strip()
    if not UID_RE.fullmatch(uid):
        return None
    local = clean_org_label((get_org(uid) or {}).get("label"))
    if local:
        return local
    try:
        async with _redis() as cache:
            cached = await cache.hgetall(LABEL_CACHE_PREFIX + uid)
        if "label" in cached:
            if cached["label"] == "":
                return None
            label = clean_org_label(cached["label"])
            if label:
                return label
    except Exception as exc:
        logger.warning("Diavgeia label cache read unavailable error=%s", type(exc).__name__)

    last_request = None

    async def remember_request(request):
        nonlocal last_request
        last_request = request

    async def release_failed_request():
        # No response hook runs after transport failure/deadline cancellation.
        # Release this attempt's token before retrying, rather than waiting for
        # the five-minute orphan lease TTL. Token checks protect newer owners.
        if last_request is not None:
            await scraper_http.host_limiter.release(last_request.extensions.get("scraper_host_leases", []))

    hooks = {**SCRAPER_HTTP_HOOKS,
             "request": [remember_request, *SCRAPER_HTTP_HOOKS["request"], _pace_label_request]}
    async with httpx.AsyncClient(
        timeout=LOOKUP_TIMEOUT, headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        follow_redirects=True, event_hooks=hooks,
    ) as client:
        for attempt in range(MAX_RETRIES):
            try:
                async with asyncio.timeout(LOOKUP_TIMEOUT):
                    resp = await client.get(f"{ORGANIZATIONS_URL}/{uid}")
                if resp.status_code == 404:
                    await _cache_label(uid, None)
                    return None
                if resp.status_code == 429 or resp.status_code >= 500:
                    logger.warning("Diavgeia label status=%d attempt=%d", resp.status_code, attempt + 1)
                elif resp.status_code != 200:
                    logger.warning("Diavgeia label unavailable status=%d", resp.status_code)
                    return None
                else:
                    try:
                        data = resp.json()
                    except ValueError:
                        data = None
                    label = None
                    if isinstance(data, dict) and str(data.get("uid")) == uid:
                        label = clean_org_label(data.get("label"))
                    if not label:
                        logger.warning("Diavgeia label invalid response")
                    await _cache_label(uid, label)
                    return label
            except (httpx.TransportError, TimeoutError) as exc:
                await release_failed_request()
                logger.warning("Diavgeia label attempt=%d error=%s", attempt + 1, type(exc).__name__)
            except Exception as exc:
                await release_failed_request()
                # Includes scraper admission/cooldown and Redis pacing failures.
                # Never log payloads or exception messages containing URLs/data.
                logger.warning("Diavgeia label deferred error=%s", type(exc).__name__)
                return None
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BASE_DELAY * 2 ** attempt)
    return None


# Compatibility for callers outside the import/repair paths.
resolve_unknown_label = resolve_org_label


def get_org(uid: str) -> dict | None:
    """Get full org dict by UID."""
    return get_org_cache().get(str(uid))
