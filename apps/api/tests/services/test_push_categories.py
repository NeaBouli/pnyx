"""Data-only category pushes: flag, dedup, cap, weekly limit, payload (T-652),
atomic send-once claim and accepted/failed contract (T-655)."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services import push_categories as pc

NOW = datetime(2026, 10, 12, 7, 0, tzinfo=timezone.utc)


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.calls = 0

    async def exists(self, key):
        self.calls += 1
        return key in self.store

    async def incr(self, key):
        self.calls += 1
        self.store[key] = str(int(self.store.get(key, "0")) + 1)
        return int(self.store[key])

    async def expire(self, key, ttl):
        return True

    async def get(self, key):
        self.calls += 1
        return self.store.get(key)

    async def set(self, key, value, nx=False, ex=None):
        self.calls += 1
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def eval(self, script, numkeys, key, claim, mode, ttl):
        # Same semantics as push_categories._SETTLE_CLAIM.
        if self.store.get(key) != claim:
            return 0
        if mode == "final":
            self.store[key] = "1"
        else:
            del self.store[key]
        return 1


class DownRedis:
    async def set(self, *a, **k):
        raise ConnectionError("redis down")


def _sender(accepted=None, failed=0, attempted=None):
    sent = []

    async def send(template_id, payload):
        await asyncio.sleep(0)  # let concurrent callers interleave
        sent.append((template_id, payload))
        acc = 1 if accepted is None else accepted
        return {"attempted": acc + failed if attempted is None else attempted, "accepted": acc, "failed": failed}

    return send, sent


bill = SimpleNamespace(id="GR-1", title_el="Νομοσχέδιο", created_at=NOW.replace(tzinfo=None) - timedelta(hours=1))


@pytest.mark.asyncio
async def test_flag_off_sends_nothing_and_touches_no_redis(monkeypatch):
    monkeypatch.delenv(pc.FLAG, raising=False)
    redis, (send, sent) = FakeRedis(), _sender()
    assert await pc.push_vote_24h(redis, bill, sender=send) is False
    assert await pc.push_system_update(redis, "1.0.34", sender=send) is False
    assert sent == [] and redis.calls == 0


@pytest.mark.asyncio
async def test_each_event_is_sent_once(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    redis, (send, sent) = FakeRedis(), _sender()
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW) is True
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW) is False
    assert sent == [("vote_24h", {"title": "⏳ Τελευταίες 24 ώρες", "body": "Νομοσχέδιο", "bill_id": "GR-1"})]


@pytest.mark.asyncio
async def test_hourly_cap_bounds_volume(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    monkeypatch.setattr(pc, "HOURLY_CAP", 2)
    redis, (send, sent) = FakeRedis(), _sender()
    results = [
        await pc.push_bill_announced(redis, SimpleNamespace(id=f"GR-{i}", title_el="t"), sender=send, now=NOW)
        for i in range(4)
    ]
    assert results == [True, True, False, False] and len(sent) == 2


@pytest.mark.asyncio
async def test_weekly_digest_at_most_once_per_iso_week(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    redis, (send, sent) = FakeRedis(), _sender()
    assert await pc.push_weekly_digest(redis, 3, 1, now=NOW, sender=send) is True
    assert await pc.push_weekly_digest(redis, 4, 2, now=NOW + timedelta(days=3), sender=send) is False
    assert await pc.push_weekly_digest(redis, 4, 2, now=NOW + timedelta(days=7), sender=send) is True
    assert [p["date"] for _, p in sent] == ["2026-W42", "2026-W43"]


@pytest.mark.asyncio
async def test_system_update_first_run_only_records_version(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    redis, (send, sent) = FakeRedis(), _sender()
    assert await pc.push_system_update(redis, "1.0.33", sender=send) is False
    assert await pc.push_system_update(redis, "1.0.33", sender=send) is False
    assert await pc.push_system_update(redis, "1.0.34", sender=send) is True
    assert await pc.push_system_update(redis, "1.0.34", sender=send) is False
    assert sent == [("system_update", {"title": "🆕 Νέα έκδοση εφαρμογής", "body": "Διαθέσιμη η έκδοση 1.0.34", "version": "1.0.34"})]


def test_only_recently_announced_bills_qualify():
    assert pc.announced_recently(bill, NOW)
    old = SimpleNamespace(created_at=NOW - timedelta(hours=49))
    assert not pc.announced_recently(old, NOW)
    assert not pc.announced_recently(SimpleNamespace(created_at=None), NOW)


@pytest.mark.asyncio
async def test_data_only_sender_has_no_os_visible_title(monkeypatch):
    from routers import notify

    posted = []

    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json):
            posted.extend(json)

    async def fake_redis():
        return object()

    async def tokens(_r):
        return ["ExponentPushToken[a]", "ExponentPushToken[b]"]

    monkeypatch.setattr(notify, "_get_redis", fake_redis)
    monkeypatch.setattr(notify, "_registered_push_tokens", tokens)
    monkeypatch.setattr(notify.httpx, "AsyncClient", Client)
    await notify.notify_all_data_only("vote_24h", {"title": "T", "body": "B", "bill_id": "GR-1"})
    assert len(posted) == 2
    for message in posted:
        assert "title" not in message and "body" not in message
        assert message["data"] == {"template_id": "vote_24h", "local_display": "1", "title": "T", "body": "B", "bill_id": "GR-1"}
        assert message["priority"] == "high"


@pytest.mark.asyncio
async def test_concurrent_schedulers_send_an_event_once(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    redis, (send, sent) = FakeRedis(), _sender()
    results = await asyncio.gather(*[
        pc.push_vote_24h(redis, bill, sender=send, now=NOW) for _ in range(5)
    ])
    assert sorted(results) == [False, False, False, False, True]
    assert len(sent) == 1
    assert redis.store["notified:vote_24h:GR-1"] == "1"


@pytest.mark.asyncio
async def test_failed_send_releases_claim_for_retry(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    redis = FakeRedis()

    async def broken(template_id, payload):
        raise RuntimeError("redis token read failed")

    assert await pc.push_vote_24h(redis, bill, sender=broken, now=NOW) is False
    assert "notified:vote_24h:GR-1" not in redis.store
    send, sent = _sender()
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW) is True
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_nothing_accepted_is_not_finalized(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    redis, (send, sent) = FakeRedis(), _sender(accepted=0, failed=3)
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW) is False
    assert "notified:vote_24h:GR-1" not in redis.store
    retry, resent = _sender()
    assert await pc.push_vote_24h(redis, bill, sender=retry, now=NOW) is True
    assert len(resent) == 1


@pytest.mark.asyncio
async def test_partial_batch_is_finalized_without_resend(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    redis, (send, sent) = FakeRedis(), _sender(accepted=100, failed=40)
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW) is True
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW) is False
    assert len(sent) == 1 and redis.store["notified:vote_24h:GR-1"] == "1"


@pytest.mark.asyncio
async def test_no_registered_devices_finalizes_without_sending(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    redis, (send, sent) = FakeRedis(), _sender(accepted=0, attempted=0)
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW) is False
    assert redis.store["notified:vote_24h:GR-1"] == "1"


@pytest.mark.asyncio
async def test_capped_event_is_retried_in_a_later_hour(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    monkeypatch.setattr(pc, "HOURLY_CAP", 0)
    redis, (send, sent) = FakeRedis(), _sender()
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW) is False
    assert "notified:vote_24h:GR-1" not in redis.store
    monkeypatch.setattr(pc, "HOURLY_CAP", 1)
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW + timedelta(hours=1)) is True
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_redis_down_fails_closed(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    send, sent = _sender()
    with pytest.raises(ConnectionError):
        await pc.push_vote_24h(DownRedis(), bill, sender=send, now=NOW)
    assert sent == []


@pytest.mark.asyncio
async def test_expired_claim_owned_by_another_worker_is_not_overwritten(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    redis = FakeRedis()

    async def slow(template_id, payload):
        # Our claim expired meanwhile and another worker took the key.
        redis.store["notified:vote_24h:GR-1"] = "claim:other"
        return {"attempted": 1, "accepted": 0, "failed": 1}

    assert await pc.push_vote_24h(redis, bill, sender=slow, now=NOW) is False
    assert redis.store["notified:vote_24h:GR-1"] == "claim:other"


def test_weekly_digest_catch_up_window():
    monday = datetime(2026, 10, 12, tzinfo=timezone.utc)
    assert not pc.weekly_digest_due(monday.replace(hour=6))
    assert pc.weekly_digest_due(monday.replace(hour=7))
    assert pc.weekly_digest_due(monday + timedelta(days=2, hours=23))
    assert not pc.weekly_digest_due(monday + timedelta(days=3))
    assert not pc.weekly_digest_due(monday + timedelta(days=6))


def _expo(monkeypatch, responses):
    from routers import notify

    posted = []

    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json):
            posted.append(json)
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

    async def fake_redis():
        return object()

    async def tokens(_r):
        return [f"ExponentPushToken[{i}]" for i in range(150)]

    monkeypatch.setattr(notify, "_get_redis", fake_redis)
    monkeypatch.setattr(notify, "_registered_push_tokens", tokens)
    monkeypatch.setattr(notify.httpx, "AsyncClient", Client)
    return notify, posted


class _Resp:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


@pytest.mark.asyncio
async def test_sender_counts_expo_tickets(monkeypatch):
    tickets = [{"status": "ok", "id": "x"}] * 98 + [{"status": "error", "details": {"error": "DeviceNotRegistered"}}] * 2
    notify, posted = _expo(monkeypatch, [_Resp(200, {"data": tickets}), _Resp(200, {"data": [{"status": "ok"}] * 50})])
    result = await notify.notify_all_data_only("vote_24h", {"bill_id": "GR-1"})
    assert result == {"attempted": 150, "accepted": 148, "failed": 2}
    assert [len(b) for b in posted] == [100, 50]


@pytest.mark.asyncio
async def test_sender_counts_failed_batches(monkeypatch):
    notify, _ = _expo(monkeypatch, [_Resp(500, {}), RuntimeError("timeout")])
    result = await notify.notify_all_data_only("vote_24h", {"bill_id": "GR-1"})
    assert result == {"attempted": 150, "accepted": 0, "failed": 150}


@pytest.mark.asyncio
async def test_sender_token_lookup_error_propagates(monkeypatch):
    from routers import notify

    async def down():
        raise ConnectionError("redis down")

    monkeypatch.setattr(notify, "_get_redis", down)
    with pytest.raises(ConnectionError):
        await notify.notify_all_data_only("vote_24h", {})


@pytest.mark.asyncio
async def test_flag_off_jobs_and_hook_return_before_redis(monkeypatch):
    import main
    from services import bill_lifecycle

    monkeypatch.delenv(pc.FLAG, raising=False)

    def no_redis(*a, **k):
        raise AssertionError("redis must not be touched while the flag is off")

    import redis.asyncio as aioredis

    monkeypatch.setattr(aioredis, "from_url", no_redis)
    await main.scheduled_push_categories()
    await main.scheduled_weekly_digest()
    await bill_lifecycle._hook_push_vote_24h(bill)


@pytest.mark.asyncio
async def test_sender_stops_when_deadline_leaves_no_time_for_a_batch(monkeypatch):
    clock = iter([0.0, 0.0, 0.0, 599.5])  # lookup x2, batch 1, batch 2 with 0.5 s left
    notify, posted = _expo(monkeypatch, [_Resp(200, {"data": [{"status": "ok"}] * 100})])
    monkeypatch.setattr(notify, "_clock", lambda: next(clock))
    result = await notify.notify_all_data_only("vote_24h", {"bill_id": "GR-1"}, deadline=600.0)
    assert result == {"attempted": 150, "accepted": 100, "failed": 50}
    assert [len(b) for b in posted] == [100]


@pytest.mark.asyncio
async def test_sender_hard_bounds_a_blocking_request(monkeypatch):
    from routers import notify

    started = []

    class Hanging:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json):
            started.append(len(json))
            await asyncio.sleep(30)  # e.g. a slow chunked response; httpx timeouts are per phase

    async def fake_redis():
        return object()

    async def tokens(_r):
        return [f"ExponentPushToken[{i}]" for i in range(150)]

    monkeypatch.setattr(notify, "_get_redis", fake_redis)
    monkeypatch.setattr(notify, "_registered_push_tokens", tokens)
    monkeypatch.setattr(notify.httpx, "AsyncClient", Hanging)
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    result = await notify.notify_all_data_only("vote_24h", {}, deadline=notify._clock() + 1.2)
    assert loop.time() - t0 < 2.0
    assert result == {"attempted": 150, "accepted": 0, "failed": 150}
    assert started == [100]  # no second batch after the deadline


@pytest.mark.asyncio
async def test_sender_slow_token_lookup_hits_deadline_before_sending(monkeypatch):
    from routers import notify

    async def fake_redis():
        return object()

    async def slow_tokens(_r):
        await asyncio.sleep(30)
        return ["ExponentPushToken[a]"]

    monkeypatch.setattr(notify, "_get_redis", fake_redis)
    monkeypatch.setattr(notify, "_registered_push_tokens", slow_tokens)
    with pytest.raises(TimeoutError):
        await notify.notify_all_data_only("vote_24h", {}, deadline=notify._clock() + 0.2)


@pytest.mark.asyncio
async def test_service_deadline_releases_claim_when_sender_overruns(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    monkeypatch.setattr(pc, "SEND_BUDGET_S", 0.2)
    redis = FakeRedis()

    async def slow(template_id, payload):
        await asyncio.sleep(30)

    assert await pc.push_vote_24h(redis, bill, sender=slow, now=NOW) is False
    assert "notified:vote_24h:GR-1" not in redis.store


@pytest.mark.asyncio
async def test_service_deadline_counts_slow_pre_work(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    monkeypatch.setattr(pc, "SEND_BUDGET_S", 0.1)
    redis = FakeRedis()
    plain_incr = redis.incr

    async def slow_incr(key):
        await asyncio.sleep(0.2)
        return await plain_incr(key)

    redis.incr = slow_incr
    send, sent = _sender()
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW) is False
    assert sent == [] and "notified:vote_24h:GR-1" not in redis.store


@pytest.mark.asyncio
async def test_default_sender_receives_the_claim_deadline(monkeypatch):
    from routers import notify

    monkeypatch.setenv(pc.FLAG, "1")
    monkeypatch.setattr(pc, "_clock", lambda: 1000.0)
    seen = {}

    async def fake(template_id, payload, *, deadline):
        seen["deadline"] = deadline
        return {"attempted": 1, "accepted": 1, "failed": 0}

    monkeypatch.setattr(notify, "notify_all_data_only", fake)
    assert await pc.push_vote_24h(FakeRedis(), bill, now=NOW) is True
    reserve = min(pc.SENDER_RESERVE_MAX_S, pc.SEND_BUDGET_S * pc.SENDER_RESERVE_FRACTION)
    assert seen == {"deadline": 1000.0 + pc.SEND_BUDGET_S - reserve}
    assert reserve > 0


@pytest.mark.parametrize("ttl", ["10", "60", "90", "150", "900", "3600"])
def test_send_budget_always_ends_inside_the_claim_lease(monkeypatch, ttl):
    import importlib

    monkeypatch.setenv("PUSH_DATA_ONLY_CLAIM_TTL", ttl)
    try:
        mod = importlib.reload(pc)
        assert mod.CLAIM_TTL >= 60
        assert 0 < mod.SEND_BUDGET_S <= mod.CLAIM_TTL - 30
    finally:
        monkeypatch.delenv("PUSH_DATA_ONLY_CLAIM_TTL")
        importlib.reload(pc)


@pytest.mark.asyncio
async def test_partial_acceptance_before_hanging_batch_is_finalized(monkeypatch):
    """Default sender: batch 1 accepted, batch 2 hangs until the deadline.

    The sender must return its counts before the outer backstop, so the event
    is finalized (no retry to devices that already got it), not released.
    """
    from routers import notify

    monkeypatch.setenv(pc.FLAG, "1")
    monkeypatch.setattr(pc, "SEND_BUDGET_S", 1.5)
    posted = []

    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json):
            posted.append(len(json))
            if len(posted) == 1:
                return _Resp(200, {"data": [{"status": "ok"}] * len(json)})
            await asyncio.sleep(30)

    async def fake_redis():
        return object()

    async def tokens(_r):
        return [f"ExponentPushToken[{i}]" for i in range(150)]

    monkeypatch.setattr(notify, "_get_redis", fake_redis)
    monkeypatch.setattr(notify, "_registered_push_tokens", tokens)
    monkeypatch.setattr(notify.httpx, "AsyncClient", Client)
    redis = FakeRedis()

    assert await pc.push_vote_24h(redis, bill, now=NOW) is True
    assert posted == [100, 50]
    assert redis.store["notified:vote_24h:GR-1"] == "1"

    # Replay (next scheduler run): nothing is sent again.
    assert await pc.push_vote_24h(redis, bill, now=NOW) is False
    assert posted == [100, 50]


@pytest.mark.asyncio
async def test_final_settle_redis_error_keeps_owned_claim_and_blocks_resend(monkeypatch):
    monkeypatch.setenv(pc.FLAG, "1")
    redis, (send, sent) = FakeRedis(), _sender(accepted=5)
    settle_calls = []

    async def failing_eval(script, numkeys, key, claim, mode, ttl):
        settle_calls.append((key, claim, mode))
        raise ConnectionError("redis down")

    redis.eval = failing_eval
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW) is True
    claim = redis.store["notified:vote_24h:GR-1"]
    assert settle_calls == [("notified:vote_24h:GR-1", claim, "final")] and claim.startswith("claim:")
    assert await pc.push_vote_24h(redis, bill, sender=send, now=NOW) is False
    assert len(sent) == 1 and redis.store["notified:vote_24h:GR-1"] == claim
