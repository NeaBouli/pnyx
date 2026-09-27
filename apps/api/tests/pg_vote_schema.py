"""Disposable PostgreSQL schema helpers for the Tier-1 vote_nullifier tests (T-410).

Only used when PNYX_TEST_POSTGRES_URL points at a loopback database whose name
starts with ``pnyx_test_``; the helpers drop and recreate the vote tables there.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection

from models import (
    CITIZEN_VOTE_NULLIFIER_UNIQUE_INDEX,
    CitizenVote,
    Dimos,
    IdentityRecord,
    ParliamentBill,
    Periferia,
)

POSTGRES_URL_ENV = "PNYX_TEST_POSTGRES_URL"
VOTE_TABLES = [
    Periferia.__table__,
    Dimos.__table__,
    IdentityRecord.__table__,
    ParliamentBill.__table__,
    CitizenVote.__table__,
]
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

requires_postgres = pytest.mark.skipif(
    not os.getenv(POSTGRES_URL_ENV), reason=f"{POSTGRES_URL_ENV} not set",
)


def disposable_postgres_url() -> str:
    raw_url = os.environ[POSTGRES_URL_ENV]
    url = make_url(raw_url)
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in _LOOPBACK_HOSTS
        or not (url.database or "").lower().startswith("pnyx_test_")
    ):
        raise RuntimeError(f"{POSTGRES_URL_ENV} must target a loopback pnyx_test_* database")
    return raw_url


async def reset_vote_schema(conn: AsyncConnection, *, with_nullifier_index: bool) -> None:
    """Recreate the vote tables; optionally without the T-410 index (pre-migration state)."""
    await conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    await conn.run_sync(lambda c: CitizenVote.metadata.drop_all(c, tables=VOTE_TABLES))
    await conn.run_sync(lambda c: CitizenVote.metadata.create_all(c, tables=VOTE_TABLES))
    if not with_nullifier_index:
        await conn.exec_driver_sql(f"DROP INDEX {CITIZEN_VOTE_NULLIFIER_UNIQUE_INDEX}")


async def drop_vote_schema(conn: AsyncConnection) -> None:
    await conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    await conn.run_sync(lambda c: CitizenVote.metadata.drop_all(c, tables=VOTE_TABLES))
