"""Stable all-time daily partitions for flag-enabled public window releases."""
from datetime import datetime

from sqlalchemy import String, cast, func, literal, select, union_all

from models import CitizenVote, ParliamentBill, VoteChoice, ZkVoteReceipt
from services.bill_visibility import public_bill_filter, results_visible_filter
from services.small_cell import small_cell_k, publishable_set, suppress_public_series
from services.public_bill_snapshot import snapshot_bill_filter, record_result_contributors
from services.bill_id_set import bill_ids_filter

CHOICES = ("yes", "no", "abstain", "unknown")


async def load_public_vote_days(db, *, bill_id=None, bill_ids=None):
    """Read all days, never just the requested window; no identities selected."""
    tier = select(CitizenVote.bill_id.label("bill_id"),
                  CitizenVote.created_at.label("created_at"),
                  cast(CitizenVote.vote, String).label("vote"), literal(0).label("zk"))
    tier = tier.join(ParliamentBill, CitizenVote.bill_id == ParliamentBill.id)
    zk = select(ParliamentBill.id.label("bill_id"), ZkVoteReceipt.created_at,
                ZkVoteReceipt.vote_commitment.label("vote"), literal(1).label("zk"))
    zk = zk.join(ParliamentBill, ZkVoteReceipt.vote_scope_id == func.concat("bill:", ParliamentBill.id))
    filters = [public_bill_filter(), results_visible_filter(), snapshot_bill_filter(results=True)]
    if bill_ids is not None:
        filters.append(bill_ids_filter(ParliamentBill.id, bill_ids))
    if bill_id is None:
        filters.append(~ParliamentBill.id.like("DEMO-%"))
    else:
        filters.append(ParliamentBill.id == bill_id)
    tier = tier.where(*filters)
    zk = zk.where(*filters, func.coalesce(ParliamentBill.source, "PARLIAMENT") == "PARLIAMENT",
                  ZkVoteReceipt.vote_commitment.in_([c.value for c in VoteChoice]))
    events = union_all(tier, zk).subquery("public_window_events")
    day = func.date(events.c.created_at)
    result = await db.execute(select(events.c.bill_id, day.label("day"), events.c.vote,
                                     events.c.zk, func.count().label("count"))
                              .group_by(events.c.bill_id, day, events.c.vote, events.c.zk))
    bills = {}
    for row in result.all():
        entry = bills.setdefault(row.bill_id, {"days": {}, "zk_total": 0,
                                               "sources": {}, "daily_sources": {}})
        date = str(row.day)[:10]
        bucket = entry["days"].setdefault(date, dict.fromkeys((*CHOICES, "total"), 0))
        bucket["date"] = date
        bucket[str(row.vote).lower()] += row.count
        bucket["total"] += row.count
        entry["zk_total"] += row.count if row.zk else 0
        source = entry["sources"].setdefault(row.zk, dict.fromkeys(CHOICES, 0))
        source[str(row.vote).lower()] += row.count
        daily = entry["daily_sources"].setdefault((date, row.zk), dict.fromkeys(CHOICES, 0))
        daily[str(row.vote).lower()] += row.count
    for entry in bills.values():
        entry["totals"] = {key: sum(r[key] for r in entry["days"].values())
                           for key in (*CHOICES, "total")}
    record_result_contributors(publishable_bill_ids(bills))
    return bills


def publishable_bill_ids(bills):
    return publishable_set({bill_id: (tuple(entry["totals"][c] for c in CHOICES),
                                     tuple(tuple(cells[c] for c in CHOICES)
                                           for cells in entry["sources"].values() if sum(cells.values())))
                            for bill_id, entry in bills.items()})


async def load_publishable_bill_ids(db):
    return publishable_bill_ids(await load_public_vote_days(db))


def hidden_daily_sources(entry):
    # Once scope enumeration is open, receipt timestamps also publish the ZK
    # count for every date/window, even when that narrower count is below k.
    k = small_cell_k()
    return entry["zk_total"] > 0 and any(
        count < k for cells in entry["daily_sources"].values() for count in cells.values())


def public_window_count(bills, *, since=None):
    """Sum only publishable bills; a withheld time complement withholds the sum."""
    k = small_cell_k()
    total = 0
    for bill_id in publishable_bill_ids(bills):
        entry = bills[bill_id]
        if since is None:
            total += entry["totals"]["total"]
            continue
        # Calendar-day boundaries prevent intraday overlapping cuts. Every
        # observed daily partition must be safe, including outside the window.
        days = list(entry["days"].values())
        if any(r["total"] < k for r in days) or hidden_daily_sources(entry):
            return None
        window = [r for r in days if r["date"] >= since.date().isoformat()]
        count = sum(r["total"] for r in window)
        complement = entry["totals"]["total"] - count
        if 0 < complement < k or any(
            0 < entry["totals"][c] - sum(r[c] for r in window) < k for c in CHOICES
        ):
            return None
        total += count
    return total


def public_daily_series(bills, *, since: datetime, platform: bool):
    timeline = {}
    for bill_id in publishable_bill_ids(bills):
        entry = bills[bill_id]
        days = list(entry["days"].values())
        published = suppress_public_series(days, choices=CHOICES, total="total", all_time_rows=days)
        if hidden_daily_sources(entry):
            for row in published:
                row.update(dict.fromkeys((*CHOICES, "total")))
                row["suppressed"] = True
        if platform and any(r["suppressed"] for r in published):
            continue
        for row in published:
            if row["date"] < since.date().isoformat():
                continue
            target = timeline.setdefault(row["date"], {**dict.fromkeys((*CHOICES, "total"), 0),
                                                       "date": row["date"], "suppressed": False,
                                                       "suppression_k": small_cell_k()})
            for key in (*CHOICES, "total"):
                target[key] = None if row[key] is None or target[key] is None else target[key] + row[key]
            target["suppressed"] |= row["suppressed"]
    return sorted(timeline.values(), key=lambda r: r["date"])
