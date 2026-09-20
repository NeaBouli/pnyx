"""
MOD-01: Identity Router
POST /api/v1/identity/verify  — HLR SIM check → Ed25519 Keypair
POST /api/v1/identity/revoke  — Key Revokation
GET  /api/v1/identity/status  — Key Status prüfen
"""
import gc
import logging
import json
from datetime import date, datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import ColumnElement, or_, select, update, text
from sqlalchemy.sql import Select
import redis.asyncio as aioredis

from database import get_db
from models import Dimos, IdentityRecord, KeyStatus, Periferia

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages/crypto"))
sys.path.insert(0, "/packages/crypto")  # Docker container path
from keypair import generate_keypair, verify_signature
from nullifier import generate_nullifier_hash, generate_nullifier_hash_v2
from hlr import normalize_greek_number, verify_greek_number

from ip_utils import (
    hashed_rate_subject,
    rate_limit_key_for_ip,
    redis_fixed_window_limit,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/identity", tags=["MOD-01 Identity"])

# ─── HLR Credits Tracking (Redis) ────────────────────────────────────────────
# Primary: hlrlookup.com — 2499 credits (15€ = 2500, ~0.006€/query)
# Fallback: hlr-lookups.com — 1000 credits (10€ = 1000, 0.01€/query)
# Redis keys:
#   "hlr:hlrlookupcom:used" — tracks primary (hlrlookup.com) usage
#   "hlr:used"              — tracks fallback (hlr-lookups.com) usage (legacy key)

HLR_PRIMARY_INITIAL_CREDITS = 2499   # hlrlookup.com
HLR_PRIMARY_COST_PER_QUERY = 0.006   # ~0.006€
HLR_PRIMARY_REDIS_KEY = "hlr:hlrlookupcom:used"

HLR_FALLBACK_INITIAL_CREDITS = 1000  # hlr-lookups.com
HLR_FALLBACK_COST_PER_QUERY = 0.01   # 0.01€
HLR_FALLBACK_REDIS_KEY = "hlr:used"  # legacy key
IDENTITY_VERIFY_LOCK_TTL_SECONDS = 90

_hlr_redis: aioredis.Redis | None = None

async def _get_hlr_redis() -> aioredis.Redis:
    global _hlr_redis
    if _hlr_redis is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _hlr_redis = aioredis.from_url(url, decode_responses=True)
    return _hlr_redis

async def _increment_hlr_usage(providers: list[str]) -> int:
    """Increment the providers queried by this verification request."""
    r = await _get_hlr_redis()
    usage = 0
    for provider in dict.fromkeys(providers):
        if provider == "primary":
            usage = await r.incr(HLR_PRIMARY_REDIS_KEY)
        elif provider == "fallback":
            usage = await r.incr(HLR_FALLBACK_REDIS_KEY)
    return usage

async def _get_hlr_usage(key: str) -> int:
    r = await _get_hlr_redis()
    val = await r.get(key)
    return int(val) if val else 0


# ─── HLR Kosten-/Missbrauchsschutz (EKA-06) ──────────────────────────────────
# Dedizierte Redis-Limits VOR jedem kostenpflichtigen Provideraufruf.
# Keys enthalten ausschließlich gehashte Bucket-IDs (ip_utils), niemals rohe
# IP-Adressen oder Telefonnummern. Fail-closed: ohne Redis kein HLR-Aufruf.

HLR_VERIFY_IP_MINUTE_LIMIT = 5
HLR_VERIFY_IP_MINUTE_WINDOW_SECONDS = 60
HLR_VERIFY_IP_DAY_LIMIT = 20
HLR_VERIFY_NUMBER_COOLDOWN_SECONDS = 300
HLR_VERIFY_NUMBER_DAY_LIMIT = 3
HLR_VERIFY_DAY_WINDOW_SECONDS = 86400

_HLR_VERIFY_UNAVAILABLE_DETAIL = (
    "Η επαλήθευση είναι προσωρινά μη διαθέσιμη. Δοκιμάστε ξανά αργότερα."
)


async def _enforce_hlr_verify_limits(request: Request, normalized_number: str) -> None:
    """Fail-closed cost/abuse guard before any paid HLR provider call.

    Reihenfolge: Nummer-Cooldown → Nummer/Tag → IP/Minute → IP/Tag.
    Nummern-Limits zuerst, damit reine Wiederholungsversuche derselben Nummer
    die IP-Budgets nicht aufblähen; IP-Limits deckeln danach verteilte Angriffe.
    """
    today = date.today()
    number_hash = hashed_rate_subject(normalized_number, "hlr_verify:number", today=today)
    day = today.isoformat()
    try:
        r = await _get_hlr_redis()
        cooldown_set = await r.set(
            f"ratelimit:hlr_verify:number_cooldown:{day}:{number_hash}",
            "1",
            ex=HLR_VERIFY_NUMBER_COOLDOWN_SECONDS,
            nx=True,
        )
        if not cooldown_set:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Πολλές προσπάθειες για αυτόν τον αριθμό. Δοκιμάστε ξανά σε λίγα λεπτά.",
            )
        await redis_fixed_window_limit(
            r,
            f"ratelimit:hlr_verify:number_day:{day}:{number_hash}",
            HLR_VERIFY_NUMBER_DAY_LIMIT,
            HLR_VERIFY_DAY_WINDOW_SECONDS,
        )
        await redis_fixed_window_limit(
            r,
            rate_limit_key_for_ip(request, "hlr_verify:ip_min", today=today),
            HLR_VERIFY_IP_MINUTE_LIMIT,
            HLR_VERIFY_IP_MINUTE_WINDOW_SECONDS,
        )
        await redis_fixed_window_limit(
            r,
            rate_limit_key_for_ip(request, "hlr_verify:ip_day", today=today),
            HLR_VERIFY_IP_DAY_LIMIT,
            HLR_VERIFY_DAY_WINDOW_SECONDS,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "[MOD-01] HLR cost guard Redis unavailable — paid lookup blocked (fail-closed)",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_HLR_VERIFY_UNAVAILABLE_DETAIL,
        ) from exc


