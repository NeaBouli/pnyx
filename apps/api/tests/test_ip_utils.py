from datetime import date

from starlette.requests import Request

from ip_utils import get_client_ip, hashed_rate_subject, ip_reference, rate_limit_key_for_ip


def _request(headers: dict[str, str] | None = None, client_host: str = "10.0.0.4") -> Request:
    raw_headers = [
        (key.lower().encode(), value.encode())
        for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": raw_headers,
            "client": (client_host, 12345),
        }
    )


def test_get_client_ip_uses_rightmost_forwarded_ip_by_default(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    req = _request({"X-Forwarded-For": "203.0.113.10, 198.51.100.20"})

    assert get_client_ip(req) == "198.51.100.20"


def test_get_client_ip_ignores_invalid_forwarded_header():
    req = _request({"X-Forwarded-For": "not-an-ip"}, client_host="10.0.0.9")

    assert get_client_ip(req) == "10.0.0.9"


def test_rate_limit_key_does_not_contain_raw_ip(monkeypatch):
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    req = _request({"X-Forwarded-For": "198.51.100.20"})

    key = rate_limit_key_for_ip(req, "public_api:anon", today=date(2026, 6, 10))

    assert key.startswith("ratelimit:public_api:anon:2026-06-10:")
    assert "198.51.100.20" not in key


def test_ip_reference_is_stable_and_redacted(monkeypatch):
    monkeypatch.setenv("SERVER_SALT", "s" * 64)
    req = _request({"X-Forwarded-For": "198.51.100.20"})

    ref = ip_reference(req, "contact")

    assert ref.startswith("ipref:")
    assert "198.51.100.20" not in ref
    assert ref == ip_reference(req, "contact")


def test_hashed_rate_subject_rotates_by_day(monkeypatch):
    monkeypatch.setenv("SERVER_SALT", "s" * 64)

    first = hashed_rate_subject("198.51.100.20", "contact", date(2026, 6, 10))
    second = hashed_rate_subject("198.51.100.20", "contact", date(2026, 6, 11))

    assert first != second
