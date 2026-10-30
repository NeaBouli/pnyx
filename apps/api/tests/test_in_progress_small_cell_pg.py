"""#661 regression: the in-progress ticker works on PostgreSQL when no bill is publishable."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Import the app first, like production (keypair import order, see EKA-10 test).
import main  # noqa: F401
from models import ZkVoteReceipt
from routers import voting
from tests.pg_vote_schema import disposable_postgres_url, drop_vote_schema, requires_postgres, reset_vote_schema

pytestmark = requires_postgres


@pytest.mark.asyncio
async def test_in_progress_with_small_cells_and_empty_publishable_set(monkeypatch):
    monkeypatch.setenv("PUBLIC_RESULTS_MIN_COUNT", "10")
    engine = create_async_engine(disposable_postgres_url())
    try:
        async with engine.begin() as conn:
            await reset_vote_schema(conn, with_nullifier_index=True)
            await conn.run_sync(lambda sync: ZkVoteReceipt.__table__.create(sync, checkfirst=True))
        async with AsyncSession(engine) as db:
            ticker = await voting.get_votes_in_progress(db=db)
        assert ticker["threshold"] == max(voting.votes_in_progress_threshold(), 10)
        assert ticker["bills"] == []
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync: ZkVoteReceipt.__table__.drop(sync, checkfirst=True))
            await drop_vote_schema(conn)
        await engine.dispose()
