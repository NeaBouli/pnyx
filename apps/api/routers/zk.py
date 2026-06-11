"""GH#112: disabled ZK verifier endpoint.

This router is intentionally not a vote endpoint. It only verifies public
Semaphore proof payloads when ZK_VOTING_ENABLED is explicitly enabled.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from services.zk_groth16_verifier import (
    SEMAPHORE_V4_DEPTH16_VKEY_SHA256,
    load_verification_key,
    normalize_native_proof,
    verify_semaphore_proof,
)

router = APIRouter(prefix="/api/v1/zk", tags=["GH#112 ZK V2"])

VKEY_PATH = Path(__file__).resolve().parents[1] / "data" / "semaphore-v4-depth16-vkey.json"
ZK_VOTING_ENABLED_ENV = "ZK_VOTING_ENABLED"


class ZkVerifyRequest(BaseModel):
    proof: dict[str, Any] = Field(..., description="Public Semaphore proof payload only")


class ZkVerifyResponse(BaseModel):
    enabled: bool
    proof_verified: bool
    merkle_tree_depth: int
    verifier_version: str


def zk_voting_enabled() -> bool:
    return os.getenv(ZK_VOTING_ENABLED_ENV, "false").lower() == "true"


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
