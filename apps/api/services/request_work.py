"""Bound request work independently of the number of waiting clients."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from functools import wraps
from weakref import WeakKeyDictionary

from fastapi import HTTPException, Request
from fastapi.responses import Response

from rate_limit import global_key, limiter


class SingleFlight:
    """One in-flight calculation per key and event loop, with bounded key count.

    Followers share the leader's result or error. Cancelling a follower cannot
    cancel the leader. Completed entries (including errors) are always removed.
    """

    def __init__(self, capacity: int = 128):
        self.capacity = capacity
        self._loops = WeakKeyDictionary()

    async def run(self, key, factory):
        loop = asyncio.get_running_loop()
        pending = self._loops.setdefault(loop, {})
        if key in pending:
            return await asyncio.shield(pending[key])
        if len(pending) >= self.capacity:
            raise HTTPException(429, "Work capacity reached", headers={"Retry-After": "1"})
        future = loop.create_future()
        pending[key] = future
        try:
            result = await factory()
            future.set_result(result)
            return result
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                future.cancel()
            else:
                future.set_exception(exc)
                future.exception()  # Retrieve even when there are no followers.
            raise
        finally:
            pending.pop(key, None)


_flights = SingleFlight()


def coalesce(key):
    def decorate(function):
        @wraps(function)
        async def wrapped(*args, **kwargs):
            return await _flights.run(key(), lambda: function(*args, **kwargs))
        return wrapped
    return decorate


class WorkSlots:
    """A per-loop semaphore with immediate rejection instead of a wait queue."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._loops = WeakKeyDictionary()

    @asynccontextmanager
    async def slot(self):
        semaphore = self._loops.setdefault(asyncio.get_running_loop(), asyncio.Semaphore(self.capacity))
        if semaphore.locked():
            raise HTTPException(429, "Work capacity reached", headers={"Retry-After": "1"})
        async with semaphore:
            yield


def _fill_guard(name, quota="6/minute"):
    async def guard(request: Request):
        return Response(status_code=204)
    guard.__name__ = f"fill_{name}"
    return limiter.shared_limit(quota, scope=f"cache-fill:{name}", key_func=global_key)(guard)


_fill_guards = {name: _fill_guard(name) for name in ("cplm", "representation", "newsletter")}


def register_public_fill_budget(name: str, quota: str) -> None:
    if name not in _fill_guards:
        _fill_guards[name] = _fill_guard(name, quota)


async def cache_fill_quota(name: str):
    """Shared across workers; outage fallback permits half the configured quota."""
    await _fill_guards[name](request=Request({"type": "http", "path": "/cache-fill", "headers": []}))
