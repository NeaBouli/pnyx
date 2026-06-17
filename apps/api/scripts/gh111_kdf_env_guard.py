"""Safe env-file helper for the GH#111 Nullifier v2 canary.

The helper edits only IDENTITY_NULLIFIER_KDF_VERSION in a dotenv-style file.
It never sources shell env, so unrelated secret values containing "$" remain
literal text. Writes require an explicit confirmation token.
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast


KDF_KEY = "IDENTITY_NULLIFIER_KDF_VERSION"
CONFIRM_TOKEN = "GH111-KDF-WRITE"
KdfTarget = Literal["v1", "v2"]


@dataclass(frozen=True)
class KdfEnvPlan:
    target: KdfTarget
    previous_values: list[str]
    active_key_count: int
    changed: bool
    would_append: bool
    would_remove_duplicates: bool


@dataclass(frozen=True)
class KdfEnvWriteReport:
    target: KdfTarget
    env_file: str
    backup_file: str
    previous_values: list[str]
    active_key_count: int
    changed: bool
    removed_duplicates: bool


def normalize_target(value: str) -> KdfTarget:
    """Normalize and validate the requested KDF target version."""
    clean = value.strip().lower()
    if clean not in {"v1", "v2"}:
        raise ValueError("target must be v1 or v2")
    return cast(KdfTarget, clean)


def _is_active_kdf_line(line: str) -> bool:
    stripped = line.lstrip()
    return not stripped.startswith("#") and stripped.startswith(f"{KDF_KEY}=")


def _kdf_value(line: str) -> str:
    return line.split("=", 1)[1].strip()


def active_kdf_values(content: str) -> list[str]:
    """Return all active KDF values in the env content."""
    return [_kdf_value(line) for line in content.splitlines() if _is_active_kdf_line(line)]


def render_kdf_env(content: str, target: KdfTarget) -> str:
    """Render env content with exactly one active KDF key set to target.

    Comments and unrelated lines are preserved. If duplicate active KDF lines
    exist, the first one is replaced and later duplicates are removed so Docker
    Compose sees one authoritative value.
    """
    lines = content.splitlines()
    out: list[str] = []
    wrote_key = False
    for line in lines:
        if _is_active_kdf_line(line):
            if not wrote_key:
                out.append(f"{KDF_KEY}={target}")
                wrote_key = True
            continue
        out.append(line)
    if not wrote_key:
        out.append(f"{KDF_KEY}={target}")
    return "\n".join(out) + "\n"


def plan_kdf_env(content: str, target: KdfTarget) -> KdfEnvPlan:
    """Return a redacted mutation plan for operator review."""
    previous = active_kdf_values(content)
    rendered = render_kdf_env(content, target)
    return KdfEnvPlan(
        target=target,
        previous_values=previous,
        active_key_count=len(previous),
        changed=rendered != content,
        would_append=len(previous) == 0,
        would_remove_duplicates=len(previous) > 1,
    )


def write_kdf_env(env_file: Path, backup_dir: Path, target: KdfTarget, confirm: str) -> KdfEnvWriteReport:
    """Write the KDF target after creating a backup; requires confirmation."""
    if confirm != CONFIRM_TOKEN:
        raise PermissionError(f"write requires --confirm {CONFIRM_TOKEN}")
    content = env_file.read_text()
    plan = plan_kdf_env(content, target)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"{env_file.name}.gh111-kdf-{target}.{stamp}.bak"
    shutil.copy2(env_file, backup_file)
    env_file.write_text(render_kdf_env(content, target))
    return KdfEnvWriteReport(
        target=target,
        env_file=str(env_file),
        backup_file=str(backup_file),
        previous_values=plan.previous_values,
        active_key_count=plan.active_key_count,
        changed=plan.changed,
        removed_duplicates=plan.would_remove_duplicates,
    )


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GH#111 KDF env-file guard")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Print a redacted KDF env rewrite plan")
    plan.add_argument("--env-file", required=True)
    plan.add_argument("--target", required=True, choices=["v1", "v2"])

    write = sub.add_parser("write", help="Backup and write the KDF env target")
    write.add_argument("--env-file", required=True)
    write.add_argument("--backup-dir", required=True)
    write.add_argument("--target", required=True, choices=["v1", "v2"])
    write.add_argument("--confirm", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    target = normalize_target(args.target)
    env_file = Path(args.env_file)
    if args.command == "plan":
        _print_json(asdict(plan_kdf_env(env_file.read_text(), target)))
        return 0
    if args.command == "write":
        report = write_kdf_env(env_file, Path(args.backup_dir), target, args.confirm)
        _print_json(asdict(report))
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
