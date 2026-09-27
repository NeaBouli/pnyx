"""EKA-10: concurrent duplicate municipal votes must end as 409, never 500.

Runs against a real database with independent connections per session so the
check-then-insert race in POST /api/v1/municipal/vote is actually exercised:

- SQLite (aiosqlite, temp file, NullPool) — always, like test_polis_router_db.
- PostgreSQL (asyncpg) — only when PNYX_TEST_POSTGRES_URL points at a
  disposable test database, e.g.
  postgresql+asyncpg://test:test@127.0.0.1:55432/t407

A barrier inside AsyncSession.commit() holds both requests after their
duplicate pre-check SELECT has returned nothing, so both reach the INSERT and
the existing uq_diavgeia_vote constraint decides the winner deterministically.
"""
import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any

import pytest

pytest.importorskip("aiosqlite", reason="aiosqlite required for SQLite DB tests")

from fastapi import HTTPException
from nacl.signing import SigningKey
from sqlalchemy import func, insert, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import NullPool

# Import the app first, like production: main puts packages/crypto on sys.path
# before the router's lazy `from keypair import verify_signature` runs.
# Otherwise the apps/api/keypair.py shadow is cached and main's import fails.
import main  # noqa: F401
from models import (
    DiavgeiaDecision,
    DiavgeiaVote,
    Dimos,
    IdentityRecord,
    KeyStatus,
    Periferia,
    VoteChoice,
)
from routers import municipal


@compiles(JSONB, "sqlite")
def _jsonb_as_sqlite_json(_type: JSONB, _compiler: Any, **_kw: Any) -> str:
    return "JSON"


_TABLES = [
    Periferia.__table__,
    Dimos.__table__,
    IdentityRecord.__table__,
    DiavgeiaDecision.__table__,
    DiavgeiaVote.__table__,
]

ADA = "ADA-EKA10-RACE-1"
OTHER_ADA = "ADA-EKA10-RACE-2"
PERIFERIA_ID = 6
DIMOS_ID = 22
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _disposable_postgres_url() -> str:
    raw_url = os.environ["PNYX_TEST_POSTGRES_URL"]
    url = make_url(raw_url)
    database = (url.database or "").lower()
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in _LOOPBACK_HOSTS
        or not (database == "t407" or database.startswith("pnyx_test_"))
    ):
        raise RuntimeError("PNYX_TEST_POSTGRES_URL must target a loopback disposable test database")
    return raw_url


def _backends() -> list[Any]:
    params: list[Any] = ["sqlite"]
    if os.getenv("PNYX_TEST_POSTGRES_URL"):
        params.append("postgres")
    else:
        params.append(pytest.param(
            "postgres",
            marks=pytest.mark.skip(reason="PNYX_TEST_POSTGRES_URL not set"),
        ))
    return params


@pytest.fixture(params=_backends())
async def engine(request: pytest.FixtureRequest, tmp_path: Any) -> AsyncIterator[AsyncEngine]:
    if request.param == "postgres":
        url = _disposable_postgres_url()
    else:
        url = f"sqlite+aiosqlite:///{tmp_path / 'eka10.db'}"
    eng = create_async_engine(url, poolclass=NullPool)
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: DiavgeiaVote.metadata.drop_all(c, tables=_TABLES))
        await conn.run_sync(lambda c: DiavgeiaVote.metadata.create_all(c, tables=_TABLES))
    try:
        yield eng
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(lambda c: DiavgeiaVote.metadata.drop_all(c, tables=_TABLES))
        await eng.dispose()


def test_postgres_fixture_rejects_non_disposable_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "PNYX_TEST_POSTGRES_URL",
        "postgresql+asyncpg://user:secret@db.example.org/production",
    )
    with pytest.raises(RuntimeError, match="loopback disposable test database"):
        _disposable_postgres_url()


def test_postgres_fixture_accepts_explicit_loopback_test_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_url = "postgresql+asyncpg://test:test@127.0.0.1:55432/t407"
    monkeypatch.setenv("PNYX_TEST_POSTGRES_URL", raw_url)
    assert _disposable_postgres_url() == raw_url


