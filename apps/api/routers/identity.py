"""
MOD-01: Identity Router
POST /api/v1/identity/verify  — SMS Verifikation → Ed25519 Keypair
POST /api/v1/identity/revoke  — Key Revokation
GET  /api/v1/identity/status  — Key Status prüfen
"""
import gc
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database import get_db
from models import IdentityRecord, KeyStatus

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages/crypto"))
sys.path.insert(0, "/packages/crypto")  # Docker container path
from keypair import generate_keypair
from nullifier import generate_nullifier_hash
from hlr import verify_greek_number

router = APIRouter(prefix="/api/v1/identity", tags=["MOD-01 Identity"])


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
    if not hlr_result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=hlr_result["error"] or f"Ungültige Nummer ({hlr_result['status']}). Nur echte griechische Mobilnummern."
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Diese Nummer ist bereits registriert. Für neuen Key: /revoke aufrufen."
        )

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

    await db.commit()

    # 7. Private Key einmalig zurückgeben — danach nie wieder verfügbar
    return VerifyResponse(
        success=True,
        public_key_hex=keypair["public_key_hex"],
        private_key_hex=keypair["private_key_hex"],
        nullifier_hash=nullifier,
        message="Schlüssel erzeugt. Speichere den Private Key sofort im Secure Enclave. Er wird nicht gespeichert und ist nicht wiederherstellbar."
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
        raise HTTPException(status_code=400, detail="Nullifier stimmt nicht mit Telefonnummer überein.")

    result = await db.execute(
        select(IdentityRecord).where(IdentityRecord.nullifier_hash == new_nullifier)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Kein Key für diese Nummer gefunden.")

    await db.execute(
        update(IdentityRecord)
        .where(IdentityRecord.nullifier_hash == new_nullifier)
        .values(status=KeyStatus.REVOKED, revoked_at=datetime.utcnow())
    )
    await db.commit()

    return {"success": True, "message": "Key revoziert. Rufe /verify auf um einen neuen Key zu erhalten."}


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
