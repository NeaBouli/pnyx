"""
MOD-11: Public API + Rate Limiting + API Keys
Öffentliche REST API für NGOs, Journalisten, Forscher.

Rate Limits:
  - Anonym:       100 req/min
  - Mit API Key: 1000 req/min
  - API Keys:    community-generiert, kein Konto nötig

@ai-anchor MOD11_PUBLIC_API
"""
import hashlib
import os
import json
import secrets
import logging
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import httpx

from database import get_db
from ip_utils import rate_limit_key_for_ip, redis_fixed_window_limit
from services.bill_visibility import is_public_bill, public_bill_filter, public_bill_with_demo_filter
from services.zk_vote_aggregation import aggregate_bill_vote_totals
from models import (
    ParliamentBill, CitizenVote, Party,
    BillStatus, VoteChoice
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/public", tags=["MOD-11 Public API"])


# ── Redis-backed API Key Store ────────────────────────────────────────────────

import redis.asyncio as aioredis

_redis_client: Optional[aioredis.Redis] = None
REDIS_KEY_HASH = "public_api:keys"
DEFAULT_MIRROR_TARGETS = [
    ("sandbox-1", "1.ekklesia.gr", "https://1.ekklesia.gr"),
    ("sandbox-2", "2.ekklesia.gr", "https://2.ekklesia.gr"),
    ("sandbox-3", "3.ekklesia.gr", "https://3.ekklesia.gr"),
]
MIRROR_STATUS_CACHE_SECONDS = 20
_mirror_status_cache: dict[str, object] | None = None
_mirror_status_cache_until = 0.0


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis_client = aioredis.from_url(url, decode_responses=True)
    return _redis_client


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def verify_api_key(key: str) -> bool:
    r = await get_redis()
    return await r.hexists(REDIS_KEY_HASH, hash_key(key))


def _classify_mirror_status(checks: dict[str, bool]) -> str:
    """Return traffic-light state for a fixed read-only mirror."""
    if not checks.get("health"):
        return "offline"
    if checks.get("status") and checks.get("api"):
        return "online"
    return "degraded"


def _mirror_targets() -> list[tuple[str, str, str]]:
    """Return configured public read-only mirrors as id, label, base-url triples."""
    configured = os.getenv("MIRROR_READONLY_URLS")
    if configured:
        targets: list[tuple[str, str, str]] = []
        for index, raw_url in enumerate(configured.split(","), start=1):
            url = raw_url.strip().rstrip("/")
            if not url:
                continue
            host = url.split("://", 1)[-1].split("/", 1)[0]
            targets.append((f"sandbox-{index}", host, url))
        if targets:
            return targets

    legacy_url = os.getenv("MIRROR_SANDBOX_URL")
    if legacy_url:
        url = legacy_url.rstrip("/")
        host = url.split("://", 1)[-1].split("/", 1)[0]
        return [("sandbox-1", "1.ekklesia.gr", url if host == "1.ekklesia.gr" else url)]

    return DEFAULT_MIRROR_TARGETS


async def _mirror_get_ok(client: httpx.AsyncClient, url: str) -> bool:
    response = await client.get(url)
    return response.status_code == 200


async def _check_mirror_target(
    client: httpx.AsyncClient,
    mirror_id: str,
    name: str,
    base_url: str,
) -> dict[str, object]:
    checks = {"health": False, "status": False, "api": False}
    latency_ms: int | None = None
    started = time.monotonic()
    try:
        checks["health"] = await _mirror_get_ok(client, f"{base_url}/health")
        if checks["health"]:
            checks["status"] = await _mirror_get_ok(client, f"{base_url}/mirror-status.json")
            checks["api"] = await _mirror_get_ok(client, f"{base_url}/api/v1/bills?limit=1")
        latency_ms = int((time.monotonic() - started) * 1000)
    except httpx.HTTPError:
        latency_ms = int((time.monotonic() - started) * 1000)

    return {
        "id": mirror_id,
        "name": name,
        "url": base_url,
        "role": "sandbox-read-only-mirror",
        "status": _classify_mirror_status(checks),
        "latency_ms": latency_ms,
        "checks": checks,
    }


async def _build_mirror_status() -> dict[str, object]:
    global _mirror_status_cache, _mirror_status_cache_until

    now = time.monotonic()
    if _mirror_status_cache is not None and now < _mirror_status_cache_until:
        return _mirror_status_cache

    checked_at = datetime.now(timezone.utc)
    mirrors: list[dict[str, object]] = []
    try:
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
            for mirror_id, name, base_url in _mirror_targets():
                mirrors.append(await _check_mirror_target(client, mirror_id, name, base_url))
    except httpx.HTTPError as exc:
        logger.warning("mirror status check failed before target loop completed: %s", exc)

    payload: dict[str, object] = {
        "updated_at": checked_at.isoformat(),
        "cache_seconds": MIRROR_STATUS_CACHE_SECONDS,
        "mirrors": mirrors,
    }
    _mirror_status_cache = payload
    _mirror_status_cache_until = now + MIRROR_STATUS_CACHE_SECONDS
    return payload


# ── Rate Limiter (Redis fixed window, privacy-preserving IP buckets) ─────────


async def rate_limit_check(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """Dependency für Rate Limiting."""
    r = await get_redis()
    valid_key = bool(x_api_key and await verify_api_key(x_api_key))
    limit = 1000 if valid_key else 100
    if valid_key and x_api_key:
        rate_key = f"ratelimit:public_api:key:{hash_key(x_api_key)}"
    else:
        rate_key = rate_limit_key_for_ip(request, "public_api:anon")

    try:
        await redis_fixed_window_limit(r, rate_key, limit, 60)
    except HTTPException:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": limit,
                "window": "60s",
                "tip": "POST /api/v1/public/keys/generate for 1000 req/min"
            }
        )
    return x_api_key if valid_key else None


