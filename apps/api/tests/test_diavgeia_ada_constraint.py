"""T-9027: execute the actual ADA length rule; inspect emitted migration DDL.

SQLite exercises Unicode character length and exact identifier round trips
without PostgreSQL, provider calls, or the model's unrelated JSONB/FK columns.
Alembic's PostgreSQL offline compiler checks the real upgrade/downgrade actions;
it does not apply either migration to a database.
"""
from __future__ import annotations

import importlib.util
from io import StringIO
import os
from pathlib import Path
import re
from types import ModuleType
from collections.abc import Iterator

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from models import DiavgeiaDecision


CONSTRAINT_NAME = "diavgeia_decisions_ada_chk"
MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "y801a2b3c4d5_diavgeia_ada_length.py"
)
NINE_CHARACTER_ADAS = ("ΕΘΘ9Η-58Ψ", "Ψ7ΙΤΗ-ΗΩΞ", "6ΣΣΡΗ-ΘΑΤ")


def _model_predicate() -> str:
    constraints = [
        constraint
        for constraint in DiavgeiaDecision.__table__.constraints
        if isinstance(constraint, sa.CheckConstraint)
        and constraint.name == CONSTRAINT_NAME
    ]
    assert len(constraints) == 1, "The model must expose exactly one named ADA check"
    return str(constraints[0].sqltext)


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("t9027_ada_length_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ddl(direction: str, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    migration = _load_migration()
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    getattr(migration, direction)()
    return [
        re.sub(r"\s+", " ", statement).strip()
        for statement in output.getvalue().split(";")
        if statement.strip()
    ]


@pytest.fixture
def ada_table() -> Iterator[tuple[Engine, sa.Table]]:
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    table = sa.Table(
        "ada_constraint_fixture",
        metadata,
        sa.Column("ada", sa.String(32), nullable=False),
        sa.CheckConstraint(_model_predicate(), name=CONSTRAINT_NAME),
    )
    metadata.create_all(engine)
    try:
        yield engine, table
    finally:
        engine.dispose()


@pytest.mark.parametrize("ada", NINE_CHARACTER_ADAS)
def test_real_greek_adas_round_trip_without_identifier_changes(
    ada_table: tuple[Engine, sa.Table], ada: str,
) -> None:
    assert len(ada) == 9
    engine, table = ada_table
    with engine.begin() as connection:
        connection.execute(table.insert().values(ada=ada))
        stored = connection.execute(sa.select(table.c.ada)).scalar_one()
    assert stored == ada
    assert stored.encode("utf-8") == ada.encode("utf-8")


@pytest.mark.parametrize(
    "length, accepted", [(8, False), (9, True), (10, True), (32, True), (33, False)],
)
def test_actual_model_check_enforces_character_length_boundaries(
    ada_table: tuple[Engine, sa.Table], length: int, accepted: bool,
) -> None:
    engine, table = ada_table
    ada = "Α" * (length - 2) + "-1"
    assert len(ada) == length
    if accepted:
        with engine.begin() as connection:
            connection.execute(table.insert().values(ada=ada))
            assert connection.execute(sa.select(table.c.ada)).scalar_one() == ada
    else:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(table.insert().values(ada=ada))


def test_upgrade_replaces_only_the_named_check_without_data_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statements = _ddl("upgrade", monkeypatch)
    assert statements == [
        f"ALTER TABLE diavgeia_decisions DROP CONSTRAINT {CONSTRAINT_NAME}",
        f"ALTER TABLE diavgeia_decisions ADD CONSTRAINT {CONSTRAINT_NAME} "
        "CHECK (length(ada) BETWEEN 9 AND 32)",
    ]
    # Exact two-statement comparison excludes UPDATE/DELETE/INSERT/TRUNCATE,
    # renaming or normalizing identifiers, and touching unrelated constraints.


def test_upgrade_predicate_matches_the_actual_model(monkeypatch: pytest.MonkeyPatch) -> None:
    add_check = _ddl("upgrade", monkeypatch)[1]
    match = re.search(r"CHECK \((.+)\)$", add_check)
    assert match is not None
    normalize = lambda value: re.sub(r"\s+", " ", value).strip().lower()
    assert normalize(match.group(1)) == normalize(_model_predicate())


def test_downgrade_restores_old_check_not_valid_without_rewriting_existing_adas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statements = _ddl("downgrade", monkeypatch)
    assert statements == [
        f"ALTER TABLE diavgeia_decisions DROP CONSTRAINT {CONSTRAINT_NAME}",
        f"ALTER TABLE diavgeia_decisions ADD CONSTRAINT {CONSTRAINT_NAME} "
        "CHECK (length(ada) BETWEEN 10 AND 32) NOT VALID",
    ]
    # PostgreSQL NOT VALID deliberately avoids rescanning/rejecting already
    # stored nine-character ADAs; future writes still follow the old check.


def test_new_migration_extends_current_chain_without_forks() -> None:
    migration = _load_migration()
    assert migration.revision == "y801a2b3c4d5"
    assert migration.down_revision == "x701a2b3c4d5"
    assert migration.branch_labels is None
    assert migration.depends_on is None


def _apply_migration(connection: Connection, direction: str) -> None:
    migration = _load_migration()
    migration.op = Operations(MigrationContext.configure(connection))
    getattr(migration, direction)()


@pytest.mark.asyncio
async def test_postgres_upgrade_downgrade_preserves_existing_nine_character_adas() -> None:
    """Optional real PostgreSQL proof, restricted to an explicit loopback fixture.

    The root runner supplies an isolated local PostgreSQL namespace. All DDL
    targets a temporary table in one rollback-only transaction; no persistent
    schema, real rows, provider endpoint, or production database is touched.
    """
    raw_url = os.getenv("T9027_TEST_DATABASE_URL", "")
    if not raw_url:
        pytest.skip("T9027_TEST_DATABASE_URL not set; isolated local PostgreSQL proof optional")
    url = make_url(raw_url)
    if url.drivername != "postgresql+asyncpg" or url.host not in {"127.0.0.1", "::1", "localhost"}:
        pytest.fail("T9027 PostgreSQL fixture must use asyncpg and a loopback host")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(sa.text(
                    "CREATE TEMPORARY TABLE diavgeia_decisions ("
                    "ada varchar(32) UNIQUE NOT NULL, "
                    f"CONSTRAINT {CONSTRAINT_NAME} CHECK (length(ada) BETWEEN 10 AND 32))"
                ))
                with pytest.raises(IntegrityError) as before_upgrade:
                    async with connection.begin_nested():
                        await connection.execute(sa.text(
                            "INSERT INTO diavgeia_decisions (ada) VALUES (:ada)"
                        ), {"ada": NINE_CHARACTER_ADAS[0]})
                assert before_upgrade.value.orig.__cause__.constraint_name == CONSTRAINT_NAME
                await connection.run_sync(lambda conn: _apply_migration(conn, "upgrade"))
                for ada in NINE_CHARACTER_ADAS:
                    await connection.execute(sa.text(
                        "INSERT INTO diavgeia_decisions (ada) VALUES (:ada)"
                    ), {"ada": ada})
                rows = (await connection.execute(sa.text(
                    "SELECT ada FROM diavgeia_decisions ORDER BY ada"
                ))).scalars().all()
                assert set(rows) == set(NINE_CHARACTER_ADAS)
                validated_query = sa.text(
                    "SELECT convalidated FROM pg_constraint "
                    "WHERE conrelid = 'pg_temp.diavgeia_decisions'::regclass "
                    "AND conname = :name"
                )
                assert (await connection.execute(
                    validated_query, {"name": CONSTRAINT_NAME}
                )).scalar_one() is True

                await connection.run_sync(lambda conn: _apply_migration(conn, "downgrade"))
                assert (await connection.execute(sa.text(
                    "SELECT ada FROM diavgeia_decisions ORDER BY ada"
                ))).scalars().all() == rows
                assert (await connection.execute(
                    validated_query, {"name": CONSTRAINT_NAME}
                )).scalar_one() is False

                # NOT VALID preserves old nine-character rows, but still
                # enforces the historical minimum for subsequent writes.
                with pytest.raises(IntegrityError) as exc:
                    async with connection.begin_nested():
                        await connection.execute(sa.text(
                            "INSERT INTO diavgeia_decisions (ada) VALUES (:ada)"
                        ), {"ada": "ΑΒΓΔΕ-123"})
                assert exc.value.orig.__cause__.constraint_name == CONSTRAINT_NAME
                # NOT VALID is a rollback compatibility choice, not permission
                # to update old nine-character rows under the restored rule.
                with pytest.raises(IntegrityError) as update_after_downgrade:
                    async with connection.begin_nested():
                        await connection.execute(sa.text(
                            "UPDATE diavgeia_decisions SET ada = ada WHERE ada = :ada"
                        ), {"ada": NINE_CHARACTER_ADAS[0]})
                assert update_after_downgrade.value.orig.__cause__.constraint_name == CONSTRAINT_NAME
                await connection.execute(sa.text(
                    "INSERT INTO diavgeia_decisions (ada) VALUES (:ada)"
                ), {"ada": "ΑΒΓΔΕΖ-123"})
                expected = (await connection.execute(sa.text(
                    "SELECT ada FROM diavgeia_decisions ORDER BY ada"
                ))).scalars().all()
                await connection.run_sync(lambda conn: _apply_migration(conn, "upgrade"))
                assert (await connection.execute(
                    validated_query, {"name": CONSTRAINT_NAME}
                )).scalar_one() is True
                assert (await connection.execute(sa.text(
                    "SELECT ada FROM diavgeia_decisions ORDER BY ada"
                ))).scalars().all() == expected
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
