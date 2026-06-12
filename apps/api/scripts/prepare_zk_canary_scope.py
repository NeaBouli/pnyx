"""Prepare the hidden GH#112 ZK canary bill scope.

Default is dry-run. Use --apply to create/update the hidden canary row.
This script intentionally does not enable any ZK flags.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import AsyncSessionLocal  # noqa: E402
from models import BillStatus, GovernanceLevel, ParliamentBill  # noqa: E402

DEFAULT_CANARY_BILL_ID = "ZK-CANARY-001"
DEFAULT_VOTE_SCOPE_ID = f"bill:{DEFAULT_CANARY_BILL_ID}"


@dataclass(frozen=True)
class CanaryBillValues:
    id: str
    title_el: str
    title_en: str
    pill_el: str
    pill_en: str
    summary_short_el: str
    summary_short_en: str
    status: BillStatus
    governance_level: GovernanceLevel
    source: str
    results_visibility: str
    admin_hidden: bool
    categories: list[str]


def canary_bill_values(bill_id: str = DEFAULT_CANARY_BILL_ID) -> CanaryBillValues:
    """Return the exact hidden row values for the ZK canary scope."""
    return CanaryBillValues(
        id=bill_id,
        title_el="ZK Canary Scope — εσωτερική δοκιμή",
        title_en="ZK Canary Scope — internal test",
        pill_el="Εσωτερική δοκιμή ZK, μη δημόσια.",
        pill_en="Internal ZK test, not public.",
        summary_short_el="Κρυφό τεχνικό αντικείμενο για ελεγχόμενη δοκιμή Semaphore ZK.",
        summary_short_en="Hidden technical object for a controlled Semaphore ZK canary.",
        status=BillStatus.ACTIVE,
        governance_level=GovernanceLevel.NATIONAL,
        source="ZK_CANARY",
        results_visibility="HIDDEN",
        admin_hidden=True,
        categories=["ZK_CANARY"],
    )


def validate_existing_canary_row(bill: Any) -> None:
    """Fail closed if an existing row is not safe to reuse as canary scope."""
    if not getattr(bill, "admin_hidden", False):
        raise RuntimeError(f"Bill {bill.id} exists but is not admin_hidden")
    if getattr(bill, "forum_topic_id", None) is not None:
        raise RuntimeError(f"Bill {bill.id} already has forum_topic_id={bill.forum_topic_id}")
    if getattr(bill, "arweave_tx_id", None):
        raise RuntimeError(f"Bill {bill.id} already has arweave_tx_id={bill.arweave_tx_id}")


def _apply_values(bill: ParliamentBill, values: CanaryBillValues) -> None:
    for key, value in asdict(values).items():
        setattr(bill, key, value)
    bill.parliament_vote_date = None
    bill.submitted_date = None
    bill.parliament_url = None
    bill.diavgeia_ada = None
    bill.party_votes_parliament = None
    bill.forum_topic_id = None
    bill.arweave_tx_id = None


async def prepare_canary_scope(*, bill_id: str, apply: bool) -> dict[str, Any]:
    """Create/update the hidden canary bill row when apply=True."""
    values = canary_bill_values(bill_id)
    async with AsyncSessionLocal() as db:
        existing = await db.get(ParliamentBill, bill_id)
        if existing:
            validate_existing_canary_row(existing)
            if apply:
                _apply_values(existing, values)
                existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await db.commit()
            return {
                "bill_id": bill_id,
                "vote_scope_id": f"bill:{bill_id}",
                "action": "updated_existing" if apply else "would_update_existing",
                "apply": apply,
                "admin_hidden": True,
            }

        if apply:
            bill = ParliamentBill()
            _apply_values(bill, values)
            db.add(bill)
            await db.commit()

        return {
            "bill_id": bill_id,
            "vote_scope_id": f"bill:{bill_id}",
            "action": "created" if apply else "would_create",
            "apply": apply,
            "admin_hidden": True,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare hidden GH#112 ZK canary scope")
    parser.add_argument("--bill-id", default=DEFAULT_CANARY_BILL_ID)
    parser.add_argument("--apply", action="store_true", help="Write hidden canary row to DB")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await prepare_canary_scope(bill_id=args.bill_id, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
