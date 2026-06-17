"""Validate a GH#111 no-mutation preflight evidence package.

This helper is intentionally read-only. It checks that the backup directory
created by scripts/gh111-prepare-nullifier-v2-window.sh contains the evidence
needed before a real Nullifier v2 operator window can begin.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "README.txt",
    "SHA256SUMS",
    "gh111_before_snapshot.json",
    "gh111_preflight_report.json",
    "identity_records_audit_alembic.sql",
    "kdf_env_plan_v2.json",
    "monitor_once.txt",
    "preflight_stdout.json",
    "v2_lifespan_probe.txt",
)


@dataclass(frozen=True)
class IdentityKdfSnapshot:
    kdf_env: str
    total: int
    with_v2: int
    version_v2: int
    active: int
    revoked: int
    active_with_v2: int = 0
    v2_without_version: int = 0
    version_without_v2: int = 0
    malformed_v2: int = 0


@dataclass(frozen=True)
class Gh111PreflightPackageVerdict:
    ok: bool
    backup_dir: str
    blockers: list[str]
    warnings: list[str]
    required_files: list[str]


def evaluate_preflight(snapshot: IdentityKdfSnapshot) -> list[str]:
    """Return blockers that must be resolved before first GH#111 activation."""
    blockers: list[str] = []
    if snapshot.kdf_env not in {"unset", "v1"}:
        blockers.append("kdf_env_not_v1_or_unset")
    if snapshot.with_v2 != 0:
        blockers.append("v2_rows_already_present")
    if snapshot.version_v2 != 0:
        blockers.append("version_v2_rows_already_present")
    if snapshot.active_with_v2 != 0:
        blockers.append("active_v2_rows_already_present")
    if snapshot.v2_without_version != 0:
        blockers.append("v2_hash_without_v2_version_present")
    if snapshot.version_without_v2 != 0:
        blockers.append("v2_version_without_v2_hash_present")
    if snapshot.malformed_v2 != 0:
        blockers.append("malformed_v2_hash_present")
    if snapshot.total <= 0:
        blockers.append("no_identity_rows_to_canary")
    return blockers


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _snapshot_from_payload(payload: dict[str, Any]) -> IdentityKdfSnapshot:
    return IdentityKdfSnapshot(
        kdf_env=str(payload["kdf_env"]),
        total=int(payload["total"]),
        with_v2=int(payload["with_v2"]),
        version_v2=int(payload["version_v2"]),
        active=int(payload["active"]),
        revoked=int(payload["revoked"]),
        active_with_v2=int(payload.get("active_with_v2", 0)),
        v2_without_version=int(payload.get("v2_without_version", 0)),
        version_without_v2=int(payload.get("version_without_v2", 0)),
        malformed_v2=int(payload.get("malformed_v2", 0)),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_sha256sums(backup_dir: Path) -> list[str]:
    blockers: list[str] = []
    sums_path = backup_dir / "SHA256SUMS"
    for line_number, raw_line in enumerate(sums_path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            blockers.append(f"sha256sums_malformed_line_{line_number}")
            continue
        expected, recorded_path = parts
        candidate = Path(recorded_path)
        if not candidate.exists():
            candidate = backup_dir / candidate.name
        if not candidate.exists():
            blockers.append(f"sha256_missing_file:{recorded_path}")
            continue
        actual = _sha256(candidate)
        if actual != expected:
            blockers.append(f"sha256_mismatch:{candidate.name}")
    return blockers


def validate_preflight_package(backup_dir: Path) -> Gh111PreflightPackageVerdict:
    """Return a read-only readiness verdict for a GH#111 preflight package."""
    blockers: list[str] = []
    warnings: list[str] = []

    if not backup_dir.exists() or not backup_dir.is_dir():
        return Gh111PreflightPackageVerdict(
            ok=False,
            backup_dir=str(backup_dir),
            blockers=["backup_dir_missing"],
            warnings=[],
            required_files=list(REQUIRED_FILES),
        )

    for file_name in REQUIRED_FILES:
        path = backup_dir / file_name
        if not path.exists():
            blockers.append(f"missing_required_file:{file_name}")
        elif path.stat().st_size == 0:
            blockers.append(f"empty_required_file:{file_name}")

    if "missing_required_file:SHA256SUMS" not in blockers and "empty_required_file:SHA256SUMS" not in blockers:
        blockers.extend(_check_sha256sums(backup_dir))

    try:
        report = _load_json(backup_dir / "gh111_preflight_report.json")
        snapshot = _snapshot_from_payload(dict(report["snapshot"]))
        report_blockers = report.get("preflight_blockers", [])
        if report_blockers:
            blockers.append("preflight_report_has_blockers")
        blockers.extend(f"snapshot_{blocker}" for blocker in evaluate_preflight(snapshot))
    except Exception as exc:
        blockers.append(f"preflight_report_unreadable:{type(exc).__name__}")

    try:
        before_snapshot = _snapshot_from_payload(_load_json(backup_dir / "gh111_before_snapshot.json"))
        blockers.extend(f"before_snapshot_{blocker}" for blocker in evaluate_preflight(before_snapshot))
    except Exception as exc:
        blockers.append(f"before_snapshot_unreadable:{type(exc).__name__}")

    try:
        kdf_plan = _load_json(backup_dir / "kdf_env_plan_v2.json")
        if kdf_plan.get("target") != "v2":
            blockers.append("kdf_plan_target_not_v2")
        previous_values = kdf_plan.get("previous_values", [])
        if not isinstance(previous_values, list):
            blockers.append("kdf_plan_previous_values_not_list")
        elif any(str(value).strip().lower() != "v1" for value in previous_values):
            blockers.append("kdf_plan_previous_value_not_v1")
        if int(kdf_plan.get("active_key_count", 0)) > 1:
            blockers.append("kdf_plan_duplicate_active_keys")
    except Exception as exc:
        blockers.append(f"kdf_plan_unreadable:{type(exc).__name__}")

    try:
        probe_lines = [line.strip().lower() for line in (backup_dir / "v2_lifespan_probe.txt").read_text().splitlines()]
        if "ok" not in probe_lines:
            blockers.append("v2_lifespan_probe_missing_ok")
    except Exception as exc:
        blockers.append(f"v2_lifespan_probe_unreadable:{type(exc).__name__}")

    monitor_text = (backup_dir / "monitor_once.txt").read_text(errors="replace") if (backup_dir / "monitor_once.txt").exists() else ""
    if "Traceback" in monitor_text:
        blockers.append("monitor_output_contains_traceback")
    if "Alerts" in monitor_text and "0 Alerts" not in monitor_text:
        warnings.append("monitor_output_mentions_alerts_review_manually")

    deduped_blockers = sorted(set(blockers))
    deduped_warnings = sorted(set(warnings))
    return Gh111PreflightPackageVerdict(
        ok=not deduped_blockers,
        backup_dir=str(backup_dir),
        blockers=deduped_blockers,
        warnings=deduped_warnings,
        required_files=list(REQUIRED_FILES),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate GH#111 no-mutation preflight package")
    parser.add_argument("--backup-dir", required=True, help="Directory created by gh111-prepare-nullifier-v2-window.sh")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    verdict = validate_preflight_package(Path(args.backup_dir))
    print(json.dumps(asdict(verdict), indent=2, sort_keys=True))
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
