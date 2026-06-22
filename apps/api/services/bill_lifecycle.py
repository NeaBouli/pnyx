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
from services.bill_visibility import public_bill_filter, is_public_bill

logger = logging.getLogger(__name__)

# Transition rules: (from_status, timedelta_before_vote, to_status)
# Negative timedelta = before vote, positive = after vote
LIFECYCLE_RULES = [
    (BillStatus.ANNOUNCED, timedelta(days=-14), BillStatus.ACTIVE),
    (BillStatus.ACTIVE, timedelta(hours=-24), BillStatus.WINDOW_24H),
    (BillStatus.WINDOW_24H, timedelta(0), BillStatus.PARLIAMENT_VOTED),
    (BillStatus.PARLIAMENT_VOTED, timedelta(days=7), BillStatus.OPEN_END),
]


MIN_WINDOW_24H_AGE = timedelta(hours=24)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def due_lifecycle_transitions(
    current_status: BillStatus,
    vote_date: datetime,
    now: datetime,
    status_changed_at: datetime | None = None,
) -> list[BillStatus]:
    """Return the next lifecycle status now due.

    A late scrape can discover a parliament vote date after its trigger time.
    In that case, never collapse multiple public voting states into one run:
    citizens must see at least one real ACTIVE/WINDOW_24H interval before
    PARLIAMENT_VOTED closes the normal vote UI.
    """
    for from_status, offset, to_status in LIFECYCLE_RULES:
        if current_status != from_status:
            continue
        trigger_time = vote_date + offset
        if now < trigger_time:
            break
        if (
            current_status == BillStatus.WINDOW_24H
            and to_status == BillStatus.PARLIAMENT_VOTED
            and status_changed_at is not None
            and now < _as_utc(status_changed_at) + MIN_WINDOW_24H_AGE
        ):
            return []
        return [to_status]
    return []


async def _transition_bill(
    db: AsyncSession,
    bill: ParliamentBill,
    new_status: BillStatus,
) -> None:
    """Execute a status transition with audit log."""
    old_status = bill.status
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    bill.status = new_status
    bill.status_changed_at = now_naive

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
            public_bill_filter(),
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
            due_transitions = due_lifecycle_transitions(
                bill.status,
                vote_date,
                now,
                status_changed_at=bill.status_changed_at,
            )
            if not due_transitions:
                continue

            catch_up = len(due_transitions) > 1
            for to_status in due_transitions:
                await _transition_bill(db, bill, to_status)
                stats["transitioned"] += 1

            final_status = due_transitions[-1]
            if catch_up:
                logger.info(
                    "[LIFECYCLE] %s catch-up applied %d transitions → %s",
                    bill.id, len(due_transitions), final_status.value,
                )

            # Hooks: normal one-step transitions preserve existing behavior.
            # Catch-up suppresses stale intermediate Telegram/push messages and
            # only runs the hook relevant to the final live status.
            if final_status == BillStatus.ACTIVE:
                await _hook_notify_new_bill(bill)
                await _hook_telegram_community(bill, final_status)
            elif final_status == BillStatus.WINDOW_24H:
                await _hook_telegram_community(bill, final_status)
            elif final_status == BillStatus.PARLIAMENT_VOTED:
                await _hook_arweave_snapshot(db, bill)
                await _hook_telegram_community(bill, final_status, db=db)
            elif final_status == BillStatus.OPEN_END:
                pass  # no community post for OPEN_END

        except Exception as e:
            logger.error("[LIFECYCLE] Error processing %s: %s", bill.id, e)
            stats["errors"] += 1

    if stats["transitioned"] > 0:
        await db.commit()

    # Catch-up: archive bills that missed Arweave snapshot
    catchup = await _catchup_arweave(db)
    stats["arweave_catchup"] = catchup

    return stats


