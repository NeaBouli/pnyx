"""
Admin Test Account — generates Ed25519 keypair + nullifier for test devices.
POST /api/v1/admin/test-account → QR deep-link data
"""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from database import get_db
from dependencies import verify_admin_key
from models import Dimos, IdentityRecord, KeyStatus, Periferia
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

SERVER_SALT = os.getenv("SERVER_SALT", "dev-salt")
DEFAULT_TEST_PERIFERIA_ID = int(os.getenv("ADMIN_TEST_DEFAULT_PERIFERIA_ID", "6"))
DEFAULT_TEST_DIMOS_ID = int(os.getenv("ADMIN_TEST_DEFAULT_DIMOS_ID", "22"))


class TestAccountResponse(BaseModel):
    nullifier_hash: str
    public_key_hex: str
    private_key_hex: str
    qr_data: str
    db_id: int
    region_locked: bool
    periferia_id: int | None = None
    dimos_id: int | None = None


class TestAccountRequest(BaseModel):
    periferia_id: int | None = None
    dimos_id: int | None = None


@router.post("/test-account", response_model=TestAccountResponse)
async def create_test_account(
    req: TestAccountRequest | None = Body(default=None),
    _auth: bool = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
):
    """Generate a test account with Ed25519 keypair. For admin/dev testing only."""
    from nacl.signing import SigningKey
    req = req or TestAccountRequest()

    if req.periferia_id is None and req.dimos_id is None:
        req.periferia_id = DEFAULT_TEST_PERIFERIA_ID
        req.dimos_id = DEFAULT_TEST_DIMOS_ID

    if req.periferia_id is not None:
        periferia = await db.get(Periferia, req.periferia_id)
        if not periferia:
            raise HTTPException(status_code=400, detail=f"Invalid periferia_id: {req.periferia_id}")

    if req.dimos_id is not None:
        dimos = await db.get(Dimos, req.dimos_id)
        if not dimos:
            raise HTTPException(status_code=400, detail=f"Invalid dimos_id: {req.dimos_id}")
        if req.periferia_id is None:
            req.periferia_id = dimos.periferia_id
        elif dimos.periferia_id != req.periferia_id:
            raise HTTPException(status_code=400, detail="dimos_id does not belong to periferia_id")

    # Generate random keypair
    signing_key = SigningKey.generate()
    private_key_hex = signing_key.encode().hex()
    public_key_hex = signing_key.verify_key.encode().hex()

    # Generate nullifier (random, not phone-based)
    random_seed = secrets.token_hex(16)
    nullifier_hash = hashlib.sha256(
        f"{random_seed}:{SERVER_SALT}:admin-test".encode()
    ).hexdigest()

    # Store in DB with source marker
    record = IdentityRecord(
        nullifier_hash=nullifier_hash,
        public_key_hex=public_key_hex,
        status=KeyStatus.ACTIVE,
        source="ADMIN_TEST",
        periferia_id=req.periferia_id,
        dimos_id=req.dimos_id,
        region_locked=bool(req.periferia_id or req.dimos_id),
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(record)
    await db.flush()  # get record.id before audit log

    # Audit log in same transaction (ORM)
    from models import AuditLog
    audit = AuditLog(
        action="identity.admin_test_created",
        actor="admin_api_key",
        target_type="identity_record",
        target_id=str(record.id),
        details={
            "reason": "test_account",
            "endpoint": "/admin/test-account",
            "periferia_id": req.periferia_id,
            "dimos_id": req.dimos_id,
            "region_locked": bool(req.periferia_id or req.dimos_id),
        },
    )
    db.add(audit)

    await db.commit()
    await db.refresh(record)

    # Build QR deep-link
    qr_data = (
        f"ekklesia://import-account"
        f"?key={private_key_hex}"
        f"&nullifier={nullifier_hash}"
        f"&pubkey={public_key_hex}"
    )
    if record.periferia_id:
        qr_data += f"&periferia_id={record.periferia_id}"
    if record.dimos_id:
        qr_data += f"&dimos_id={record.dimos_id}"

    logger.info("[ADMIN] Test account created: id=%d nullifier=%s...%s",
                record.id, nullifier_hash[:8], nullifier_hash[-4:])

    return TestAccountResponse(
        nullifier_hash=nullifier_hash,
        public_key_hex=public_key_hex,
        private_key_hex=private_key_hex,
        qr_data=qr_data,
        db_id=record.id,
        region_locked=record.region_locked,
        periferia_id=record.periferia_id,
        dimos_id=record.dimos_id,
    )
