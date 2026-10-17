"""The optional role URLs preserve the legacy configuration and stay separate."""
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("api_url", ["", "postgresql+asyncpg://ekklesia_api:test@localhost/pnyx_test_config"])
def test_api_url_falls_back_without_changing_migration_source(api_url):
    legacy = "postgresql+asyncpg://legacy:test@localhost/pnyx_test_config"
    env = {**os.environ, "DATABASE_URL": legacy, "API_DATABASE_URL": api_url, "MIGRATOR_DATABASE_URL": ""}
    result = subprocess.run(
        [sys.executable, "-c", "from database import engine; print(engine.url.render_as_string(hide_password=False))"],
        cwd=ROOT / "apps/api", env=env, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == (api_url or legacy)


def test_compose_role_url_defaults_and_migrator_is_one_shot():
    services = yaml.safe_load((ROOT / "infra/docker/docker-compose.prod.yml").read_text())["services"]
    for name in ("api", "monitor", "migrator"):
        env = services[name]["environment"]
        expected = f"{name.upper()}_DATABASE_URL"
        assert env["DATABASE_URL"].startswith("${" + expected + ":-postgresql")
        assert "${POSTGRES_USER}:${POSTGRES_PASSWORD}" in env["DATABASE_URL"]
    assert services["migrator"]["profiles"] == ["ops"]
    assert services["migrator"]["command"] == ["alembic", "upgrade", "head"]
    assert services["api"]["environment"]["MIGRATOR_DATABASE_URL"] == ""
    assert services["api"]["environment"]["POSTGRES_PASSWORD"] == ""
    # Pre-PR dashboard configuration has no DB connection at all, including
    # when the reserved DASHBOARD_DATABASE_URL is unset during rollback.
    assert "DATABASE_URL" not in services["dashboard"]["environment"]
    assert "env_file" not in services["dashboard"]


@pytest.mark.parametrize("monitor_url", ["", "postgresql://ekklesia_monitor:test@localhost/pnyx_test_config"])
def test_monitor_url_falls_back_to_legacy(monitor_url):
    legacy = "postgresql://legacy:test@localhost/pnyx_test_config"
    env = {**os.environ, "DATABASE_URL": legacy, "MONITOR_DATABASE_URL": monitor_url}
    # The URL selection itself needs no psycopg2 connection or network.
    result = subprocess.run(
        [sys.executable, "-c", "import sys, types; sys.modules['psycopg2'] = types.ModuleType('psycopg2'); import monitor; print(monitor.DB_URL)"],
        cwd=ROOT / "apps/monitor", env=env, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == (monitor_url or legacy)
