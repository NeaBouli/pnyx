"""Operator checks for GH#111 Nullifier v2 canary.

This script is intentionally read-only. It snapshots identity/nullifier state
before and after the real HLR verification window, then evaluates whether the
observed DB changes match the selected canary mode.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


CanaryMode = Literal["existing-reregistration", "new-registration"]


@dataclass(frozen=True)
class IdentityKdfSnapshot:
    kdf_env: str
    total: int
    with_v2: int
    version_v2: int
    active: int
    revoked: int


@dataclass(frozen=True)
class NullifierV2CanaryVerdict:
    ok: bool
    mode: CanaryMode
    blockers: list[str]
    warnings: list[str]
    before: IdentityKdfSnapshot
    after: IdentityKdfSnapshot


async def collect_snapshot() -> IdentityKdfSnapshot:
    """Collect the current identity KDF state without mutating production data."""
    from database import AsyncSessionLocal

    kdf_env = os.getenv("IDENTITY_NULLIFIER_KDF_VERSION", "unset").strip().lower() or "unset"
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE nullifier_hash_v2 IS NOT NULL) AS with_v2,
                       COUNT(*) FILTER (WHERE nullifier_version = 'v2') AS version_v2,
                       COUNT(*) FILTER (WHERE status = 'ACTIVE') AS active,
                       COUNT(*) FILTER (WHERE status = 'REVOKED') AS revoked
                FROM identity_records
                """
            )
        )
        row = result.mappings().one()
    return IdentityKdfSnapshot(
        kdf_env=kdf_env,
        total=int(row["total"]),
        with_v2=int(row["with_v2"]),
        version_v2=int(row["version_v2"]),
        active=int(row["active"]),
        revoked=int(row["revoked"]),
    )


def evaluate_preflight(snapshot: IdentityKdfSnapshot) -> list[str]:
    """Return blockers that must be resolved before first GH#111 activation."""
    blockers: list[str] = []
    if snapshot.kdf_env not in {"unset", "v1"}:
        blockers.append("kdf_env_not_v1_or_unset")
    if snapshot.with_v2 != 0:
        blockers.append("v2_rows_already_present")
    if snapshot.version_v2 != 0:
        blockers.append("version_v2_rows_already_present")
    if snapshot.total <= 0:
        blockers.append("no_identity_rows_to_canary")
    return blockers


def evaluate_canary(
    before: IdentityKdfSnapshot,
    after: IdentityKdfSnapshot,
    mode: CanaryMode,
) -> NullifierV2CanaryVerdict:
    """Compare before/after snapshots for the selected canary mode."""
    blockers: list[str] = []
    warnings: list[str] = []

    if after.kdf_env != "v2":
        blockers.append("after_kdf_env_not_v2")
    if after.with_v2 <= before.with_v2:
        blockers.append("no_new_v2_hash_observed")
    if after.version_v2 <= before.version_v2:
        blockers.append("no_new_version_v2_row_observed")
    if after.with_v2 != after.version_v2:
        blockers.append("v2_hash_and_version_counts_diverge")

    if mode == "existing-reregistration":
        if after.total != before.total:
            blockers.append("existing_reregistration_changed_total_identity_rows")
        if after.active != before.active:
            blockers.append("existing_reregistration_changed_active_identity_rows")
        if after.revoked != before.revoked:
            warnings.append("revoked_count_changed_during_existing_reregistration")
    elif mode == "new-registration":
        if after.total != before.total + 1:
            blockers.append("new_registration_did_not_add_exactly_one_identity_row")
        if after.active != before.active + 1:
            blockers.append("new_registration_did_not_add_exactly_one_active_row")
    else:
        blockers.append("unknown_canary_mode")

    return NullifierV2CanaryVerdict(
        ok=not blockers,
        mode=mode,
        blockers=blockers,
        warnings=warnings,
        before=before,
        after=after,
    )


def write_snapshot(snapshot: IdentityKdfSnapshot, output: Path) -> None:
    output.write_text(json.dumps(asdict(snapshot), indent=2, sort_keys=True) + "\n")


def read_snapshot(path: Path) -> IdentityKdfSnapshot:
    payload = json.loads(path.read_text())
    return IdentityKdfSnapshot(
        kdf_env=str(payload["kdf_env"]),
        total=int(payload["total"]),
        with_v2=int(payload["with_v2"]),
        version_v2=int(payload["version_v2"]),
        active=int(payload["active"]),
        revoked=int(payload["revoked"]),
    )


def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


async def _cmd_snapshot(args: argparse.Namespace) -> int:
    snapshot = await collect_snapshot()
    if args.output:
        write_snapshot(snapshot, Path(args.output))
    blockers = evaluate_preflight(snapshot) if args.preflight else []
    _print_json({"snapshot": asdict(snapshot), "preflight_blockers": blockers})
    return 1 if blockers else 0


async def _cmd_compare(args: argparse.Namespace) -> int:
    before = read_snapshot(Path(args.before))
    after = await collect_snapshot()
    verdict = evaluate_canary(before, after, args.mode)
    _print_json(asdict(verdict))
    return 0 if verdict.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GH#111 Nullifier v2 canary read-only checks")
    sub = parser.add_subparsers(dest="command", required=True)

    snapshot = sub.add_parser("snapshot", help="Capture current identity KDF state")
    snapshot.add_argument("--output", help="Optional JSON snapshot output path")
    snapshot.add_argument("--preflight", action="store_true", help="Fail if first-activation preflight is not clean")

    compare = sub.add_parser("compare", help="Compare current state with a pre-window snapshot")
    compare.add_argument("--before", required=True, help="JSON snapshot captured before the canary")
    compare.add_argument(
        "--mode",
        required=True,
        choices=["existing-reregistration", "new-registration"],
        help="Expected real HLR verification mode",
    )
    return parser


async def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "snapshot":
        return await _cmd_snapshot(args)
    if args.command == "compare":
        return await _cmd_compare(args)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
