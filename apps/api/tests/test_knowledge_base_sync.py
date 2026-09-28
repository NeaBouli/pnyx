"""EKA-57 knowledge_base lifecycle: canonical catalog, exact sync, read-only check.

DB-free by default (in-memory fake engine). The final test exercises real
PostgreSQL only when PNYX_TEST_POSTGRES_URL targets a loopback pnyx_test_* DB.
"""
from __future__ import annotations

import copy
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.dml import Delete, Insert, Update
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.selectable import Select

from scripts import seed_knowledge_base as kb
from tests.pg_vote_schema import disposable_postgres_url, requires_postgres

REPO_ROOT = Path(__file__).resolve().parents[3]
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"


# ─── Fake engine ──────────────────────────────────────────────────────────────


class FakeDbError(Exception):
    pass


class FakeDb:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows: dict[int, dict[str, Any]] = {row["id"]: dict(row) for row in rows}
        self.commits = 0
        self.rollbacks = 0
        self.disposed = False
        self.fail_on: type | None = None
        self.ignore_deletes = False


class FakeRow:
    def __init__(self, mapping: dict[str, Any]) -> None:
        self._mapping = mapping


class FakeConn:
    """Transaction-local copy of FakeDb; applies Core DML compiled for PostgreSQL."""

    def __init__(self, db: FakeDb) -> None:
        self.db = db
        self.work = copy.deepcopy(db.rows)
        self.statements: list[Any] = []
        self.read_only = False

    @property
    def writes(self) -> list[Any]:
        return [s for s in self.statements if isinstance(s, (Insert, Update, Delete))]

    async def execute(self, stmt: Any) -> list[FakeRow] | None:
        self.statements.append(stmt)
        if isinstance(stmt, TextClause):
            if "READ ONLY" in stmt.text:
                self.read_only = True
            return None
        if isinstance(stmt, Select):
            return [FakeRow(copy.deepcopy(self.work[i])) for i in sorted(self.work)]
        if self.read_only:
            raise FakeDbError("cannot execute DML in a read-only transaction")
        if self.db.fail_on is not None and isinstance(stmt, self.db.fail_on):
            raise FakeDbError("injected failure")
        params = stmt.compile(dialect=postgresql.dialect()).params
        values = {name: params[name] for name in kb.FIELDS if name in params}
        if isinstance(stmt, Delete):
            if not self.db.ignore_deletes:
                for row_id in params["id_1"]:
                    del self.work[row_id]
        elif isinstance(stmt, Update):
            self.work[params["id_1"]].update(values)
        else:
            new_id = max([*self.work, *self.db.rows, 0]) + 1
            self.work[new_id] = {"id": new_id, **values}
        return None

    async def rollback(self) -> None:
        self.db.rollbacks += 1


class FakeEngine:
    def __init__(self, db: FakeDb) -> None:
        self.db = db
        self.connections: list[FakeConn] = []

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[FakeConn]:
        conn = FakeConn(self.db)
        self.connections.append(conn)
        try:
            yield conn
        except BaseException:
            self.db.rollbacks += 1
            raise
        self.db.rows = conn.work
        self.db.commits += 1

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[FakeConn]:
        conn = FakeConn(self.db)
        self.connections.append(conn)
        yield conn  # never committed; work is discarded

    async def dispose(self) -> None:
        self.db.disposed = True


# ─── Helpers ──────────────────────────────────────────────────────────────────


CATALOG = kb.canonical_rows(kb.ENTRIES)
KEYS = list(CATALOG)


def _row(row_id: int, key: tuple[str, str], **overrides: Any) -> dict[str, Any]:
    return {"id": row_id, **copy.deepcopy(CATALOG[key]), **overrides}


def _exact_rows() -> list[dict[str, Any]]:
    return [_row(i + 1, key) for i, key in enumerate(KEYS)]


def _as_catalog(rows: dict[int, dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    by_key = {(r["category"], r["title_en"]): {f: r[f] for f in kb.FIELDS} for r in rows.values()}
    assert len(by_key) == len(rows), "duplicate natural keys remain"
    return by_key


def _drifted_rows() -> list[dict[str, Any]]:
    """Missing KEYS[0], changed KEYS[1], duplicate KEYS[2], stale + NULL-title rows."""
    rows = [_row(10 + i, key) for i, key in enumerate(KEYS[1:])]
    rows[0]["content_en"] = "outdated"
    rows.append(_row(99, KEYS[2]))
    rows.append({**_row(5, KEYS[3]), "title_en": "Who created ekklesia?"})
    rows.append({**_row(6, KEYS[4]), "title_en": None})
    return rows


# ─── Canonical catalog ────────────────────────────────────────────────────────


def test_canonical_catalog_keys_are_unique_and_non_empty() -> None:
    assert len(CATALOG) == len(kb.ENTRIES) == 14
    for category, title_en in CATALOG:
        assert category.strip() and title_en.strip()


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda e: e + [e[0]], "duplicate natural key"),
        (lambda e: [(e[0][0], e[0][1], "  ", *e[0][3:])] + e[1:], "title_en"),
        (lambda e: [("", *e[0][1:])] + e[1:], "category"),
        (lambda e: [(*e[0][:5], "not json", e[0][6])] + e[1:], "keywords"),
        (lambda e: [(*e[0][:5], '{"a": 1}', e[0][6])] + e[1:], "keywords"),
        (lambda e: [(*e[0][:6], True)] + e[1:], "priority"),
        (lambda e: [e[0][:6]] + e[1:], "expected 7 fields"),
    ],
)
def test_canonical_catalog_rejects_invalid_entries(mutate: Any, message: str) -> None:
    with pytest.raises(kb.CatalogError, match=message):
        kb.canonical_rows(mutate(list(kb.ENTRIES)))


