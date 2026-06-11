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
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from database import get_db
from models import ZkVoteReceipt
from services.zk_arweave_payload import build_public_zk_receipt_from_storage
from services.zk_groth16_verifier import (
    SEMAPHORE_V4_DEPTH16_VKEY_SHA256,
    load_verification_key,
    normalize_native_proof,
    verify_semaphore_proof,
)

router = APIRouter(prefix="/api/v1/zk", tags=["GH#112 ZK V2"])

VKEY_PATH = Path(__file__).resolve().parents[1] / "data" / "semaphore-v4-depth16-vkey.json"
ZK_VOTING_ENABLED_ENV = "ZK_VOTING_ENABLED"
ZK_OPT_IN_ENABLED_ENV = "ZK_OPT_IN_ENABLED"
ZK_CANARY_ENABLED_ENV = "ZK_CANARY_ENABLED"
SEMAPHORE_MERKLE_TREE_DEPTH = 16


class ZkVerifyRequest(BaseModel):
    proof: dict[str, Any] = Field(..., description="Public Semaphore proof payload only")


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


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "false").lower() == "true"


@router.get("/status", response_model=ZkStatusResponse)
async def get_zk_status() -> ZkStatusResponse:
    production_enabled = zk_voting_enabled()
    return ZkStatusResponse(
        production_enabled=production_enabled,
        verifier_enabled=production_enabled,
        opt_in_enabled=production_enabled and _env_enabled(ZK_OPT_IN_ENABLED_ENV),
        canary_enabled=production_enabled and _env_enabled(ZK_CANARY_ENABLED_ENV),
        merkle_tree_depth=SEMAPHORE_MERKLE_TREE_DEPTH,
        verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
        message_el=(
            "Η παραγωγική ZK ψηφοφορία είναι ενεργή."
            if production_enabled
            else "Η παραγωγική ZK ψηφοφορία δεν είναι ενεργή ακόμη."
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
