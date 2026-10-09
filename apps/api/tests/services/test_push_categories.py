"""Data-only category pushes: flag, dedup, cap, weekly limit, payload (T-652)."""
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

    async def setex(self, key, ttl, value):
        self.store[key] = value

    async def get(self, key):
        self.calls += 1
        return self.store.get(key)

    async def set(self, key, value):
        self.store[key] = value


def _sender():
    sent = []

    async def send(template_id, payload):
        sent.append((template_id, payload))

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
