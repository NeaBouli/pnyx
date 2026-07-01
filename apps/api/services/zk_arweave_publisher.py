"""Safe ZK receipt publication to Arweave.

This module is the single publication path for GH#112 ZK receipts. It is used
by the admin endpoint and by the scheduler. It must never receive or publish
identity bridge fields.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import BillStatus, ParliamentBill, ZkMerkleRoot, ZkVoteReceipt
from services.bill_visibility import is_public_bill
from services.zk_arweave_payload import build_zk_vote_arweave_record
from services.zk_group_registry import validate_vote_scope_id

logger = logging.getLogger(__name__)

ZK_ARWEAVE_PUBLICATION_ENABLED_ENV = "ZK_ARWEAVE_PUBLICATION_ENABLED"
ZK_ARWEAVE_SCOPE_ALLOWLIST_ENV = "ZK_ARWEAVE_SCOPE_ALLOWLIST"
ZK_ARWEAVE_AUTO_PARLIAMENT_ENABLED_ENV = "ZK_ARWEAVE_AUTO_PARLIAMENT_ENABLED"
ZK_ARWEAVE_MIN_GROUP_SIZE_ENV = "ZK_ARWEAVE_MIN_GROUP_SIZE"
ZK_ARWEAVE_MIN_GROUP_SIZE_DEFAULT = 5
ZK_CANARY_ENABLED_ENV = "ZK_CANARY_ENABLED"
ZK_PUBLIC_ROLLOUT_STATUSES = {BillStatus.ACTIVE, BillStatus.WINDOW_24H, BillStatus.OPEN_END}


@dataclass(slots=True)
class ZkReceiptPublishStats:
    vote_scope_id: str
    attempted: int = 0
    published: int = 0
    failed: int = 0
    skipped_small_group: int = 0
    tx_ids: list[str] = field(default_factory=list)


class ZkArweavePublicationError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def zk_arweave_publication_enabled() -> bool:
    return _env_enabled(ZK_ARWEAVE_PUBLICATION_ENABLED_ENV)


def zk_arweave_auto_parliament_enabled() -> bool:
    return _env_enabled(ZK_ARWEAVE_AUTO_PARLIAMENT_ENABLED_ENV)


def zk_arweave_scope_allowlist() -> set[str]:
    return _scope_allowlist(ZK_ARWEAVE_SCOPE_ALLOWLIST_ENV)


def zk_arweave_min_group_size() -> int:
    raw = os.getenv(ZK_ARWEAVE_MIN_GROUP_SIZE_ENV, str(ZK_ARWEAVE_MIN_GROUP_SIZE_DEFAULT)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ZkArweavePublicationError(503, "ZK Arweave minimum group size is invalid") from exc
    if value < 2:
        raise ZkArweavePublicationError(503, "ZK Arweave minimum group size is too low")
    return value


async def publish_pending_zk_receipts_for_scope(
    db: AsyncSession,
    *,
    vote_scope_id: str,
    limit: int = 25,
    require_allowlist: bool = True,
    raise_on_small_group: bool = True,
) -> ZkReceiptPublishStats:
    if not zk_arweave_publication_enabled():
        raise ZkArweavePublicationError(503, "ZK Arweave publication is not enabled")
    if _env_enabled(ZK_CANARY_ENABLED_ENV):
        raise ZkArweavePublicationError(403, "ZK canary receipts are not published to Arweave")

    scope = validate_vote_scope_id(vote_scope_id)
    if require_allowlist:
        allowlist = zk_arweave_scope_allowlist()
        if not allowlist:
            raise ZkArweavePublicationError(503, "ZK Arweave scope allowlist is not configured")
        if scope not in allowlist:
            raise ZkArweavePublicationError(403, "ZK Arweave scope is not allowed")

    await ensure_public_parliament_scope(db, scope)
    scope_type, scope_id = scope.split(":", 1)
    if scope_type != "bill":
        raise ZkArweavePublicationError(400, "ZK Arweave publication currently supports bill scopes only")

    result = await db.execute(
        select(ZkVoteReceipt)
        .where(
            ZkVoteReceipt.vote_scope_id == scope,
            ZkVoteReceipt.arweave_pending.is_(True),
        )
        .order_by(ZkVoteReceipt.id)
        .limit(limit)
    )
    receipts = result.scalars().all()
    stats = ZkReceiptPublishStats(vote_scope_id=scope, attempted=len(receipts))
    if not receipts:
        return stats

    min_group_size = zk_arweave_min_group_size()
    publication_bucket = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    from routers.arweave import publish_to_arweave

    for receipt in receipts:
        root_result = await db.execute(
            select(ZkMerkleRoot)
            .where(
                ZkMerkleRoot.vote_scope_id == scope,
                ZkMerkleRoot.merkle_root == receipt.merkle_root,
            )
            .order_by(ZkMerkleRoot.id.desc())
            .limit(1)
        )
        root = root_result.scalar_one_or_none()
        if root is None:
            stats.failed += 1
            continue
        if int(root.group_size) < min_group_size:
            stats.skipped_small_group += 1
            if raise_on_small_group:
                raise ZkArweavePublicationError(
                    409,
                    "ZK Arweave publication requires group size "
                    f">= {min_group_size}; current group size is {root.group_size}",
                )
            continue

        record = build_zk_vote_arweave_record(
            vote_scope_id=scope,
            bill_id=scope_id,
            vote_commitment=receipt.vote_commitment,
            semaphore_nullifier=receipt.semaphore_nullifier,
            merkle_root=receipt.merkle_root,
            merkle_depth=receipt.merkle_depth,
            proof_public=receipt.proof_public_json,
            verifier_version=receipt.verifier_version,
            circuit_version=receipt.circuit_version,
            group_size=root.group_size,
            publication_bucket=publication_bucket,
        )
        tx_id = await publish_to_arweave(record, f"zk-{scope_id}-{receipt.id}")
        if not tx_id:
            stats.failed += 1
            continue
        receipt.arweave_tx_id = tx_id
        receipt.arweave_pending = False
        receipt.publication_bucket = publication_bucket
        stats.published += 1
        stats.tx_ids.append(tx_id)

    if stats.published:
        await db.commit()
    return stats


async def publish_auto_zk_arweave_receipts(db: AsyncSession, *, limit_per_scope: int = 25) -> list[ZkReceiptPublishStats]:
    if not zk_arweave_publication_enabled():
        return []
    if _env_enabled(ZK_CANARY_ENABLED_ENV):
        logger.info("[ZK-ARWEAVE] Canary enabled; automatic publication skipped")
        return []

    scopes = set(zk_arweave_scope_allowlist())
    if zk_arweave_auto_parliament_enabled():
        scopes.update(await list_pending_public_parliament_scopes(db))

    if not scopes:
        logger.info("[ZK-ARWEAVE] Publication enabled but no exact/auto scopes are eligible")
        return []

    results: list[ZkReceiptPublishStats] = []
    for scope in sorted(scopes):
        try:
            stats = await publish_pending_zk_receipts_for_scope(
                db,
                vote_scope_id=scope,
                limit=limit_per_scope,
                require_allowlist=scope in zk_arweave_scope_allowlist(),
                raise_on_small_group=False,
            )
            results.append(stats)
        except ZkArweavePublicationError as exc:
            logger.warning("[ZK-ARWEAVE] Skipped %s: %s", scope, exc.detail)
    return results


async def list_pending_public_parliament_scopes(db: AsyncSession) -> set[str]:
    result = await db.execute(
        select(ZkVoteReceipt.vote_scope_id)
        .join(ParliamentBill, ZkVoteReceipt.vote_scope_id == func.concat("bill:", ParliamentBill.id))
        .where(
            ZkVoteReceipt.arweave_pending.is_(True),
            ParliamentBill.source == "PARLIAMENT",
            ParliamentBill.admin_hidden.is_(False),
            ParliamentBill.status.in_(ZK_PUBLIC_ROLLOUT_STATUSES),
        )
        .distinct()
    )
    scopes: set[str] = set()
    for scope in result.scalars().all():
        if not str(scope).startswith("bill:DEMO-"):
            scopes.add(validate_vote_scope_id(str(scope)))
    return scopes


async def ensure_public_parliament_scope(db: AsyncSession, vote_scope_id: str) -> None:
    scope_type, scope_id = validate_vote_scope_id(vote_scope_id).split(":", 1)
    if scope_type != "bill":
        raise ZkArweavePublicationError(400, "ZK Arweave publication currently supports bill scopes only")
    result = await db.execute(select(ParliamentBill).where(ParliamentBill.id == scope_id))
    bill = result.scalar_one_or_none()
    if not _is_public_parliament_bill_scope(bill):
        raise ZkArweavePublicationError(404, "ZK vote scope not found")


def _is_public_parliament_bill_scope(bill: ParliamentBill | None) -> bool:
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
    return bill_status in ZK_PUBLIC_ROLLOUT_STATUSES


def _scope_allowlist(env_name: str) -> set[str]:
    scopes: set[str] = set()
    raw = os.getenv(env_name, "")
    for value in raw.split(","):
        clean = value.strip()
        if clean:
            scopes.add(validate_vote_scope_id(clean))
    return scopes


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "false").lower() == "true"