# ─── Diff ─────────────────────────────────────────────────────────────────────


def test_plan_is_empty_only_for_exact_match() -> None:
    assert kb.plan_sync(CATALOG, _exact_rows()).is_empty


@pytest.mark.parametrize("name", ["title_el", "content_el", "content_en", "keywords", "priority"])
def test_plan_detects_changed_field_and_keeps_id(name: str) -> None:
    rows = _exact_rows()
    rows[3][name] = ["changed"] if name == "keywords" else (9 if name == "priority" else "changed")

    plan = kb.plan_sync(CATALOG, rows)

    assert plan.updates == [(rows[3]["id"], KEYS[3])]
    assert not (plan.inserts or plan.stale or plan.duplicates)


def test_plan_classifies_missing_stale_and_duplicate_rows() -> None:
    plan = kb.plan_sync(CATALOG, _drifted_rows())

    assert plan.inserts == [KEYS[0]]
    assert plan.updates == [(10, KEYS[1])]
    assert plan.duplicates == [99]  # lowest id per key is kept
    assert sorted(plan.stale) == [5, 6]
    assert plan.deletes == [5, 6, 99]
    assert "outdated" not in plan.summary()


def test_plan_treats_changed_natural_key_as_stale_plus_missing() -> None:
    rows = _exact_rows()
    rows[0]["category"] = "legacy"

    plan = kb.plan_sync(CATALOG, rows)

    assert plan.stale == [1] and plan.inserts == [KEYS[0]] and not plan.updates


# ─── Sync / check against the fake engine ────────────────────────────────────


async def test_sync_reconciles_exactly_and_preserves_matching_ids() -> None:
    db = FakeDb(_drifted_rows())
    engine = FakeEngine(db)

    assert await kb.run("sync", engine) == kb.EXIT_OK

    assert _as_catalog(db.rows) == CATALOG
    assert {10, 11, 12} <= set(db.rows)  # changed + matching rows keep their ids
    assert not {5, 6, 99} & set(db.rows)
    assert db.commits == 1 and db.rollbacks == 0 and db.disposed
    first = engine.connections[0].statements[0]
    assert isinstance(first, TextClause) and first.text.startswith("LOCK TABLE knowledge_base")


async def test_sync_is_idempotent() -> None:
    db = FakeDb(_drifted_rows())
    await kb.run("sync", FakeEngine(db))
    snapshot = copy.deepcopy(db.rows)

    engine = FakeEngine(db)
    assert await kb.run("sync", engine) == kb.EXIT_OK

    assert db.rows == snapshot
    assert engine.connections[0].writes == []


async def test_sync_populates_empty_table() -> None:
    db = FakeDb([])
    assert await kb.run("sync", FakeEngine(db)) == kb.EXIT_OK
    assert _as_catalog(db.rows) == CATALOG


async def test_check_is_read_only_and_reports_drift() -> None:
    db = FakeDb(_drifted_rows())
    before = copy.deepcopy(db.rows)
    engine = FakeEngine(db)

    assert await kb.run("check", engine) == kb.EXIT_DRIFT

    conn = engine.connections[0]
    assert isinstance(conn.statements[0], TextClause)
    assert conn.statements[0].text == "SET TRANSACTION READ ONLY"
    assert conn.writes == []
    assert db.rows == before and db.commits == 0 and db.rollbacks == 1


@pytest.mark.parametrize(
    "rows",
    [
        _exact_rows()[1:],  # missing
        _exact_rows() + [_row(100, KEYS[0])],  # duplicate
        _exact_rows() + [{**_row(100, KEYS[0]), "title_en": "stale"}],  # stale
        [{**r, "priority": 3} if r["id"] == 1 else r for r in _exact_rows()],  # changed
    ],
    ids=["missing", "duplicate", "stale", "changed"],
)
def test_main_check_exits_non_zero_on_drift(
    rows: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kb, "engine", FakeEngine(FakeDb(rows)))
    assert kb.main(["check"]) == kb.EXIT_DRIFT


