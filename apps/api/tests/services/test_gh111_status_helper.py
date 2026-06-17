import json
import os
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def _make_fake_app(tmp_path: Path) -> tuple[Path, Path, Path]:
    app_dir = tmp_path / "app"
    fake_bin = tmp_path / "bin"
    backup_dir = tmp_path / "backup"
    (app_dir / "apps/api/scripts").mkdir(parents=True)
    fake_bin.mkdir()
    backup_dir.mkdir()

    _write_executable(
        fake_bin / "git",
        "#!/usr/bin/env bash\n"
        "if [[ \"$1 $2 $3\" == \"rev-parse --short HEAD\" ]]; then echo testhead; exit 0; fi\n"
        "echo unexpected-git-call >&2\n"
        "exit 2\n",
    )
    _write_executable(
        fake_bin / "curl",
        "#!/usr/bin/env bash\n"
        "if [[ \"${FAKE_CURL_OK:-1}\" == \"1\" ]]; then exit 0; fi\n"
        "exit 22\n",
    )
    _write_executable(
        fake_bin / "docker",
        "#!/usr/bin/env bash\n"
        "if [[ \"${FAKE_DOCKER_EXIT:-0}\" == \"0\" ]]; then\n"
        "  printf '%s\\n' \"${FAKE_LIVE_JSON}\"\n"
        "  exit 0\n"
        "fi\n"
        "printf 'not-json\\n'\n"
        "exit \"${FAKE_DOCKER_EXIT:-1}\"\n",
    )
    (app_dir / "apps/api/scripts/gh111_preflight_package_check.py").write_text(
        "import json\n"
        "import os\n"
        "import sys\n"
        "ok = os.environ.get('FAKE_PACKAGE_OK', '1') == '1'\n"
        "payload = {\n"
        "  'ok': ok,\n"
        "  'blockers': [] if ok else ['backup_dir_missing'],\n"
        "  'warnings': [],\n"
        "}\n"
        "print(json.dumps(payload))\n"
        "raise SystemExit(0 if ok else 1)\n"
    )
    return app_dir, fake_bin, backup_dir


def _run_status_helper(
    tmp_path: Path,
    *,
    kdf: str = "v1",
    package_ok: bool = True,
    live_ok: bool = True,
    api_health_ok: bool = True,
) -> dict[str, str]:
    app_dir, fake_bin, backup_dir = _make_fake_app(tmp_path)
    env_file = tmp_path / ".env.production"
    env_file.write_text(f"IDENTITY_NULLIFIER_KDF_VERSION={kdf}\n")
    live_payload = {
        "preflight_blockers": [],
        "snapshot": {
            "active": 17,
            "active_with_v2": 0,
            "kdf_env": kdf,
            "malformed_v2": 0,
            "revoked": 0,
            "total": 17,
            "v2_without_version": 0,
            "version_v2": 0,
            "version_without_v2": 0,
            "with_v2": 0,
        },
    }
    env = {
        **os.environ,
        "APP_DIR": str(app_dir),
        "ENV_FILE": str(env_file),
        "COMPOSE_FILE": "compose.yml",
        "BACKUP_DIR": str(backup_dir),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_PACKAGE_OK": "1" if package_ok else "0",
        "FAKE_DOCKER_EXIT": "0" if live_ok else "1",
        "FAKE_CURL_OK": "1" if api_health_ok else "0",
        "FAKE_LIVE_JSON": json.dumps(live_payload),
    }
    result = subprocess.run(
        ["bash", str(_repo_root() / "scripts/gh111-status-nullifier-v2-window.sh")],
        check=True,
        env=env,
        text=True,
        capture_output=True,
    )
    lines: dict[str, str] = {}
    for raw_line in result.stdout.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        lines[key] = value
    return lines


def test_status_helper_reports_ready_when_all_readiness_inputs_are_clean(tmp_path: Path) -> None:
    status = _run_status_helper(tmp_path)

    assert status["APP_HEAD"] == "testhead"
    assert status["KDF_ENV"] == "v1"
    assert status["API_HEALTH"] == "ok"
    assert status["PACKAGE_OK"] == "true"
    assert status["LIVE_PREFLIGHT_OK"] == "true"
    assert status["LIVE_PREFLIGHT_BLOCKERS"] == "[]"
    assert status["GH111_NEXT_STEP"] == "prepare-or-activate-only-when-Gio-ready-with-S10-and-real-HLR"


def test_status_helper_blocks_when_package_is_not_ok(tmp_path: Path) -> None:
    status = _run_status_helper(tmp_path, package_ok=False)

    assert status["PACKAGE_OK"] == "false"
    assert status["PACKAGE_BLOCKERS"] == '["backup_dir_missing"]'
    assert status["GH111_NEXT_STEP"] == "review-status-before-any-action"


def test_status_helper_blocks_when_live_snapshot_fails(tmp_path: Path) -> None:
    status = _run_status_helper(tmp_path, live_ok=False)

    assert status["LIVE_PREFLIGHT_OK"] == "false"
    assert status["LIVE_PREFLIGHT_BLOCKERS"] == '["live_snapshot_unreadable"]'
    assert status["LIVE_SNAPSHOT"] == "{}"
    assert status["GH111_NEXT_STEP"] == "review-status-before-any-action"


def test_status_helper_blocks_when_api_health_fails(tmp_path: Path) -> None:
    status = _run_status_helper(tmp_path, api_health_ok=False)

    assert status["API_HEALTH"] == "failed"
    assert status["GH111_NEXT_STEP"] == "review-status-before-any-action"


def test_status_helper_blocks_when_kdf_is_not_v1(tmp_path: Path) -> None:
    status = _run_status_helper(tmp_path, kdf="v2")

    assert status["KDF_ENV"] == "v2"
    assert status["GH111_NEXT_STEP"] == "review-status-before-any-action"
