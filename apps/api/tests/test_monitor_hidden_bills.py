import os
import sys
import types


sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *args, **kwargs: None))
sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))

import monitor  # noqa: E402


class FakeCursor:
    def __init__(self, *, rows=None, one=None):
        self.rows = rows or []
        self.one = one
        self.statements = []
        self.params = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, *args, **_kwargs):
        self.statements.append(statement)
        self.params.append(args[0] if args else None)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return (self.one,)


class FakeConn:
    def __init__(self, cursor):
        self.cursor_obj = cursor

    def cursor(self):
        return self.cursor_obj


def test_forum_missing_query_excludes_hidden_canary_bills():
    cursor = FakeCursor(rows=[])
    alerts = monitor.check_forum_missing(FakeConn(cursor))

    assert alerts == []
    sql = cursor.statements[0]
    assert "COALESCE(admin_hidden, FALSE) = FALSE" in sql
    assert "(source IS NULL OR source != 'ZK_CANARY')" in sql


def test_forum_completeness_query_excludes_hidden_canary_bills():
    cursor = FakeCursor(one=0)
    alerts = monitor.check_forum_completeness(FakeConn(cursor))

    assert alerts == []
    sql = cursor.statements[0]
    assert "COALESCE(admin_hidden, FALSE) = FALSE" in sql
    assert "(source IS NULL OR source != 'ZK_CANARY')" in sql


def test_forum_completeness_gives_diavgeia_backlog_longer_grace():
    cursor = FakeCursor(one=0)
    monitor.check_forum_completeness(FakeConn(cursor))

    sql = cursor.statements[0]
    assert "COALESCE(source, 'PARLIAMENT') = 'PARLIAMENT'" in sql
    assert "INTERVAL '1 hour'" in sql
    assert "COALESCE(source, 'PARLIAMENT') != 'PARLIAMENT'" in sql
    assert "INTERVAL '6 hours'" in sql


def test_lifecycle_stuck_query_gives_recent_scraper_updates_short_grace():
    cursor = FakeCursor(rows=[])
    alerts = monitor.check_lifecycle_stuck(FakeConn(cursor))

    assert alerts == []
    sql = cursor.statements[0]
    assert "parliament_vote_date < %s" in sql
    assert "COALESCE(updated_at, TIMESTAMP '1970-01-01') < %s" in sql
    assert len(cursor.params[0]) == 2
