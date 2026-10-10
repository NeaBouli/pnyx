"""Offline compatibility guards for the shared admin Bearer dependency."""

from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from dependencies import verify_admin_key


def token(value: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=value)


@pytest.mark.parametrize("configured", ["test-admin", "δοκιμή"])
def test_equal_tokens_use_constant_time_byte_comparison(monkeypatch: pytest.MonkeyPatch, configured: str) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_KEY", configured)
    with patch("hmac.compare_digest", return_value=True) as compare:
        assert verify_admin_key(token(configured)) is True
    compare.assert_called_once_with(configured.encode("utf-8"), configured.encode("utf-8"))


@pytest.mark.parametrize("submitted", ["", "test-admi", "test-admin-x", "wrong", "δοκιμή"])
def test_wrong_tokens_remain_forbidden(monkeypatch: pytest.MonkeyPatch, submitted: str) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_KEY", "test-admin")
    with pytest.raises(HTTPException) as error:
        verify_admin_key(token(submitted))
    assert error.value.status_code == 403


def test_equal_non_ascii_token_preserves_existing_direct_dependency_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_KEY", "δοκιμή")
    assert verify_admin_key(token("δοκιμή")) is True


@pytest.mark.parametrize("configured", ["", "dev-admin-key"])
def test_production_missing_or_default_key_stays_fail_closed(monkeypatch: pytest.MonkeyPatch, configured: str) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_KEY", configured)
    with patch("hmac.compare_digest") as compare:
        with pytest.raises(HTTPException) as error:
            verify_admin_key(token("dev-admin-key"))
    assert error.value.status_code == 403
    compare.assert_not_called()


def test_development_default_stays_compatible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    assert verify_admin_key(token("dev-admin-key")) is True


@pytest.mark.parametrize(
    ("headers", "query", "expected"),
    [({}, "", 403), ({}, "?admin_key=test-admin", 403),
     ({"Authorization": "Basic test-admin"}, "", 403),
     ({"Authorization": "Bearer wrong"}, "?admin_key=test-admin", 403),
     ({"Authorization": "Bearer test-admin"}, "", 200)],
)
def test_real_http_bearer_dependency_never_accepts_query_or_basic(
    monkeypatch: pytest.MonkeyPatch, headers: dict[str, str], query: str, expected: int,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_KEY", "test-admin")
    app = FastAPI()

    @app.get("/guard", dependencies=[Depends(verify_admin_key)])
    def guard() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get(f"/guard{query}", headers=headers).status_code == expected
