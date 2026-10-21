"""One renewable Redis lease for newsletter transitions and campaign dispatch."""
import asyncio
from contextlib import asynccontextmanager, suppress
from uuid import uuid4


LOCK_KEY = "newsletter:campaign_lock"
LOCK_MS = 60_000
RENEW_LOCK = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
return redis.call('PEXPIRE', KEYS[1], ARGV[2])
"""
RELEASE_LOCK = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
return redis.call('DEL', KEYS[1])
"""


class NewsletterLockUnavailable(Exception):
    """Contention or a lost lease; callers must retry without dispatching."""


class NewsletterLease:
    def __init__(self, store):
        self.store = store
        self.owner = uuid4().hex

    async def check(self):
        try:
            renewed = await asyncio.wait_for(
                self.store.eval(RENEW_LOCK, 1, LOCK_KEY, self.owner, LOCK_MS),
                timeout=min(5, LOCK_MS / 3000),
            )
            if renewed == 1:
                return
        except Exception:
            pass
        raise NewsletterLockUnavailable()


@asynccontextmanager
async def newsletter_lock(store=None):
    try:
        if store is None:
            from routers.newsletter import _get_redis
            store = await _get_redis()
        lease = NewsletterLease(store)
        acquired = await asyncio.wait_for(
            store.set(LOCK_KEY, lease.owner, nx=True, px=LOCK_MS), timeout=5,
        )
    except Exception:
        raise NewsletterLockUnavailable() from None
    if not acquired:
        raise NewsletterLockUnavailable()
    task = asyncio.current_task()
    lost = False

    async def renew():
        nonlocal lost
        try:
            while True:
                await asyncio.sleep(LOCK_MS / 3000)
                await lease.check()
        except NewsletterLockUnavailable:
            lost = True
            task.cancel()

    heartbeat = asyncio.create_task(renew())
    try:
        yield lease
    except asyncio.CancelledError:
        if lost:
            raise NewsletterLockUnavailable() from None
        raise
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat
        with suppress(Exception):
            await asyncio.wait_for(
                store.eval(RELEASE_LOCK, 1, LOCK_KEY, lease.owner),
                timeout=min(5, LOCK_MS / 3000),
            )
