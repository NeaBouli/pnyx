"""z904 commits bounded batches and retains z903's concurrent-index safeguards."""
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest

from tests.pg_public_bill_schema import sensitivity_revision


@pytest.mark.parametrize("action", ["upgrade", "downgrade"])
def test_non_postgres_is_unchanged(action: str) -> None:
    revision = sensitivity_revision()
    operations = MagicMock()
    operations.get_bind.return_value.dialect.name = "sqlite"
    with patch.object(revision, "op", operations):
        getattr(revision, action)()
    operations.execute.assert_not_called()


@pytest.mark.parametrize("action", ["upgrade", "downgrade"])
@pytest.mark.parametrize("valid", [True, False])
def test_unknown_indexes_are_never_adopted(action: str, valid: bool) -> None:
    revision = sensitivity_revision()
    operations = MagicMock()
    bind = operations.get_bind.return_value
    bind.dialect.name = "postgresql"
    bind.execute.return_value.scalar_one_or_none.return_value = valid
    with patch.object(revision, "op", operations), pytest.raises(RuntimeError, match="unknown index"):
        getattr(revision, action)()
    operations.execute.assert_not_called()


@pytest.mark.parametrize("action", ["upgrade", "downgrade"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_failed_build_preserves_working_index_and_original_exception(action: str, cleanup_fails: bool) -> None:
    revision = sensitivity_revision()
    operations = MagicMock()
    bind = operations.get_bind.return_value
    bind.dialect.name = "postgresql"
    bind.execute.return_value.scalar_one_or_none.side_effect = [None, False]
    operations.get_context.return_value.autocommit_block.return_value = nullcontext()
    target = revision.INDEX_NAME if action == "upgrade" else revision.LEGACY_INDEX_NAME
    error = RuntimeError("synthetic build failure")

    def execute(sql: str) -> None:
        if sql.startswith("CREATE INDEX CONCURRENTLY"):
            raise error
        if cleanup_fails and sql.startswith("DROP INDEX"):
            raise RuntimeError("synthetic cleanup failure")

    operations.execute.side_effect = execute
    with patch.object(revision, "op", operations), patch.object(revision, "_backfill"), \
            pytest.raises(RuntimeError) as caught:
        getattr(revision, action)()
    assert caught.value is error
    assert [call.args[0] for call in operations.execute.call_args_list
            if call.args[0].startswith("DROP INDEX")] == [f"DROP INDEX CONCURRENTLY IF EXISTS {target}"]


@pytest.mark.parametrize("action", ["upgrade", "downgrade"])
def test_concurrent_replacement_precedes_drop_and_function_is_retained(action: str) -> None:
    revision = sensitivity_revision()
    operations = MagicMock()
    bind = operations.get_bind.return_value
    bind.dialect.name = "postgresql"
    bind.execute.return_value.scalar_one_or_none.return_value = None
    operations.get_context.return_value.autocommit_block.return_value = nullcontext()
    with patch.object(revision, "op", operations), patch.object(revision, "_backfill"):
        getattr(revision, action)()
    statements = [call.args[0] for call in operations.execute.call_args_list]
    target, old = ((revision.INDEX_NAME, revision.LEGACY_INDEX_NAME) if action == "upgrade"
                   else (revision.LEGACY_INDEX_NAME, revision.INDEX_NAME))
    create = next(i for i, sql in enumerate(statements) if sql.startswith(f"CREATE INDEX CONCURRENTLY {target}"))
    drop = statements.index(f"DROP INDEX CONCURRENTLY IF EXISTS {old}")
    assert create < drop
    assert not any(sql.startswith("DROP FUNCTION public_bill_sensitive") for sql in statements)
    if action == "upgrade":
        assert statements.index(revision.TRIGGER_DDL) < create
        assert statements.index(revision.BACKFILL_TRIGGER_FUNCTION_DDL) < statements.index(revision.TRIGGER_DDL)
        assert statements.index(revision.TRIGGER_FUNCTION_DDL) < create
        assert "public_bill_sensitive(OLD.source" not in revision.TRIGGER_FUNCTION_DDL
    else:
        assert statements.index("DROP TRIGGER trg_bill_sensitivity ON parliament_bills") > drop


def test_backfill_uses_keyset_batches_and_preserves_null_sensitivity() -> None:
    revision = sensitivity_revision()
    bind = MagicMock()
    bind.execute.return_value.scalar_one.side_effect = ["B", "C", None]
    revision._backfill(bind)
    calls = bind.execute.call_args_list
    assert len(calls) == 3
    assert [call.args[1] for call in calls] == [
        {"after": None, "size": 1000}, {"after": "B", "size": 1000}, {"after": "C", "size": 1000},
    ]
    for call in calls:
        sql = str(call.args[0])
        assert "LIMIT :size" in sql and "IS NOT FALSE" in sql
        assert "SELECT max(id) FROM batch" in sql
        assert "b.sensitive_public_block OR" in sql
