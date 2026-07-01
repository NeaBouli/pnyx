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
    VoteChoice,
    ZkIdentityCommitment,
    ZkMerkleRoot,
    ZkVoteTierLock,
    ZkVoteReceipt,
)
from services.zk_arweave_payload import build_public_zk_receipt_from_storage
from services.zk_arweave_publisher import (
    ZkArweavePublicationError,
    publish_pending_zk_receipts_for_scope,
    zk_arweave_auto_parliament_enabled,
    zk_arweave_min_group_size,
    zk_arweave_scope_allowlist,
)
from services.zk_group_registry import (
    build_active_group_root_for_scope,
    list_public_group_members_for_scope,
    list_active_commitments_for_scope,
    validate_vote_scope_id,
)
from services.bill_visibility import is_public_bill
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
ZK_PRODUCTION_SCOPE_ALLOWLIST_ENV = "ZK_PRODUCTION_SCOPE_ALLOWLIST"
ZK_GLOBAL_ROLLOUT_ENABLED_ENV = "ZK_GLOBAL_ROLLOUT_ENABLED"
ZK_ARWEAVE_PUBLICATION_ENABLED_ENV = "ZK_ARWEAVE_PUBLICATION_ENABLED"
ZK_ARWEAVE_SCOPE_ALLOWLIST_ENV = "ZK_ARWEAVE_SCOPE_ALLOWLIST"
ZK_ARWEAVE_MIN_GROUP_SIZE_ENV = "ZK_ARWEAVE_MIN_GROUP_SIZE"
ZK_ARWEAVE_MIN_GROUP_SIZE_DEFAULT = 5
SEMAPHORE_MERKLE_TREE_DEPTH = 16
NATIVE_PROOF_KEYS = {"merkle_tree_depth", "merkle_tree_root"}
CANONICAL_PROOF_KEYS = {"merkleTreeDepth", "merkleTreeRoot"}
ZK_GLOBAL_ROLLOUT_STATUSES = {BillStatus.ACTIVE, BillStatus.WINDOW_24H, BillStatus.OPEN_END}


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
    root_publication_enabled: bool
    arweave_publication_enabled: bool
    arweave_scope_allowlist_configured: bool
    arweave_auto_parliament_enabled: bool
    arweave_min_group_size: int
    global_rollout_enabled: bool
    production_scope_allowlist_configured: bool
    merkle_tree_depth: int
    verifier_version: str
    message_el: str


class ZkScopeStatusResponse(BaseModel):
    vote_scope_id: str
    scope_type: str
    production_enabled: bool
    verifier_enabled: bool
    opt_in_enabled: bool
    canary_enabled: bool
    allowlisted: bool
    global_rollout_enabled: bool
    root_published: bool
    active_commitments: int
    can_opt_in: bool
    can_vote: bool
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


class ZkReceiptPublishResponse(BaseModel):
    vote_scope_id: str
    attempted: int
    published: int
    failed: int
    tx_ids: list[str]


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
    return _scope_allowlist(ZK_CANARY_SCOPE_ALLOWLIST_ENV)


def _production_scope_allowlist() -> set[str]:
    return _scope_allowlist(ZK_PRODUCTION_SCOPE_ALLOWLIST_ENV)


def _arweave_scope_allowlist() -> set[str]:
    return zk_arweave_scope_allowlist()


def _scope_allowlist(env_name: str) -> set[str]:
    scopes: set[str] = set()
    raw = os.getenv(env_name, "")
    for value in raw.split(","):
        clean = value.strip()
        if clean:
            scopes.add(validate_vote_scope_id(clean))
    return scopes


def _global_rollout_enabled() -> bool:
    return _env_enabled(ZK_GLOBAL_ROLLOUT_ENABLED_ENV)


