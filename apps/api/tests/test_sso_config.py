import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _reload_sso(monkeypatch, *, environment: str, secret: str = "", salt: str = ""):
    monkeypatch.setenv("ENVIRONMENT", environment)
    if secret:
        monkeypatch.setenv("DISCOURSE_SSO_SECRET", secret)
    else:
        monkeypatch.delenv("DISCOURSE_SSO_SECRET", raising=False)
    if salt:
        monkeypatch.setenv("FORUM_SSO_SALT", salt)
    else:
        monkeypatch.delenv("FORUM_SSO_SALT", raising=False)

    import routers.sso as sso
    return importlib.reload(sso)


def test_forum_sso_config_fails_closed_in_production(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="")

    with pytest.raises(RuntimeError, match="FORUM_SSO_SALT"):
        sso.validate_forum_sso_config()


def test_forum_sso_config_accepts_explicit_secret_and_salt(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="production", secret="secret", salt="salt")

    sso.validate_forum_sso_config()


def test_forum_sso_config_warns_only_in_development(monkeypatch):
    sso = _reload_sso(monkeypatch, environment="development", secret="", salt="")

    sso.validate_forum_sso_config()
