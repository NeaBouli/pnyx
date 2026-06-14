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
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from database import get_db
from dependencies import verify_admin_key
from keypair import verify_signature
from models import (
    BillStatus,
    CitizenVote,
    GovernanceLevel,
    IdentityRecord,
    KeyStatus,
    ParliamentBill,
    ZkIdentityCommitment,
    ZkMerkleRoot,
    ZkVoteTierLock,
    ZkVoteReceipt,
)
from services.zk_arweave_payload import build_public_zk_receipt_from_storage
from services.zk_group_registry import (
    build_active_group_root_for_scope,
    list_public_group_members_for_scope,
    list_active_commitments_for_scope,
    validate_vote_scope_id,
)
from services.zk_groth16_verifier import (
    SEMAPHORE_V4_DEPTH16_VKEY_SHA256,
    load_verification_key,
    normalize_native_proof,
    verify_semaphore_proof,
)
from services.zk_merkle_root import build_semaphore_group_root
from services.zk_proof_binding import proof_matches_canonical_binding
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
ZK_ROOT_PUBLICATION_ENABLED_ENV = "ZK_ROOT_PUBLICATION_ENABLED"
ZK_CANARY_SCOPE_ALLOWLIST_ENV = "ZK_CANARY_SCOPE_ALLOWLIST"
SEMAPHORE_MERKLE_TREE_DEPTH = 16


class ZkVerifyRequest(BaseModel):
    proof: dict[str, Any] = Field(..., description="Public Semaphore proof payload only")
    vote_scope_id: str | None = Field(
        default=None,
        min_length=6,
        max_length=128,
        pattern=r"^(bill|municipal|regional):[^/]{1,110}$",
    )


class ZkVoteRequest(BaseModel):
    vote_scope_id: str = Field(
        ...,
        min_length=6,
        max_length=128,
        pattern=r"^(bill|municipal|regional):[^/]{1,110}$",
    )
    vote_commitment: str = Field(..., min_length=1, max_length=160)
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


class ZkVoteAcceptResponse(BaseModel):
    accepted: bool
    vote_scope_id: str
    receipt_id: int
    arweave_pending: bool
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


class ZkCanaryPreflightFlags(BaseModel):
    production_enabled: bool
    opt_in_enabled: bool
    tier1_guard_enabled: bool
    canary_enabled: bool
    root_publication_enabled: bool


class ZkCanaryPreflightResponse(BaseModel):
    vote_scope_id: str
    scope_type: str
    allowlisted: bool
    flags: ZkCanaryPreflightFlags
    bill_exists: bool
    bill_admin_hidden: bool | None
    bill_source: str | None
    bill_status: str | None
    forum_topic_absent: bool | None
    arweave_absent: bool | None
    active_commitments: int
    tier_locks: int
    receipts: int
    latest_root_exists: bool
    latest_root_group_size: int | None
    latest_root_status: str | None
    ready_for_canary_opt_in: bool
    ready_to_publish_root: bool
    private_fields_exposed: bool = False


class ZkReceiptListResponse(BaseModel):
    vote_scope_id: str
    limit: int
    offset: int
    receipts: list[dict[str, Any]]


class ZkRootResponse(BaseModel):
    vote_scope_id: str
    merkle_root: str
    merkle_depth: int
    group_size: int
    commitment_version: str
    status: str
    root_id: int


class ZkRootPublishResponse(ZkRootResponse):
    created: bool


class ZkRootMembersResponse(ZkRootResponse):
    members: list[str]


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


def _ensure_zk_root_publication_enabled() -> None:
    if not _env_enabled(ZK_ROOT_PUBLICATION_ENABLED_ENV):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK root publication is not enabled",
        )


def _canary_scope_allowlist() -> set[str]:
    raw = os.getenv(ZK_CANARY_SCOPE_ALLOWLIST_ENV, "")
    scopes: set[str] = set()
    for value in raw.split(","):
        clean = value.strip()
        if clean:
            scopes.add(validate_vote_scope_id(clean))
    return scopes


def _ensure_canary_scope_allowed(vote_scope_id: str | None) -> str:
    if not _env_enabled(ZK_CANARY_ENABLED_ENV):
        if vote_scope_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ZK vote_scope_id is required",
            )
        return validate_vote_scope_id(vote_scope_id)

    allowlist = _canary_scope_allowlist()
    if not allowlist:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK canary scope allowlist is not configured",
        )
    if vote_scope_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZK vote_scope_id is required in canary mode",
        )
    scope = validate_vote_scope_id(vote_scope_id)
    if scope not in allowlist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ZK canary scope is not allowed",
        )
    return scope


