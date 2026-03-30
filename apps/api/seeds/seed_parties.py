"""
seed_parties.py — Async upsert of Greek parties from parties_config.json
Reads the config, updates existing parties, inserts new ones.
Usage: python seeds/seed_parties.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from models import Party
from config import settings


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "parties_config.json")


def load_config() -> dict:
    """Load parties_config.json from disk."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


async def upsert_parties():
    """
    Upsert parties from parties_config.json.
    - Existing party (matched by id): update all fields
    - New party: insert row
    - is_active=false: soft-delete (party stays in DB but inactive)
    """
    config = load_config()
    parties = config.get("parties", [])
    version = config.get("version", "unknown")

    if not parties:
        print("No parties found in config.")
        return

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    updated, inserted = 0, 0

    async with Session() as session:
        for p in parties:
            result = await session.execute(
                select(Party).where(Party.id == p["id"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update all mutable fields
                existing.name_el = p["name_el"]
                existing.name_en = p.get("name_en")
                existing.abbreviation = p.get("abbreviation")
                existing.color_hex = p.get("color_hex")
                existing.description_el = p.get("description_el")
                existing.description_en = p.get("description_en")
                existing.is_active = p.get("is_active", True)
                updated += 1
                print(f"  Updated: {p['abbreviation']} (id={p['id']})")
            else:
                # Insert new party
                new_party = Party(
                    id=p["id"],
                    name_el=p["name_el"],
                    name_en=p.get("name_en"),
                    abbreviation=p.get("abbreviation"),
                    color_hex=p.get("color_hex"),
                    description_el=p.get("description_el"),
                    description_en=p.get("description_en"),
                    is_active=p.get("is_active", True),
                )
                session.add(new_party)
                inserted += 1
                print(f"  Inserted: {p['abbreviation']} (id={p['id']})")

        await session.commit()

    active = sum(1 for p in parties if p.get("is_active", True))
    print(f"\nDone (v{version}): {updated} updated, {inserted} inserted, {active} active.")
    await engine.dispose()


async def main():
    print(f"Loading parties from {CONFIG_PATH}")
    print(f"Database: {settings.database_url.split('@')[-1]}\n")
    await upsert_parties()


if __name__ == "__main__":
    asyncio.run(main())
