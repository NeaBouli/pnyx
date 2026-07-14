from config import Settings


def test_environment_uses_production_environment_name(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENV", "development")

    settings = Settings(_env_file=None)

    assert settings.env == "production"


def test_environment_keeps_legacy_env_compatibility(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("ENV", "development")

    settings = Settings(_env_file=None)

    assert settings.env == "development"