def _is_safe_canary_bill(bill: ParliamentBill | None) -> bool:
    return (
        bill is not None
        and bool(getattr(bill, "admin_hidden", False)) is True
        and getattr(bill, "source", None) == "ZK_CANARY"
        and getattr(bill, "forum_topic_id", None) is None
        and getattr(bill, "arweave_tx_id", None) is None
    )


def _ensure_canary_bill_isolated(bill: ParliamentBill | None) -> None:
    if not _env_enabled(ZK_CANARY_ENABLED_ENV):
        return
    if not _is_safe_canary_bill(bill):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ZK canary bill is not isolated",
        )


async def _ensure_canary_scope_isolated(db: AsyncSession, vote_scope_id: str) -> None:
    if not _env_enabled(ZK_CANARY_ENABLED_ENV):
        return
    scope_type, scope_id = validate_vote_scope_id(vote_scope_id).split(":", 1)
    if scope_type != "bill":
        return
    bill_result = await db.execute(select(ParliamentBill).where(ParliamentBill.id == scope_id))
    _ensure_canary_bill_isolated(bill_result.scalar_one_or_none())


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


@router.get("/canary/preflight/{vote_scope_id}", response_model=ZkCanaryPreflightResponse)
async def get_zk_canary_preflight(
    vote_scope_id: str = FastAPIPath(
        ...,
        min_length=6,
        max_length=128,
        pattern=r"^(bill|municipal|regional):[^/]{1,110}$",
    ),
    _admin: bool = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
) -> ZkCanaryPreflightResponse:
    scope = validate_vote_scope_id(vote_scope_id)
    scope_type, scope_id = scope.split(":", 1)
    allowlisted = scope in _canary_scope_allowlist()

    bill: ParliamentBill | None = None
    if scope_type == "bill":
        bill_result = await db.execute(select(ParliamentBill).where(ParliamentBill.id == scope_id))
        bill = bill_result.scalar_one_or_none()

    active_commitments = await _count_rows(
        db,
        select(func.count(ZkIdentityCommitment.id)).where(
            ZkIdentityCommitment.vote_scope_id == scope,
            ZkIdentityCommitment.status == "ACTIVE",
        ),
    )
    tier_locks = await _count_rows(
        db,
        select(func.count(ZkVoteTierLock.id)).where(ZkVoteTierLock.vote_scope_id == scope),
    )
    receipts = await _count_rows(
        db,
        select(func.count(ZkVoteReceipt.id)).where(ZkVoteReceipt.vote_scope_id == scope),
    )
    root_result = await db.execute(
        select(ZkMerkleRoot)
        .where(
            ZkMerkleRoot.vote_scope_id == scope,
            ZkMerkleRoot.status == "OPEN",
        )
        .order_by(ZkMerkleRoot.id.desc())
        .limit(1)
    )
    latest_root = root_result.scalar_one_or_none()

    flags = ZkCanaryPreflightFlags(
        production_enabled=zk_voting_enabled(),
        opt_in_enabled=_env_enabled(ZK_OPT_IN_ENABLED_ENV),
        tier1_guard_enabled=_env_enabled(ZK_TIER1_GUARD_ENABLED_ENV),
        canary_enabled=_env_enabled(ZK_CANARY_ENABLED_ENV),
        root_publication_enabled=_env_enabled(ZK_ROOT_PUBLICATION_ENABLED_ENV),
    )
    bill_hidden = bool(bill.admin_hidden) if bill is not None else None
    forum_absent = bill.forum_topic_id is None if bill is not None else None
    arweave_absent = bill.arweave_tx_id is None if bill is not None else None
    bill_is_safe_canary = _is_safe_canary_bill(bill)

    return ZkCanaryPreflightResponse(
        vote_scope_id=scope,
        scope_type=scope_type,
        allowlisted=allowlisted,
        flags=flags,
        bill_exists=bill is not None,
        bill_admin_hidden=bill_hidden,
        bill_source=bill.source if bill is not None else None,
        bill_status=bill.status.value if bill is not None else None,
        forum_topic_absent=forum_absent,
        arweave_absent=arweave_absent,
        active_commitments=active_commitments,
        tier_locks=tier_locks,
        receipts=receipts,
        latest_root_exists=latest_root is not None,
        latest_root_group_size=latest_root.group_size if latest_root is not None else None,
        latest_root_status=str(latest_root.status) if latest_root is not None else None,
        ready_for_canary_opt_in=(
            flags.production_enabled
            and flags.opt_in_enabled
            and flags.tier1_guard_enabled
            and flags.canary_enabled
            and allowlisted
            and bill_is_safe_canary
        ),
        ready_to_publish_root=(
            flags.root_publication_enabled
            and flags.canary_enabled
            and allowlisted
            and bill_is_safe_canary
            and active_commitments > 0
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
    vote_scope_id = canonical_vote_scope_id(VoteScopeType.BILL, req.bill_id)
    _ensure_canary_scope_allowed(vote_scope_id)
    _ensure_canary_bill_isolated(bill)

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
    scope = validate_vote_scope_id(vote_scope_id)
    if _env_enabled(ZK_CANARY_ENABLED_ENV):
        _ensure_canary_scope_allowed(scope)
        await _ensure_canary_scope_isolated(db, scope)
    result = await db.execute(
        select(ZkVoteReceipt)
        .where(ZkVoteReceipt.vote_scope_id == scope)
        .order_by(ZkVoteReceipt.id)
        .offset(offset)
        .limit(limit)
    )
    receipts = [
        build_public_zk_receipt_from_storage(receipt)
        for receipt in result.scalars().all()
    ]
    return ZkReceiptListResponse(
        vote_scope_id=scope,
        limit=limit,
        offset=offset,
        receipts=receipts,
    )


@router.get("/roots/{vote_scope_id}", response_model=ZkRootResponse)
async def get_current_zk_root(
    vote_scope_id: str = FastAPIPath(
        ...,
        min_length=6,
        max_length=128,
        pattern=r"^(bill|municipal|regional):[^/]{1,110}$",
    ),
    db: AsyncSession = Depends(get_db),
) -> ZkRootResponse:
    scope = validate_vote_scope_id(vote_scope_id)
    if _env_enabled(ZK_CANARY_ENABLED_ENV):
        _ensure_canary_scope_allowed(scope)
        await _ensure_canary_scope_isolated(db, scope)
    result = await db.execute(
        select(ZkMerkleRoot)
        .where(
            ZkMerkleRoot.vote_scope_id == scope,
            ZkMerkleRoot.status == "OPEN",
        )
        .order_by(ZkMerkleRoot.id.desc())
        .limit(1)
    )
    root = result.scalar_one_or_none()
    if not root:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZK root not found")
    return _zk_root_response(root)


@router.get("/roots/{vote_scope_id}/members", response_model=ZkRootMembersResponse)
async def get_current_zk_root_members(
    vote_scope_id: str = FastAPIPath(
        ...,
        min_length=6,
        max_length=128,
        pattern=r"^(bill|municipal|regional):[^/]{1,110}$",
    ),
    db: AsyncSession = Depends(get_db),
) -> ZkRootMembersResponse:
    scope = validate_vote_scope_id(vote_scope_id)
    if _env_enabled(ZK_CANARY_ENABLED_ENV):
        _ensure_canary_scope_allowed(scope)
        await _ensure_canary_scope_isolated(db, scope)

    result = await db.execute(
        select(ZkMerkleRoot)
        .where(
            ZkMerkleRoot.vote_scope_id == scope,
            ZkMerkleRoot.status == "OPEN",
        )
        .order_by(ZkMerkleRoot.id.desc())
        .limit(1)
    )
    root = result.scalar_one_or_none()
    if not root:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZK root not found")

    members = await list_public_group_members_for_scope(db, vote_scope_id=scope)
    current_group = build_semaphore_group_root(members)
    if (
        str(current_group.root) != str(root.merkle_root)
        or current_group.size != int(root.group_size)
        or int(root.merkle_depth) != SEMAPHORE_MERKLE_TREE_DEPTH
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ZK root is stale; publish a fresh root before proof generation",
        )

    response = _zk_root_response(root)
    return ZkRootMembersResponse(**response.model_dump(), members=members)


@router.post("/roots/{vote_scope_id}/publish", response_model=ZkRootPublishResponse)
async def publish_zk_root(
    vote_scope_id: str = FastAPIPath(
        ...,
        min_length=6,
        max_length=128,
        pattern=r"^(bill|municipal|regional):[^/]{1,110}$",
    ),
    _admin: bool = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
) -> ZkRootPublishResponse:
    _ensure_zk_root_publication_enabled()
    scope = validate_vote_scope_id(vote_scope_id)
    _ensure_canary_scope_allowed(scope)
    await _ensure_canary_scope_isolated(db, scope)
    try:
        group = await build_active_group_root_for_scope(db, vote_scope_id=scope)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    existing_result = await db.execute(
        select(ZkMerkleRoot).where(
            ZkMerkleRoot.vote_scope_id == scope,
            ZkMerkleRoot.merkle_root == str(group.root),
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        response = _zk_root_response(existing)
        return ZkRootPublishResponse(**response.model_dump(), created=False)

    root = ZkMerkleRoot(
        vote_scope_id=scope,
        scope_type=scope.split(":", 1)[0].upper(),
        merkle_root=str(group.root),
        merkle_depth=SEMAPHORE_MERKLE_TREE_DEPTH,
        group_size=group.size,
        commitment_version="semaphore-v4",
        status="OPEN",
    )
    db.add(root)
    try:
        await db.commit()
        await db.refresh(root)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ZK root already exists") from exc

    response = _zk_root_response(root)
    return ZkRootPublishResponse(**response.model_dump(), created=True)


@router.post("/vote", response_model=ZkVoteAcceptResponse)
async def accept_zk_vote(req: ZkVoteRequest, db: AsyncSession = Depends(get_db)) -> ZkVoteAcceptResponse:
    if not zk_voting_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK voting is not enabled",
        )

    scope = _ensure_canary_scope_allowed(req.vote_scope_id)
    await _ensure_canary_scope_isolated(db, scope)
    vote_commitment = req.vote_commitment.strip()
    normalized = _normalize_public_proof(req.proof)

    if not proof_matches_canonical_binding(
        proof_message=normalized["message"],
        proof_scope=normalized["scope"],
        vote_scope_id=scope,
        vote_commitment=vote_commitment,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZK proof is not bound to this vote scope and commitment",
        )

    root_result = await db.execute(
        select(ZkMerkleRoot)
        .where(
            ZkMerkleRoot.vote_scope_id == scope,
            ZkMerkleRoot.merkle_root == str(normalized["merkleTreeRoot"]),
            ZkMerkleRoot.status == "OPEN",
        )
        .order_by(ZkMerkleRoot.id.desc())
        .limit(1)
    )
    root = root_result.scalar_one_or_none()
    if not root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ZK root is not published for this scope",
        )
    if int(normalized["merkleTreeDepth"]) != int(root.merkle_depth):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZK proof merkle depth does not match the published root",
        )

    vkey = load_verification_key(VKEY_PATH, SEMAPHORE_V4_DEPTH16_VKEY_SHA256)
    verified = await run_in_threadpool(verify_semaphore_proof, normalized, vkey)
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZK proof failed verification",
        )

    receipt = ZkVoteReceipt(
        vote_scope_id=scope,
        vote_commitment=vote_commitment,
        semaphore_nullifier=str(normalized["nullifier"]),
        merkle_root=str(normalized["merkleTreeRoot"]),
        merkle_depth=int(normalized["merkleTreeDepth"]),
        signal_hash=str(normalized["message"]),
        external_nullifier=str(normalized["scope"]),
        proof_public_json=normalized,
        verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
        circuit_version="semaphore-v4-depth16",
        arweave_pending=True,
    )
    db.add(receipt)
    try:
        await db.commit()
        await db.refresh(receipt)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ZK vote already exists for this scope",
        ) from exc

    return ZkVoteAcceptResponse(
        accepted=True,
        vote_scope_id=scope,
        receipt_id=receipt.id,
        arweave_pending=True,
        merkle_tree_depth=receipt.merkle_depth,
        verifier_version=receipt.verifier_version,
    )