@pytest.fixture
async def voter(engine: AsyncEngine) -> SigningKey:
    signing_key = SigningKey.generate()
    async with engine.begin() as conn:
        await conn.execute(insert(Periferia.__table__).values(
            id=PERIFERIA_ID, name_el="Αττική", code="GR-ATT", is_active=True,
        ))
        await conn.execute(insert(Dimos.__table__).values(
            id=DIMOS_ID, name_el="Αθηναίων", periferia_id=PERIFERIA_ID, is_active=True,
        ))
        await conn.execute(insert(IdentityRecord.__table__).values(
            id=1,
            nullifier_hash=_nullifier(),
            nullifier_version="v1",
            public_key_hex=signing_key.verify_key.encode().hex(),
            periferia_id=PERIFERIA_ID,
            dimos_id=DIMOS_ID,
            region_locked=False,
            source="SMS",
            status=KeyStatus.ACTIVE.name,
            created_at=func.now(),
        ))
        for decision_id, ada in ((1, ADA), (2, OTHER_ADA)):
            await conn.execute(insert(DiavgeiaDecision.__table__).values(
                id=decision_id,
                ada=ada,
                subject="Έγκριση προϋπολογισμού",
                decision_type_uid="2.4.6.1",
                organization_uid="6106",
                organization_label="ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ",
                document_url="https://diavgeia.gov.gr/doc/test",
                publish_timestamp=func.now(),
                raw_payload={},
                fetched_at=func.now(),
                dimos_id=DIMOS_ID,
                periferia_id=PERIFERIA_ID,
                governance_level="MUNICIPAL",
            ))
    return signing_key


def _nullifier() -> str:
    return "e" * 64


def _request(signing_key: SigningKey, ada: str = ADA, vote: str = "YES") -> municipal.DecisionVoteRequest:
    payload = f"municipal:{ada}:{vote}:{_nullifier()}"
    return municipal.DecisionVoteRequest(
        ada=ada,
        nullifier_hash=_nullifier(),
        vote=vote,
        signature_hex=signing_key.sign(payload.encode("utf-8")).signature.hex(),
    )


class _BarrierSession(AsyncSession):
    """Holds commit() until every racing request has passed its pre-check."""

    barrier: asyncio.Barrier

    async def commit(self) -> None:
        await self.barrier.wait()
        await super().commit()


async def _vote_outcome(db: AsyncSession, req: municipal.DecisionVoteRequest) -> Any:
    try:
        return await municipal.vote_on_decision(req, db)
    except HTTPException as exc:
        return exc.status_code
    except Exception as exc:  # noqa: BLE001 - the race outcome is the assertion subject
        return exc


async def _stored_votes(engine: AsyncEngine, ada: str = ADA) -> int:
    async with AsyncSession(engine) as db:
        return int(await db.scalar(
            select(func.count()).select_from(DiavgeiaVote).where(DiavgeiaVote.ada == ada)
        ) or 0)


async def test_concurrent_identical_votes_yield_one_success_and_one_409(
    engine: AsyncEngine, voter: SigningKey,
) -> None:
    _BarrierSession.barrier = asyncio.Barrier(2)
    sessions = [_BarrierSession(engine, expire_on_commit=False) for _ in range(2)]
    try:
        outcomes = await asyncio.wait_for(asyncio.gather(
            *(_vote_outcome(db, _request(voter)) for db in sessions)
        ), timeout=30)

        successes = [o for o in outcomes if isinstance(o, dict)]
        conflicts = [o for o in outcomes if o == 409]
        assert len(successes) == 1, outcomes
        assert len(conflicts) == 1, outcomes
        assert successes[0] == {"success": True, "ada": ADA, "vote": "YES"}
        assert await _stored_votes(engine) == 1

        # Both sessions — including the one that lost the race — stay usable.
        for db in sessions:
            count = await db.scalar(
                select(func.count()).select_from(DiavgeiaVote).where(DiavgeiaVote.ada == ADA)
            )
            assert count == 1
    finally:
        for db in sessions:
            await db.close()


async def test_sequential_duplicate_vote_is_409(engine: AsyncEngine, voter: SigningKey) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as db:
        first = await municipal.vote_on_decision(_request(voter), db)
        assert first["success"] is True

        with pytest.raises(HTTPException) as exc:
            await municipal.vote_on_decision(_request(voter, vote="NO"), db)
        assert exc.value.status_code == 409

    assert await _stored_votes(engine) == 1
    async with AsyncSession(engine) as db:
        stored = await db.scalar(select(DiavgeiaVote.vote).where(DiavgeiaVote.ada == ADA))
    assert stored == VoteChoice.YES


