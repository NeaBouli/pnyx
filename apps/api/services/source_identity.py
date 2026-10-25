"""Preserve existing bill IDs when official source URL paths change."""
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ParliamentBill


def official_law_id(url: object) -> str | None:
    if not isinstance(url, str):
        return None
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in {
            "www.hellenicparliament.gr", "hellenicparliament.gr",
        } or parsed.username or parsed.password or parsed.port not in {None, 443}
            or not parsed.path.startswith("/Nomothetiko-Ergo/")):
            return None
        values = parse_qs(parsed.query, keep_blank_values=True).get("law_id", [])
        if len(values) != 1:
            return None
        identity = UUID(values[0])
        return str(identity) if identity.int else None
    except (ValueError, TypeError):
        return None


async def find_existing_parliament_bill(
    db: AsyncSession, *, bill_id: str, url: object,
) -> ParliamentBill | None:
    identity = official_law_id(url)
    if identity is None:
        result = await db.execute(select(ParliamentBill).where(ParliamentBill.id == bill_id))
        return result.scalar_one_or_none()
    # Narrow in SQL, then validate the actual URL query binding in Python.
    # This matches submitted/voted/search links and retains legacy GR-lawnum
    # IDs, votes, lifecycle state and manually maintained content.
    result = await db.execute(select(ParliamentBill).where(
        ParliamentBill.source == "PARLIAMENT",
        or_(ParliamentBill.id == bill_id, ParliamentBill.parliament_url.ilike("%" + identity + "%")),
    ))
    rows = result.scalars().all()
    matches = [row for row in rows if official_law_id(row.parliament_url) == identity]
    if len(matches) > 1:
        raise ValueError("Multiple stored bills share one official source identity")
    if matches:
        return matches[0]
    legacy = next((row for row in rows if row.id == bill_id), None)
    if legacy and official_law_id(legacy.parliament_url) is not None:
        raise ValueError("Stored bill ID belongs to another official source identity")
    return legacy
