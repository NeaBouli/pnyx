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
import json
import secrets
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from database import get_db
from models import (
    ParliamentBill, CitizenVote, Party,
    BillStatus, VoteChoice
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/public", tags=["MOD-11 Public API"])


# ── Redis-backed API Key Store ────────────────────────────────────────────────

import redis.asyncio as aioredis
import os

_redis_client: Optional[aioredis.Redis] = None
REDIS_KEY_HASH = "public_api:keys"


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


# ── Rate Limiter (In-Memory — acceptable for single-instance) ────────────────

request_counts: dict = defaultdict(list)

def check_rate_limit(identifier: str, limit: int) -> bool:
    now = time.time()
    request_counts[identifier] = [
        t for t in request_counts[identifier] if now - t < 60
    ]
    if len(request_counts[identifier]) >= limit:
        return False
    request_counts[identifier].append(now)
    return True


async def rate_limit_check(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """Dependency für Rate Limiting."""
    identifier = x_api_key if x_api_key else (request.client.host if request.client else "unknown")
    limit = 1000 if (x_api_key and await verify_api_key(x_api_key)) else 100
    if not check_rate_limit(identifier, limit):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": limit,
                "window": "60s",
                "tip": "POST /api/v1/public/keys/generate for 1000 req/min"
            }
        )
    return x_api_key


# ── API Key Management ────────────────────────────────────────────────────────

@router.post("/keys/generate")
async def generate_api_key(label: str = "ekklesia-client"):
    """Generiert einen API Key — kein Konto nötig."""
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
    limit: int = 20, offset: int = 0,
    _key=Depends(rate_limit_check),
    db: AsyncSession = Depends(get_db)
):
    """Alle Gesetzentwürfe — öffentlich, CC BY 4.0."""
    query = select(ParliamentBill).order_by(
        ParliamentBill.parliament_vote_date.desc().nullslast()
    ).limit(min(limit, 100)).offset(offset)

    if status:
        try:
            query = query.where(ParliamentBill.status == BillStatus(status.upper()))
        except ValueError:
            raise HTTPException(400, f"Ungültiger Status: {status}")

    result = await db.execute(query)
    bills = result.scalars().all()

    return {
        "data": [{
            "id":         b.id,
            "title_el":   b.title_el,
            "title_en":   b.title_en,
            "pill_el":    b.pill_el,
            "pill_en":    b.pill_en,
            "categories": b.categories,
            "status":     b.status.value,
            "vote_date":  b.parliament_vote_date.isoformat() if b.parliament_vote_date else None,
            "arweave_tx": b.arweave_tx_id,
            "arweave_url": f"https://arweave.net/{b.arweave_tx_id}" if b.arweave_tx_id else None,
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
    if not bill:
        raise HTTPException(404, f"Bill {bill_id} nicht gefunden")

    yes     = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.YES)) or 0
    no      = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.NO)) or 0
    abstain = await db.scalar(select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill_id, CitizenVote.vote == VoteChoice.ABSTAIN)) or 0
    total = yes + no + abstain

    def pct(n): return round(n / total * 100, 1) if total > 0 else 0.0

    divergence = None
    if total > 0 and bill.party_votes_parliament:
        yes_pct = yes / total
        parl_yes = sum(1 for v in bill.party_votes_parliament.values() if v in ("ΝΑΙ", "YES"))
        parl_no  = sum(1 for v in bill.party_votes_parliament.values() if v in ("ΟΧΙ", "NO"))
        divergence = round(abs(yes_pct - (1.0 if parl_yes >= parl_no else 0.0)), 3)

    return {
        "bill_id": bill_id, "title_el": bill.title_el, "status": bill.status.value,
        "citizen_votes": {"yes": yes, "no": no, "abstain": abstain, "total": total,
                          "yes_pct": pct(yes), "no_pct": pct(no), "abstain_pct": pct(abstain)},
        "parliament_votes": bill.party_votes_parliament,
        "divergence_score": divergence,
        "arweave_tx": bill.arweave_tx_id,
        "data_license": "CC BY 4.0", "source": "ekklesia.gr",
    }


@router.get("/stats")
async def public_stats(_key=Depends(rate_limit_check), db: AsyncSession = Depends(get_db)):
    """Plattform-Statistiken — öffentlich."""
    total_bills  = await db.scalar(select(func.count(ParliamentBill.id))) or 0
    total_votes  = await db.scalar(select(func.count(CitizenVote.id))) or 0
    active_bills = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.status.in_([BillStatus.ACTIVE, BillStatus.WINDOW_24H])
        )
    ) or 0

    return {
        "platform": "ekklesia.gr", "version": "Beta",
        "stats": {"total_bills": total_bills, "active_bills": active_bills, "total_votes": total_votes},
        "license": "MIT", "source_code": "https://github.com/NeaBouli/pnyx",
        "data_license": "CC BY 4.0",
        "arweave_wallet": "2hkK3Bcr6garERqyBCLCiJ-d8zZzM5ZWe3_AzGdhBTs",
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