async def test_insert_race_past_precheck_maps_to_409_and_rolls_back(
    engine: AsyncEngine, voter: SigningKey,
) -> None:
    """A row committed after the pre-check still ends as 409, not 500."""
    async with AsyncSession(engine, expire_on_commit=False) as db:
        original_execute = db.execute
        calls = 0

        async def execute_then_commit_competitor(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            result = await original_execute(*args, **kwargs)
            if calls == 3:  # identity, decision, duplicate pre-check
                async with engine.begin() as conn:
                    await conn.execute(insert(DiavgeiaVote.__table__).values(
                        ada=ADA, nullifier_hash=_nullifier(), vote=VoteChoice.NO.name,
                    ))
            return result

        db.execute = execute_then_commit_competitor  # type: ignore[method-assign]
        with pytest.raises(HTTPException) as exc:
            await municipal.vote_on_decision(_request(voter), db)
        assert exc.value.status_code == 409

        db.execute = original_execute  # type: ignore[method-assign]
        assert await db.scalar(
            select(func.count()).select_from(DiavgeiaVote).where(DiavgeiaVote.ada == ADA)
        ) == 1

    async with AsyncSession(engine) as db:
        stored = await db.scalar(select(DiavgeiaVote.vote).where(DiavgeiaVote.ada == ADA))
    assert stored == VoteChoice.NO


async def test_other_integrity_error_is_not_masked_as_409(
    engine: AsyncEngine, voter: SigningKey,
) -> None:
    """A unique violation on a different constraint stays an internal error."""
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE UNIQUE INDEX uq_test_eka10_other ON diavgeia_votes (nullifier_hash)"
        ))

    async with AsyncSession(engine, expire_on_commit=False) as db:
        first = await municipal.vote_on_decision(_request(voter, ada=ADA), db)
        assert first["success"] is True

        with pytest.raises(IntegrityError):
            await municipal.vote_on_decision(_request(voter, ada=OTHER_ADA), db)

        # Rolled back: the session is usable and nothing leaked in.
        assert await db.scalar(select(func.count()).select_from(DiavgeiaVote)) == 1

    assert await _stored_votes(engine, OTHER_ADA) == 0


async def test_non_unique_integrity_error_is_not_masked_as_409(
    engine: AsyncEngine, voter: SigningKey,
) -> None:
    if engine.dialect.name != "postgresql":
        pytest.skip("ALTER TABLE ADD CONSTRAINT CHECK is PostgreSQL-only")
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE diavgeia_votes ADD CONSTRAINT ck_test_eka10 "
            f"CHECK (ada <> '{OTHER_ADA}')"
        ))

    async with AsyncSession(engine, expire_on_commit=False) as db:
        with pytest.raises(IntegrityError):
            await municipal.vote_on_decision(_request(voter, ada=OTHER_ADA), db)
        assert await db.scalar(select(func.count()).select_from(DiavgeiaVote)) == 0


async def test_http_concurrent_identical_votes_return_200_and_409(
    engine: AsyncEngine, voter: SigningKey,
) -> None:
    from httpx import ASGITransport, AsyncClient

    from database import get_db

    app = main.app

    _BarrierSession.barrier = asyncio.Barrier(2)

    async def _get_racing_db() -> AsyncIterator[AsyncSession]:
        async with _BarrierSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = _get_racing_db
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            body = _request(voter).model_dump()
            responses = await asyncio.wait_for(asyncio.gather(
                client.post("/api/v1/municipal/vote", json=body),
                client.post("/api/v1/municipal/vote", json=body),
            ), timeout=30)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert sorted(r.status_code for r in responses) == [200, 409]
    ok = next(r for r in responses if r.status_code == 200)
    conflict = next(r for r in responses if r.status_code == 409)
    assert ok.json() == {"success": True, "ada": ADA, "vote": "YES"}
    assert conflict.json() == {"detail": "Έχετε ήδη ψηφίσει για αυτή την απόφαση."}
    assert await _stored_votes(engine) == 1
