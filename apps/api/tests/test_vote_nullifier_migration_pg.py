"""T-410: migration x701a2b3c4d5 — case-insensitive unique Tier-1 vote_nullifier.

Runs the real Alembic CLI against a disposable local PostgreSQL
(PNYX_TEST_POSTGRES_URL, loopback, database name pnyx_test_*). The schema is
built from the models at revision v501a2b3c4d5 (without the new index) and
stamped, because the full migration chain does not replay on an empty DB.
"""
from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from models import CITIZEN_VOTE_NULLIFIER_UNIQUE_INDEX
from tests.pg_vote_schema import (
    disposable_postgres_url,
    drop_vote_schema,
    requires_postgres,
    reset_vote_schema,
)

pytestmark = requires_postgres

API_DIR = Path(__file__).resolve().parents[1]
PREVIOUS = "v501a2b3c4d5"
TARGET = "x701a2b3c4d5"
NULLIFIER = "ab" * 32
BILL_A = "GR-T410-A"
BILL_B = "GR-T410-B"


def _alembic(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": disposable_postgres_url()}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR, env=env, capture_output=True, text=True, timeout=120,
    )


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(disposable_postgres_url(), poolclass=NullPool)
    async with eng.begin() as conn:
        await reset_vote_schema(conn, with_nullifier_index=False)
        for bill_id in (BILL_A, BILL_B):
            await conn.execute(text(
                "INSERT INTO parliament_bills (id, title_el, status, governance_level)"
                " VALUES (:id, 'T-410', 'ACTIVE', 'NATIONAL')"
            ), {"id": bill_id})
    stamp = _alembic("stamp", PREVIOUS)
    assert stamp.returncode == 0, stamp.stderr
    try:
        yield eng
    finally:
        async with eng.begin() as conn:
            await drop_vote_schema(conn)
        await eng.dispose()


async def _insert_vote(
    engine: AsyncEngine, citizen: str, bill_id: str, vote_nullifier: str | None,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO citizen_votes"
            " (nullifier_hash, bill_id, vote, signature_hex, vote_nullifier, is_correction)"
            " VALUES (:citizen, :bill, 'YES', :sig, :vn, false)"
        ), {"citizen": citizen * 64, "bill": bill_id, "sig": "b" * 128, "vn": vote_nullifier})


async def _rows(engine: AsyncEngine) -> list[tuple]:
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT id, nullifier_hash, bill_id, vote::text, vote_nullifier"
            " FROM citizen_votes ORDER BY id"
        ))
        return [tuple(r) for r in result]


async def _indexes(engine: AsyncEngine) -> dict[str, str]:
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'citizen_votes'"
        ))
        return dict(result.all())


async def _index_valid(engine: AsyncEngine) -> bool | None:
    async with engine.connect() as conn:
        return (await conn.execute(text(
            "SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid"
            " WHERE c.relname = :name"
        ), {"name": CITIZEN_VOTE_NULLIFIER_UNIQUE_INDEX})).scalar_one_or_none()


async def _version(engine: AsyncEngine) -> str:
    async with engine.connect() as conn:
        return (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()


async def test_upgrade_downgrade_upgrade_keeps_data_and_other_indexes(engine: AsyncEngine) -> None:
    # Legacy/Tier-0 NULLs (several) plus one mixed-case legacy Tier-1 value.
    await _insert_vote(engine, "1", BILL_A, None)
    await _insert_vote(engine, "2", BILL_A, None)
    await _insert_vote(engine, "3", BILL_A, NULLIFIER.upper())
    rows_before = await _rows(engine)
    indexes_before = await _indexes(engine)
    assert CITIZEN_VOTE_NULLIFIER_UNIQUE_INDEX not in indexes_before

    up = _alembic("upgrade", TARGET)
    assert up.returncode == 0, up.stderr
    indexes_after = await _indexes(engine)
    definition = indexes_after.pop(CITIZEN_VOTE_NULLIFIER_UNIQUE_INDEX)
    assert "CREATE UNIQUE INDEX" in definition
    assert "lower((vote_nullifier)::text)" in definition
    assert "WHERE (vote_nullifier IS NOT NULL)" in definition
    assert indexes_after == indexes_before
    assert await _index_valid(engine) is True
    assert await _rows(engine) == rows_before  # nothing rewritten (uppercase kept)
    assert await _version(engine) == TARGET

    # The index protects the pre-existing uppercase value case-insensitively,
    # across bills, while NULL rows stay unconstrained.
    with pytest.raises(IntegrityError) as exc:
        await _insert_vote(engine, "4", BILL_B, NULLIFIER)
    assert exc.value.orig.__cause__.constraint_name == CITIZEN_VOTE_NULLIFIER_UNIQUE_INDEX
    await _insert_vote(engine, "4", BILL_B, None)

    down = _alembic("downgrade", PREVIOUS)
    assert down.returncode == 0, down.stderr
    assert await _indexes(engine) == indexes_before  # only the new index removed
    assert await _version(engine) == PREVIOUS
    assert len(await _rows(engine)) == len(rows_before) + 1

    again = _alembic("upgrade", TARGET)
    assert again.returncode == 0, again.stderr
    assert await _index_valid(engine) is True
    assert await _version(engine) == TARGET


@pytest.mark.parametrize(
    "first, second, second_bill",
    [
        (NULLIFIER, NULLIFIER, BILL_B),            # exact duplicate, other bill
        (NULLIFIER, NULLIFIER.upper(), BILL_A),    # case duplicate, same bill
        (NULLIFIER.upper(), NULLIFIER, BILL_B),    # case duplicate, other bill
    ],
)
async def test_preflight_aborts_on_duplicates_without_changes(
    engine: AsyncEngine, first: str, second: str, second_bill: str,
) -> None:
    await _insert_vote(engine, "1", BILL_A, first)
    await _insert_vote(engine, "2", second_bill, second)
    await _insert_vote(engine, "3", BILL_A, None)
    rows_before = await _rows(engine)
    indexes_before = await _indexes(engine)

    up = _alembic("upgrade", TARGET)

    assert up.returncode != 0
    output = up.stdout + up.stderr
    assert "VoteNullifierPreflightError" in output
    assert "1 case-insensitive duplicate group(s)" in output
    # Fail closed without disclosing any value.
    assert NULLIFIER not in output.lower()
    assert await _rows(engine) == rows_before
    assert await _indexes(engine) == indexes_before
    assert await _index_valid(engine) is None
    assert await _version(engine) == PREVIOUS


async def test_upgrade_refuses_preexisting_index_with_same_name(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(
            f"CREATE INDEX {CITIZEN_VOTE_NULLIFIER_UNIQUE_INDEX} ON citizen_votes (vote_nullifier)"
        ))
    up = _alembic("upgrade", TARGET)
    assert up.returncode != 0
    assert "already exists before upgrade" in up.stdout + up.stderr
    assert await _version(engine) == PREVIOUS
