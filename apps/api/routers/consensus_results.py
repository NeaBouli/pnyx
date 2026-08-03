"""Public, aggregate-only DIAVGEIA consensus representation views."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.bill_visibility import public_bill_raw_sql
from services.geographic_scope import validate_region_filter


router = APIRouter(prefix="/api/v1/consensus", tags=["consensus-results"])

ViewName = Literal["municipal", "regional", "national"]
K_ANONYMITY_MIN = 10


def _public_visibility_sql() -> tuple[str, dict[str, str]]:
    """Mirror the shared public DIAVGEIA guard with bound raw-SQL terms."""
    return public_bill_raw_sql("pb")


def _scope_sql(view: ViewName) -> str:
    """Return a fixed SQL predicate for one public geographic view."""
    if view == "municipal":
        return "pb.governance_level = 'MUNICIPAL' AND pb.dimos_id = :dimos_id"
    if view == "regional":
        return "pb.governance_level = 'REGIONAL' AND pb.periferia_id = :periferia_id"
    return """
        (
            pb.governance_level = 'NATIONAL'
            OR (pb.governance_level = 'REGIONAL' AND pb.periferia_id IS NOT NULL)
            OR (pb.governance_level = 'MUNICIPAL' AND pb.dimos_id IS NOT NULL)
        )
    """


def _empty_view(view: ViewName, available: bool) -> dict:
    return {
        "view": view,
        "available": available,
        "bill_count": 0,
        "consensus_vote_count": 0,
        "weighted_score": None,
        "bills": [],
    }


def _view_payload(view: ViewName, rows: list[dict], available: bool = True) -> dict:
    """Convert already-aggregated rows without exposing individual votes."""
    if not available or not rows:
        return _empty_view(view, available)

    first = rows[0]
    total_votes = int(first["total_consensus_votes"] or 0)
    weighted_sum = float(first["weighted_score_sum"] or 0.0)
    weighted_score = round(weighted_sum / total_votes, 2) if total_votes else None
    bills = [
        {
            "bill_id": str(row["bill_id"]),
            "title_el": str(row["title_el"]),
            "governance_level": str(row["governance_level"]),
            "dimos_id": row["dimos_id"],
            "periferia_id": row["periferia_id"],
            "org_label": row["org_label"],
            "diavgeia_ada": row["diavgeia_ada"],
            "consensus_score": round(float(row["consensus_score"]), 2),
            "consensus_count": int(row["consensus_count"]),
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]
    return {
        "view": view,
        "available": True,
        "bill_count": int(first["total_bills"] or 0),
        "consensus_vote_count": total_votes,
        "weighted_score": weighted_score,
        "bills": bills,
    }


async def _load_view(
    db: AsyncSession,
    view: ViewName,
    *,
    dimos_id: int | None,
    periferia_id: int | None,
    limit: int,
) -> dict:
    if view == "municipal" and dimos_id is None:
        return _empty_view(view, False)
    if view == "regional" and periferia_id is None:
        return _empty_view(view, False)

    visibility_sql, visibility_params = _public_visibility_sql()
    statement = text(f"""
        WITH bill_consensus AS (
            SELECT
                cv.bill_id,
                AVG(cv.score)::float AS consensus_score,
                COUNT(*)::integer AS consensus_count
            FROM consensus_votes cv
            GROUP BY cv.bill_id
            HAVING COUNT(*) >= :k_anonymity_min
        ), scoped AS (
            SELECT
                pb.id AS bill_id,
                pb.title_el,
                pb.governance_level::text AS governance_level,
                pb.dimos_id,
                pb.periferia_id,
                pb.org_label,
                pb.diavgeia_ada,
                pb.updated_at,
                bc.consensus_score,
                bc.consensus_count
            FROM parliament_bills pb
            JOIN bill_consensus bc ON bc.bill_id = pb.id
            WHERE pb.source = 'DIAVGEIA'
              AND {visibility_sql}
              AND ({_scope_sql(view)})
        )
        SELECT
            scoped.*,
            COUNT(*) OVER ()::integer AS total_bills,
            SUM(consensus_count) OVER ()::integer AS total_consensus_votes,
            SUM(consensus_score * consensus_count) OVER ()::float AS weighted_score_sum
        FROM scoped
        ORDER BY consensus_count DESC, updated_at DESC NULLS LAST, bill_id ASC
        LIMIT :limit
    """)
    result = await db.execute(statement, {
        **visibility_params,
        "dimos_id": dimos_id,
        "periferia_id": periferia_id,
        "k_anonymity_min": K_ANONYMITY_MIN,
        "limit": limit,
    })
    return _view_payload(view, [dict(row) for row in result.mappings().all()])


@router.get("/representation")
async def get_consensus_representation(
    dimos_id: int | None = Query(None, ge=1),
    periferia_id: int | None = Query(None, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Return separate aggregate views; never return individual consensus rows."""
    if dimos_id is not None or periferia_id is not None:
        await validate_region_filter(
            db,
            periferia_id=periferia_id,
            dimos_id=dimos_id,
        )

    visibility_sql, visibility_params = _public_visibility_sql()
    coverage_result = await db.execute(text(f"""
        SELECT
            COUNT(*)::integer AS total_diavgeia_bills,
            COUNT(*) FILTER (
                WHERE governance_level = 'NATIONAL'
                   OR (governance_level = 'REGIONAL' AND periferia_id IS NOT NULL)
                   OR (governance_level = 'MUNICIPAL' AND dimos_id IS NOT NULL)
            )::integer AS geographically_represented_bills,
            COUNT(*) FILTER (
                WHERE governance_level = 'INSTITUTIONAL'
            )::integer AS institutional_or_unresolved_bills,
            COUNT(*) FILTER (
                WHERE (governance_level = 'REGIONAL' AND periferia_id IS NULL)
                   OR (governance_level = 'MUNICIPAL' AND dimos_id IS NULL)
            )::integer AS geographic_mapping_gaps
        FROM parliament_bills pb
        WHERE pb.source = 'DIAVGEIA'
          AND {visibility_sql}
    """), visibility_params)
    coverage_row = coverage_result.mappings().one()
    institutional_or_unresolved = int(coverage_row["institutional_or_unresolved_bills"] or 0)
    mapping_gaps = int(coverage_row["geographic_mapping_gaps"] or 0)

    municipal = await _load_view(
        db, "municipal", dimos_id=dimos_id, periferia_id=periferia_id, limit=limit,
    )
    regional = await _load_view(
        db, "regional", dimos_id=dimos_id, periferia_id=periferia_id, limit=limit,
    )
    national = await _load_view(
        db, "national", dimos_id=dimos_id, periferia_id=periferia_id, limit=limit,
    )
    return {
        "source": "DIAVGEIA",
        "privacy": "aggregate_only",
        "minimum_group_size": K_ANONYMITY_MIN,
        "institutional_excluded": True,
        "unmapped_geographic_excluded": True,
        "coverage": {
            "total_diavgeia_bills": int(coverage_row["total_diavgeia_bills"] or 0),
            "geographically_represented_bills": int(coverage_row["geographically_represented_bills"] or 0),
            "institutional_or_unresolved_bills": institutional_or_unresolved,
            "geographic_mapping_gaps": mapping_gaps,
            "complete_geographic_representation": institutional_or_unresolved == 0 and mapping_gaps == 0,
        },
        "dimos_id": dimos_id,
        "periferia_id": periferia_id,
        "views": {
            "municipal": municipal,
            "regional": regional,
            "national": national,
        },
    }
