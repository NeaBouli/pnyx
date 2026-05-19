"""
Org label lookup from snapshot. Loaded once, cached.
Provides label resolution for scraper and display.
"""
import gzip
import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_PATH = DATA_DIR / "diavgeia_orgs_snapshot.json"
SNAPSHOT_GZ_PATH = DATA_DIR / "diavgeia_orgs_snapshot.json.gz"

_org_cache: dict[str, dict] | None = None


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


async def resolve_unknown_label(uid: str) -> str | None:
    """Live-resolve an unknown org UID via Diavgeia API. Caches result."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://diavgeia.gov.gr/opendata/organizations/{uid}.json")
            if resp.status_code == 200:
                data = resp.json()
                label = data.get("label", "")
                if label:
                    # Cache it
                    cache = get_org_cache()
                    cache[str(uid)] = {"uid": uid, "label": label}
                    logger.info("Resolved org %s → %s", uid, label)
                    return label
    except Exception as e:
        logger.warning("Failed to resolve org %s: %s", uid, e)
    return None


def get_org(uid: str) -> dict | None:
    """Get full org dict by UID."""
    return get_org_cache().get(str(uid))
