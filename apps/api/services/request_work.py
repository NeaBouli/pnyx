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

    def __init__(self, capacity: int = 128, *, reject_on_capacity=True, wait_timeout=10):
        self.capacity = capacity
        self.reject_on_capacity = reject_on_capacity
        self.wait_timeout = wait_timeout
        self._loops = WeakKeyDictionary()
        self._tasks = set()

    def _pending(self):
        return self._loops.setdefault(asyncio.get_running_loop(), {})

    async def _execute(self, pending, key, future, factory):
        try:
            result = await factory()
            future.set_result(result)
            return result
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                future.cancel()
            else:
                future.set_exception(exc)
                future.exception()
            raise
        finally:
            pending.pop(key, None)

    def start(self, key, factory):
        """Start one background fill, or leave it for a later request at capacity."""
        pending = self._pending()
        if key in pending:
            return pending[key]
        if len(pending) >= self.capacity:
            return None
        future = asyncio.get_running_loop().create_future()
        pending[key] = future
        task = asyncio.create_task(self._execute(pending, key, future, factory))
        self._tasks.add(task)

        def finished(task):
            self._tasks.discard(task)
            if not task.cancelled():
                task.exception()

        task.add_done_callback(finished)
        return future

    async def run(self, key, factory):
        loop = asyncio.get_running_loop()
        pending = self._pending()
        if key in pending:
            if self.reject_on_capacity:
                return await asyncio.shield(pending[key])
            try:
                return await asyncio.wait_for(asyncio.shield(pending[key]), self.wait_timeout)
            except asyncio.TimeoutError:
                return await factory()
        if len(pending) >= self.capacity:
            if self.reject_on_capacity:
                raise HTTPException(429, "Work capacity reached", headers={"Retry-After": "1"})
            return await factory()
        future = loop.create_future()
        pending[key] = future
        return await self._execute(pending, key, future, factory)


class WaitingWorkSlots:
    """FIFO execution slots with bounded waiters; cold reads fall back inline.

    A full queue waits out the same deadline without joining the semaphore's
    wait list. Saturation never becomes an HTTP error.
    """

    DEFERRED = object()

    def __init__(self, capacity=32, queue_capacity=128, wait_timeout=10):
        self.capacity = capacity
        self.queue_capacity = queue_capacity
        self.wait_timeout = wait_timeout
        self._loops = WeakKeyDictionary()

    async def run(self, factory, *, background=False):
        state = self._loops.setdefault(
            asyncio.get_running_loop(), {"slots": asyncio.Semaphore(self.capacity), "waiting": 0},
        )
        slots = state["slots"]
        if state["waiting"] >= self.queue_capacity:
            if background:
                return self.DEFERRED
            await asyncio.sleep(self.wait_timeout)
            return await factory()
        state["waiting"] += 1
        acquired = False
        try:
            try:
                await asyncio.wait_for(slots.acquire(), self.wait_timeout)
                acquired = True
            except asyncio.TimeoutError:
                pass
        finally:
            state["waiting"] -= 1
        if not acquired:
            if background:
                return self.DEFERRED
            return await factory()
        try:
            return await factory()
        finally:
            slots.release()


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


async def cache_fill_quota(name: str):
    """Shared across workers; outage fallback permits half the configured quota."""
    await _fill_guards[name](request=Request({"type": "http", "path": "/cache-fill", "headers": []}))
