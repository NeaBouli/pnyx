"""
MOD-01: Identity Router
POST /api/v1/identity/verify  — HLR SIM check → Ed25519 Keypair
POST /api/v1/identity/revoke  — Key Revokation
GET  /api/v1/identity/status  — Key Status prüfen
POST /api/v2/identity/verify  — HLR check + device-generated key with PoP (EVA-001, flag IDENTITY_V2_ENABLED)
POST /api/v2/identity/rotate-key — key swap signed by old + new key (EVA-001 PR2, flag IDENTITY_ROTATE_ENABLED)
"""
import gc
import re
import logging
import json
from datetime import date, datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import ColumnElement, or_, select, update, text
from sqlalchemy.exc import IntegrityError
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

from rate_limit import limiter
from ip_utils import (
    hashed_rate_subject,
    rate_limit_key_for_ip,
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

_HLR_VERIFY_LIMITS_LUA = """
local cooldown_exists = redis.call("EXISTS", KEYS[1])
local number_day = tonumber(redis.call("GET", KEYS[2]) or "0")
local ip_minute = tonumber(redis.call("GET", KEYS[3]) or "0")
local ip_day = tonumber(redis.call("GET", KEYS[4]) or "0")

if cooldown_exists == 1 then return -1 end
if number_day >= tonumber(ARGV[2]) then return -2 end
if ip_minute >= tonumber(ARGV[4]) then return -3 end
if ip_day >= tonumber(ARGV[6]) then return -4 end

redis.call("SET", KEYS[1], "1", "EX", ARGV[1])

local number_day_new = redis.call("INCR", KEYS[2])
if number_day_new == 1 then redis.call("EXPIRE", KEYS[2], ARGV[3]) end

local ip_minute_new = redis.call("INCR", KEYS[3])
if ip_minute_new == 1 then redis.call("EXPIRE", KEYS[3], ARGV[5]) end

local ip_day_new = redis.call("INCR", KEYS[4])
if ip_day_new == 1 then redis.call("EXPIRE", KEYS[4], ARGV[7]) end

return 1
"""


async def _enforce_hlr_verify_limits(request: Request, normalized_number: str) -> None:
    """Fail-closed cost/abuse guard before any paid HLR provider call.

    Alle vier Limits werden atomar geprüft. Redis verändert Cooldown und
    Zähler nur, wenn der gesamte Versuch zulässig ist.
    """
    today = date.today()
    number_hash = hashed_rate_subject(normalized_number, "hlr_verify:number", today=today)
    day = today.isoformat()
    cooldown_key = f"ratelimit:hlr_verify:number_cooldown:{day}:{number_hash}"
    number_day_key = f"ratelimit:hlr_verify:number_day:{day}:{number_hash}"
    ip_minute_key = rate_limit_key_for_ip(request, "hlr_verify:ip_min", today=today)
    ip_day_key = rate_limit_key_for_ip(request, "hlr_verify:ip_day", today=today)
    try:
        r = await _get_hlr_redis()
        result = int(
            await r.eval(
                _HLR_VERIFY_LIMITS_LUA,
                4,
                cooldown_key,
                number_day_key,
                ip_minute_key,
                ip_day_key,
                HLR_VERIFY_NUMBER_COOLDOWN_SECONDS,
                HLR_VERIFY_NUMBER_DAY_LIMIT,
                HLR_VERIFY_DAY_WINDOW_SECONDS,
                HLR_VERIFY_IP_MINUTE_LIMIT,
                HLR_VERIFY_IP_MINUTE_WINDOW_SECONDS,
                HLR_VERIFY_IP_DAY_LIMIT,
                HLR_VERIFY_DAY_WINDOW_SECONDS,
            )
        )
        if result == -1:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Πολλές προσπάθειες για αυτόν τον αριθμό. Δοκιμάστε ξανά σε λίγα λεπτά.",
            )
        if result < 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Πάρα πολλές προσπάθειες επαλήθευσης. Δοκιμάστε ξανά αργότερα.",
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
    age_group:    str | None = Field(None, description="Legacy: akzeptiert, wird nicht gespeichert (EVA-002)")
    region:       str | None = Field(None, description="Legacy: akzeptiert, wird nicht gespeichert (EVA-002)")
    gender_code:  str | None = Field(None, description="Legacy: akzeptiert, wird nicht gespeichert (EVA-002)")

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

