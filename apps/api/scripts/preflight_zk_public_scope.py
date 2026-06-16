"""Preflight a real public bill scope for GH#112 production ZK rollout.

This script is read-only. It does not enable flags, publish roots, create
commitments, or mutate votes.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import AsyncSessionLocal  # noqa: E402


VOTABLE_STATUSES = {"ACTIVE", "WINDOW_24H", "OPEN_END"}
PUBLIC_ROLLOUT_SOURCES = {"PARLIAMENT"}
PUBLIC_ROLLOUT_GOVERNANCE_LEVELS = {"NATIONAL", "INSTITUTIONAL"}


@dataclass(frozen=True)
class ZkScopeCounts:
    commitments: int
    roots: int
    receipts: int
    tier_locks: int


@dataclass(frozen=True)
class PublicScopePreflight:
    bill_id: str
    vote_scope_id: str
    title_el: str | None
    status: str | None
    source: str | None
    governance_level: str | None
    admin_hidden: bool | None
    results_visibility: str | None
    forum_topic_id: int | None
    arweave_tx_id: str | None
    counts: ZkScopeCounts
    eligible: bool
    blockers: list[str]
    warnings: list[str]


def evaluate_public_scope_candidate(
    bill: dict[str, Any] | None,
    *,
    bill_id: str,
    counts: ZkScopeCounts,
) -> PublicScopePreflight:
    """Return a conservative preflight verdict for a first public ZK scope."""
    vote_scope_id = f"bill:{bill_id}"
    blockers: list[str] = []
    warnings: list[str] = []

    if bill is None:
        blockers.append("bill_not_found")
        return PublicScopePreflight(
            bill_id=bill_id,
            vote_scope_id=vote_scope_id,
            title_el=None,
            status=None,
            source=None,
            governance_level=None,
            admin_hidden=None,
            results_visibility=None,
            forum_topic_id=None,
            arweave_tx_id=None,
            counts=counts,
            eligible=False,
            blockers=blockers,
            warnings=warnings,
        )

    status = _optional_str(bill.get("status"))
    source = _optional_str(bill.get("source"))
    governance_level = _optional_str(bill.get("governance_level"))
    admin_hidden = bool(bill.get("admin_hidden"))
    forum_topic_id = bill.get("forum_topic_id")
    arweave_tx_id = _optional_str(bill.get("arweave_tx_id"))
    results_visibility = _optional_str(bill.get("results_visibility"))

    if admin_hidden:
        blockers.append("admin_hidden_bill")
    if bill_id.startswith("DEMO-"):
        blockers.append("demo_bill_not_allowed_for_first_public_rollout")
    if bill_id == "ZK-CANARY-001" or source == "ZK_CANARY":
        blockers.append("hidden_canary_scope_not_public_rollout")
    if source not in PUBLIC_ROLLOUT_SOURCES:
        blockers.append("source_not_allowed_for_first_public_rollout")
    if status not in VOTABLE_STATUSES:
        blockers.append("bill_status_not_votable")
    if governance_level not in PUBLIC_ROLLOUT_GOVERNANCE_LEVELS:
        blockers.append("governance_scope_not_first_rollout_safe")

    if forum_topic_id is None:
        warnings.append("forum_topic_missing")
    if not arweave_tx_id:
        warnings.append("bill_not_archived_to_arweave")
    if results_visibility == "HIDDEN" and status not in {"OPEN_END", "WINDOW_24H", "PARLIAMENT_VOTED"}:
        warnings.append("results_hidden_for_active_vote")
    if counts.commitments or counts.roots or counts.receipts or counts.tier_locks:
        warnings.append("existing_zk_scope_state_present")

    return PublicScopePreflight(
        bill_id=bill_id,
        vote_scope_id=vote_scope_id,
        title_el=_optional_str(bill.get("title_el")),
        status=status,
        source=source,
        governance_level=governance_level,
        admin_hidden=admin_hidden,
        results_visibility=results_visibility,
        forum_topic_id=int(forum_topic_id) if forum_topic_id is not None else None,
        arweave_tx_id=arweave_tx_id,
        counts=counts,
        eligible=not blockers,
        blockers=blockers,
        warnings=warnings,
    )


async def preflight_bill(bill_id: str) -> PublicScopePreflight:
    vote_scope_id = f"bill:{bill_id}"
    async with AsyncSessionLocal() as db:
        bill_result = await db.execute(
            text(
                """
                SELECT id, title_el, status::text AS status, source,
                       admin_hidden, results_visibility,
                       governance_level::text AS governance_level,
                       forum_topic_id, arweave_tx_id
                FROM parliament_bills
                WHERE id = :bill_id
                """
            ),
            {"bill_id": bill_id},
        )
        bill = bill_result.mappings().first()
        counts = await _scope_counts(db, vote_scope_id)
        return evaluate_public_scope_candidate(
            dict(bill) if bill is not None else None,
            bill_id=bill_id,
            counts=counts,
        )


async def list_candidate_bills(limit: int) -> list[PublicScopePreflight]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT id, title_el, status::text AS status, source,
                       admin_hidden, results_visibility,
                       governance_level::text AS governance_level,
                       forum_topic_id, arweave_tx_id
                FROM parliament_bills
                WHERE COALESCE(admin_hidden, false) IS false
                  AND source = 'PARLIAMENT'
                  AND status::text IN ('ACTIVE', 'WINDOW_24H', 'OPEN_END')
                ORDER BY submitted_date DESC NULLS LAST,
                         parliament_vote_date DESC NULLS LAST,
                         id
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        candidates: list[PublicScopePreflight] = []
        for row in result.mappings().all():
            bill = dict(row)
            bill_id = str(bill["id"])
            counts = await _scope_counts(db, f"bill:{bill_id}")
            candidates.append(
                evaluate_public_scope_candidate(
                    bill,
                    bill_id=bill_id,
                    counts=counts,
                )
            )
        return candidates


async def _scope_counts(db: Any, vote_scope_id: str) -> ZkScopeCounts:
    queries = {
        "commitments": "SELECT count(*) FROM zk_identity_commitments WHERE vote_scope_id = :scope",
        "roots": "SELECT count(*) FROM zk_merkle_roots WHERE vote_scope_id = :scope",
        "receipts": "SELECT count(*) FROM zk_vote_receipts WHERE vote_scope_id = :scope",
        "tier_locks": "SELECT count(*) FROM zk_vote_tier_locks WHERE vote_scope_id = :scope",
    }
    values: dict[str, int] = {}
    for key, query in queries.items():
        result = await db.execute(text(query), {"scope": vote_scope_id})
        values[key] = int(result.scalar_one())
    return ZkScopeCounts(**values)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None


def _to_json(value: PublicScopePreflight | list[PublicScopePreflight]) -> str:
    if isinstance(value, list):
        payload = [asdict(item) for item in value]
    else:
        payload = asdict(value)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only preflight for public ZK bill scope")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bill-id", help="Bill id to preflight, e.g. GR-5294")
    group.add_argument("--list-candidates", action="store_true", help="List conservative public candidates")
    parser.add_argument("--limit", type=int, default=20, help="Candidate list limit")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.list_candidates:
        print(_to_json(await list_candidate_bills(args.limit)))
    else:
        print(_to_json(await preflight_bill(args.bill_id)))


if __name__ == "__main__":
    asyncio.run(main())
