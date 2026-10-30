"""Serve-time DB authorization for bill-derived cache bodies, independent of Redis."""
import asyncio
from copy import deepcopy
from functools import wraps
from inspect import signature

from fastapi import HTTPException
from sqlalchemy import select

from models import ParliamentBill
from services.bill_visibility import filter_public_bill_rows, public_bill_filter


BILL_SCHEMAS = frozenset({"independent", "rows", "aggregate", "representation", "point", "history"})
BODY_KEY = "_public_bill_body"
IDS_KEY = "_public_bill_ids"


async def public_bill_ids(db, candidates=None):
    if candidates is not None and not candidates:
        return set()
    query = select(ParliamentBill.id).where(public_bill_filter())
    if candidates is not None and len(candidates) <= 500:
        query = query.where(ParliamentBill.id.in_(candidates))
    # Scalar SQL bypasses stale ORM visibility fields in the identity map.
    return set((await db.execute(query)).scalars().all())


async def capture_public_bill_body(factory, *, db):
    # Capture before calculation: a hide during calculation must also invalidate
    # the resulting aggregate. Provenance stays private, including truncated rows.
    ids = await public_bill_ids(db)
    return {IDS_KEY: sorted(ids), BODY_KEY: await factory()}


async def serve_public_bill_body(body, *, db, schema, refresh=None, bill_ids=()):
    """Filter rows, deny hidden points, or rebuild/drop unsafe aggregates.

    A generation counter and cache age never authorize bill data. Legacy
    aggregates without provenance are unverified and must be rebuilt or dropped.
    Failed DB checks propagate; cached objects are never modified.
    """
    if schema not in BILL_SCHEMAS:
        raise ValueError(f"Unknown public bill schema: {schema}")
    if schema == "independent":
        return deepcopy(body)
    if schema == "rows":
        return deepcopy(await filter_public_bill_rows(body, db=db))
    if schema == "point":
        ids = set(bill_ids)
        if ids - await public_bill_ids(db, ids):
            raise HTTPException(404, "Public bill not found")
        return deepcopy(body)
    if schema == "history":
        ids = {bill_id for snapshot in body if isinstance(snapshot, dict) and BODY_KEY in snapshot
               for bill_id in snapshot.get(IDS_KEY, ())}
        visible_ids = await public_bill_ids(db, ids)
        entries = []
        for snapshot in body:
            if (isinstance(snapshot, dict) and IDS_KEY in snapshot and BODY_KEY in snapshot
                    and not set(snapshot[IDS_KEY]) - visible_ids):
                entries.append(deepcopy(snapshot[BODY_KEY]))
        return entries

    try:
        async with asyncio.timeout(10):
            while True:
                verified = isinstance(body, dict) and IDS_KEY in body and BODY_KEY in body
                if verified:
                    ids = set(body[IDS_KEY])
                    value = body[BODY_KEY]
                    if schema == "representation":
                        rows = value.get("bills", []) + ([value["last_bill"]] if value.get("last_bill") else [])
                        ids.update(row["bill_id"] for row in rows)
                    visible = await public_bill_ids(db, ids)
                    if not ids - visible:
                        return deepcopy(value)
                    if schema == "representation":
                        # The detail list is truncated; its rows cannot safely
                        # reconstruct all-time totals or cumulative scores.
                        result = deepcopy(value)
                        result["bills"] = [row for row in result.get("bills", []) if row["bill_id"] in visible]
                        last = result.get("last_bill")
                        if last and last["bill_id"] not in visible:
                            result["last_bill"] = None
                        for field in ("cumulative_representation", "cumulative_divergence", "bills_analyzed",
                                      "total_citizen_votes", "label_el", "label_en", "color"):
                            if field in result:
                                result[field] = None
                        return result
                if refresh is None:
                    return None
                body = await refresh()
    except TimeoutError as exc:
        raise HTTPException(504, "Fresh public data is temporarily unavailable") from exc


def public_bill_response(schema, *, refresh=None, bill_ids=None):
    """Register inline/Redis caches at their shared public serving boundary."""
    if schema not in BILL_SCHEMAS:
        raise ValueError(f"Unknown public bill schema: {schema}")

    def decorate(function):
        parameters = signature(function)
        @wraps(function)
        async def wrapped(*args, **kwargs):
            bound = parameters.bind(*args, **kwargs)
            bound.apply_defaults()
            body = await function(*args, **kwargs)
            ids = bill_ids(bound.arguments) if bill_ids else (
                (bound.arguments["bill_id"],) if schema == "point" else ()
            )
            return await serve_public_bill_body(
                body, db=bound.arguments["db"], schema=schema,
                refresh=(lambda: refresh(**bound.arguments)) if refresh else None,
                bill_ids=ids,
            )
        wrapped.public_bill_schema = schema
        wrapped.public_visibility_filter = serve_public_bill_body
        return wrapped
    return decorate
