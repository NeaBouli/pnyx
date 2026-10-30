"""Concurrent index replacement must preserve the working index on failure."""
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest

from tests.pg_public_bill_schema import public_metadata_revision


@pytest.mark.parametrize("action", ["upgrade", "downgrade"])
def test_non_postgresql_is_a_noop(action: str) -> None:
    revision = public_metadata_revision()
    operations = MagicMock()
    operations.get_bind.return_value.dialect.name = "sqlite"
    with patch.object(revision, "op", operations):
        getattr(revision, action)()
    operations.execute.assert_not_called()
    operations.get_context.assert_not_called()


@pytest.mark.parametrize("action", ["upgrade", "downgrade"])
@pytest.mark.parametrize("valid", [True, False])
def test_refuses_unknown_valid_or_invalid_index(action: str, valid: bool) -> None:
    revision = public_metadata_revision()
    operations = MagicMock()
    bind = operations.get_bind.return_value
    bind.dialect.name = "postgresql"
    bind.execute.return_value.scalar_one_or_none.return_value = valid
    name = revision.INDEX_NAME if action == "upgrade" else revision.LEGACY_INDEX_NAME
    with patch.object(revision, "op", operations), pytest.raises(RuntimeError, match=f"{name} already exists"):
        getattr(revision, action)()
    operations.execute.assert_not_called()
    operations.get_context.assert_not_called()


@pytest.mark.parametrize("action", ["upgrade", "downgrade"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_failed_build_cleans_invalid_index_and_preserves_original_error(
    action: str, cleanup_fails: bool,
) -> None:
    revision = public_metadata_revision()
    operations = MagicMock()
    bind = operations.get_bind.return_value
    bind.dialect.name = "postgresql"
    bind.execute.return_value.scalar_one_or_none.side_effect = [None, False]
    operations.get_context.return_value.autocommit_block.return_value = nullcontext()
    target = revision.INDEX_NAME if action == "upgrade" else revision.LEGACY_INDEX_NAME
    build_error = RuntimeError("synthetic concurrent build failure")

    def execute(sql: str) -> None:
        if sql.startswith("CREATE INDEX CONCURRENTLY"):
            raise build_error
        if cleanup_fails and sql.startswith("DROP INDEX"):
            raise RuntimeError("synthetic cleanup failure")

    operations.execute.side_effect = execute
    with patch.object(revision, "op", operations), pytest.raises(RuntimeError) as caught:
        getattr(revision, action)()
    assert caught.value is build_error
    drops = [call.args[0] for call in operations.execute.call_args_list if call.args[0].startswith("DROP")]
    assert drops == [f"DROP INDEX CONCURRENTLY IF EXISTS {target}"]


@pytest.mark.parametrize("action", ["upgrade", "downgrade"])
def test_replacement_is_built_before_old_index_is_dropped(action: str) -> None:
    revision = public_metadata_revision()
    operations = MagicMock()
    bind = operations.get_bind.return_value
    bind.dialect.name = "postgresql"
    bind.execute.return_value.scalar_one_or_none.return_value = None
    operations.get_context.return_value.autocommit_block.return_value = nullcontext()
    with patch.object(revision, "op", operations):
        getattr(revision, action)()
    statements = [call.args[0] for call in operations.execute.call_args_list]
    if action == "upgrade":
        assert statements[0] == revision.FUNCTION_DDL
        assert statements[1].startswith(f"CREATE INDEX CONCURRENTLY {revision.INDEX_NAME} ")
        assert statements[2] == f"DROP INDEX CONCURRENTLY IF EXISTS {revision.LEGACY_INDEX_NAME}"
    else:
        assert statements[0].startswith(f"CREATE INDEX CONCURRENTLY {revision.LEGACY_INDEX_NAME} ")
        assert statements[1] == f"DROP INDEX CONCURRENTLY IF EXISTS {revision.INDEX_NAME}"
        assert statements[2] == "DROP FUNCTION public_bill_sensitive(text, text, text, text)"