def _zk_arweave_min_group_size() -> int:
    try:
        return zk_arweave_min_group_size()
    except ZkArweavePublicationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _ensure_zk_arweave_scope_allowed(vote_scope_id: str | None) -> str:
    if vote_scope_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZK vote_scope_id is required",
        )
    scope = validate_vote_scope_id(vote_scope_id)
    allowlist = _arweave_scope_allowlist()
    if not allowlist:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK Arweave scope allowlist is not configured",
        )
    if scope not in allowlist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ZK Arweave scope is not allowed",
        )
    return scope


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


def _ensure_zk_write_scope_allowed(vote_scope_id: str | None) -> str:
    """Fail closed unless canary, explicit allowlist, or guarded global rollout allows the scope."""
    if _env_enabled(ZK_CANARY_ENABLED_ENV):
        return _ensure_canary_scope_allowed(vote_scope_id)
    if vote_scope_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZK vote_scope_id is required",
        )

    scope = validate_vote_scope_id(vote_scope_id)
    allowlist = _production_scope_allowlist()
    if scope in allowlist:
        return scope

    if _global_rollout_enabled():
        return scope

    if not allowlist:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK production scope allowlist is not configured",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="ZK production scope is not allowed",
    )


def _is_public_parliament_bill_scope(bill: ParliamentBill | None) -> bool:
    """Object-level guard for automatic/global ZK rollout."""
    if bill is None or not is_public_bill(bill):
        return False
    if str(getattr(bill, "id", "")).startswith("DEMO-"):
        return False
    if getattr(bill, "source", None) != "PARLIAMENT":
        return False
    bill_status = getattr(bill, "status", None)
    if isinstance(bill_status, str):
        try:
            bill_status = BillStatus(bill_status)
        except ValueError:
            return False
    if bill_status not in ZK_GLOBAL_ROLLOUT_STATUSES:
        return False
    return True


def _ensure_public_parliament_bill_scope(bill: ParliamentBill | None) -> None:
    if not _is_public_parliament_bill_scope(bill):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZK vote scope not found")


def _global_rollout_applies_to_scope(scope: str) -> bool:
    return _global_rollout_enabled() and scope not in _production_scope_allowlist()


async def _ensure_global_rollout_scope_allowed(db: AsyncSession, scope: str) -> None:
    """Guard the automatic/global path so it can only expose Parliament bill scopes."""
    if not _global_rollout_applies_to_scope(scope):
        return

    scope_type, scope_id = validate_vote_scope_id(scope).split(":", 1)
    if scope_type != "bill":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ZK global rollout supports Parliament bill scopes only",
        )
    bill_result = await db.execute(select(ParliamentBill).where(ParliamentBill.id == scope_id))
    _ensure_public_parliament_bill_scope(bill_result.scalar_one_or_none())


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


async def _ensure_scope_public_or_safe_canary(
    db: AsyncSession,
    vote_scope_id: str,
    *,
    require_existing_bill: bool = False,
) -> None:
    if _env_enabled(ZK_CANARY_ENABLED_ENV):
        scope = _ensure_canary_scope_allowed(vote_scope_id)
        await _ensure_canary_scope_isolated(db, scope)
        return

    scope_type, scope_id = validate_vote_scope_id(vote_scope_id).split(":", 1)
    if scope_type != "bill":
        return

    bill_result = await db.execute(select(ParliamentBill).where(ParliamentBill.id == scope_id))
    bill = bill_result.scalar_one_or_none()
    if bill is None and not require_existing_bill:
        return
    if not bill or not is_public_bill(bill):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZK vote scope not found")


