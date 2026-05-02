"""
MOD-21: Diavgeia Integration Router
POST /api/v1/admin/diavgeia/scrape           — Manual trigger (admin-only)
POST /api/v1/admin/diavgeia/refresh-orgs-cache — Refresh org snapshot (admin, async)
GET  /api/v1/admin/diavgeia/refresh-orgs-cache/{job_id} — Poll job status
GET  /api/v1/municipal/{dimos_id}/decisions  — Diavgeia decisions for a municipality
GET  /api/v1/regions/{periferia_id}/decisions — Diavgeia decisions for a region
"""
import asyncio
import os
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import DiavgeiaDecision, DimosDiavgeiaOrg, Dimos, Periferia

logger = logging.getLogger(__name__)
router = APIRouter(tags=["MOD-21 Diavgeia"])

from dependencies import verify_admin_key

# In-memory job tracking for async org cache refresh
_refresh_jobs: dict[str, dict] = {}


def verify_admin(key: bool = Depends(verify_admin_key)):
    return key


# ─── Schemas ────────────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    decision_type_uids: Optional[list[str]] = None
    published_after: Optional[datetime] = None
    max_pages: int = 10
    dry_run: bool = False


# ─── POST /api/v1/admin/diavgeia/scrape ─────────────────────────────────────

