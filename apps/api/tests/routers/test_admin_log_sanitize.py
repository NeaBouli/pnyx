import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from routers.admin import _sanitize_logs


def test_redacts_api_keys():
    log = 'ADMIN_KEY=secret123abc DATABASE_URL=postgres://user:pass@host/db'
    result = _sanitize_logs(log)
    assert "secret123abc" not in result
    assert "user:pass@host" not in result
    assert "ADMIN_KEY=[REDACTED]" in result
    assert "DATABASE_URL=[REDACTED]" in result


def test_redacts_bearer_tokens():
    log = 'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig'
    result = _sanitize_logs(log)
    assert "eyJhbGci" not in result
    assert "[REDACTED]" in result


def test_redacts_redis_url():
    log = 'connecting to redis://default:secret@redis:6379/0'
    result = _sanitize_logs(log)
    assert "secret@redis" not in result
    assert "redis://[REDACTED]" in result


def test_preserves_normal_log_lines():
    log = '2026-05-25 INFO: GET /api/v1/bills 200 OK in 45ms'
    result = _sanitize_logs(log)
    assert result == log


def test_redacts_discourse_key():
    log = 'DISCOURSE_API_KEY=abc123def456 loaded'
    result = _sanitize_logs(log)
    assert "abc123def456" not in result
    assert "DISCOURSE_API_KEY=[REDACTED]" in result


def test_redacts_mixed_secrets():
    log = (
        'INFO startup\n'
        'SERVER_SALT=mysalt123\n'
        'Bearer abc-token-xyz\n'
        'GET /health 200\n'
        'postgres://admin:pw@db:5432/ekklesia\n'
    )
    result = _sanitize_logs(log)
    assert "mysalt123" not in result
    assert "abc-token-xyz" not in result
    assert "admin:pw@db" not in result
    assert "INFO startup" in result
    assert "GET /health 200" in result


def test_redacts_json_double_quotes():
    log = '{"ADMIN_KEY":"secret123","status":"ok"}'
    result = _sanitize_logs(log)
    assert "secret123" not in result
    assert '"[REDACTED]"' in result
    assert '"status"' in result


def test_redacts_json_token():
    log = '{"token":"abc-token-xyz","user":"test"}'
    result = _sanitize_logs(log)
    assert "abc-token-xyz" not in result
    assert '"[REDACTED]"' in result


def test_redacts_python_dict_single_quotes():
    log = "{'SECRET': 'shhh', 'module': 'MOD-01'}"
    result = _sanitize_logs(log)
    assert "shhh" not in result
    assert "'[REDACTED]'" in result
    assert "'module'" in result


def test_redacts_json_password_lowercase():
    log = '{"password":"hunter2","host":"db"}'
    result = _sanitize_logs(log)
    assert "hunter2" not in result
    assert '"[REDACTED]"' in result


def test_redacts_json_authorization_bearer():
    log = '{"authorization":"Bearer eyJhbG.payload.sig"}'
    result = _sanitize_logs(log)
    assert "eyJhbG" not in result


def test_redacts_json_database_url():
    log = '{"DATABASE_URL":"postgres://u:p@host/db"}'
    result = _sanitize_logs(log)
    assert "u:p@host" not in result