@router.post("/verify", response_model=ZkVerifyResponse)
async def verify_zk_proof(req: ZkVerifyRequest) -> ZkVerifyResponse:
    if not zk_voting_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK voting verifier is not enabled",
        )
    if _env_enabled(ZK_CANARY_ENABLED_ENV):
        _ensure_canary_scope_allowed(req.vote_scope_id)

    normalized = _normalize_public_proof(req.proof)
    vkey = load_verification_key(VKEY_PATH, SEMAPHORE_V4_DEPTH16_VKEY_SHA256)
    verified = await run_in_threadpool(verify_semaphore_proof, normalized, vkey)

    return ZkVerifyResponse(
        enabled=True,
        proof_verified=verified,
        merkle_tree_depth=int(normalized["merkleTreeDepth"]),
        verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
    )


def _zk_root_response(root: ZkMerkleRoot) -> ZkRootResponse:
    return ZkRootResponse(
        vote_scope_id=root.vote_scope_id,
        merkle_root=root.merkle_root,
        merkle_depth=root.merkle_depth,
        group_size=root.group_size,
        commitment_version=root.commitment_version,
        status=root.status,
        root_id=root.id,
    )


async def _count_rows(db: AsyncSession, statement: Any) -> int:
    result = await db.execute(statement)
    return int(result.scalar_one() or 0)


def _normalize_public_proof(proof: dict[str, Any]) -> dict[str, Any]:
    return normalize_native_proof(proof) if "merkle_tree_depth" in proof else proof
