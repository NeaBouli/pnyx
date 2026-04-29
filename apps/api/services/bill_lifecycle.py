"""
Autonomous Bill Lifecycle Scheduler
Transitions bills based on parliament_vote_date:
  ANNOUNCED → ACTIVE:           14 days before vote
  ACTIVE → WINDOW_24H:          24 hours before vote
  WINDOW_24H → PARLIAMENT_VOTED: at vote time (snapshot)
  PARLIAMENT_VOTED → OPEN_END:  7 days after vote

Bills WITHOUT parliament_vote_date remain manual.
Runs every 1 hour via APScheduler.
"""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import ParliamentBill, BillStatus, BillStatusLog

logger = logging.getLogger(__name__)

# Transition rules: (from_status, timedelta_before_vote, to_status)
# Negative timedelta = before vote, positive = after vote
LIFECYCLE_RULES = [
    (BillStatus.ANNOUNCED, timedelta(days=-14), BillStatus.ACTIVE),
    (BillStatus.ACTIVE, timedelta(hours=-24), BillStatus.WINDOW_24H),
    (BillStatus.WINDOW_24H, timedelta(0), BillStatus.PARLIAMENT_VOTED),
    (BillStatus.PARLIAMENT_VOTED, timedelta(days=7), BillStatus.OPEN_END),
]


async def _transition_bill(
    db: AsyncSession,
    bill: ParliamentBill,
    new_status: BillStatus,
) -> None:
    """Execute a status transition with audit log."""
    old_status = bill.status
    bill.status = new_status
    bill.status_changed_at = datetime.now(timezone.utc)

    log = BillStatusLog(
        bill_id=bill.id,
        from_status=old_status.value,
        to_status=new_status.value,
    )
    db.add(log)

    logger.info(
        "[LIFECYCLE] %s: %s → %s (auto, vote_date=%s)",
        bill.id, old_status.value, new_status.value,
        bill.parliament_vote_date.strftime("%Y-%m-%d %H:%M") if bill.parliament_vote_date else "N/A",
    )


async def run_bill_lifecycle(db: AsyncSession) -> dict:
    """
    Check all bills with parliament_vote_date and auto-transition.
    Returns stats dict.
    """
    now = datetime.now(timezone.utc)
    stats = {"checked": 0, "transitioned": 0, "errors": 0}

    # Only bills that have a vote date and are not terminal (OPEN_END)
    result = await db.execute(
        select(ParliamentBill).where(
            ParliamentBill.parliament_vote_date.isnot(None),
            ParliamentBill.status.in_([
                BillStatus.ANNOUNCED,
                BillStatus.ACTIVE,
                BillStatus.WINDOW_24H,
                BillStatus.PARLIAMENT_VOTED,
            ]),
        )
    )
    bills = result.scalars().all()
    stats["checked"] = len(bills)

    for bill in bills:
        vote_date = bill.parliament_vote_date
        # Ensure vote_date is timezone-aware
        if vote_date.tzinfo is None:
            vote_date = vote_date.replace(tzinfo=timezone.utc)

        try:
            for from_status, offset, to_status in LIFECYCLE_RULES:
                if bill.status != from_status:
                    continue

                # Calculate trigger time
                trigger_time = vote_date + offset
                if now >= trigger_time:
                    await _transition_bill(db, bill, to_status)
                    stats["transitioned"] += 1

                    # Hooks
                    if to_status == BillStatus.ACTIVE:
                        await _hook_notify_new_bill(bill)
                    elif to_status == BillStatus.PARLIAMENT_VOTED:
                        await _hook_arweave_snapshot(db, bill)

                    break  # Only one transition per cycle per bill

        except Exception as e:
            logger.error("[LIFECYCLE] Error processing %s: %s", bill.id, e)
            stats["errors"] += 1

    if stats["transitioned"] > 0:
        await db.commit()

    return stats


async def _hook_notify_new_bill(bill: ParliamentBill) -> None:
    """Push-notify registered devices about newly ACTIVE bill."""
    try:
        import redis.asyncio as aioredis
        import os
        from routers.notify import notify_all

        r = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"), decode_responses=True)
        key = f"notified:new_bill:{bill.id}"
        if not await r.exists(key):
            await notify_all("new_bill", {
                "title": "🗳️ Νέα Ψηφοφορία",
                "body": (bill.title_el or bill.title_en or bill.id)[:100],
                "bill_id": bill.id,
            })
            await r.setex(key, 604800, "1")  # 7 days dedup
            logger.info("[LIFECYCLE] Notified: new ACTIVE bill %s", bill.id)
        await r.aclose()
    except Exception as e:
        logger.warning("[LIFECYCLE] Notify hook failed for %s: %s", bill.id, e)


async def _hook_arweave_snapshot(db: AsyncSession, bill: ParliamentBill) -> None:
    """Archive vote results to Arweave when bill reaches PARLIAMENT_VOTED."""
    try:
        from routers.arweave import build_audit_trail, publish_to_arweave
        from sqlalchemy import func, select as sa_select
        from models import CitizenVote, VoteChoice, BillStatusLog

        # Count votes
        yes = await db.scalar(
            sa_select(func.count(CitizenVote.id)).where(
                CitizenVote.bill_id == bill.id, CitizenVote.vote == VoteChoice.YES
            )
        ) or 0
        no = await db.scalar(
            sa_select(func.count(CitizenVote.id)).where(
                CitizenVote.bill_id == bill.id, CitizenVote.vote == VoteChoice.NO
            )
        ) or 0
        abstain = await db.scalar(
            sa_select(func.count(CitizenVote.id)).where(
                CitizenVote.bill_id == bill.id, CitizenVote.vote == VoteChoice.ABSTAIN
            )
        ) or 0

        # Get status logs
        logs_result = await db.execute(
            sa_select(BillStatusLog)
            .where(BillStatusLog.bill_id == bill.id)
            .order_by(BillStatusLog.changed_at)
        )
        status_logs = logs_result.scalars().all()

        audit = build_audit_trail(bill, yes, no, abstain, status_logs)
        tx_id = await publish_to_arweave(audit)
        if tx_id:
            bill.arweave_tx_id = tx_id
            logger.info("[LIFECYCLE] Arweave snapshot: %s → %s", bill.id, tx_id)
    except Exception as e:
        logger.warning("[LIFECYCLE] Arweave hook failed for %s: %s", bill.id, e)
