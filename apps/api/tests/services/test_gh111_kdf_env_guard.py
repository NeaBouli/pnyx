import pytest

from scripts.gh111_kdf_env_guard import (
    CONFIRM_TOKEN,
    active_kdf_values,
    normalize_target,
    plan_kdf_env,
    render_kdf_env,
    write_kdf_env,
)


def test_render_replaces_existing_kdf_without_touching_secret_like_values() -> None:
    content = "POSTGRES_PASSWORD=$2a$not_shell\nIDENTITY_NULLIFIER_KDF_VERSION=v1\nOTHER=value\n"

    rendered = render_kdf_env(content, "v2")

    assert rendered == "POSTGRES_PASSWORD=$2a$not_shell\nIDENTITY_NULLIFIER_KDF_VERSION=v2\nOTHER=value\n"


def test_render_appends_when_key_is_missing() -> None:
    content = "POSTGRES_USER=ekklesia\n"

    assert render_kdf_env(content, "v2") == "POSTGRES_USER=ekklesia\nIDENTITY_NULLIFIER_KDF_VERSION=v2\n"


def test_render_collapses_duplicate_active_keys_but_preserves_comments() -> None:
    content = "\n".join(
        [
            "# IDENTITY_NULLIFIER_KDF_VERSION=v1",
            "IDENTITY_NULLIFIER_KDF_VERSION=v1",
            "OTHER=value",
            "IDENTITY_NULLIFIER_KDF_VERSION=v2",
            "",
        ]
    )

    rendered = render_kdf_env(content, "v1")

    assert rendered == "# IDENTITY_NULLIFIER_KDF_VERSION=v1\nIDENTITY_NULLIFIER_KDF_VERSION=v1\nOTHER=value\n"
    assert active_kdf_values(rendered) == ["v1"]


def test_plan_is_redacted_and_reports_duplicate_cleanup() -> None:
    content = "IDENTITY_NULLIFIER_KDF_VERSION=v1\nSECRET=keep\nIDENTITY_NULLIFIER_KDF_VERSION=v2\n"

    plan = plan_kdf_env(content, "v2")

    assert plan.target == "v2"
    assert plan.previous_values == ["v1", "v2"]
    assert plan.active_key_count == 2
    assert plan.would_remove_duplicates is True
    assert plan.would_append is False


def test_write_requires_confirm_token(tmp_path) -> None:
    env_file = tmp_path / ".env.production"
    env_file.write_text("IDENTITY_NULLIFIER_KDF_VERSION=v1\n")

    with pytest.raises(PermissionError):
        write_kdf_env(env_file, tmp_path / "backups", "v2", "wrong")


def test_write_creates_backup_and_sets_target(tmp_path) -> None:
    env_file = tmp_path / ".env.production"
    env_file.write_text("IDENTITY_NULLIFIER_KDF_VERSION=v1\n")

    report = write_kdf_env(env_file, tmp_path / "backups", "v2", CONFIRM_TOKEN)

    assert env_file.read_text() == "IDENTITY_NULLIFIER_KDF_VERSION=v2\n"
    assert report.previous_values == ["v1"]
    assert report.changed is True
    assert report.removed_duplicates is False
    assert (tmp_path / "backups").exists()
    assert report.backup_file.endswith(".bak")


def test_normalize_target_rejects_invalid_value() -> None:
    with pytest.raises(ValueError):
        normalize_target("v3")
