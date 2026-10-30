"""Shared validation for public geographic filters."""
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def validate_region_filter(
    db: AsyncSession,
    *,
    periferia_id: int | None,
    dimos_id: int | None,
    status_code: int = 400,
) -> None:
    """Reject unknown or internally inconsistent geographic filter IDs."""
    if periferia_id is not None:
        periferia_result = await db.execute(
            text("SELECT 1 FROM periferia WHERE id = :periferia_id AND is_active = TRUE"),
            {"periferia_id": periferia_id},
        )
        if periferia_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status_code, detail="invalid periferia_id")

    if dimos_id is None:
        return

    dimos_result = await db.execute(
        text("SELECT periferia_id FROM dimos WHERE id = :dimos_id AND is_active = TRUE"),
        {"dimos_id": dimos_id},
    )
    actual_periferia_id = dimos_result.scalar_one_or_none()
    if actual_periferia_id is None:
        raise HTTPException(status_code=status_code, detail="invalid dimos_id")
    if periferia_id is not None and actual_periferia_id != periferia_id:
        raise HTTPException(status_code=status_code, detail="dimos_id does not belong to periferia_id")


async def validate_public_region_filters(*, db, periferia_id=None, dimos_id=None, **_):
    """Run semantic validation before any public cache/fill accounting."""
    if periferia_id is not None or dimos_id is not None:
        await validate_region_filter(
            db, periferia_id=periferia_id, dimos_id=dimos_id, status_code=422,
        )