# ── API Key Management ────────────────────────────────────────────────────────

@router.post("/keys/generate")
async def generate_api_key(request: Request, label: str = "ekklesia-client"):
    """Generiert einen API Key — kein Konto nötig. Rate-limited: 5/hour per IP."""
    # Rate limit: max 5 key generations per hour per IP
    r = await get_redis()
    rate_key = rate_limit_key_for_ip(request, "public_api:keygen")
    try:
        await redis_fixed_window_limit(r, rate_key, 5, 3600)
    except HTTPException:
        raise HTTPException(status_code=429, detail="Zu viele Key-Generierungen. Max 5 pro Stunde.")
    key = f"ek_{secrets.token_urlsafe(32)}"
    hashed = hash_key(key)
    r = await get_redis()
    await r.hset(REDIS_KEY_HASH, hashed, json.dumps({
        "label":      label[:50],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))
    logger.info(f"[MOD-11] API Key generiert: label={label}")
    return {
        "api_key":    key,
        "label":      label,
        "rate_limit": "1000 req/min",
        "warning":    "Dieser Key wird nur einmal angezeigt. Sicher verwahren!",
        "usage":      "Header: X-API-Key: <key>",
    }


@router.get("/keys/status")
async def api_key_status(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Prüft Status des API Keys."""
    if not x_api_key:
        return {"authenticated": False, "rate_limit": "100 req/min"}

    hashed = hash_key(x_api_key)
    r = await get_redis()
    raw = await r.hget(REDIS_KEY_HASH, hashed)
    if not raw:
        raise HTTPException(401, "Ungültiger API Key")

    info = json.loads(raw)
    return {"authenticated": True, "label": info["label"], "rate_limit": "1000 req/min"}


# ── Public Endpoints ──────────────────────────────────────────────────────────

@router.get("/bills")
async def public_bills(
    status: Optional[str] = None,
    governance: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 20, offset: int = 0,
    _key=Depends(rate_limit_check),
    db: AsyncSession = Depends(get_db)
):
    """Alle Gesetzentwürfe — öffentlich, CC BY 4.0."""
    query = select(ParliamentBill).where(public_bill_filter()).order_by(
        func.coalesce(
            ParliamentBill.parliament_vote_date,
            ParliamentBill.submitted_date,
            ParliamentBill.created_at,
        ).desc().nullslast(),
        ParliamentBill.created_at.desc(),
    ).limit(min(limit, 100)).offset(offset)

    if status:
        try:
            query = query.where(ParliamentBill.status == BillStatus(status.upper()))
        except ValueError:
            raise HTTPException(400, f"Ungültiger Status: {status}")

    if governance:
        from models import GovernanceLevel
        try:
            query = query.where(ParliamentBill.governance_level == GovernanceLevel(governance.upper()))
        except ValueError:
            pass

    if source:
        query = query.where(ParliamentBill.source == source.upper())

    result = await db.execute(query)
    bills = result.scalars().all()

    return {
        "data": [{
            "id":                  b.id,
            "title_el":            b.title_el,
            "title_en":            b.title_en,
            "pill_el":             b.pill_el,
            "pill_en":             b.pill_en,
            "categories":          b.categories,
            "status":              b.status.value,
            "governance_level":    b.governance_level.value if b.governance_level else "NATIONAL",
            "vote_date":           b.parliament_vote_date.isoformat() if b.parliament_vote_date else None,
            "arweave_tx":          b.arweave_tx_id,
            "arweave_url":         f"https://arweave.net/{b.arweave_tx_id}" if b.arweave_tx_id else None,
            "source":              b.source or "PARLIAMENT",
            "diavgeia_ada":        b.diavgeia_ada,
            "results_visibility":  b.results_visibility or "HIDDEN",
            "consensus_score":     b.consensus_score,
            "consensus_count":     b.consensus_count or 0,
            "flag_count":          b.flag_count or 0,
        } for b in bills],
        "meta": {"total": len(bills), "limit": limit, "offset": offset,
                 "source": "ekklesia.gr", "license": "CC BY 4.0"},
    }


@router.get("/bills/{bill_id}/results")
async def public_bill_results(
    bill_id: str,
    _key=Depends(rate_limit_check),
    db: AsyncSession = Depends(get_db)
):
    """Citizen Vote Ergebnisse — öffentlich."""
    bill = await db.get(ParliamentBill, bill_id)
    if not bill or not is_public_bill(bill):
        raise HTTPException(404, f"Bill {bill_id} nicht gefunden")

    totals = await aggregate_bill_vote_totals(db, bill_id)
    yes = totals.yes
    no = totals.no
    abstain = totals.abstain
    unknown = totals.unknown
    total = totals.total

    def pct(n): return round(n / total * 100, 1) if total > 0 else 0.0

    divergence = None
    if total > 0 and bill.party_votes_parliament:
        yes_pct = yes / total
        parl_yes = sum(1 for v in bill.party_votes_parliament.values() if v in ("ΝΑΙ", "YES"))
        parl_no  = sum(1 for v in bill.party_votes_parliament.values() if v in ("ΟΧΙ", "NO"))
        divergence = round(abs(yes_pct - (1.0 if parl_yes >= parl_no else 0.0)), 3)

    return {
        "bill_id": bill_id, "title_el": bill.title_el, "status": bill.status.value,
        "citizen_votes": {
            "yes": yes,
            "no": no,
            "abstain": abstain,
            "unknown": unknown,
            "total": total,
            "tier1_total": totals.tier1_total,
            "zk_total": totals.zk_total,
            "yes_pct": pct(yes),
            "no_pct": pct(no),
            "abstain_pct": pct(abstain),
        },
        "parliament_votes": bill.party_votes_parliament,
        "divergence_score": divergence,
        "arweave_tx": bill.arweave_tx_id,
        "data_license": "CC BY 4.0", "source": "ekklesia.gr",
    }


@router.get("/stats")
async def public_stats(_key=Depends(rate_limit_check), db: AsyncSession = Depends(get_db)):
    """Plattform-Statistiken — öffentlich."""
    total_bills  = await db.scalar(
        select(func.count(ParliamentBill.id)).where(public_bill_with_demo_filter())
    ) or 0
    total_votes  = await db.scalar(
        select(func.count(CitizenVote.id))
        .join(ParliamentBill, CitizenVote.bill_id == ParliamentBill.id)
        .where(public_bill_filter(), ~CitizenVote.bill_id.like("DEMO-%"))
    ) or 0
    active_bills = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.status.in_([BillStatus.ACTIVE, BillStatus.WINDOW_24H]),
            public_bill_filter(),
        )
    ) or 0

    parliament_bills = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.source == "PARLIAMENT", public_bill_with_demo_filter()
        )
    ) or 0
    diavgeia_bills = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.source == "DIAVGEIA", public_bill_filter()
        )
    ) or 0
    archived_bills = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.status.in_([BillStatus.OPEN_END, BillStatus.PARLIAMENT_VOTED]),
            public_bill_with_demo_filter(),
        )
    ) or 0
    arweave_archived = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.arweave_tx_id.isnot(None), public_bill_filter()
        )
    ) or 0
    forum_topics = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.forum_topic_id.isnot(None), public_bill_with_demo_filter()
        )
    ) or 0

    return {
        "platform": "ekklesia.gr", "version": "Beta",
        "stats": {
            "total_bills": total_bills,
            "parliament_bills": parliament_bills,
            "diavgeia_bills": diavgeia_bills,
            "active_bills": active_bills,
            "archived_bills": archived_bills,
            "arweave_archived": arweave_archived,
            "total_votes": total_votes,
            "forum_topics": forum_topics,
        },
        "license": "MIT", "source_code": "https://github.com/NeaBouli/pnyx",
        "data_license": "CC BY 4.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/vaa/parties")
async def public_parties(_key=Depends(rate_limit_check), db: AsyncSession = Depends(get_db)):
    """Alle Parteien — öffentlich."""
    result = await db.execute(select(Party).order_by(Party.name_el))
    parties = result.scalars().all()
    return {
        "data": [{
            "id": p.id, "name_el": p.name_el, "name_en": p.name_en,
            "abbreviation": p.abbreviation, "color_hex": p.color_hex,
        } for p in parties],
        "data_license": "CC BY 4.0",
    }


@router.get("/cplm")
async def public_cplm(
    _key=Depends(rate_limit_check),
    db: AsyncSession = Depends(get_db),
):
    """CPLM — Citizens Political Liquid Mirror. Aggregate political position of society. CC BY 4.0."""
    from services.cplm import get_cplm_cached
    data = await get_cplm_cached(db)
    data["data_license"] = "CC BY 4.0"
    data["source"] = "ekklesia.gr"
    data["description"] = {
        "el": "Ο CPLM αντικατοπτρίζει την πολιτική θέση της κοινωνίας βάσει των ψήφων πολιτών. "
              "X = Οικονομία (Αριστερά/Δεξιά), Y = Κοινωνία (Αυταρχικό/Ελευθεριακό). "
              "Κλίμακα: -10 έως +10. Ανανεώνεται κάθε 6 ώρες.",
        "en": "The CPLM reflects society's political position based on citizen votes. "
              "X = Economy (Left/Right), Y = Society (Authoritarian/Libertarian). "
              "Scale: -10 to +10. Updated every 6 hours.",
    }
    return data


@router.get("/scraper/status")
async def public_scraper_status(db: AsyncSession = Depends(get_db)):
    """Public scraper & archival health status."""
    import redis.asyncio as aioredis
    import os
    from config import settings

    r = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"), decode_responses=True)

    last_run = await r.get("scraper:parliament:last_run") or None
    last_success = await r.get("scraper:parliament:last_success") or None

    # Bills stats
    total = await db.scalar(select(func.count(ParliamentBill.id)).where(public_bill_filter())) or 0
    with_arweave = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.arweave_tx_id.isnot(None), public_bill_filter()
        )
    ) or 0

    # Arweave balance
    arweave_balance = None
    try:
        if settings.arweave_wallet_path:
            import arweave
            w = arweave.Wallet(settings.arweave_wallet_path)
            arweave_balance = float(w.balance)
    except Exception:
        pass

    await r.aclose()
    return {
        "parliament_scraper": {
            "last_run": last_run,
            "last_success": last_success,
        },
        "bills_total": total,
        "arweave_archived": with_arweave,
        "arweave_balance_ar": arweave_balance,
    }


@router.get("/mirrors/status")
async def public_mirror_status():
    """Live read-only mirror health for the community page traffic light."""
    return await _build_mirror_status()


@router.post("/share")
async def record_share():
    """Anonymous share counter — no tracking, just a number."""
    import redis.asyncio as aioredis
    import os
    r = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"), decode_responses=True)
    count = await r.incr("stats:share_count")
    await r.aclose()
    return {"share_count": count}


@router.get("/cplm/history")
async def public_cplm_history(
    days: int = 30,
    _key=Depends(rate_limit_check),
):
    """CPLM historical snapshots. CC BY 4.0."""
    from services.cplm import get_cplm_history
    entries = await get_cplm_history(min(days, 365))
    return {"snapshots": entries, "count": len(entries), "data_license": "CC BY 4.0"}


@router.get("/representation")
async def public_representation(
    _key=Depends(rate_limit_check),
    db: AsyncSession = Depends(get_db),
):
    """Parliament Representativeness — cumulative divergence. CC BY 4.0."""
    from routers.analytics import compute_cumulative_representation
    try:
        data = await compute_cumulative_representation(db)
        data["data_license"] = "CC BY 4.0"
        data["source"] = "ekklesia.gr"
        return data
    except Exception:
        return {"error": "Representation data not available", "data_license": "CC BY 4.0"}


@router.get("/info")
async def api_info():
    """API Dokumentation + Endpoints Übersicht."""
    return {
        "name": "Ekklesia.gr Public API", "version": "1.0.0-beta",
        "description": "Ψηφιακή Άμεση Δημοκρατία — Public Data API",
        "license": "MIT (Code) + CC BY 4.0 (Data)",
        "source_code": "https://github.com/NeaBouli/pnyx",
        "docs": "/docs",
        "rate_limits": {
            "anonymous": "100 req/min", "with_key": "1000 req/min",
            "get_key": "POST /api/v1/public/keys/generate",
        },
        "endpoints": {
            "GET /api/v1/public/info":               "Diese Seite",
            "GET /api/v1/public/stats":              "Plattform Statistiken",
            "GET /api/v1/public/bills":              "Alle Gesetzentwürfe",
            "GET /api/v1/public/bills/{id}/results": "Abstimmungsergebnisse",
            "GET /api/v1/public/vaa/parties":        "Parteien",
            "GET /api/v1/public/cplm":              "CPLM — Political Mirror (X/Y Aggregate)",
            "GET /api/v1/public/cplm/history":      "CPLM Historical Snapshots",
            "GET /api/v1/public/representation":    "Parliament Representativeness",
            "GET /api/v1/public/mirrors/status":    "Read-only Mirror Health",
            "POST /api/v1/public/keys/generate":     "API Key generieren",
            "GET /api/v1/public/keys/status":        "API Key Status",
        },
        "data_policy": {
            "stored": ["nullifier_hash", "public_key", "vote_choice"],
            "never":  ["phone", "name", "ip_address", "individual_votes"],
            "arweave": "Full audit trail bei PARLIAMENT_VOTED",
        },
        "contact": "github.com/NeaBouli/pnyx/issues",
    }