async def _find_identity(db: AsyncSession, nullifier: str, nullifier_v2: str | None) -> IdentityRecord | None:
    """Identity row for a v1 anchor and/or v2 nullifier (v1-preferred)."""
    identity_filter = IdentityRecord.nullifier_hash == nullifier
    if nullifier_v2:
        identity_filter = or_(IdentityRecord.nullifier_hash_v2 == nullifier_v2, identity_filter)
    result = await db.execute(_identity_match_query(identity_filter))
    matches = result.scalars().all()
    if len(matches) > 1:
        logger.warning("[MOD-01] Multiple identity rows matched v2 migration lookup; using v1-preferred anchor")
    return _select_identity_match(matches, nullifier)


def _is_active_key_conflict(exc: IntegrityError) -> bool:
    """Only a unique violation of the ACTIVE-public-key index (PostgreSQL names
    the index; SQLite names the column of the unique constraint)."""
    message = str(exc.orig)
    return (
        "uq_identity_records_active_public_key" in message
        or "UNIQUE constraint failed: identity_records.public_key_hex" in message
    )


def _identity_active_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="IDENTITY_ACTIVE: Η ταυτότητα είναι ήδη ενεργή. / Identity already active.",
    )


async def _register_identity(
    req: "VerifyRequest",
    request: Request,
    db: AsyncSession,
    *,
    client_public_key_hex: str | None = None,
) -> tuple[str, str | None, str]:
    """Shared registration flow for v1 and v2 (EVA-001).

    v1 (client_public_key_hex is None): the server generates the key pair and
    returns the private key once — unchanged legacy behaviour.
    v2: the client already proved possession of client_public_key_hex; the
    server stores only that public key and never sees a private key. Per D3 an
    ACTIVE identity is never re-keyed here (409, use rotate-key); REVOKED or
    unknown identities are (re)activated with the client key.

    Returns (public_key_hex, private_key_hex or None, compatibility_nullifier).
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

    precomputed: tuple[str, str | None] | None = None
    if client_public_key_hex is not None:
        # v2 preflight (EVA-001 review): rejections the database already decides
        # happen after the rate limits but before the paid HLR call.
        if await _public_key_active(db, client_public_key_hex):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PUBLIC_KEY_IN_USE")
        pre_v1 = generate_nullifier_hash(req.phone_number)
        pre_v2 = generate_nullifier_hash_v2(req.phone_number) if _identity_kdf_version() == "v2" else None
        precomputed = (pre_v1, pre_v2)
        pre_existing = await _find_identity(db, pre_v1, pre_v2)
        if pre_existing and pre_existing.status == KeyStatus.ACTIVE:
            raise _identity_active_error()

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
    if precomputed is None:
        nullifier = generate_nullifier_hash(req.phone_number)  # v1 compatibility anchor
    else:
        nullifier = precomputed[0]
    lock_key, lock_token = await _acquire_identity_verify_lock(nullifier)
    try:
        if precomputed is None:
            kdf_version = _identity_kdf_version()
            nullifier_v2 = generate_nullifier_hash_v2(req.phone_number) if kdf_version == "v2" else None
        else:
            nullifier_v2 = precomputed[1]
        del req.phone_number
        gc.collect()

        # 3. Bestehenden Record prüfen
        existing = await _find_identity(db, nullifier, nullifier_v2)

        if client_public_key_hex is not None and existing and existing.status == KeyStatus.ACTIVE:
            # D3: a key swap on an ACTIVE identity needs the old key's signature
            # (rotate-key); HLR alone must not replace it in v2. Re-checked here
            # under the per-nullifier lock (the preflight can race).
            raise _identity_active_error()
        if client_public_key_hex is not None and await _public_key_active(db, client_public_key_hex):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PUBLIC_KEY_IN_USE")

        if existing and existing.status == KeyStatus.ACTIVE:
            # Re-register in one transaction so an interrupted key rotation cannot
            # leave a valid citizen identity stuck in REVOKED.
            logger.info("[MOD-01] Re-registering existing active key atomically")

        # If v2 matched a legacy row, keep the existing v1 nullifier_hash as the
        # public compatibility anchor for votes/status/downstream tables.
        compatibility_nullifier = _compatibility_nullifier(existing, nullifier)

        # 4. Keypair: v1 erzeugt serverseitig, v2 nutzt den Client-Schlüssel
        if client_public_key_hex is None:
            keypair = generate_keypair()
        else:
            keypair = {"public_key_hex": client_public_key_hex, "private_key_hex": None}

        # 5. Roh-Demographie (EVA-002): Felder aus alten App-Versionen werden
        # akzeptiert, aber nie persistiert — nur Public Key + Nullifier.
        if req.age_group or req.region or req.gender_code:
            logger.info("[MOD-01] demographic fields supplied and discarded")

        try:
            # 6. Nur Public Key + Nullifier speichern
            if existing:
                # Revoked record reaktivieren — Legacy-Demographie (falls aus
                # alten Releases vorhanden) wird dabei mitgelöscht.
                update_values = {
                    "public_key_hex": keypair["public_key_hex"],
                    "status": KeyStatus.ACTIVE,
                    "demographic_hash": None,
                    "age_group": None,
                    "region": None,
                    "gender_code": None,
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
                    status=KeyStatus.ACTIVE,
                )
                db.add(record)

            # Cascade: SurveyResponses (VAA — Art. 9 GDPR)
            await db.execute(
                text("DELETE FROM survey_responses WHERE user_hash = :nh"),
                {"nh": compatibility_nullifier}
            )
            await db.commit()
        except IntegrityError as exc:
            # Backstop for the per-key lock (lease expiry): the partial unique
            # index allows one ACTIVE identity per public key. Covers the
            # UPDATE, autoflush and commit; other integrity errors re-raise.
            await db.rollback()
            if client_public_key_hex is not None and _is_active_key_conflict(exc):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PUBLIC_KEY_IN_USE") from None
            raise

        return keypair["public_key_hex"], keypair["private_key_hex"], compatibility_nullifier
    finally:
        await _release_identity_verify_lock(lock_key, lock_token)




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

    public_key_hex, private_key_hex, nullifier_hash = await _register_identity(req, request, db)
    # 7. Private Key einmalig zurückgeben — danach nie wieder verfügbar
    return VerifyResponse(
        success=True,
        public_key_hex=public_key_hex,
        private_key_hex=private_key_hex,
        nullifier_hash=nullifier_hash,
        message="Κλειδί δημιουργήθηκε. Αποθηκεύεται με ασφάλεια στη συσκευή σας. Δεν αποθηκεύεται στον server."
    )


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
        .values(
            status=KeyStatus.REVOKED,
            revoked_at=datetime.now(timezone.utc).replace(tzinfo=None),
            # EVA-002: Datenminimierung — Roh-Demographie bei Revokation löschen
            demographic_hash=None,
            age_group=None,
            region=None,
            gender_code=None,
        )
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


# ─── EVA-001 v2: client-generated keys with proof of possession ──────────────
# The device generates its Ed25519 key; the server receives only the public key
# plus a signature over a domain-separated registration message (PoP). The
# private key never leaves the device. Disabled unless IDENTITY_V2_ENABLED=true.

router_v2 = APIRouter(prefix="/api/v2/identity", tags=["MOD-01 Identity"])

IDENTITY_POP_WINDOW_MS = 5 * 60 * 1000
_HEX64 = re.compile(r"[0-9a-f]{64}")
_HEX128 = re.compile(r"[0-9a-f]{128}")


def identity_v2_enabled() -> bool:
    return os.getenv("IDENTITY_V2_ENABLED", "false").strip().lower() == "true"


def identity_register_pop_message(public_key_hex: str, pop_timestamp_ms: int) -> str:
    """Domain-separated, versioned PoP message; never contains the phone number."""
    return f"ekklesia:identity-register:v1:{public_key_hex}:{pop_timestamp_ms}"


class VerifyV2Request(VerifyRequest):
    public_key_hex:    str = Field(..., description="Ed25519 public key, 64 lowercase hex")
    pop_timestamp_ms:  int = Field(..., description="Client time (ms) signed in the PoP message")
    pop_signature_hex: str = Field(..., description="Ed25519 signature (128 lowercase hex) over the PoP message")


class VerifyV2Response(BaseModel):
    # Deliberately no private key field: the server never holds one in v2.
    success:        bool
    public_key_hex: str
    nullifier_hash: str
    message:        str


async def _public_key_active(db: AsyncSession, public_key_hex: str) -> bool:
    result = await db.execute(
        select(IdentityRecord.id)
        .where(IdentityRecord.public_key_hex == public_key_hex)
        .where(IdentityRecord.status == KeyStatus.ACTIVE)
        .limit(1)
    )
    return result.first() is not None


def _check_registration_pop(req: VerifyV2Request, now_ms: int) -> None:
    """Reject malformed, stale or unsigned registrations (all before HLR)."""
    if not _HEX64.fullmatch(req.public_key_hex) or not _HEX128.fullmatch(req.pop_signature_hex):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_KEY_FORMAT")
    if abs(now_ms - req.pop_timestamp_ms) > IDENTITY_POP_WINDOW_MS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="POP_EXPIRED")
    message = identity_register_pop_message(req.public_key_hex, req.pop_timestamp_ms)
    if not verify_signature(req.public_key_hex, message, req.pop_signature_hex):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_POP_SIGNATURE")


@router_v2.post("/verify", response_model=VerifyV2Response)
async def verify_identity_v2(req: VerifyV2Request, request: Request, db: AsyncSession = Depends(get_db)):
    """EVA-001: register a device-generated public key after HLR verification."""
    # One in-flight registration per public key: different phone numbers take
    # different nullifier locks, so without this a replayed PoP could bind the
    # same key to two identities concurrently (EVA-001 review).
    # The unique index uq_identity_records_active_public_key is the backstop
    # if this lease expires before commit.
    try:
        if not identity_v2_enabled():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        _check_registration_pop(req, int(datetime.now(timezone.utc).timestamp() * 1000))
        try:
            pk_lock_key, pk_lock_token = await _acquire_identity_verify_lock(f"pk:{req.public_key_hex}")
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("[MOD-01] identity key lock Redis unavailable (fail-closed)", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_HLR_VERIFY_UNAVAILABLE_DETAIL,
            ) from exc
        try:
            public_key_hex, _private, nullifier_hash = await _register_identity(
                req, request, db, client_public_key_hex=req.public_key_hex,
            )
        finally:
            await _release_identity_verify_lock(pk_lock_key, pk_lock_token)
    finally:
        # Never keep the raw number on the request object, also on early exits.
        if "phone_number" in req.__dict__:
            del req.phone_number
            gc.collect()
    return VerifyV2Response(
        success=True,
        public_key_hex=public_key_hex,
        nullifier_hash=nullifier_hash,
        message="Η ταυτότητα επαληθεύτηκε. Το ιδιωτικό κλειδί δημιουργήθηκε στη συσκευή σας και δεν φεύγει ποτέ από αυτήν.",
    )


# ─── EVA-001 PR2: key rotation authorised by the old key ─────────────────────
# D3: an ACTIVE identity changes its key only with the current key's signature.
# The message is signed by BOTH keys (old = authorisation, new = possession);
# the swap is a compare-and-swap on the current key, so a replayed message is a
# no-op once the key moved on. No HLR, no phone, no key history (D4).
# Disabled unless IDENTITY_ROTATE_ENABLED=true.

def identity_rotate_enabled() -> bool:
    return os.getenv("IDENTITY_ROTATE_ENABLED", "false").strip().lower() == "true"


def identity_rotate_message(nullifier_hash: str, old_public_key_hex: str, new_public_key_hex: str, timestamp_ms: int) -> str:
    """Domain-separated, versioned rotation message signed by both keys."""
    return f"ekklesia:identity-rotate:v1:{nullifier_hash}:{old_public_key_hex}:{new_public_key_hex}:{timestamp_ms}"


class RotateKeyRequest(BaseModel):
    nullifier_hash:     str
    old_public_key_hex: str
    new_public_key_hex: str
    timestamp_ms:       int
    old_signature_hex:  str
    new_signature_hex:  str


class RotateKeyResponse(BaseModel):
    success:         bool
    public_key_hex:  str
    already_rotated: bool = False


_ROTATION_CONFLICT = "ROTATION_CONFLICT"


@router_v2.post("/rotate-key", response_model=RotateKeyResponse)
@limiter.limit("10/minute")
async def rotate_identity_key(req: RotateKeyRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Swap the public key of an ACTIVE identity (EVA-001 PR2)."""
    if not identity_rotate_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    if not (
        _HEX64.fullmatch(req.nullifier_hash)
        and _HEX64.fullmatch(req.old_public_key_hex)
        and _HEX64.fullmatch(req.new_public_key_hex)
        and _HEX128.fullmatch(req.old_signature_hex)
        and _HEX128.fullmatch(req.new_signature_hex)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_KEY_FORMAT")
    if req.old_public_key_hex == req.new_public_key_hex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SAME_KEY")
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if abs(now_ms - req.timestamp_ms) > IDENTITY_POP_WINDOW_MS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="POP_EXPIRED")
    message = identity_rotate_message(req.nullifier_hash, req.old_public_key_hex, req.new_public_key_hex, req.timestamp_ms)
    if not (
        verify_signature(req.old_public_key_hex, message, req.old_signature_hex)
        and verify_signature(req.new_public_key_hex, message, req.new_signature_hex)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_SIGNATURE")

    # Compare-and-swap: only the identity whose CURRENT key is the old key.
    # Unknown nullifier, wrong old key, REVOKED identity and already-rotated
    # (replayed) requests all give the same 409, so the endpoint reveals nothing
    # beyond what the old key's holder already knows.
    try:
        result = await db.execute(
            update(IdentityRecord)
            .where(IdentityRecord.nullifier_hash == req.nullifier_hash)
            .where(IdentityRecord.public_key_hex == req.old_public_key_hex)
            .where(IdentityRecord.status == KeyStatus.ACTIVE)
            .values(public_key_hex=req.new_public_key_hex)
            .returning(IdentityRecord.id)
        )
        record_id = result.scalar_one_or_none()
        if record_id is None:
            await db.rollback()
            # Idempotent retry (EVA-001 PR4 crash recovery): the identity already
            # carries the new key. The caller proved possession of both keys, so
            # confirming this reveals nothing new; no second audit row.
            current = await db.execute(
                select(IdentityRecord.id)
                .where(IdentityRecord.nullifier_hash == req.nullifier_hash)
                .where(IdentityRecord.public_key_hex == req.new_public_key_hex)
                .where(IdentityRecord.status == KeyStatus.ACTIVE)
            )
            if current.first() is not None:
                return RotateKeyResponse(success=True, public_key_hex=req.new_public_key_hex, already_rotated=True)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_ROTATION_CONFLICT)
        await db.execute(
            text(
                "INSERT INTO audit_log (action, actor, target_type, target_id) "
                "VALUES ('identity.key_rotated', 'identity_holder', 'identity_record', :rid)"
            ),
            {"rid": str(record_id)},
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_active_key_conflict(exc):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PUBLIC_KEY_IN_USE") from None
        raise

    logger.info("[MOD-01] identity key rotated (record %s)", record_id)
    return RotateKeyResponse(success=True, public_key_hex=req.new_public_key_hex)
