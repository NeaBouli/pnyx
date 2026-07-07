"""Redact public Discourse topics for sensitive DIAVGEIA rows.

Default mode is dry-run. Apply mode requires an explicit confirmation token.
The script does not delete rows or topics; it neutralizes public forum content
and marks matching rows as admin_hidden so public surfaces stay closed.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass

import httpx
from sqlalchemy import select

from database import AsyncSessionLocal
from models import ParliamentBill
from services.bill_visibility import sensitive_diavgeia_filter
from services.discourse_sync import _headers, _request_discourse

DISCOURSE_API_URL = os.getenv("DISCOURSE_API_URL", "https://pnyx.ekklesia.gr")
CONFIRM_TOKEN = "REDACT-DIAVGEIA-PII"


@dataclass
class Target:
    bill_id: str
    forum_topic_id: int | None


def _safe_topic_title(topic_id: int | None, bill_id: str) -> str:
    suffix = topic_id if topic_id is not None else abs(hash(bill_id)) % 100000
    return f"Απόφαση Διαύγειας — προστασία προσωπικών δεδομένων #{suffix}"


def _safe_topic_body() -> str:
    return (
        "# Απόφαση Διαύγειας — προστασία προσωπικών δεδομένων\n\n"
        "Το αρχικό δημόσιο περιεχόμενο αυτού του θέματος αποκρύφθηκε, "
        "επειδή εντοπίστηκαν πιθανές ενδείξεις προσωπικών ή υγειονομικών δεδομένων.\n\n"
        "Η εκκλησία δεν αναδημοσιεύει τέτοια στοιχεία σε εφαρμογή, forum, API ή αρχεία. "
        "Το θέμα παραμένει καταγεγραμμένο μόνο ως τεχνικό ίχνος προστασίας."
    )


async def _targets(limit: int | None = None) -> list[Target]:
    async with AsyncSessionLocal() as db:
        stmt = (
            select(ParliamentBill.id, ParliamentBill.forum_topic_id)
            .where(
                ParliamentBill.admin_hidden.is_not(True),
                sensitive_diavgeia_filter(),
            )
            .order_by(ParliamentBill.created_at.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return [Target(str(row[0]), row[1]) for row in result.all()]


async def _redact_topic(client: httpx.AsyncClient, target: Target) -> bool:
    if target.forum_topic_id is None:
        return True

    title_response = await _request_discourse(
        client,
        "put",
        f"{DISCOURSE_API_URL}/t/-/{target.forum_topic_id}.json",
        json={"title": _safe_topic_title(target.forum_topic_id, target.bill_id)},
        headers=_headers(),
    )
    if title_response.status_code not in (200, 201):
        return False

    topic_response = await _request_discourse(
        client,
        "get",
        f"{DISCOURSE_API_URL}/t/{target.forum_topic_id}.json",
        headers=_headers(),
    )
    if topic_response.status_code != 200:
        return False
    posts = topic_response.json().get("post_stream", {}).get("posts", [])
    if not posts:
        return False

    post_id = posts[0]["id"]
    post_response = await _request_discourse(
        client,
        "put",
        f"{DISCOURSE_API_URL}/posts/{post_id}.json",
        json={"post": {"raw": _safe_topic_body()}},
        headers=_headers(),
    )
    return post_response.status_code in (200, 201)


async def _mark_hidden(successful_ids: list[str]) -> int:
    if not successful_ids:
        return 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ParliamentBill).where(ParliamentBill.id.in_(successful_ids))
        )
        bills = result.scalars().all()
        for bill in bills:
            bill.admin_hidden = True
        await db.commit()
        return len(bills)


async def run(*, apply: bool, confirm: str | None, limit: int | None) -> int:
    if apply and confirm != CONFIRM_TOKEN:
        raise SystemExit(f"--apply requires --confirm {CONFIRM_TOKEN}")

    targets = await _targets(limit=limit)
    with_forum = sum(1 for target in targets if target.forum_topic_id is not None)
    print(f"targets={len(targets)} with_forum={with_forum} apply={apply}")
    if not apply:
        return 0

    if not os.getenv("DISCOURSE_API_KEY"):
        raise SystemExit("DISCOURSE_API_KEY missing")

    successful: list[str] = []
    failed: list[str] = []
    async with httpx.AsyncClient(timeout=20) as client:
        for target in targets:
            ok = await _redact_topic(client, target)
            if ok:
                successful.append(target.bill_id)
            else:
                failed.append(target.bill_id)

    hidden = await _mark_hidden(successful)
    print(f"redacted={len(successful)} hidden={hidden} failed={len(failed)}")
    if failed:
        print("failed_ids_redacted=false count_only")
        return 2
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(apply=args.apply, confirm=args.confirm, limit=args.limit)))


if __name__ == "__main__":
    main()
