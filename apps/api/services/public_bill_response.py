"""Serve-time DB authorization for bill-derived cache bodies, independent of Redis."""
import asyncio
from copy import deepcopy
from dataclasses import replace
from functools import wraps
from inspect import signature

from fastapi import HTTPException
from sqlalchemy import select

from models import ParliamentBill
from services.bill_visibility import filter_public_bill_rows, public_bill_filter, results_hidden
from services.public_bill_snapshot import building_snapshot, read_visibility_snapshot
from services.result_cache_policy import with_result_cache_policy


BILL_SCHEMAS = frozenset({"independent", "rows", "aggregate", "representation", "point", "history"})
BODY_KEY = "_public_bill_body"
IDS_KEY = "_public_bill_ids"
RESULTS_IDS_KEY = "_public_bill_results_ids"
RESULTS_INPUTS_KEY = "_public_bill_results_inputs"
CONTRIBUTOR_KEYS = frozenset({IDS_KEY, RESULTS_IDS_KEY})


async def public_bill_ids(db, candidates=None):
    if candidates is not None and not candidates:
        return set()
    query = select(ParliamentBill.id).where(public_bill_filter())
    if candidates is not None and len(candidates) <= 500:
        query = query.where(ParliamentBill.id.in_(candidates))
    # Scalar SQL bypasses stale ORM visibility fields in the identity map.
    return set((await db.execute(query)).scalars().all())


async def capture_public_bill_body(factory, *, db, point_results=None, candidates=None):
    snapshot = await read_visibility_snapshot(db, candidates=candidates)
    if point_results is not None:
        if point_results not in snapshot.result_inputs or results_hidden(snapshot.result_inputs[point_results]):
            raise HTTPException(404, "Public results are no longer visible")
        # Point totals must retain even suppressed cells. Build without the
        # aggregate contributor filter, and attest the counts actually read.
        totals = await factory()
        inputs = replace(snapshot.result_inputs[point_results], counts=(
            totals.yes, totals.no, totals.abstain, totals.unknown,
            totals.tier1_total, totals.zk_total, totals.publishable,
        ))
        return {IDS_KEY: [point_results], RESULTS_IDS_KEY: [point_results] if totals.publishable else [], BODY_KEY: totals,
                RESULTS_INPUTS_KEY: {point_results: inputs}}
    token = building_snapshot.set(snapshot)
    try:
        body = await factory()
        return {IDS_KEY: sorted(snapshot.listed), RESULTS_IDS_KEY: sorted(snapshot.contributors), BODY_KEY: body}
    finally:
        building_snapshot.reset(token)


def verified_body(body):
    return isinstance(body, dict) and CONTRIBUTOR_KEYS <= body.keys() and BODY_KEY in body


def safe_body(body, snapshot):
    return (verified_body(body) and not set(body[IDS_KEY]) - snapshot.listed
            and not set(body[RESULTS_IDS_KEY]) - snapshot.results
            and all(snapshot.result_inputs.get(bill_id) == inputs
                    for bill_id, inputs in body.get(RESULTS_INPUTS_KEY, {}).items()))


async def serve_public_bill_body(body, *, db, schema, refresh=None, bill_ids=(), point_results=False):
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
    if schema == "point" and not point_results:
        ids = set(bill_ids)
        if ids - await public_bill_ids(db, ids):
            raise HTTPException(404, "Public bill not found")
        return deepcopy(body)
    if schema == "history":
        current = await read_visibility_snapshot(db)
        return [deepcopy(entry[BODY_KEY]) for entry in body if safe_body(entry, current)]

    try:
        async with asyncio.timeout(10):
            while True:
                # Representation contains only the captured bill population.
                # Recheck all of it (including contributors outside the detail
                # limit), without scanning unrelated imported bills' text.
                candidates = None
                if schema == "representation":
                    candidates = (set(body[IDS_KEY]) | set(body[RESULTS_IDS_KEY])) if verified_body(body) else ()
                current = await read_visibility_snapshot(db, candidates=candidates)
                if schema == "point" and set(bill_ids) - current.listed:
                    raise HTTPException(404, "Public bill not found")
                inputs_verified = (not point_results or (
                    bool(bill_ids) and verified_body(body)
                    and set(body.get(RESULTS_INPUTS_KEY, {})) == set(bill_ids)
                ))
                if inputs_verified and safe_body(body, current):
                    return deepcopy(body[BODY_KEY])
                if refresh is None:
                    return None
                body = await refresh()
                await asyncio.sleep(0)
    except TimeoutError as exc:
        raise HTTPException(504, "Fresh public data is temporarily unavailable") from exc


def public_bill_response(schema, *, refresh=None, bill_ids=None, suppression_dependent=False):
    """Register inline/Redis caches at their shared public serving boundary."""
    if schema not in BILL_SCHEMAS:
        raise ValueError(f"Unknown public bill schema: {schema}")

    def decorate(function):
        parameters = signature(function)
        @wraps(function)
        async def wrapped(*args, **kwargs):
            bound = parameters.bind(*args, **kwargs)
            bound.apply_defaults()
            async def respond(_policy):
                body = await function(*args, **kwargs)
                ids = bill_ids(bound.arguments) if bill_ids else (
                    (bound.arguments["bill_id"],) if schema == "point" else ()
                )
                return await serve_public_bill_body(
                    body, db=bound.arguments["db"], schema=schema,
                    refresh=(lambda: refresh(**bound.arguments)) if refresh else None,
                    bill_ids=ids,
                )
            if suppression_dependent or schema in {"aggregate", "representation", "history"}:
                return await with_result_cache_policy(respond)
            return await respond(None)
        wrapped.public_bill_contributor_keys = CONTRIBUTOR_KEYS if schema in {"aggregate", "representation", "history"} else frozenset()
        wrapped.public_bill_schema = schema
        wrapped.public_visibility_filter = serve_public_bill_body
        wrapped.public_suppression_dependent = suppression_dependent or schema in {"aggregate", "representation", "history"}
        return wrapped
    return decorate