def _identity_kdf_version() -> str:
    version = os.getenv("IDENTITY_NULLIFIER_KDF_VERSION", "v1").lower()
    if version not in {"v1", "v2"}:
        logger.warning("[MOD-01] Unknown IDENTITY_NULLIFIER_KDF_VERSION=%s; falling back to v1", version)
        return "v1"
    return version


def _compatibility_nullifier(existing: IdentityRecord | None, computed_v1: str) -> str:
    if existing is not None:
        return existing.nullifier_hash
    return computed_v1


def _select_identity_match(matches: list[IdentityRecord], computed_v1: str) -> IdentityRecord | None:
    existing = next((record for record in matches if record.nullifier_hash == computed_v1), None)
    if existing is not None:
        return existing
    if matches:
        return matches[0]
    return None


def _identity_match_query(identity_filter: ColumnElement[bool]) -> Select:
    return select(IdentityRecord).where(identity_filter).with_for_update()


async def _acquire_identity_verify_lock(nullifier_hash: str) -> tuple[str, str]:
    """Acquire a short in-flight lock for one identity verification."""
    lock_key = f"identity:verify:lock:{nullifier_hash}"
    token = uuid4().hex
    r = await _get_hlr_redis()
    acquired = await r.set(lock_key, token, ex=IDENTITY_VERIFY_LOCK_TTL_SECONDS, nx=True)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Η επαλήθευση είναι ήδη σε εξέλιξη. Δοκιμάστε ξανά σε λίγα δευτερόλεπτα.",
        )
    return lock_key, token


async def _release_identity_verify_lock(lock_key: str, token: str) -> None:
    """Release only the lock owned by this request."""
    try:
        r = await _get_hlr_redis()
        await r.eval(
            """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            end
            return 0
            """,
            1,
            lock_key,
            token,
        )
    except Exception:
        logger.warning("[MOD-01] Failed to release identity verify lock %s", lock_key, exc_info=True)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    phone_number: str = Field(..., description="Griechische Mobilnummer (+30...)")
    age_group:    str | None = Field(None, description="AGE_18_25 .. AGE_65_PLUS")
    region:       str | None = Field(None, description="REG_ATTICA, REG_CRETE ...")
    gender_code:  str | None = Field(None, description="GENDER_MALE / FEMALE / DIVERSE / NO_ANSWER")