def test_main_check_exits_zero_only_on_exact_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kb, "engine", FakeEngine(FakeDb(_exact_rows())))
    assert kb.main(["check"]) == kb.EXIT_OK


def test_main_sync_then_check_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeDb(_drifted_rows())
    monkeypatch.setattr(kb, "engine", FakeEngine(db))
    assert kb.main(["sync"]) == kb.EXIT_OK
    monkeypatch.setattr(kb, "engine", FakeEngine(db))
    assert kb.main(["check"]) == kb.EXIT_OK


@pytest.mark.parametrize("failing", [Delete, Update, Insert])
def test_sync_failure_rolls_back_and_exits_non_zero(
    failing: type, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    db = FakeDb(_drifted_rows())
    db.fail_on = failing
    before = copy.deepcopy(db.rows)
    monkeypatch.setattr(kb, "engine", FakeEngine(db))

    assert kb.main(["sync"]) == kb.EXIT_ERROR

    assert db.rows == before and db.commits == 0 and db.rollbacks == 1
    err = capsys.readouterr().err
    assert "FakeDbError" in err and "injected failure" not in err


def test_sync_verification_failure_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeDb(_drifted_rows())
    db.ignore_deletes = True
    before = copy.deepcopy(db.rows)
    monkeypatch.setattr(kb, "engine", FakeEngine(db))

    assert kb.main(["sync"]) == kb.EXIT_ERROR
    assert db.rows == before and db.commits == 0 and db.rollbacks == 1


@pytest.mark.parametrize("mode", ["sync", "check"])
def test_invalid_catalog_fails_before_any_db_access(
    mode: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = FakeEngine(FakeDb([]))
    monkeypatch.setattr(kb, "engine", engine)
    monkeypatch.setattr(kb, "ENTRIES", list(kb.ENTRIES) + [kb.ENTRIES[0]])

    assert kb.main([mode]) == kb.EXIT_ERROR
    assert engine.connections == []


def test_cli_requires_explicit_mode() -> None:
    with pytest.raises(SystemExit) as exc:
        kb.main([])
    assert exc.value.code != 0


# ─── Repository wiring ───────────────────────────────────────────────────────


def test_legacy_sql_seed_is_retired() -> None:
    assert not (REPO_ROOT / "scripts" / "seed_knowledge_base.sql").exists()


def test_manual_deploy_runs_sync_then_check_after_api_or_infra_rebuild() -> None:
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    on_block = workflow.split("\non:", 1)[1].split("\njobs:", 1)[0]
    assert re.findall(r"^  (\w+):", on_block, flags=re.MULTILINE) == ["workflow_dispatch"]

    sync_cmd = "$CD exec -T api python scripts/seed_knowledge_base.py sync"
    check_cmd = "$CD exec -T api python scripts/seed_knowledge_base.py check"
    assert workflow.count(sync_cmd) == 1 and workflow.count(check_cmd) == 1
    script = workflow.split("script: |", 1)[1]
    assert script.lstrip().startswith("set -e")
    sync_at, check_at = script.index(sync_cmd), script.index(check_cmd)
    assert script.index("$CD build api && $CD up -d api") < sync_at < check_at

    guard = script[: sync_at].rsplit("if [", 1)[1]
    assert 'steps.changes.outputs.infra }}" = "true"' in guard
    assert 'steps.changes.outputs.api }}" = "true"' in guard
    assert "fi" not in script[script.rindex("then", 0, sync_at): check_at]


# ─── Optional real PostgreSQL (disposable loopback DB only) ───────────────────


@requires_postgres
async def test_sync_and_check_against_disposable_postgres() -> None:
    from sqlalchemy import insert
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    url = disposable_postgres_url()

    def _engine() -> Any:
        return create_async_engine(url, poolclass=NullPool)

    setup = _engine()
    async with setup.begin() as conn:
        await conn.run_sync(lambda c: kb.TABLE.drop(c, checkfirst=True))
        await conn.run_sync(lambda c: kb.TABLE.create(c))
        for row in _drifted_rows():
            await conn.execute(insert(kb.TABLE).values(**row))
        await conn.exec_driver_sql("SELECT setval('knowledge_base_id_seq', 200)")
    await setup.dispose()

    try:
        assert await kb.run("check", _engine()) == kb.EXIT_DRIFT
        assert await kb.run("sync", _engine()) == kb.EXIT_OK
        assert await kb.run("check", _engine()) == kb.EXIT_OK
        assert await kb.run("sync", _engine()) == kb.EXIT_OK  # idempotent

        verify = _engine()
        async with verify.connect() as conn:
            rows = {r["id"]: r for r in await kb.load_rows(conn)}
        await verify.dispose()
        assert _as_catalog(rows) == CATALOG
        assert {10, 11, 12} <= set(rows) and not {5, 6, 99} & set(rows)
    finally:
        teardown = _engine()
        async with teardown.begin() as conn:
            await conn.run_sync(lambda c: kb.TABLE.drop(c, checkfirst=True))
        await teardown.dispose()
