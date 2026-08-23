"""Create a read-only correction plan for primary Diavgeia mappings.

This command never writes to the database. For reproducible offline review, pass
CSV exports made with PostgreSQL COPY:

    python -m scripts.audit_diavgeia_mappings \
      --dimos-csv /tmp/dimos.csv \
      --mappings-csv /tmp/mappings.csv \
      --output-csv ./diavgeia-primary-plan.csv \
      --summary-json ./diavgeia-primary-summary.json
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.seed_diavgeia_orgs import load_snapshot
from services.diavgeia_mapping import DimosRecord, PrimaryMatch, propose_primary_mappings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit primary dimos-Diavgeia mappings without writing")
    parser.add_argument("--snapshot", type=Path, default=None)
    parser.add_argument("--dimos-csv", type=Path)
    parser.add_argument("--mappings-csv", type=Path)
    parser.add_argument("--confidence-threshold", type=float, default=0.85)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    return parser.parse_args()


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "t", "true", "yes"}


def load_csv_state(dimos_path: Path, mappings_path: Path) -> tuple[list[DimosRecord], list[dict[str, Any]]]:
    with dimos_path.open(newline="", encoding="utf-8") as handle:
        dimoi = [
            DimosRecord(
                id=int(row["id"]),
                name_el=row["name_el"],
                periferia_id=int(row["periferia_id"]),
            )
            for row in csv.DictReader(handle)
            if _as_bool(row.get("is_active", True))
        ]
    with mappings_path.open(newline="", encoding="utf-8") as handle:
        mappings = list(csv.DictReader(handle))
    return dimoi, mappings


async def load_database_state() -> tuple[list[DimosRecord], list[dict[str, Any]]]:
    from database import AsyncSessionLocal
    from models import Dimos, DimosDiavgeiaOrg

    async with AsyncSessionLocal() as db:
        dimos_result = await db.execute(select(Dimos).where(Dimos.is_active.is_(True)))
        mapping_result = await db.execute(select(DimosDiavgeiaOrg))
        dimoi = [
            DimosRecord(id=row.id, name_el=row.name_el, periferia_id=row.periferia_id)
            for row in dimos_result.scalars().all()
        ]
        mappings = [
            {
                "dimos_id": row.dimos_id,
                "diavgeia_uid": row.diavgeia_uid,
                "org_label": row.org_label,
                "is_primary": row.is_primary,
            }
            for row in mapping_result.scalars().all()
        ]
    return dimoi, mappings


def build_audit_rows(
    proposals: list[PrimaryMatch],
    mappings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    current_primary: dict[int, list[dict[str, Any]]] = defaultdict(list)
    current_primary_owners: dict[str, set[int]] = defaultdict(set)
    subsidiary_owners: dict[str, set[int]] = defaultdict(set)
    for mapping in mappings:
        dimos_id = int(mapping["dimos_id"])
        if _as_bool(mapping.get("is_primary")):
            current_primary[dimos_id].append(mapping)
            current_primary_owners[str(mapping["diavgeia_uid"])].add(dimos_id)
        else:
            subsidiary_owners[str(mapping["diavgeia_uid"])].add(dimos_id)

    proposals_by_dimos = {proposal.dimos_id: proposal for proposal in proposals}
    proposed_primary_owners: dict[str, set[int]] = defaultdict(set)
    for proposal in proposals:
        if proposal.status == "matched" and proposal.org_uid:
            proposed_primary_owners[proposal.org_uid].add(proposal.dimos_id)

    rows: list[dict[str, Any]] = []
    for proposal in proposals:
        existing = current_primary.get(proposal.dimos_id, [])
        old_uids = sorted(str(mapping["diavgeia_uid"]) for mapping in existing)
        conflicting_current_owners: set[int] = set()
        if proposal.org_uid:
            for owner in current_primary_owners.get(proposal.org_uid, set()) - {proposal.dimos_id}:
                owner_proposal = proposals_by_dimos.get(owner)
                owner_has_accepted_move = (
                    owner_proposal is not None
                    and owner_proposal.status == "matched"
                    and not owner_proposal.needs_review
                    and owner_proposal.org_uid not in {None, proposal.org_uid}
                )
                if not owner_has_accepted_move:
                    conflicting_current_owners.add(owner)

        if len(existing) > 1:
            action = "blocked_multiple_primary"
        elif proposal.status != "matched":
            action = "manual_review"
        elif proposal.needs_review:
            action = "manual_review"
        elif len(proposed_primary_owners[proposal.org_uid or ""]) > 1 or conflicting_current_owners:
            action = "blocked_primary_uid_owned"
        elif not existing:
            action = "add_primary"
        elif old_uids[0] == proposal.org_uid:
            action = "unchanged"
        else:
            action = "correct_primary"

        rows.append(
            {
                "dimos_id": proposal.dimos_id,
                "dimos_name_el": proposal.dimos_name_el,
                "action": action,
                "current_primary_uids": "|".join(old_uids),
                "proposed_primary_uid": proposal.org_uid or "",
                "proposed_org_label": proposal.org_label or "",
                "token_set_score": f"{proposal.token_set_score:.3f}",
                "ratio_score": f"{proposal.ratio_score:.3f}",
                "needs_review": str(proposal.needs_review).upper(),
                "source": proposal.source,
                "reason": proposal.reason or "",
                "evidence_url": proposal.evidence_url or "",
                "conflicting_primary_dimos_ids": "|".join(
                    str(owner) for owner in sorted(conflicting_current_owners)
                ),
            }
        )

    action_counts = Counter(row["action"] for row in rows)
    shared_subsidiaries = {
        uid: sorted(owners)
        for uid, owners in subsidiary_owners.items()
        if len(owners) > 1
    }
    summary = {
        "mode": "read_only",
        "review_gate": "explicit_approval_required_before_database_write",
        "total_dimoi": len(proposals),
        "actions": dict(sorted(action_counts.items())),
        "shared_subsidiary_uid_count": len(shared_subsidiaries),
        "shared_subsidiary_examples": dict(list(sorted(shared_subsidiaries.items()))[:10]),
    }
    return rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else ["dimos_id", "action"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


async def main() -> None:
    args = parse_args()
    if bool(args.dimos_csv) != bool(args.mappings_csv):
        raise SystemExit("--dimos-csv and --mappings-csv must be provided together")

    if args.dimos_csv:
        dimoi, mappings = load_csv_state(args.dimos_csv, args.mappings_csv)
    else:
        dimoi, mappings = await load_database_state()

    snapshot = load_snapshot(args.snapshot)
    proposals = propose_primary_mappings(
        dimoi,
        snapshot["organizations"],
        threshold=args.confidence_threshold,
    )
    rows, summary = build_audit_rows(proposals, mappings)
    write_csv(args.output_csv, rows)
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Read-only correction plan: {args.output_csv}")
    print(f"Read-only summary: {args.summary_json}")
    print("Review gate: explicit approval is required before any database write")


if __name__ == "__main__":
    asyncio.run(main())
