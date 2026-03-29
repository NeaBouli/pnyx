"""
Seed-Script: Lädt Parteien, Thesen und Gesetzentwürfe in die Datenbank.
Ausführung: python seeds/seed.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from models import Base, Party, Statement, ParliamentBill, BillStatus
from config import settings


async def seed():
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    seeds_dir = os.path.dirname(__file__)

    async with Session() as session:
        # 1. Parteien
        with open(os.path.join(seeds_dir, "parties.json")) as f:
            for p in json.load(f):
                session.add(Party(**p))

        # 2. Thesen
        with open(os.path.join(seeds_dir, "statements.json")) as f:
            for i, s in enumerate(json.load(f)):
                s["display_order"] = i + 1
                session.add(Statement(**s))

        # 3. Gesetzentwürfe
        with open(os.path.join(seeds_dir, "bills.json")) as f:
            for b in json.load(f):
                vote_date = None
                if b.get("parliament_vote_date"):
                    vote_date = datetime.fromisoformat(b["parliament_vote_date"])
                bill = ParliamentBill(
                    id=b["id"],
                    title_el=b["title_el"],
                    title_en=b.get("title_en"),
                    pill_el=b.get("pill_el"),
                    pill_en=b.get("pill_en"),
                    summary_short_el=b.get("summary_short_el"),
                    summary_short_en=b.get("summary_short_en"),
                    categories=b.get("categories"),
                    party_votes_parliament=b.get("party_votes_parliament"),
                    status=BillStatus(b.get("status", "ANNOUNCED")),
                    parliament_vote_date=vote_date,
                )
                session.add(bill)

        await session.commit()
        print("✅ Seed abgeschlossen:")
        print("   8 Parteien | 15 Thesen | 3 Gesetzentwürfe")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
