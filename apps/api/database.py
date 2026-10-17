from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings

# hide_parameters: DBAPI errors must not carry bound values (nullifiers,
# public keys) into logs or Sentry exception text (EVA-036 review T-9101).
engine = create_async_engine(
    settings.api_database_url or settings.database_url,
    echo=settings.env == "development",
    hide_parameters=True,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
