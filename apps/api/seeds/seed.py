"""
Seed-Script: Lädt Parteien und Thesen in die Datenbank.
Ausführung: python seeds/seed.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from models import Base, Party, Statement
from config import settings


async def seed():
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    seeds_dir = os.path.dirname(__file__)

    async with Session() as session:
        # Parteien
        with open(os.path.join(seeds_dir, "parties.json")) as f:
            parties_data = json.load(f)

        for p in parties_data:
            party = Party(**p)
            session.add(party)

        # Thesen
        with open(os.path.join(seeds_dir, "statements.json")) as f:
            statements_data = json.load(f)

        for i, s in enumerate(statements_data):
            s["display_order"] = i + 1
            statement = Statement(**s)
            session.add(statement)

        await session.commit()
        print(f"✅ {len(parties_data)} Parteien geladen")
        print(f"✅ {len(statements_data)} Thesen geladen")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