def _zk_vote_choice(vote_commitment: str) -> VoteChoice:
    try:
        return VoteChoice(vote_commitment.strip().upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZK vote_commitment must be YES, NO, ABSTAIN, or UNKNOWN",
        ) from exc


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
        root_publication_enabled=_env_enabled(ZK_ROOT_PUBLICATION_ENABLED_ENV),
        arweave_publication_enabled=_env_enabled(ZK_ARWEAVE_PUBLICATION_ENABLED_ENV),
        arweave_scope_allowlist_configured=bool(_arweave_scope_allowlist()),
        arweave_auto_parliament_enabled=zk_arweave_auto_parliament_enabled(),
        arweave_min_group_size=_zk_arweave_min_group_size(),
        global_rollout_enabled=_global_rollout_enabled(),
        production_scope_allowlist_configured=bool(_production_scope_allowlist()),
        merkle_tree_depth=SEMAPHORE_MERKLE_TREE_DEPTH,
        verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
        message_el=(
            "Η παραγωγική ZK ψηφοφορία είναι ενεργή."
            if production_enabled
            else "Η παραγωγική ZK ψηφοφορία δεν είναι ενεργή ακόμη."
        ),
    )


@router.get("/scopes/{vote_scope_id}/status", response_model=ZkScopeStatusResponse)
async def get_zk_scope_status(
    vote_scope_id: str = FastAPIPath(
        ...,
        min_length=6,
        max_length=128,
        pattern=r"^(bill|municipal|regional):[^/]{1,110}$",
    ),
    db: AsyncSession = Depends(get_db),
) -> ZkScopeStatusResponse:
    try:
        scope = validate_vote_scope_id(vote_scope_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid vote_scope_id") from exc
    scope_type, _scope_id = scope.split(":", 1)
    await _ensure_scope_public_or_safe_canary(db, scope, require_existing_bill=(scope_type == "bill"))

    production_enabled = zk_voting_enabled()
    opt_in_enabled = zk_opt_in_enabled()
    canary_enabled = production_enabled and _env_enabled(ZK_CANARY_ENABLED_ENV)
    global_rollout = _global_rollout_enabled()
    allowlisted = scope in _production_scope_allowlist()
    global_scope_allowed = False
    if global_rollout and not allowlisted:
        if scope_type == "bill":
            bill_result = await db.execute(select(ParliamentBill).where(ParliamentBill.id == _scope_id))
            global_scope_allowed = _is_public_parliament_bill_scope(bill_result.scalar_one_or_none())

    active_commitments = await _count_rows(
        db,
        select(func.count(ZkIdentityCommitment.id)).where(
            ZkIdentityCommitment.vote_scope_id == scope,
            ZkIdentityCommitment.status == "ACTIVE",
        ),
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
    root_published = root_result.scalar_one_or_none() is not None
    scope_allowed = (allowlisted or global_scope_allowed) and not canary_enabled
    can_opt_in = production_enabled and opt_in_enabled and scope_allowed
    can_vote = can_opt_in and root_published
    return ZkScopeStatusResponse(
        vote_scope_id=scope,
        scope_type=scope_type,
        production_enabled=production_enabled,
        verifier_enabled=production_enabled,
        opt_in_enabled=opt_in_enabled,
        canary_enabled=canary_enabled,
        allowlisted=allowlisted,
        global_rollout_enabled=global_rollout,
        root_published=root_published,
        active_commitments=active_commitments,
        can_opt_in=can_opt_in,
        can_vote=can_vote,
        merkle_tree_depth=SEMAPHORE_MERKLE_TREE_DEPTH,
        verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
        message_el=(
            "Η προαιρετική ZK διαδρομή είναι διαθέσιμη για αυτό το θέμα."
            if can_opt_in
            else "Η προαιρετική ZK διαδρομή δεν είναι διαθέσιμη για αυτό το θέμα."
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
    _ensure_zk_write_scope_allowed(vote_scope_id)
    if _global_rollout_applies_to_scope(vote_scope_id):
        _ensure_public_parliament_bill_scope(bill)
    if _env_enabled(ZK_CANARY_ENABLED_ENV):
        _ensure_canary_bill_isolated(bill)
    elif not is_public_bill(bill):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Το νομοσχέδιο {req.bill_id} δεν βρέθηκε.")

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
    await _ensure_scope_public_or_safe_canary(db, scope)
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
    await _ensure_scope_public_or_safe_canary(db, scope)
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
    await _ensure_scope_public_or_safe_canary(db, scope)

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
    scope = _ensure_zk_write_scope_allowed(vote_scope_id)
    await _ensure_global_rollout_scope_allowed(db, scope)
    await _ensure_scope_public_or_safe_canary(db, scope, require_existing_bill=True)
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

    scope = _ensure_zk_write_scope_allowed(req.vote_scope_id)
    await _ensure_global_rollout_scope_allowed(db, scope)
    await _ensure_scope_public_or_safe_canary(db, scope, require_existing_bill=True)
    vote_commitment = req.vote_commitment.strip()
    vote_choice = _zk_vote_choice(vote_commitment)
    try:
        normalized = _normalize_public_proof(req.proof)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed ZK proof") from exc

    if not proof_matches_canonical_binding(
        proof_message=normalized["message"],
        proof_scope=normalized["scope"],
        vote_scope_id=scope,
        vote_commitment=vote_choice.value,
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
async def verify_zk_proof(req: ZkVerifyRequest, db: AsyncSession = Depends(get_db)) -> ZkVerifyResponse:
    if not zk_voting_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK voting verifier is not enabled",
        )
    scope: str | None = None
    if _env_enabled(ZK_CANARY_ENABLED_ENV):
        scope = _ensure_canary_scope_allowed(req.vote_scope_id)
    elif req.vote_scope_id is not None:
        scope = _ensure_zk_write_scope_allowed(req.vote_scope_id)
        await _ensure_global_rollout_scope_allowed(db, scope)
    try:
        normalized = _normalize_public_proof(req.proof)
    except (KeyError, TypeError, ValueError):
        return ZkVerifyResponse(
            enabled=True,
            proof_verified=False,
            merkle_tree_depth=SEMAPHORE_MERKLE_TREE_DEPTH,
            verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
        )
    if scope is not None and not await _proof_matches_published_root(db, scope, normalized):
        return ZkVerifyResponse(
            enabled=True,
            proof_verified=False,
            merkle_tree_depth=int(normalized["merkleTreeDepth"]),
            verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
        )

    vkey = load_verification_key(VKEY_PATH, SEMAPHORE_V4_DEPTH16_VKEY_SHA256)
    verified = await run_in_threadpool(verify_semaphore_proof, normalized, vkey)

    return ZkVerifyResponse(
        enabled=True,
        proof_verified=verified,
        merkle_tree_depth=int(normalized["merkleTreeDepth"]),
        verifier_version="py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
    )


@router.post("/receipts/{vote_scope_id}/publish-pending", response_model=ZkReceiptPublishResponse)
async def publish_pending_zk_receipts(
    vote_scope_id: str = FastAPIPath(
        ...,
        min_length=6,
        max_length=128,
        pattern=r"^(bill|municipal|regional):[^/]{1,110}$",
    ),
    limit: int = Query(25, ge=1, le=100),
    _admin: bool = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db),
) -> ZkReceiptPublishResponse:
    try:
        stats = await publish_pending_zk_receipts_for_scope(
            db,
            vote_scope_id=vote_scope_id,
            limit=limit,
            require_allowlist=True,
            raise_on_small_group=True,
        )
    except ZkArweavePublicationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return ZkReceiptPublishResponse(
        vote_scope_id=stats.vote_scope_id,
        attempted=stats.attempted,
        published=stats.published,
        failed=stats.failed,
        tx_ids=stats.tx_ids,
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


async def _proof_matches_published_root(db: AsyncSession, scope: str, normalized: dict[str, Any]) -> bool:
    await _ensure_scope_public_or_safe_canary(db, scope)

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
    return root is not None and int(normalized["merkleTreeDepth"]) == int(root.merkle_depth)


def _normalize_public_proof(proof: dict[str, Any]) -> dict[str, Any]:
    if NATIVE_PROOF_KEYS.intersection(proof) and CANONICAL_PROOF_KEYS.intersection(proof):
        raise ValueError("ZK proof mixes native and canonical field names")
    return normalize_native_proof(proof) if "merkle_tree_depth" in proof else proof