@router.post("/api/v1/admin/diavgeia/scrape")
async def admin_scrape_diavgeia(
    req: ScrapeRequest,
    _key: str = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger Diavgeia scrape. Admin-only."""
    from services.diavgeia_scraper import scrape_decisions

    result = await scrape_decisions(
        session=db,
        decision_type_uids=req.decision_type_uids,
        published_after=req.published_after,
        max_pages=req.max_pages,
        dry_run=req.dry_run,
    )
    return result.to_dict()


# ─── POST /api/v1/admin/diavgeia/refresh-orgs-cache ─────────────────────────

async def _run_refresh_job(job_id: str) -> None:
    """Background task: fetch all orgs and write snapshot."""
    job = _refresh_jobs[job_id]
    job["status"] = "running"
    start = time.monotonic()
    try:
        from scripts.fetch_diavgeia_orgs_snapshot import fetch_all_orgs, DATA_DIR, SNAPSHOT_PATH, SNAPSHOT_GZ_PATH
        import json
        import gzip

        orgs = await fetch_all_orgs()
        snapshot = {
            "metadata": {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "total_count": len(orgs),
                "source_url": "https://diavgeia.gov.gr/luminapi/opendata/organizations.json",
                "api_version_hint": "luminapi-v1",
                "script_version": "1.0",
                "fetch_duration_seconds": round(time.monotonic() - start, 1),
            },
            "organizations": orgs,
        }
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(snapshot, ensure_ascii=False, indent=1)
        raw_bytes = raw.encode("utf-8")

        if len(raw_bytes) > 10 * 1024 * 1024:
            with gzip.open(SNAPSHOT_GZ_PATH, "wt", encoding="utf-8") as f:
                f.write(raw)
            snapshot_size = SNAPSHOT_GZ_PATH.stat().st_size
        else:
            with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
                f.write(raw)
            snapshot_size = SNAPSHOT_PATH.stat().st_size

        job["status"] = "completed"
        job["result"] = {
            "fetched_count": len(orgs),
            "snapshot_size_bytes": snapshot_size,
            "duration_seconds": round(time.monotonic() - start, 1),
        }
    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        logger.error("Refresh orgs cache failed: %s", e)


@router.post("/api/v1/admin/diavgeia/refresh-orgs-cache", status_code=202)
async def admin_refresh_orgs_cache(
    _key: str = Depends(verify_admin),
) -> dict:
    """Start async org cache refresh. Returns job_id for polling."""
    # Check for existing running jobs
    for jid, job in _refresh_jobs.items():
        if job["status"] == "running":
            return {"status": "already_running", "job_id": jid}

    # Compute previous snapshot age
    snapshot_path = Path(__file__).resolve().parent.parent / "data" / "diavgeia_orgs_snapshot.json"
    snapshot_gz_path = snapshot_path.with_suffix(".json.gz")
    previous_age_days = None
    for p in (snapshot_path, snapshot_gz_path):
        if p.exists():
            import json as _json
            import gzip as _gzip
            try:
                opener = _gzip.open if p.suffix == ".gz" else open
                with opener(p, "rt", encoding="utf-8") as f:
                    meta = _json.load(f).get("metadata", {})
                fetched_at = meta.get("fetched_at", "")
                if fetched_at:
                    age = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)).days
                    previous_age_days = age
            except Exception:
                pass
            break

    job_id = str(uuid.uuid4())[:8]
    _refresh_jobs[job_id] = {"status": "accepted", "started_at": datetime.now(timezone.utc).isoformat()}

    # Fire and forget
    asyncio.create_task(_run_refresh_job(job_id))

    return {
        "status": "accepted",
        "job_id": job_id,
        "previous_snapshot_age_days": previous_age_days,
    }


@router.get("/api/v1/admin/diavgeia/refresh-orgs-cache/{job_id}")
async def admin_refresh_orgs_cache_status(
    job_id: str,
    _key: str = Depends(verify_admin),
) -> dict:
    """Poll status of an org cache refresh job."""
    if job_id not in _refresh_jobs:
        raise HTTPException(404, f"Job {job_id} not found")
    return {"job_id": job_id, **_refresh_jobs[job_id]}


# ─── GET /api/v1/municipal/{dimos_id}/decisions ─────────────────────────────

@router.get("/api/v1/municipal/{dimos_id}/decisions")
async def list_municipal_decisions(
    dimos_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    decision_type_uid: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List Diavgeia decisions for a municipality."""
    dimos = await db.get(Dimos, dimos_id)
    if not dimos:
        raise HTTPException(404, "Dimos not found")

    stmt = (
        select(DiavgeiaDecision)
        .where(DiavgeiaDecision.dimos_id == dimos_id)
    )
    if decision_type_uid:
        stmt = stmt.where(DiavgeiaDecision.decision_type_uid == decision_type_uid)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    stmt = stmt.order_by(DiavgeiaDecision.publish_timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return {
        "dimos_id": dimos_id,
        "dimos_name_el": dimos.name_el,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "ada": r.ada,
                "subject": r.subject,
                "decision_type_uid": r.decision_type_uid,
                "decision_type_label": r.decision_type_label,
                "organization_label": r.organization_label,
                "document_url": r.document_url,
                "publish_timestamp": r.publish_timestamp.isoformat() if r.publish_timestamp else None,
            }
            for r in rows
        ],
    }


# ─── GET /api/v1/regions/{periferia_id}/decisions ───────────────────────────

@router.get("/api/v1/regions/{periferia_id}/decisions")
async def list_regional_decisions(
    periferia_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    decision_type_uid: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List Diavgeia decisions for a region (all municipalities within)."""
    periferia = await db.get(Periferia, periferia_id)
    if not periferia:
        raise HTTPException(404, "Periferia not found")

    stmt = (
        select(DiavgeiaDecision)
        .where(DiavgeiaDecision.periferia_id == periferia_id)
    )
    if decision_type_uid:
        stmt = stmt.where(DiavgeiaDecision.decision_type_uid == decision_type_uid)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    stmt = stmt.order_by(DiavgeiaDecision.publish_timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return {
        "periferia_id": periferia_id,
        "periferia_name_el": periferia.name_el,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "ada": r.ada,
                "subject": r.subject,
                "decision_type_uid": r.decision_type_uid,
                "decision_type_label": r.decision_type_label,
                "organization_label": r.organization_label,
                "document_url": r.document_url,
                "publish_timestamp": r.publish_timestamp.isoformat() if r.publish_timestamp else None,
                "dimos_id": r.dimos_id,
            }
            for r in rows
        ],
    }
