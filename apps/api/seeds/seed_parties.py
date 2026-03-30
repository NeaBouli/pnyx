"""
Scalable party management. Config in parties_config.json.
Usage: python seeds/seed_parties.py
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from models import Party
from config import settings

async def seed_parties():
    config_path = os.path.join(os.path.dirname(__file__), "parties_config.json")
    with open(config_path) as f:
        config = json.load(f)

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        for p in config["parties"]:
            result = await session.execute(select(Party).where(Party.id == p["id"]))
            existing = result.scalar_one_or_none()
            if existing:
                for k, v in p.items():
                    if k != "id":
                        setattr(existing, k, v)
                print(f"  Updated: {p['abbreviation']}")
            else:
                session.add(Party(**p))
                print(f"  Added: {p['abbreviation']}")
        await session.commit()

    active = sum(1 for p in config["parties"] if p.get("is_active", True))
    print(f"\n✅ {active} active parties from {len(config['parties'])} total")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_parties())