class VerifyResponse(BaseModel):
    success:         bool
    public_key_hex:  str
    private_key_hex: str   # Einmalig — Client muss sofort im Secure Enclave speichern
    nullifier_hash:  str
    message:         str

class RevokeRequest(BaseModel):
    nullifier_hash:  str
    phone_number:    str   # Zur erneuten Verifikation

class StatusRequest(BaseModel):
    nullifier_hash: str

class StatusResponse(BaseModel):
    status:     str
    created_at: str | None
    region_locked: bool = False
    periferia_id: int | None = None
    dimos_id: int | None = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/verify", response_model=VerifyResponse)
async def verify_identity(req: VerifyRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Beta-Flow:
    1. HLR Lookup → nur echte griechische Mobilnummern
    2. Nullifier Hash erzeugen (Telefonnummer danach gelöscht)
    3. Prüfen: existiert dieser Nullifier bereits?
    4. Ed25519 Keypair erzeugen
    5. Public Key + Nullifier speichern (KEIN Private Key, KEINE Telefonnummer)
    6. Private Key einmalig zurückgeben → Client speichert im Secure Enclave
    """

    # 0. Lokale Formatprüfung + Kosten-/Missbrauchsschutz (EKA-06) — vor jedem
    # kostenpflichtigen Provideraufruf. Ungültige Nummern werden lokal
    # abgelehnt, ohne Redis oder Provider zu berühren.
    normalized_number = normalize_greek_number(req.phone_number)
    if not normalized_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Μη έγκυρος αριθμός. Μόνο ελληνικοί αριθμοί κινητού.",
        )
    await _enforce_hlr_verify_limits(request, normalized_number)

    # 1. HLR Prüfung
    hlr_result = await verify_greek_number(req.phone_number)
    # Track HLR usage (even failed lookups cost a credit if not DRY_RUN)
    if hlr_result.get("status") != "DRY_RUN":
        await _increment_hlr_usage(hlr_result.get("_providers_queried", ["primary"]))
    if not hlr_result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=hlr_result["error"] or f"Μη έγκυρος αριθμός. Μόνο ελληνικοί αριθμοί κινητού."
        )

    # 2. Nullifier Hash (Telefonnummer wird in der Funktion sofort gelöscht)
    nullifier = generate_nullifier_hash(req.phone_number)  # v1 compatibility anchor
    lock_key, lock_token = await _acquire_identity_verify_lock(nullifier)
    try:
        kdf_version = _identity_kdf_version()
        nullifier_v2 = generate_nullifier_hash_v2(req.phone_number) if kdf_version == "v2" else None
        del req.phone_number
        gc.collect()

        # 3. Bestehenden Record prüfen
        identity_filter = IdentityRecord.nullifier_hash == nullifier
        if nullifier_v2:
            identity_filter = or_(IdentityRecord.nullifier_hash_v2 == nullifier_v2, identity_filter)
        result = await db.execute(_identity_match_query(identity_filter))
        matches = result.scalars().all()
        if len(matches) > 1:
            logger.warning("[MOD-01] Multiple identity rows matched v2 migration lookup; using v1-preferred anchor")
        existing = _select_identity_match(matches, nullifier)

        if existing and existing.status == KeyStatus.ACTIVE:
            # Re-register in one transaction so an interrupted key rotation cannot
            # leave a valid citizen identity stuck in REVOKED.
            logger.info("[MOD-01] Re-registering existing active key atomically")

        # If v2 matched a legacy row, keep the existing v1 nullifier_hash as the
        # public compatibility anchor for votes/status/downstream tables.
        compatibility_nullifier = _compatibility_nullifier(existing, nullifier)

        # 4. Keypair erzeugen
        keypair = generate_keypair()

        # 5. Demographischen Hash berechnen (optional, Beta)
        demographic_hash = None
        if req.age_group and req.region:
            from nullifier import generate_demographic_hash
            demographic_hash = generate_demographic_hash(
                req.age_group,
                req.region,
                req.gender_code or "GENDER_NO_ANSWER"
            )

        # 6. Nur Public Key + Nullifier speichern
        if existing:
            # Revoked record reaktivieren
            update_values = {
                "public_key_hex": keypair["public_key_hex"],
                "status": KeyStatus.ACTIVE,
                "demographic_hash": demographic_hash,
                "age_group": req.age_group,
                "region": req.region,
                "gender_code": req.gender_code,
                "revoked_at": None,
                "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
            }
            if nullifier_v2:
                update_values.update({
                    "nullifier_hash_v2": nullifier_v2,
                    "nullifier_version": "v2",
                    "nullifier_migrated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                })
            await db.execute(
                update(IdentityRecord)
                .where(IdentityRecord.id == existing.id)
                .values(**update_values)
            )
        else:
            record = IdentityRecord(
                nullifier_hash=nullifier,
                nullifier_hash_v2=nullifier_v2,
                nullifier_version="v2" if nullifier_v2 else "v1",
                nullifier_migrated_at=datetime.now(timezone.utc).replace(tzinfo=None) if nullifier_v2 else None,
                public_key_hex=keypair["public_key_hex"],
                demographic_hash=demographic_hash,
                age_group=req.age_group,
                region=req.region,
                gender_code=req.gender_code,
                status=KeyStatus.ACTIVE,
            )
            db.add(record)

        # Cascade: SurveyResponses (VAA — Art. 9 GDPR)
        await db.execute(
            text("DELETE FROM survey_responses WHERE user_hash = :nh"),
            {"nh": compatibility_nullifier}
        )
        await db.commit()

        # 7. Private Key einmalig zurückgeben — danach nie wieder verfügbar
        return VerifyResponse(
            success=True,
            public_key_hex=keypair["public_key_hex"],
            private_key_hex=keypair["private_key_hex"],
            nullifier_hash=compatibility_nullifier,
            message="Κλειδί δημιουργήθηκε. Αποθηκεύεται με ασφάλεια στη συσκευή σας. Δεν αποθηκεύεται στον server."
        )
    finally:
        await _release_identity_verify_lock(lock_key, lock_token)


@router.post("/revoke")
async def revoke_identity(req: RevokeRequest, db: AsyncSession = Depends(get_db)):
    """
    Key Revokation: alter Key wird ungültig, neuer Nullifier-Check.
    Telefonnummer wird nach Hash-Generierung sofort gelöscht.
    """
    new_nullifier = generate_nullifier_hash(req.phone_number)
    del req.phone_number
    gc.collect()

    if new_nullifier != req.nullifier_hash:
        raise HTTPException(status_code=400, detail="Ο Nullifier δεν αντιστοιχεί στον αριθμό.")

    result = await db.execute(
        select(IdentityRecord).where(IdentityRecord.nullifier_hash == new_nullifier)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Δεν βρέθηκε κλειδί για αυτόν τον αριθμό.")

    await db.execute(
        update(IdentityRecord)
        .where(IdentityRecord.nullifier_hash == new_nullifier)
        .values(status=KeyStatus.REVOKED, revoked_at=datetime.now(timezone.utc).replace(tzinfo=None))
    )
    await db.commit()

    return {"success": True, "message": "Το κλειδί ανακλήθηκε. Μπορείτε τώρα να επαληθευτείτε εκ νέου."}


@router.post("/status", response_model=StatusResponse)
async def check_status(req: StatusRequest, db: AsyncSession = Depends(get_db)):
    """Prüft ob ein Nullifier Hash aktiv oder revoziert ist."""
    result = await db.execute(
        select(IdentityRecord).where(IdentityRecord.nullifier_hash == req.nullifier_hash)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Nullifier nicht gefunden.")

    return StatusResponse(
        status=record.status.value,
        created_at=record.created_at.isoformat() if record.created_at else None,
        region_locked=record.region_locked if hasattr(record, 'region_locked') else False,
        periferia_id=record.periferia_id,
        dimos_id=record.dimos_id,
    )


# ─── HLR Credits Public Endpoint ─────────────────────────────────────────────

def _hlr_coarse_status(remaining: int) -> str:
    return "critical" if remaining < 50 else ("low" if remaining < 200 else "ok")


def _hlr_coarse_level(remaining: int, initial: int) -> str:
    """Grobe Kapazitätsstufe — keine exakten Guthaben oder Nutzungszahlen."""
    if remaining <= 0 or initial <= 0:
        return "empty"
    ratio = remaining / initial
    if ratio > 0.5:
        return "high"
    if ratio > 0.2:
        return "medium"
    return "low"


async def build_hlr_credits_snapshot() -> dict:
    """Interner exakter HLR-Snapshot — NICHT geroutet.

    Vollständiges bisheriges Schema (Flat-/primary-/fallback-Felder inklusive
    exakter Werte). Ausschließlich für geschützte Admin-Konsumenten;
    öffentliche Endpunkte geben nur grobe Projektionen zurück.
    """
    primary_used = await _get_hlr_usage(HLR_PRIMARY_REDIS_KEY)
    fallback_used = await _get_hlr_usage(HLR_FALLBACK_REDIS_KEY)

    primary_remaining = max(0, HLR_PRIMARY_INITIAL_CREDITS - primary_used)
    fallback_remaining = max(0, HLR_FALLBACK_INITIAL_CREDITS - fallback_used)

    primary_balance_eur = round(primary_remaining * HLR_PRIMARY_COST_PER_QUERY, 2)
    fallback_balance_eur = round(fallback_remaining * HLR_FALLBACK_COST_PER_QUERY, 2)

    primary_status = _hlr_coarse_status(primary_remaining)
    fallback_status = _hlr_coarse_status(fallback_remaining)

    # Failover status from Redis
    r = await _get_hlr_redis()
    failover_active = (await r.get("hlr:failover:active")) == "true"
    failover_reason = await r.get("hlr:failover:reason")

    fallback_enabled = os.getenv("HLR_FALLBACK_ENABLED", "false").lower() == "true"
    fallback_configured = bool(os.getenv("HLRLOOKUPS_API_KEY"))

    # Flat fields for backward compat: show primary (hlrlookup.com)
    return {
        # ── Rückwärtskompatibilität (flat) ──
        "initial": HLR_PRIMARY_INITIAL_CREDITS,
        "used": primary_used,
        "remaining": primary_remaining,
        "balance_eur": primary_balance_eur,
        "cost_per_query_eur": HLR_PRIMARY_COST_PER_QUERY,
        "status": primary_status,
        # ── Detaillierte Provider-Struktur ──
        "primary": {
            "provider": "hlrlookup.com",
            "initial": HLR_PRIMARY_INITIAL_CREDITS,
            "used": primary_used,
            "remaining": primary_remaining,
            "balance_eur": primary_balance_eur,
            "cost_per_query_eur": HLR_PRIMARY_COST_PER_QUERY,
            "status": primary_status,
        },
        "fallback": {
            "provider": "hlr-lookups.com",
            "enabled": fallback_enabled,
            "configured": fallback_configured,
            "initial": HLR_FALLBACK_INITIAL_CREDITS,
            "used": fallback_used,
            "remaining": fallback_remaining,
            "balance_eur": fallback_balance_eur,
            "cost_per_query_eur": HLR_FALLBACK_COST_PER_QUERY,
            "status": fallback_status,
        },
        "failover_active": failover_active,
        "failover_reason": failover_reason,
    }


@router.get("/hlr/credits")
async def hlr_credits():
    """
    Öffentlicher Endpoint — grober HLR-Betriebszustand für die Community-Kachel.

    Datensparsam (EKA-06): keine exakten Guthaben, Nutzungszahlen,
    Euro-Beträge, Kosten pro Anfrage, Providernamen, Konfigurationsdetails
    oder Failover-Gründe. Nur grobe Zustände:
    status (ok|low|critical), level (high|medium|low|empty).
    """
    snapshot = await build_hlr_credits_snapshot()
    primary = snapshot["primary"]
    fallback = snapshot["fallback"]

    fallback_usable = fallback["enabled"] and fallback["configured"] and fallback["remaining"] > 0

    # Flat fields describe the currently active verification path.
    active = fallback if snapshot["failover_active"] else primary

    return {
        "status": active["status"],
        "level": _hlr_coarse_level(active["remaining"], active["initial"]),
        "primary": {
            "status": primary["status"],
            "level": _hlr_coarse_level(primary["remaining"], primary["initial"]),
        },
        "fallback": {
            "status": fallback["status"],
            "level": _hlr_coarse_level(fallback["remaining"], fallback["initial"]),
        },
        "failover_active": snapshot["failover_active"],
        "verification_available": primary["remaining"] > 0 or fallback_usable,
    }


# ─── Profile Location Sync ────────────────────────────────────────────────────

class LocationUpdateRequest(BaseModel):
    nullifier_hash: str = Field(..., min_length=16, max_length=64)
    periferia_id: int | None = None
    dimos_id: int | None = None
    signature_hex: str = Field(..., min_length=128, max_length=128)


@router.patch("/profile/location")
async def update_profile_location(
    req: LocationUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Sync user's declared Dimos/Periferia to server.
    Enables vote scope enforcement for MUNICIPAL/REGIONAL bills.
    No PII stored — only integer IDs linked to anonymous nullifier.
    """
    # Find identity
    result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        ).with_for_update()
    )
    identity = result.scalar_one_or_none()
    if not identity:
        raise HTTPException(403, "Nullifier nicht gefunden oder revoziert.")

    payload = (
        f"profile-location:{req.periferia_id or 0}:{req.dimos_id or 0}:"
        f"{req.nullifier_hash}"
    ).encode()
    if not verify_signature(identity.public_key_hex, payload, req.signature_hex):
        raise HTTPException(401, "Μη έγκυρη υπογραφή γεωγραφικού προφίλ.")

    # Region lock: einmalig setzbar, danach gesperrt
    if identity.region_locked:
        raise HTTPException(
            403,
            "Ο εκλογικός σας κύκλος έχει ήδη οριστεί και δεν μπορεί να αλλαχθεί."
        )

    requested_periferia = req.periferia_id if req.periferia_id and req.periferia_id > 0 else None
    requested_dimos = req.dimos_id if req.dimos_id and req.dimos_id > 0 else None

    # Validate against authoritative geography and derive the Periferia from the
    # Dimos. A client must not be able to create an impossible location pair.
    if requested_dimos is not None:
        dimos_result = await db.execute(
            select(Dimos).where(Dimos.id == requested_dimos, Dimos.is_active.is_(True))
        )
        dimos = dimos_result.scalar_one_or_none()
        if dimos is None:
            raise HTTPException(400, "Ο επιλεγμένος Δήμος δεν είναι έγκυρος.")
        if requested_periferia is not None and requested_periferia != dimos.periferia_id:
            raise HTTPException(400, "Ο Δήμος δεν ανήκει στην επιλεγμένη Περιφέρεια.")
        requested_periferia = dimos.periferia_id
    elif requested_periferia is not None:
        periferia_result = await db.execute(
            select(Periferia).where(
                Periferia.id == requested_periferia,
                Periferia.is_active.is_(True),
            )
        )
        if periferia_result.scalar_one_or_none() is None:
            raise HTTPException(400, "Η επιλεγμένη Περιφέρεια δεν είναι έγκυρη.")

    identity.periferia_id = requested_periferia
    identity.dimos_id = requested_dimos

    # Lock after first meaningful set
    if identity.periferia_id or identity.dimos_id:
        identity.region_locked = True

    await db.commit()

    return {
        "success": True,
        "periferia_id": identity.periferia_id,
        "dimos_id": identity.dimos_id,
        "region_locked": identity.region_locked,
    }
