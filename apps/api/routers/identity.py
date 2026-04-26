"""
MOD-01: Identity Router
POST /api/v1/identity/verify  — SMS Verifikation → Ed25519 Keypair
POST /api/v1/identity/revoke  — Key Revokation
GET  /api/v1/identity/status  — Key Status prüfen
"""
import gc
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text
import redis.asyncio as aioredis

from database import get_db
from models import IdentityRecord, KeyStatus

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages/crypto"))
sys.path.insert(0, "/packages/crypto")  # Docker container path
from keypair import generate_keypair
from nullifier import generate_nullifier_hash
from hlr import verify_greek_number

router = APIRouter(prefix="/api/v1/identity", tags=["MOD-01 Identity"])

# ─── HLR Credits Tracking (Redis) ────────────────────────────────────────────
# Initial credits loaded: 10€ = 1000 HLR / 2000 MNP / 4000 NT
# Each verify_greek_number() call consumes 1 HLR credit.
# Redis key "hlr:used" tracks total lookups performed.

HLR_INITIAL_CREDITS = 1000  # HLR lookups purchased
HLR_REDIS_KEY = "hlr:used"

_hlr_redis: aioredis.Redis | None = None

async def _get_hlr_redis() -> aioredis.Redis:
    global _hlr_redis
    if _hlr_redis is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _hlr_redis = aioredis.from_url(url, decode_responses=True)
    return _hlr_redis

async def _increment_hlr_usage() -> int:
    r = await _get_hlr_redis()
    return await r.incr(HLR_REDIS_KEY)

async def _get_hlr_usage() -> int:
    r = await _get_hlr_redis()
    val = await r.get(HLR_REDIS_KEY)
    return int(val) if val else 0


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


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/verify", response_model=VerifyResponse)
async def verify_identity(req: VerifyRequest, db: AsyncSession = Depends(get_db)):
    """
    Beta-Flow:
    1. HLR Lookup → nur echte griechische Mobilnummern
    2. Nullifier Hash erzeugen (Telefonnummer danach gelöscht)
    3. Prüfen: existiert dieser Nullifier bereits?
    4. Ed25519 Keypair erzeugen
    5. Public Key + Nullifier speichern (KEIN Private Key, KEINE Telefonnummer)
    6. Private Key einmalig zurückgeben → Client speichert im Secure Enclave
    """

    # 1. HLR Prüfung
    hlr_result = await verify_greek_number(req.phone_number)
    # Track HLR usage (even failed lookups cost a credit if not DRY_RUN)
    if hlr_result.get("status") != "DRY_RUN":
        await _increment_hlr_usage()
    if not hlr_result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=hlr_result["error"] or f"Μη έγκυρος αριθμός. Μόνο ελληνικοί αριθμοί κινητού."
        )

    # 2. Nullifier Hash (Telefonnummer wird in der Funktion sofort gelöscht)
    nullifier = generate_nullifier_hash(req.phone_number)
    del req.phone_number
    gc.collect()

    # 3. Bestehenden Record prüfen
    result = await db.execute(
        select(IdentityRecord).where(IdentityRecord.nullifier_hash == nullifier)
    )
    existing = result.scalar_one_or_none()

    if existing and existing.status == KeyStatus.ACTIVE:
        # Auto-revoke and re-register (user lost their key or reinstalled app)
        await db.execute(
            update(IdentityRecord)
            .where(IdentityRecord.nullifier_hash == nullifier)
            .values(status=KeyStatus.REVOKED)
        )
        await db.commit()
        # Refresh existing reference
        result = await db.execute(
            select(IdentityRecord).where(IdentityRecord.nullifier_hash == nullifier)
        )
        existing = result.scalar_one_or_none()
        logger.info(f"[MOD-01] Auto-revoked existing key for re-registration")

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
        await db.execute(
            update(IdentityRecord)
            .where(IdentityRecord.nullifier_hash == nullifier)
            .values(
                public_key_hex=keypair["public_key_hex"],
                status=KeyStatus.ACTIVE,
                demographic_hash=demographic_hash,
                age_group=req.age_group,
                region=req.region,
                gender_code=req.gender_code,
                revoked_at=None,
                created_at=datetime.utcnow()
            )
        )
    else:
        record = IdentityRecord(
            nullifier_hash=nullifier,
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
        {"nh": nullifier}
    )
    await db.commit()

    # 7. Private Key einmalig zurückgeben — danach nie wieder verfügbar
    return VerifyResponse(
        success=True,
        public_key_hex=keypair["public_key_hex"],
        private_key_hex=keypair["private_key_hex"],
        nullifier_hash=nullifier,
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
        .values(status=KeyStatus.REVOKED, revoked_at=datetime.utcnow())
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
        created_at=record.created_at.isoformat() if record.created_at else None
    )


# ─── HLR Credits Public Endpoint ─────────────────────────────────────────────

@router.get("/hlr/credits")
async def hlr_credits():
    """
    Öffentlicher Endpoint — zeigt verbleibende HLR Credits.
    Kein Auth nötig (Transparenz-Prinzip).
    Für community.html Live-Kachel.
    """
    used = await _get_hlr_usage()
    remaining = max(0, HLR_INITIAL_CREDITS - used)
    cost_per_query = 0.01  # 10€ / 1000 credits
    balance_eur = remaining * cost_per_query

    return {
        "initial": HLR_INITIAL_CREDITS,
        "used": used,
        "remaining": remaining,
        "balance_eur": round(balance_eur, 2),
        "cost_per_query_eur": cost_per_query,
        "status": "critical" if remaining < 50 else ("low" if remaining < 200 else "ok"),
    }


# ─── Profile Location Sync ────────────────────────────────────────────────────

class LocationUpdateRequest(BaseModel):
    nullifier_hash: str = Field(..., min_length=16, max_length=64)
    periferia_id: int | None = None
    dimos_id: int | None = None


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
        )
    )
    identity = result.scalar_one_or_none()
    if not identity:
        raise HTTPException(403, "Nullifier nicht gefunden oder revoziert.")

    # Update location
    if req.periferia_id is not None:
        identity.periferia_id = req.periferia_id if req.periferia_id > 0 else None
    if req.dimos_id is not None:
        identity.dimos_id = req.dimos_id if req.dimos_id > 0 else None

    await db.commit()

    return {
        "success": True,
        "periferia_id": identity.periferia_id,
        "dimos_id": identity.dimos_id,
    }
