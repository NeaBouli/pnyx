"""
Diavgeia Decision Scraper — fetches decisions and upserts into diavgeia_decisions.
Links to dimos/periferia via dimos_diavgeia_orgs mapping.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models import DiavgeiaDecision, DimosDiavgeiaOrg
from services.diavgeia_client import DiavgeiaClient, parse_timestamp
from services.diavgeia_org_lookup import get_label as get_org_label

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "fetched": self.fetched,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
        }


async def _resolve_dimos(
    session: AsyncSession,
    organization_uid: str,
) -> tuple[int | None, int | None]:
    """Resolve dimos_id and periferia_id from org mapping."""
    result = await session.execute(
        select(DimosDiavgeiaOrg.dimos_id)
        .where(DimosDiavgeiaOrg.diavgeia_uid == organization_uid)
        .where(DimosDiavgeiaOrg.is_primary == True)  # noqa: E712
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None, None

    # Resolve periferia_id via dimos
    from models import Dimos
    dimos = await session.get(Dimos, row)
    if dimos:
        return dimos.id, dimos.periferia_id
    return row, None


async def scrape_decisions(
    session: AsyncSession,
    decision_type_uids: list[str] | None = None,
    published_after: datetime | None = None,
    max_pages: int = 10,
    dry_run: bool = False,
) -> ScrapeResult:
    """
    Fetch decisions from Diavgeia, upsert into diavgeia_decisions table.
    Links to dimos/periferia via dimos_diavgeia_orgs mapping.
    """
    if decision_type_uids is None:
        decision_type_uids = ["Α.1.1", "Α.2", "2.4.1", "2.4.2"]  # Νόμοι, Κανονιστικές, Οικονομικές

    result = ScrapeResult()

    # Determine published_after cursor
    if published_after is None:
        row = await session.execute(
            text("SELECT MAX(publish_timestamp) FROM diavgeia_decisions")
        )
        latest = row.scalar_one_or_none()
        if latest:
            published_after = latest
        else:
            published_after = datetime.now(timezone.utc) - timedelta(days=7)

    async with DiavgeiaClient() as client:
        for type_uid in decision_type_uids:
            logger.info("Scraping decision_type_uid=%s from %s (max %d pages)",
                        type_uid, published_after.isoformat(), max_pages)

            async for raw_decision in client.iter_decisions(
                decision_type_uid=type_uid,
                published_after=published_after,
                max_pages=max_pages,
            ):
                result.fetched += 1
                ada = raw_decision.get("ada")
                if not ada:
                    result.errors.append("Decision without ADA — skipped")
                    continue

                org_uid = str(raw_decision.get("organizationId", ""))
                publish_ts = parse_timestamp(raw_decision.get("issueDate"))
                submission_ts = parse_timestamp(raw_decision.get("submissionTimestamp"))

                if not publish_ts:
                    result.errors.append(f"ADA {ada}: no publish timestamp — skipped")
                    continue

                # Resolve dimos
                dimos_id, periferia_id = await _resolve_dimos(session, org_uid)
                if dimos_id is None:
                    logger.warning("ADA %s: org %s not mapped to any dimos", ada, org_uid)

                # Resolve org label from snapshot (not API — API doesn't return it)
                org_label = get_org_label(org_uid)
                if org_label.startswith("[unknown:"):
                    logger.warning("ADA %s: org %s not in snapshot — label unknown", ada, org_uid)

                row_data = {
                    "ada": ada,
                    "subject": raw_decision.get("subject", ""),
                    "decision_type_uid": raw_decision.get("decisionTypeId", type_uid),
                    "decision_type_label": raw_decision.get("decisionTypeId", ""),
                    "organization_uid": org_uid,
                    "organization_label": org_label,
                    "document_url": raw_decision.get("documentUrl", ""),
                    "submission_timestamp": submission_ts,
                    "publish_timestamp": publish_ts,
                    "raw_payload": raw_decision,
                    "dimos_id": dimos_id,
                    "periferia_id": periferia_id,
                }

                if dry_run:
                    logger.info("[DRY RUN] Would upsert ADA %s (%s)", ada, org_uid)
                    result.inserted += 1
                    continue

                # Upsert by ADA
                stmt = pg_insert(DiavgeiaDecision).values(**row_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["ada"],
                    set_={
                        "subject": stmt.excluded.subject,
                        "decision_type_label": stmt.excluded.decision_type_label,
                        "organization_label": stmt.excluded.organization_label,
                        "document_url": stmt.excluded.document_url,
                        "raw_payload": stmt.excluded.raw_payload,
                        "dimos_id": stmt.excluded.dimos_id,
                        "periferia_id": stmt.excluded.periferia_id,
                        "fetched_at": stmt.excluded.fetched_at,
                    },
                )

                try:
                    res = await session.execute(stmt)
                    if res.rowcount == 1:
                        result.inserted += 1
                    else:
                        result.updated += 1
                except Exception as e:
                    result.errors.append(f"ADA {ada}: {e}")
                    logger.error("Failed to upsert ADA %s: %s", ada, e)

    if not dry_run:
        await session.commit()

    logger.info("Scrape complete: %s", result.to_dict())
    return result
