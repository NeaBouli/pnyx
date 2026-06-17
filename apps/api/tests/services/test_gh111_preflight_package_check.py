import hashlib
import json
from pathlib import Path

from scripts.gh111_preflight_package_check import REQUIRED_FILES, validate_preflight_package


def _write_package_file(backup_dir: Path, name: str, content: str) -> None:
    (backup_dir / name).write_text(content)


def _write_sha256sums(backup_dir: Path) -> None:
    lines = []
    for path in sorted(backup_dir.iterdir()):
        if path.name == "SHA256SUMS" or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path}")
    (backup_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n")


def _valid_snapshot() -> dict[str, int | str]:
    return {
        "active": 17,
        "active_with_v2": 0,
        "kdf_env": "v1",
        "malformed_v2": 0,
        "revoked": 0,
        "total": 17,
        "v2_without_version": 0,
        "version_v2": 0,
        "version_without_v2": 0,
        "with_v2": 0,
    }


def _write_valid_package(backup_dir: Path) -> None:
    backup_dir.mkdir()
    snapshot = _valid_snapshot()
    _write_package_file(backup_dir, "README.txt", "GH111_BACKUP_DIR=/tmp/example\n")
    _write_package_file(backup_dir, "gh111_before_snapshot.json", json.dumps(snapshot))
    _write_package_file(
        backup_dir,
        "gh111_preflight_report.json",
        json.dumps({"snapshot": snapshot, "preflight_blockers": []}),
    )
    _write_package_file(backup_dir, "identity_records_audit_alembic.sql", "-- dump\n")
    _write_package_file(
        backup_dir,
        "kdf_env_plan_v2.json",
        json.dumps(
            {
                "active_key_count": 1,
                "changed": True,
                "previous_values": ["v1"],
                "target": "v2",
                "would_append": False,
                "would_remove_duplicates": False,
            }
        ),
    )
    _write_package_file(backup_dir, "monitor_once.txt", "PASS\n")
    _write_package_file(backup_dir, "preflight_stdout.json", "{}\n")
    _write_package_file(backup_dir, "v2_lifespan_probe.txt", "ok\n")
    _write_sha256sums(backup_dir)


def test_valid_preflight_package_passes(tmp_path: Path) -> None:
    backup_dir = tmp_path / "preflight"
    _write_valid_package(backup_dir)

    verdict = validate_preflight_package(backup_dir)

    assert verdict.ok is True
    assert verdict.blockers == []
    assert set(verdict.required_files) == set(REQUIRED_FILES)


def test_missing_required_file_blocks(tmp_path: Path) -> None:
    backup_dir = tmp_path / "preflight"
    _write_valid_package(backup_dir)
    (backup_dir / "v2_lifespan_probe.txt").unlink()

    verdict = validate_preflight_package(backup_dir)

    assert verdict.ok is False
    assert "missing_required_file:v2_lifespan_probe.txt" in verdict.blockers


def test_sha_mismatch_blocks(tmp_path: Path) -> None:
    backup_dir = tmp_path / "preflight"
    _write_valid_package(backup_dir)
    (backup_dir / "monitor_once.txt").write_text("changed after checksums\n")

    verdict = validate_preflight_package(backup_dir)

    assert verdict.ok is False
    assert "sha256_mismatch:monitor_once.txt" in verdict.blockers


def test_preflight_blockers_block(tmp_path: Path) -> None:
    backup_dir = tmp_path / "preflight"
    _write_valid_package(backup_dir)
    snapshot = _valid_snapshot()
    (backup_dir / "gh111_preflight_report.json").write_text(
        json.dumps({"snapshot": snapshot, "preflight_blockers": ["v2_rows_already_present"]})
    )
    _write_sha256sums(backup_dir)

    verdict = validate_preflight_package(backup_dir)

    assert verdict.ok is False
    assert "preflight_report_has_blockers" in verdict.blockers


def test_kdf_plan_must_target_v2_from_v1(tmp_path: Path) -> None:
    backup_dir = tmp_path / "preflight"
    _write_valid_package(backup_dir)
    (backup_dir / "kdf_env_plan_v2.json").write_text(
        json.dumps({"active_key_count": 1, "previous_values": ["v2"], "target": "v1"})
    )
    _write_sha256sums(backup_dir)

    verdict = validate_preflight_package(backup_dir)

    assert verdict.ok is False
    assert "kdf_plan_target_not_v2" in verdict.blockers
    assert "kdf_plan_previous_value_not_v1" in verdict.blockers
