import importlib.util

import pytest

from security_startup import validate_identity_kdf_config, validate_server_salt_config


@pytest.mark.parametrize(
    "salt",
    ["", "dev-salt", "dev-salt-change-in-production"],
)
def test_server_salt_guard_fails_closed_for_missing_or_default_production_salt(salt):
    with pytest.raises(RuntimeError, match="missing or default"):
        validate_server_salt_config({"ENVIRONMENT": "production", "SERVER_SALT": salt})


def test_server_salt_guard_fails_closed_for_short_production_salt():
    with pytest.raises(RuntimeError, match="at least 32"):
        validate_server_salt_config({"ENVIRONMENT": "production", "SERVER_SALT": "short-salt"})


def test_server_salt_guard_accepts_strong_production_salt():
    validate_server_salt_config(
        {"ENVIRONMENT": "production", "SERVER_SALT": "a" * 64}
    )


def test_server_salt_guard_warns_only_in_development(caplog):
    validate_server_salt_config(
        {"ENVIRONMENT": "development", "SERVER_SALT": "dev-salt"}
    )

    assert "SERVER_SALT is weak/missing in non-production" in caplog.text


def test_server_salt_guard_accepts_legacy_env_development_flag(caplog):
    validate_server_salt_config({"ENV": "development", "SERVER_SALT": "dev-salt"})

    assert "SERVER_SALT is weak/missing in non-production" in caplog.text


def test_identity_kdf_guard_accepts_default_v1():
    validate_identity_kdf_config({})


def test_identity_kdf_guard_rejects_unknown_version():
    with pytest.raises(RuntimeError, match="must be v1 or v2"):
        validate_identity_kdf_config({"IDENTITY_NULLIFIER_KDF_VERSION": "banana"})


def test_identity_kdf_guard_accepts_v2_when_argon2_available():
    if importlib.util.find_spec("argon2") is None:
        pytest.skip("argon2-cffi not installed in this local Python environment")

    validate_identity_kdf_config({"IDENTITY_NULLIFIER_KDF_VERSION": "v2"})
