"""
Admin Test Account — generates Ed25519 keypair + nullifier for test devices.
POST /api/v1/admin/test-account → QR deep-link data
"""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database import get_db
from dependencies import verify_admin_key
from models import IdentityRecord, KeyStatus
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

SERVER_SALT = os.getenv("SERVER_SALT", "dev-salt")


class TestAccountResponse(BaseModel):
    nullifier_hash: str
    public_key_hex: str
    private_key_hex: str
    qr_data: str
    db_id: int


@router.post("/test-account", response_model=TestAccountResponse)
async def create_test_account(
    _auth: bool = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
):
    """Generate a test account with Ed25519 keypair. For admin/dev testing only."""
    from nacl.signing import SigningKey

    # Generate random keypair
    signing_key = SigningKey.generate()
    private_key_hex = signing_key.encode().hex()
    public_key_hex = signing_key.verify_key.encode().hex()

    # Generate nullifier (random, not phone-based)
    random_seed = secrets.token_hex(16)
    nullifier_hash = hashlib.sha256(
        f"{random_seed}:{SERVER_SALT}:admin-test".encode()
    ).hexdigest()

    # Store in DB
    record = IdentityRecord(
        nullifier_hash=nullifier_hash,
        public_key_hex=public_key_hex,
        status=KeyStatus.ACTIVE,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    # Build QR deep-link
    qr_data = (
        f"ekklesia://import-account"
        f"?key={private_key_hex}"
        f"&nullifier={nullifier_hash}"
        f"&pubkey={public_key_hex}"
    )

    logger.info("[ADMIN] Test account created: id=%d nullifier=%s...%s",
                record.id, nullifier_hash[:8], nullifier_hash[-4:])

    return TestAccountResponse(
        nullifier_hash=nullifier_hash,
        public_key_hex=public_key_hex,
        private_key_hex=private_key_hex,
        qr_data=qr_data,
        db_id=record.id,
    )
