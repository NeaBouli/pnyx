"""GH#112: disabled ZK verifier endpoint.

This router is intentionally not a vote endpoint. It only verifies public
Semaphore proof payloads when ZK_VOTING_ENABLED is explicitly enabled.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path as FastAPIPath, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from database import get_db
from keypair import verify_signature
from models import (
    BillStatus,
    CitizenVote,
    GovernanceLevel,
    IdentityRecord,
    KeyStatus,
    ParliamentBill,
    ZkIdentityCommitment,
    ZkVoteReceipt,
)
from services.zk_arweave_payload import build_public_zk_receipt_from_storage
from services.zk_groth16_verifier import (
    SEMAPHORE_V4_DEPTH16_VKEY_SHA256,
    load_verification_key,
    normalize_native_proof,
    verify_semaphore_proof,
)
from services.zk_tier_lock import (
    VoteScopeType,
    canonical_vote_scope_id,
    create_tier_lock,
    derive_tier_guard_hash,
    tier_lock_exists,
)

router = APIRouter(prefix="/api/v1/zk", tags=["GH#112 ZK V2"])

VKEY_PATH = Path(__file__).resolve().parents[1] / "data" / "semaphore-v4-depth16-vkey.json"
ZK_VOTING_ENABLED_ENV = "ZK_VOTING_ENABLED"
ZK_OPT_IN_ENABLED_ENV = "ZK_OPT_IN_ENABLED"
ZK_CANARY_ENABLED_ENV = "ZK_CANARY_ENABLED"
ZK_TIER1_GUARD_ENABLED_ENV = "ZK_TIER1_GUARD_ENABLED"
SEMAPHORE_MERKLE_TREE_DEPTH = 16


class ZkVerifyRequest(BaseModel):
    proof: dict[str, Any] = Field(..., description="Public Semaphore proof payload only")


class ZkOptInRequest(BaseModel):
    nullifier_hash: str = Field(..., min_length=64, max_length=64)
    bill_id: str = Field(..., min_length=1, max_length=50)
    commitment: str = Field(..., min_length=1, max_length=160, pattern=r"^[0-9]+$")
    signature_hex: str = Field(..., min_length=128, max_length=128)


class ZkOptInResponse(BaseModel):
    status: str
    vote_scope_id: str
    commitment_id: int
    tier_locked: bool
    merkle_tree_depth: int
    message_el: str


class ZkVerifyResponse(BaseModel):
    enabled: bool
    proof_verified: bool
    merkle_tree_depth: int
    verifier_version: str


class ZkStatusResponse(BaseModel):
    production_enabled: bool
    verifier_enabled: bool
    opt_in_enabled: bool
    canary_enabled: bool
    merkle_tree_depth: int
    verifier_version: str
    message_el: str


class ZkReceiptListResponse(BaseModel):
    vote_scope_id: str
    limit: int
    offset: int
    receipts: list[dict[str, Any]]


def zk_voting_enabled() -> bool:
    return _env_enabled(ZK_VOTING_ENABLED_ENV)


def zk_opt_in_enabled() -> bool:
    return (
        zk_voting_enabled()
        and _env_enabled(ZK_OPT_IN_ENABLED_ENV)
        and _env_enabled(ZK_TIER1_GUARD_ENABLED_ENV)
    )


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "false").lower() == "true"


def _ensure_zk_opt_in_enabled() -> None:
    if not zk_opt_in_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK opt-in is not enabled",
        )


def _ensure_bill_scope_allowed(identity: IdentityRecord, bill: ParliamentBill) -> None:
    gov_level = getattr(bill, "governance_level", None)
    if gov_level in (None, GovernanceLevel.NATIONAL, GovernanceLevel.INSTITUTIONAL):
        return

    if gov_level == GovernanceLevel.REGIONAL:
        if not identity.periferia_id or identity.periferia_id != bill.periferia_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Αυτή η ψηφοφορία αφορά μόνο κατοίκους αυτής της Περιφέρειας.",
            )
        return

    if gov_level == GovernanceLevel.MUNICIPAL:
        if not identity.dimos_id or identity.dimos_id != bill.dimos_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Αυτή η ψηφοφορία αφορά μόνο κατοίκους αυτού του Δήμου.",
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Αυτό το επίπεδο ψηφοφορίας δεν υποστηρίζεται ακόμη για Semaphore ZK.",
    )


@router.get("/status", response_model=ZkStatusResponse)
async def get_zk_status() -> ZkStatusResponse:
    production_enabled = zk_voting_enabled()
    return ZkStatusResponse(
        production_enabled=production_enabled,
        verifier_enabled=production_enabled,
        opt_in_enabled=zk_opt_in_enabled(),
        canary_enabled=production_enabled and _env_enabled(ZK_CANARY_ENABLED_ENV),
        merkle_tree_depth=SEMAPHORE_MERKLE_TREE_DEPTH,
        verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
        message_el=(
            "Η παραγωγική ZK ψηφοφορία είναι ενεργή."
            if production_enabled
            else "Η παραγωγική ZK ψηφοφορία δεν είναι ενεργή ακόμη."
        ),
    )


@router.post("/opt-in", response_model=ZkOptInResponse)
async def opt_in_zk(req: ZkOptInRequest, db: AsyncSession = Depends(get_db)) -> ZkOptInResponse:
    _ensure_zk_opt_in_enabled()

    id_result = await db.execute(
        select(IdentityRecord).where(
            IdentityRecord.nullifier_hash == req.nullifier_hash,
            IdentityRecord.status == KeyStatus.ACTIVE,
        )
    )
    identity = id_result.scalar_one_or_none()
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Δεν έχετε επαληθευτεί ή το κλειδί σας έχει ανακληθεί.",
        )

    bill_result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == req.bill_id).with_for_update()
    )
    bill = bill_result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Το νομοσχέδιο {req.bill_id} δεν βρέθηκε.")

    if bill.status not in (BillStatus.ACTIVE, BillStatus.WINDOW_24H, BillStatus.OPEN_END):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Η ZK ενεργοποίηση δεν είναι δυνατή. Κατάσταση: {bill.status.value}.",
        )

    _ensure_bill_scope_allowed(identity, bill)

    payload = f"zk_opt_in:{req.bill_id}:{req.commitment}:{req.nullifier_hash}".encode()
    if not verify_signature(identity.public_key_hex, payload, req.signature_hex):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Μη έγκυρη υπογραφή.")

    existing_vote_result = await db.execute(
        select(CitizenVote.id).where(
            CitizenVote.nullifier_hash == req.nullifier_hash,
            CitizenVote.bill_id == req.bill_id,
        )
    )
    if existing_vote_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Έχετε ήδη ψηφίσει σε αυτή την ψηφοφορία με την κανονική διαδρομή.",
        )

    server_salt = os.getenv("SERVER_SALT", "")
    vote_scope_id = canonical_vote_scope_id(VoteScopeType.BILL, req.bill_id)
    try:
        tier_guard_hash = derive_tier_guard_hash(
            server_salt=server_salt,
            vote_scope_id=vote_scope_id,
            tier1_nullifier_hash=req.nullifier_hash,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK opt-in is not configured.",
        ) from exc

    if await tier_lock_exists(db, vote_scope_id=vote_scope_id, tier_guard_hash=tier_guard_hash):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Έχετε ήδη ενεργοποιήσει τη διαδρομή Semaphore ZK για αυτή την ψηφοφορία.",
        )

    commitment = ZkIdentityCommitment(
        identity_record_id=identity.id,
        vote_scope_id=vote_scope_id,
        commitment=req.commitment,
        merkle_depth=SEMAPHORE_MERKLE_TREE_DEPTH,
    )
    db.add(commitment)
    try:
        await create_tier_lock(db, vote_scope_id=vote_scope_id, tier_guard_hash=tier_guard_hash)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Δεν ήταν δυνατή η ενεργοποίηση Semaphore ZK για αυτή την ψηφοφορία.",
        ) from exc

    return ZkOptInResponse(
        status="pending_root",
        vote_scope_id=vote_scope_id,
        commitment_id=commitment.id,
        tier_locked=True,
        merkle_tree_depth=SEMAPHORE_MERKLE_TREE_DEPTH,
        message_el=(
            "Η δέσμευση Semaphore καταχωρήθηκε. Η κανονική διαδρομή ψήφου "
            "είναι πλέον κλειδωμένη για αυτό το αντικείμενο."
        ),
    )


@router.get("/receipts/{vote_scope_id}", response_model=ZkReceiptListResponse)
async def list_zk_receipts(
    vote_scope_id: str = FastAPIPath(
        ...,
        min_length=6,
        max_length=128,
        pattern=r"^(bill|municipal|regional):[^/]{1,110}$",
    ),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ZkReceiptListResponse:
    result = await db.execute(
        select(ZkVoteReceipt)
        .where(ZkVoteReceipt.vote_scope_id == vote_scope_id)
        .order_by(ZkVoteReceipt.id)
        .offset(offset)
        .limit(limit)
    )
    receipts = [
        build_public_zk_receipt_from_storage(receipt)
        for receipt in result.scalars().all()
    ]
    return ZkReceiptListResponse(
        vote_scope_id=vote_scope_id,
        limit=limit,
        offset=offset,
        receipts=receipts,
    )


@router.post("/verify", response_model=ZkVerifyResponse)
async def verify_zk_proof(req: ZkVerifyRequest) -> ZkVerifyResponse:
    if not zk_voting_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK voting verifier is not enabled",
        )

    normalized = normalize_native_proof(req.proof) if "merkle_tree_depth" in req.proof else req.proof
    vkey = load_verification_key(VKEY_PATH, SEMAPHORE_V4_DEPTH16_VKEY_SHA256)
    verified = await run_in_threadpool(verify_semaphore_proof, normalized, vkey)

    return ZkVerifyResponse(
        enabled=True,
        proof_verified=verified,
        merkle_tree_depth=int(normalized["merkleTreeDepth"]),
        verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
    )