async def _catchup_arweave(db: AsyncSession) -> int:
    """Find eligible bills without arweave_tx_id and archive them.

    Policy (NEA-304):
    - PARLIAMENT source only (no DIAVGEIA)
    - PARLIAMENT_VOTED or OPEN_END only
    - party_votes_parliament must be present (both statuses)
    - ANNOUNCED/ACTIVE/WINDOW_24H: never
    """
    result = await db.execute(
        select(ParliamentBill).where(
            ParliamentBill.arweave_tx_id.is_(None),
            public_bill_filter(),
            ParliamentBill.source == "PARLIAMENT",
            ParliamentBill.party_votes_parliament.isnot(None),
            ParliamentBill.status.in_([
                BillStatus.PARLIAMENT_VOTED,
                BillStatus.OPEN_END,
            ]),
        )
    )
    bills = result.scalars().all()
    archived = 0
    for bill in bills:

        await _hook_arweave_snapshot(db, bill)
        if bill.arweave_tx_id:
            archived += 1
            logger.info("[LIFECYCLE] Arweave catch-up: %s → %s", bill.id, bill.arweave_tx_id)
            await _hook_telegram_arweave(bill)

    if archived > 0:
        await db.commit()

    return archived


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


def is_arweave_eligible(bill: ParliamentBill) -> tuple[bool, str]:
    """Pure guard: check if a bill may be archived to Arweave. Returns (eligible, reason)."""
    if not is_public_bill(bill):
        return False, "admin_hidden"
    source = getattr(bill, "source", None)
    if source and source != "PARLIAMENT":
        return False, f"source={source} (not PARLIAMENT)"
    if bill.status not in (BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END):
        return False, f"status={bill.status.value} (not eligible)"
    if not bill.party_votes_parliament:
        return False, "missing party_votes_parliament"
    return True, "eligible"


async def _hook_arweave_snapshot(db: AsyncSession, bill: ParliamentBill) -> None:
    """Archive vote results to Arweave. Guards per NEA-304 policy."""
    eligible, reason = is_arweave_eligible(bill)
    if not eligible:
        logger.info("[LIFECYCLE] Arweave skipped: %s — %s", bill.id, reason)
        return

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

        vote_results = {"yes": yes, "no": no, "abstain": abstain, "total": yes + no + abstain}
        audit = build_audit_trail(bill, status_logs, vote_results, divergence_score=None)
        tx_id = await publish_to_arweave(audit, bill.id)
        if tx_id:
            bill.arweave_tx_id = tx_id
            logger.info("[LIFECYCLE] Arweave snapshot: %s → %s", bill.id, tx_id)
    except Exception as e:
        logger.warning("[LIFECYCLE] Arweave hook failed for %s: %s", bill.id, e)


async def _hook_telegram_community(bill: ParliamentBill, new_status: BillStatus, db: AsyncSession | None = None) -> None:
    """Post bill transition to community Telegram channel + group."""
    try:
        from services.telegram_community import notify_active, notify_window_24h, notify_parliament_voted
        title = bill.title_el or bill.id
        gov = bill.governance_level.value if bill.governance_level else None

        if new_status == BillStatus.ACTIVE:
            vote_date = bill.parliament_vote_date.strftime("%d.%m.%Y") if bill.parliament_vote_date else None
            await notify_active(bill.id, title, vote_date, governance_level=gov)
        elif new_status == BillStatus.WINDOW_24H:
            await notify_window_24h(bill.id, title, governance_level=gov)
        elif new_status == BillStatus.PARLIAMENT_VOTED:
            citizen_votes = 0
            if db:
                from sqlalchemy import func, select as sa_select
                from models import CitizenVote
                citizen_votes = await db.scalar(
                    sa_select(func.count(CitizenVote.id)).where(CitizenVote.bill_id == bill.id)
                ) or 0
            await notify_parliament_voted(bill.id, title, citizen_votes=citizen_votes)
    except Exception as e:
        logger.warning("[LIFECYCLE] Telegram community hook failed for %s: %s", bill.id, e)


async def _hook_telegram_arweave(bill: ParliamentBill) -> None:
    """Post Arweave archival to community Telegram."""
    try:
        from services.telegram_community import notify_arweave
        title = bill.title_el or bill.id
        if bill.arweave_tx_id:
            await notify_arweave(bill.id, title, bill.arweave_tx_id)
    except Exception as e:
        logger.warning("[LIFECYCLE] Telegram arweave hook failed for %s: %s", bill.id, e)
