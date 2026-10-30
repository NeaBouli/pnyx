"""Opt-in overview diagnostics; never log query parameters or bill identities."""
from contextlib import contextmanager
from contextvars import ContextVar
import logging
import os
from time import monotonic


logger = logging.getLogger(__name__)
_enabled = ContextVar("overview_timing", default=False)


@contextmanager
def overview_timing():
    token = _enabled.set(os.getenv("PUBLIC_OVERVIEW_TIMING") == "1")
    try:
        with timing("request"):
            yield
    finally:
        _enabled.reset(token)


@contextmanager
def timing(phase):
    if not _enabled.get():
        yield
        return
    started = monotonic()
    try:
        yield
    finally:
        logger.info("overview_timing phase=%s elapsed_ms=%.3f", phase, (monotonic() - started) * 1000)
