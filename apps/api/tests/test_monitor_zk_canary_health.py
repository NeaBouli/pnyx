import os
import sys
import types


sys.modules.setdefault("psycopg2", types.SimpleNamespace(connect=lambda *args, **kwargs: None))
sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "monitor"))

import monitor  # noqa: E402


class FakeCursor:
    def __init__(self, values):
        self.values = list(values)
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return (self.values.pop(0),)


class FakeConn:
    def __init__(self, values):
        self.cursor_obj = FakeCursor(values)
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj

    def rollback(self):
        self.rolled_back = True


class UndefinedTable(Exception):
    pass


class FailingCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *_args, **_kwargs):
        raise UndefinedTable('relation "zk_vote_receipts" does not exist')


class FailingConn:
    def __init__(self):
        self.rolled_back = False

    def cursor(self):
        return FailingCursor()

    def rollback(self):
        self.rolled_back = True


def test_zk_canary_health_alerts_on_old_pending_receipts(monkeypatch):
    monkeypatch.setattr(monitor, "ZK_PENDING_MAX_HOURS", 24)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_PUBLICATION_ENABLED", True)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_AUTO_PARLIAMENT_ENABLED", False)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_MIN_GROUP_SIZE", 5)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_SCOPE_ALLOWLIST", {"bill:GR-0490a766"})
    conn = FakeConn([2, 0])

    alerts = monitor.check_zk_canary_health(conn)

    assert len(alerts) == 1
    assert alerts[0].type == "zk_receipts_pending"
    assert alerts[0].service == "ekklesia-api"
    assert alerts[0].severity == "warning"
    assert alerts[0].recovery_allowed is False
    assert ">24h" in alerts[0].message
    pending_statement, params = conn.cursor_obj.statements[0]
    assert "ANY" in pending_statement
    assert "root.group_size >= %s" in pending_statement
    assert params == (24, 5, ["bill:GR-0490a766"], False)


def test_zk_canary_health_skips_pending_receipts_when_publication_is_gated_off(monkeypatch):
    monkeypatch.setattr(monitor, "ZK_PENDING_MAX_HOURS", 24)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_PUBLICATION_ENABLED", False)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_AUTO_PARLIAMENT_ENABLED", False)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_SCOPE_ALLOWLIST", set())
    conn = FakeConn([0])

    alerts = monitor.check_zk_canary_health(conn)

    assert alerts == []
    assert len(conn.cursor_obj.statements) == 1
    assert "zk_merkle_roots" in conn.cursor_obj.statements[0][0]


def test_zk_canary_health_alerts_when_publication_enabled_without_allowlist(monkeypatch):
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_PUBLICATION_ENABLED", True)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_AUTO_PARLIAMENT_ENABLED", False)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_SCOPE_ALLOWLIST", set())
    conn = FakeConn([0])

    alerts = monitor.check_zk_canary_health(conn)

    assert len(alerts) == 1
    assert alerts[0].type == "zk_publication_config"
    assert "without scope allowlist or Parliament auto mode" in alerts[0].message


def test_zk_canary_health_allows_parliament_auto_mode_without_allowlist(monkeypatch):
    monkeypatch.setattr(monitor, "ZK_PENDING_MAX_HOURS", 24)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_PUBLICATION_ENABLED", True)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_AUTO_PARLIAMENT_ENABLED", True)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_MIN_GROUP_SIZE", 5)
    monkeypatch.setattr(monitor, "ZK_ARWEAVE_SCOPE_ALLOWLIST", set())
    conn = FakeConn([0, 0])

    alerts = monitor.check_zk_canary_health(conn)

    assert alerts == []
    pending_statement, params = conn.cursor_obj.statements[0]
    assert "b.source = 'PARLIAMENT'" in pending_statement
    assert params == (24, 5, [], True)


def test_zk_canary_health_alerts_on_invalid_root_status():
    conn = FakeConn([1])

    alerts = monitor.check_zk_canary_health(conn)

    assert len(alerts) == 1
    assert alerts[0].type == "zk_root_invalid"
    assert alerts[0].severity == "critical"
    assert alerts[0].recovery_allowed is False


def test_zk_canary_health_passes_when_no_pending_or_invalid_roots():
    conn = FakeConn([0, 0])

    alerts = monitor.check_zk_canary_health(conn)

    assert alerts == []


def test_zk_canary_health_skips_when_zk_schema_is_missing():
    conn = FailingConn()

    alerts = monitor.check_zk_canary_health(conn)

    assert alerts == []
    assert conn.rolled_back is True
