import os
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers import payments


@pytest.fixture(autouse=True)
def _enable_test_payment_intake(monkeypatch):
    monkeypatch.setenv("PAYMENTS_INTAKE_GATE", "legal_recipient_confirmed")


class _Request:
    def __init__(self, body: bytes = b"{}", signature: str = ""):
        self._body = body
        self.headers = {"stripe-signature": signature} if signature else {}

    async def body(self) -> bytes:
        return self._body


class _DuplicateRedis:
    async def mget(self, *_keys):
        return ["0", "0", "0"]

    async def set(self, _key, _value, **_kwargs):
        return None

    async def get(self, _key):
        return "processed"


class _Pipeline:
    def __init__(self, redis):
        self.redis = redis
        self.commands = []

    def __getattr__(self, name):
        def queue(*args, **kwargs):
            self.commands.append((name, args, kwargs))
            return self
        return queue

    async def execute(self):
        return [await getattr(self.redis, name)(*args, **kwargs) for name, args, kwargs in self.commands]


class _SuccessRedis:
    def __init__(self):
        self.set_calls = []
        self.pushed = []
        self.values = {
            payments.R_SERVER_RECEIVED: "0",
            payments.R_DOMAIN_RECEIVED: "0",
            payments.R_RESERVE: "0",
        }

    def pipeline(self, **_kwargs):
        return _Pipeline(self)

    async def mget(self, *keys):
        return [self.values.get(key) for key in keys]

    async def set(self, key, value, **kwargs):
        self.set_calls.append((key, value, kwargs))
        if kwargs.get("nx") and key in self.values:
            return None
        self.values[key] = str(value)
        return True

    async def rpush(self, key, value):
        self.pushed.append((key, value))

    async def lrange(self, key, _start, _end):
        return [value for stored_key, value in self.pushed if stored_key == key]

    async def lpop(self, key):
        for index, (stored_key, value) in enumerate(self.pushed):
            if stored_key == key:
                self.pushed.pop(index)
                return value
        return None

    async def lpush(self, key, value):
        self.pushed.insert(0, (key, value))

    async def llen(self, key):
        return len([value for stored_key, value in self.pushed if stored_key == key])

    async def lmove(self, source, destination, wherefrom, whereto):
        indices = [index for index, (stored_key, _value) in enumerate(self.pushed) if stored_key == source]
        if not indices:
            return None
        source_index = indices[0] if wherefrom == "LEFT" else indices[-1]
        _stored_key, value = self.pushed.pop(source_index)
        destination_indices = [
            index for index, (stored_key, _value) in enumerate(self.pushed) if stored_key == destination
        ]
        if whereto == "LEFT" and destination_indices:
            self.pushed.insert(destination_indices[0], (destination, value))
        else:
            insert_at = destination_indices[-1] + 1 if destination_indices else len(self.pushed)
            self.pushed.insert(insert_at, (destination, value))
        return value

    async def lrem(self, key, count, value):
        removed = 0
        for index in range(len(self.pushed) - 1, -1, -1):
            if self.pushed[index] == (key, value) and removed < abs(count):
                self.pushed.pop(index)
                removed += 1
        return removed

    async def get(self, key):
        return self.values.get(key)

    async def setex(self, key, ttl, value):
        self.set_calls.append((key, value, {"ex": ttl}))
        self.values[key] = str(value)

    async def delete(self, key):
        self.set_calls.append((key, None, {"delete": True}))
        self.values.pop(key, None)

    async def incrbyfloat(self, _key, _value):
        value = float(self.values.get(_key, "0")) + float(_value)
        self.values[_key] = str(value)
        return value

    async def incr(self, _key):
        value = int(self.values.get(_key, "0")) + 1
        self.values[_key] = str(value)
        return value

    async def incrby(self, _key, amount):
        value = int(self.values.get(_key, "0")) + int(amount)
        self.values[_key] = str(value)
        return value

    async def eval(self, script, numkeys, *args):
        keys = args[:numkeys]
        argv = args[numkeys:]
        if "finance_event_append_v1" in script:
            if keys[1] in self.values:
                return 0
            self.pushed.append((keys[0], argv[0]))
            self.values[keys[1]] = "recorded"
            return 1
        if "pending_adjustment_quarantine_v1" in script:
            removed = await self.lrem(keys[0], 1, argv[0])
            if removed == 1:
                self.pushed.append((keys[1], argv[0]))
            return removed
        if "webhook_claim_resume_v1" in script:
            if self.values.get(keys[0]) != argv[0]:
                return 0
            self.values[keys[0]] = "processing"
            return 1
        if "payment_projection_commit_v2" in script:
            # Keep this emulation aligned with PROJECTION_ADJUSTMENT_COMMIT_SCRIPT.
            lock_key, applied_key = keys[:2]
            if self.values.get(lock_key) != argv[0]:
                return 0
            if applied_key in self.values:
                return 2
            for index in range(3):
                delta = argv[index + 1]
                if delta != "0":
                    await self.incrbyfloat(keys[index + 2], delta)
                    await self.incrbyfloat(keys[index + 5], delta)
            if int(argv[4]):
                await self.incrby(keys[8], argv[4])
            current_last = self.values.get(keys[9])
            try:
                current_last_reference = __import__("json").loads(current_last)["projection_reference"]
            except (KeyError, TypeError, ValueError):
                current_last_reference = None
            if current_last_reference == argv[10]:
                if argv[5] == "delete":
                    await self.delete(keys[9])
                elif argv[5] == "set":
                    await self.set(keys[9], argv[6])
            if argv[8] != "0":
                await self.incrbyfloat(keys[11], argv[8])
            if int(argv[9]):
                await self.incrby(keys[12], argv[9])
            await self.set(keys[10], argv[7])
            await self.set(applied_key, "processed")
            return 1
        key, token = keys[0], argv[0]
        if self.values.get(key) == token:
            self.values.pop(key, None)
            return 1
        return 0


class _PublicProjectionRedis:
    def __init__(self, *, server=None, domain=None, reserve=None, count=None, last=None):
        self.values = {
            payments.R_PUBLIC_SERVER_RECEIVED: server,
            payments.R_PUBLIC_DOMAIN_RECEIVED: domain,
            payments.R_PUBLIC_RESERVE: reserve,
            payments.R_PUBLIC_PAYMENT_COUNT: count,
            payments.R_PUBLIC_LAST_PAYMENT: __import__("json").dumps(last) if last else None,
        }

    async def mget(self, *keys):
        return [self.values.get(key) for key in keys]

    async def get(self, key):
        return self.values.get(key)


def _verified_public_record(amount=10.0, allocation=None):
    return {
        "date": "2026-07-13 12:00",
        "amount": amount,
        "currency": "EUR",
        "allocation": allocation or {"server": amount, "domain": 0.0, "reserve": 0.0},
        "method": "stripe",
        "purpose": "infrastructure_support",
        "category": "donation",
        "provider_mode": "live",
        "fulfillment_state": "not_applicable",
        "requires_accounting_review": True,
    }


def test_public_payment_record_redacts_identity_and_processor_ids():
    result = payments._public_payment_record(
        {
            "date": "2026-07-11",
            "amount": 10.0,
            "method": "stripe",
            "allocation": {"server": 10.0},
            "from": "donor@example.com",
            "stripe_session": "cs_live_secret",
        }
    )

    assert result == {
        "amount": 10.0,
        "allocation": {"server": 10.0},
    }


def test_public_support_projection_rejects_seed_test_and_incomplete_records():
    assert payments._is_public_support_record(_verified_public_record()) is True
    assert payments._is_public_support_record({
        **_verified_public_record(),
        "method": "paypal",
    }) is True
    assert payments._is_public_support_record({
        "date": "2026-04-16",
        "amount": 20.0,
        "method": "manual",
        "to": "server",
    }) is False
    assert payments._is_public_support_record({
        **_verified_public_record(),
        "method": "test",
    }) is False
    assert payments._is_public_support_record({
        **_verified_public_record(),
        "purpose": "",
    }) is False
    assert payments._is_public_support_record({
        **_verified_public_record(),
        "provider_mode": "test",
    }) is False
    assert payments._is_public_support_record({
        **_verified_public_record(),
        "allocation": {"server": 9.0, "domain": 0.0, "reserve": 0.0},
    }) is False
    assert payments._is_public_support_record({
        **_verified_public_record(),
        "allocation": {"server": 11.0, "domain": 0.0, "reserve": -1.0},
    }) is False
    assert payments._is_public_support_record({
        **_verified_public_record(),
        "amount": "NaN",
    }) is False
    assert payments._is_public_support_record({
        **_verified_public_record(),
        "allocation": {"server": "NaN", "domain": 0.0, "reserve": 0.0},
    }) is False
    assert payments._public_support_amount("Infinity") is None
    assert payments._public_allocation_amount("-Infinity") is None


@pytest.mark.asyncio
async def test_public_status_excludes_seed_and_test_records(monkeypatch):
    redis = _PublicProjectionRedis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    result = await payments.payment_status()

    assert result["server"]["received"] == 0.0
    assert result["domain"]["received"] == 0.0
    assert result["total_received"] == 0.0
    assert result["last_payment"] is None
    assert result["payment_count"] == 0


@pytest.mark.asyncio
async def test_public_status_uses_only_verified_support_records(monkeypatch):
    verified = _verified_public_record(
        amount=25.0,
        allocation={"server": 20.0, "domain": 5.0, "reserve": 0.0},
    )
    redis = _PublicProjectionRedis(
        server="20.00",
        domain="5.00",
        reserve="0.00",
        count="1",
        last=payments._public_payment_record(verified),
    )

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    result = await payments.payment_status()

    assert result["server"]["received"] == 20.0
    assert result["domain"]["received"] == 5.0
    assert result["total_received"] == 25.0
    assert result["payment_count"] == 1
    assert result["last_payment"] == {
        "amount": 25.0,
        "allocation": {"server": 20.0, "domain": 5.0, "reserve": 0.0},
    }


def test_public_community_page_keeps_payment_links_paused():
    community = (Path(__file__).parents[3] / "docs" / "community.html").read_text(encoding="utf-8")
    assert "donate.stripe.com" not in community
    assert "paypal.com/paypalme" not in community.lower()
    assert 'id="payment-intake-paused"' in community
    assert "HLR credits are procured privately" in community
    assert "BTC → HLR" not in community
    assert "LTC → HLR" not in community
    assert "var liveServerData = { received: 0, cost_total: 10, balance: -10 };" in community
    assert "var liveDomainData = { received: 0, cost_total: 9.30, balance: -9.30 };" in community


@pytest.mark.asyncio
async def test_operating_funding_initialization_is_atomic_and_preserves_existing_values():
    redis = _SuccessRedis()
    redis.values[payments.R_SERVER_RECEIVED] = "7.50"
    redis.values.pop(payments.R_DOMAIN_RECEIVED)
    redis.values.pop(payments.R_RESERVE)

    await payments._init_operating_funding(redis)

    assert redis.values[payments.R_SERVER_RECEIVED] == "7.50"
    assert redis.values[payments.R_DOMAIN_RECEIVED] == payments.INITIAL_DOMAIN_FUNDING
    assert redis.values[payments.R_RESERVE] == "0.00"
    init_calls = [call for call in redis.set_calls if call[0] in {
        payments.R_SERVER_RECEIVED, payments.R_DOMAIN_RECEIVED, payments.R_RESERVE,
    }]
    assert all(call[2] == {"nx": True} for call in init_calls)


@pytest.mark.asyncio
async def test_stripe_webhook_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)

    with pytest.raises(HTTPException) as exc:
        await payments.stripe_webhook(_Request())

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_stripe_webhook_rejects_invalid_signature(monkeypatch):
    class SignatureError(Exception):
        pass

    def reject_signature(*_args):
        raise SignatureError()

    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=reject_signature),
        error=SimpleNamespace(SignatureVerificationError=SignatureError),
    )
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)

    with pytest.raises(HTTPException) as exc:
        await payments.stripe_webhook(_Request(signature="invalid"))

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_unpaid_checkout_is_ignored(monkeypatch):
    event = {
        "id": "evt_test_duplicate",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_unpaid", "payment_status": "unpaid"}},
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)

    result = await payments.stripe_webhook(_Request(signature="test-signature"))

    assert result == {"received": True, "processed": False}


@pytest.mark.asyncio
async def test_duplicate_stripe_session_is_not_allocated(monkeypatch):
    event = {
        "id": "evt_test_duplicate",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_duplicate",
                "payment_status": "paid",
                "mode": "payment",
                "currency": "eur",
                "metadata": {"payment_purpose": "infrastructure_support"},
                "amount_total": 1000,
                "payment_intent": "pi_test_duplicate",
            }
        },
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    allocation_called = False

    async def fake_get_redis():
        return _DuplicateRedis()

    async def fake_allocate(_amount, _redis):
        nonlocal allocation_called
        allocation_called = True
        return {}

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    result = await payments.stripe_webhook(_Request(signature="test-signature"))

    assert result == {"received": True, "processed": False, "duplicate": True}
    assert allocation_called is False


@pytest.mark.asyncio
async def test_paid_checkout_is_processed_once_and_logged(monkeypatch):
    event = {
        "id": "evt_test_paid",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_paid",
                "payment_status": "paid",
                "mode": "payment",
                "currency": "eur",
                "metadata": {"payment_purpose": "infrastructure_support"},
                "amount_total": 2500,
                "payment_intent": "pi_test_paid",
            }
        },
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    redis = _SuccessRedis()

    async def fake_get_redis():
        return redis

    async def fake_allocate(amount, _redis):
        return {"server": amount, "domain": 0.0, "reserve": 0.0}

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    result = await payments.stripe_webhook(_Request(signature="test-signature"))

    assert result == {
        "received": True,
        "processed": True,
        "allocation": {"server": 25.0, "domain": 0.0, "reserve": 0.0},
    }
    assert redis.set_calls[0] == (
        "donations:stripe:session:cs_test_paid",
        "processing",
        {"nx": True, "ex": 900},
    )
    assert redis.set_calls[-1] == (
        "donations:stripe:session:cs_test_paid",
        "processed",
        {},
    )
    assert len(redis.pushed) == 2
    key, raw_record = redis.pushed[0]
    assert key == payments.R_PAYMENTS
    record = __import__("json").loads(raw_record)
    assert record["amount"] == 25.0
    assert "from" not in record
    assert record["stripe_session"] == "cs_test_paid"
    assert record["payment_intent"] == "pi_test_paid"
    assert record["purpose"] == "infrastructure_support"
    assert record["category"] == "donation"
    assert record["provider_mode"] == "test"
    assert record["requires_accounting_review"] is True
    finance_key, raw_event = redis.pushed[1]
    assert finance_key == payments.R_FINANCE_EVENTS
    finance_event = __import__("json").loads(raw_event)
    assert finance_event["event_id"] == "evt_test_paid"
    assert finance_event["event_type"] == "payment_captured"
    assert finance_event["provider_mode"] == "test"
    assert finance_event["amount_cents"] == 2500


@pytest.mark.asyncio
async def test_stripe_capture_recovers_after_atomic_record_commit(monkeypatch):
    redis = _SuccessRedis()
    await payments._append_payment_record(redis, {
        **_verified_public_record(amount=15.0),
        "stripe_session": "cs_live_recovery",
        "payment_intent": "pi_live_recovery",
    })
    redis.values[f"{payments.R_STRIPE_SESSION_PREFIX}cs_live_recovery"] = "accounting_review_required"
    await payments._append_finance_event(redis, {
        "event_id": "evt_live_recovery",
        "event_type": "payment_captured",
    })
    event = {
        "id": "evt_live_recovery",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_live_recovery",
            "payment_status": "paid",
            "mode": "payment",
            "currency": "eur",
            "amount_total": 1500,
            "payment_intent": "pi_live_recovery",
            "livemode": True,
            "metadata": {"payment_purpose": "infrastructure_support"},
        }},
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    allocation_called = False

    async def fake_allocate(_amount, _redis):
        nonlocal allocation_called
        allocation_called = True
        return {}

    async def fake_get_redis():
        return redis

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    result = await payments.stripe_webhook(_Request(signature="test-signature"))

    assert result == {
        "received": True, "processed": True, "allocation": None, "recovered": True,
    }
    assert allocation_called is False
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "15.0"
    assert redis.values[payments.R_PUBLIC_PAYMENT_COUNT] == "1"
    assert len([item for item in redis.pushed if item[0] == payments.R_PAYMENTS]) == 1
    assert len([item for item in redis.pushed if item[0] == payments.R_FINANCE_EVENTS]) == 1


@pytest.mark.asyncio
async def test_finance_event_append_is_idempotent():
    redis = _SuccessRedis()
    event = {"event_id": "evt_finance_once", "event_type": "payment_captured"}

    assert await payments._append_finance_event(redis, event) is True
    assert await payments._append_finance_event(redis, {**event, "occurred_at": "later"}) is False

    raw_events = [value for key, value in redis.pushed if key == payments.R_FINANCE_EVENTS]
    assert len(raw_events) == 1
    assert __import__("json").loads(raw_events[0]) == event


@pytest.mark.asyncio
async def test_pending_adjustment_survives_lock_contention_and_redrives():
    redis = _SuccessRedis()
    await payments._append_payment_record(redis, {
        **_verified_public_record(amount=15.0),
        "stripe_session": "cs_live_redrive",
    })
    pending_key = f"{payments.R_PENDING_STRIPE_ADJUSTMENT_PREFIX}pi_live_redrive"
    processing_key = f"{pending_key}:processing"
    raw = __import__("json").dumps({
        "event_key": f"{payments.R_STRIPE_EVENT_PREFIX}evt_live_redrive",
        "adjustment_id": "evt_live_redrive",
        "amount_cents": 500,
        "adjustment_kind": "stripe_refund_cumulative",
    }, separators=(",", ":"))
    redis.pushed.append((processing_key, raw))
    projection_lock = f"{payments.R_PUBLIC_PAYMENT_LOCK_PREFIX}stripe:cs_live_redrive"
    redis.values[projection_lock] = "another-worker"

    with pytest.raises(HTTPException) as exc:
        await payments._drain_pending_adjustments(
            redis,
            pending_key,
            "stripe:cs_live_redrive",
        )

    assert exc.value.status_code == 503
    assert (processing_key, raw) in redis.pushed

    redis.values.pop(projection_lock)
    processed = await payments._drain_pending_adjustments(
        redis,
        pending_key,
        "stripe:cs_live_redrive",
    )

    assert processed == 1
    assert not [item for item in redis.pushed if item[0] in {pending_key, processing_key}]
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "10.0"
    assert redis.values[f"{payments.R_STRIPE_EVENT_PREFIX}evt_live_redrive"] == "processed"


@pytest.mark.asyncio
async def test_pending_adjustment_stays_queued_while_projection_is_missing():
    redis = _SuccessRedis()
    pending_key = f"{payments.R_PENDING_STRIPE_ADJUSTMENT_PREFIX}pi_missing"
    processing_key = f"{pending_key}:processing"
    raw = __import__("json").dumps({
        "event_key": f"{payments.R_STRIPE_EVENT_PREFIX}evt_missing",
        "adjustment_id": "evt_missing",
        "amount_cents": 500,
        "adjustment_kind": "stripe_refund_cumulative",
    }, separators=(",", ":"))
    redis.pushed.append((pending_key, raw))

    with pytest.raises(HTTPException) as exc:
        await payments._drain_pending_adjustments(redis, pending_key, "stripe:cs_missing")

    assert exc.value.status_code == 503
    assert (processing_key, raw) in redis.pushed
    assert not [item for item in redis.pushed if item[0] == f"{pending_key}:quarantine"]
    assert f"{payments.R_STRIPE_EVENT_PREFIX}evt_missing" not in redis.values


@pytest.mark.asyncio
async def test_malformed_pending_adjustment_is_quarantined_and_tail_drains():
    redis = _SuccessRedis()
    await payments._append_payment_record(redis, {
        **_verified_public_record(amount=15.0),
        "stripe_session": "cs_live_quarantine",
    })
    pending_key = f"{payments.R_PENDING_STRIPE_ADJUSTMENT_PREFIX}pi_live_quarantine"
    processing_key = f"{pending_key}:processing"
    quarantine_key = f"{pending_key}:quarantine"
    malformed = "not-json"
    valid = __import__("json").dumps({
        "event_key": f"{payments.R_STRIPE_EVENT_PREFIX}evt_after_poison",
        "adjustment_id": "evt_after_poison",
        "amount_cents": 500,
        "adjustment_kind": "stripe_refund_cumulative",
    }, separators=(",", ":"))
    await redis.rpush(pending_key, malformed)
    await redis.rpush(pending_key, valid)

    processed = await payments._drain_pending_adjustments(
        redis,
        pending_key,
        "stripe:cs_live_quarantine",
    )

    assert processed == 1
    assert (quarantine_key, malformed) in redis.pushed
    assert not [item for item in redis.pushed if item[0] in {pending_key, processing_key}]
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "10.0"
    assert redis.values[f"{payments.R_STRIPE_EVENT_PREFIX}evt_after_poison"] == "processed"


@pytest.mark.asyncio
async def test_adjustment_commit_rejects_expired_lock_without_mutation():
    class _ExpiringLockRedis(_SuccessRedis):
        async def eval(self, script, numkeys, *args):
            if "payment_projection_commit_v2" in script:
                self.values[args[0]] = "replacement-worker"
            return await super().eval(script, numkeys, *args)

    redis = _ExpiringLockRedis()
    await payments._append_payment_record(redis, {
        **_verified_public_record(amount=15.0),
        "stripe_session": "cs_live_expired_lock",
    })

    with pytest.raises(HTTPException) as exc:
        await payments._apply_public_payment_adjustment(
            redis,
            "stripe:cs_live_expired_lock",
            500,
            "stripe_refund_cumulative",
            "evt_live_expired_lock",
        )

    assert exc.value.status_code == 503
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "15.0"
    assert redis.values[payments.R_SERVER_RECEIVED] == "15.0"
    assert f"{payments.R_ADJUSTMENT_APPLIED_PREFIX}evt_live_expired_lock" not in redis.values


@pytest.mark.asyncio
async def test_adjustment_does_not_replace_a_newer_last_payment():
    newer_last = {
        "amount": 20.0,
        "allocation": {"server": 20.0, "domain": 0.0, "reserve": 0.0},
        "projection_reference": "stripe:cs_live_newer",
    }

    class _ConcurrentCaptureRedis(_SuccessRedis):
        async def eval(self, script, numkeys, *args):
            if "payment_projection_commit_v2" in script:
                self.values[payments.R_PUBLIC_LAST_PAYMENT] = __import__("json").dumps(newer_last)
            return await super().eval(script, numkeys, *args)

    redis = _ConcurrentCaptureRedis()
    await payments._append_payment_record(redis, {
        **_verified_public_record(amount=15.0),
        "stripe_session": "cs_live_older",
    })

    await payments._apply_public_payment_adjustment(
        redis,
        "stripe:cs_live_older",
        1500,
        "stripe_refund_cumulative",
        "evt_live_older_refund",
    )

    assert __import__("json").loads(redis.values[payments.R_PUBLIC_LAST_PAYMENT]) == newer_last
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "0.0"


@pytest.mark.asyncio
async def test_adjustment_commit_tolerates_scalar_last_payment():
    class _ConcurrentScalarLastRedis(_SuccessRedis):
        async def eval(self, script, numkeys, *args):
            if "payment_projection_commit_v2" in script:
                self.values[payments.R_PUBLIC_LAST_PAYMENT] = "5"
            return await super().eval(script, numkeys, *args)

    redis = _ConcurrentScalarLastRedis()
    await payments._append_payment_record(redis, {
        **_verified_public_record(amount=15.0),
        "stripe_session": "cs_live_scalar_last",
    })

    result = await payments._apply_public_payment_adjustment(
        redis,
        "stripe:cs_live_scalar_last",
        500,
        "stripe_refund_cumulative",
        "evt_live_scalar_last",
    )

    assert result["applied"] is True
    assert redis.values[payments.R_PUBLIC_LAST_PAYMENT] == "5"
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "10.0"


@pytest.mark.asyncio
async def test_payment_intake_gate_blocks_before_stripe_capture_processing(monkeypatch):
    event = {
        "id": "evt_gate_closed",
        "type": "checkout.session.completed",
        "data": {"object": {}},
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    monkeypatch.delenv("PAYMENTS_INTAKE_GATE", raising=False)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)

    with pytest.raises(HTTPException) as exc:
        await payments.stripe_webhook(_Request(signature="test-signature"))

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_closed_intake_still_processes_signed_stripe_adjustments(monkeypatch):
    redis = _SuccessRedis()
    await payments._append_payment_record(redis, {
        **_verified_public_record(amount=15.0),
        "stripe_session": "cs_closed_gate",
        "payment_intent": "pi_closed_gate",
    })
    redis.values[f"{payments.R_STRIPE_PAYMENT_PREFIX}pi_closed_gate"] = "cs_closed_gate"
    event = {
        "id": "evt_closed_gate_refund",
        "type": "charge.refunded",
        "livemode": True,
        "data": {"object": {
            "payment_intent": "pi_closed_gate",
            "currency": "eur",
            "amount_refunded": 500,
        }},
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )

    async def fake_get_redis():
        return redis

    monkeypatch.delenv("PAYMENTS_INTAKE_GATE", raising=False)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    result = await payments.stripe_webhook(_Request(signature="test-signature"))

    assert result["processed"] is True
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "10.0"


@pytest.mark.asyncio
async def test_stripe_adjustment_resumes_after_accounting_review_failure(monkeypatch):
    redis = _SuccessRedis()
    await payments._append_payment_record(redis, {
        **_verified_public_record(amount=15.0),
        "stripe_session": "cs_retry_adjustment",
        "payment_intent": "pi_retry_adjustment",
    })
    redis.values[f"{payments.R_STRIPE_PAYMENT_PREFIX}pi_retry_adjustment"] = "cs_retry_adjustment"
    event_key = f"{payments.R_STRIPE_EVENT_PREFIX}evt_retry_adjustment"
    redis.values[event_key] = "accounting_review_required"
    event = {
        "id": "evt_retry_adjustment",
        "type": "charge.refunded",
        "livemode": True,
        "data": {"object": {
            "payment_intent": "pi_retry_adjustment",
            "currency": "eur",
            "amount_refunded": 500,
        }},
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )

    async def fake_get_redis():
        return redis

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    result = await payments.stripe_webhook(_Request(signature="test-signature"))

    assert result["processed"] is True
    assert redis.values[event_key] == "processed"
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "10.0"


@pytest.mark.asyncio
async def test_late_stripe_projection_lock_contention_remains_retryable(monkeypatch):
    payment_intent_key = f"{payments.R_STRIPE_PAYMENT_PREFIX}pi_late_busy"

    class _LateSessionRedis(_SuccessRedis):
        def __init__(self):
            super().__init__()
            self.payment_intent_reads = 0

        async def get(self, key):
            if key == payment_intent_key:
                self.payment_intent_reads += 1
                return None if self.payment_intent_reads == 1 else "cs_late_busy"
            return await super().get(key)

    redis = _LateSessionRedis()
    event = {
        "id": "evt_late_busy",
        "type": "charge.refunded",
        "livemode": True,
        "data": {"object": {
            "payment_intent": "pi_late_busy",
            "currency": "eur",
            "amount_refunded": 500,
        }},
    }

    async def fake_get_redis():
        return redis

    async def busy_drain(*_args):
        return 0

    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "_drain_pending_adjustments", busy_drain)

    with pytest.raises(HTTPException) as exc:
        await payments._process_stripe_adjustment(event, "charge.refunded")

    event_key = f"{payments.R_STRIPE_EVENT_PREFIX}evt_late_busy"
    pending_key = f"{payments.R_PENDING_STRIPE_ADJUSTMENT_PREFIX}pi_late_busy"
    assert exc.value.status_code == 503
    assert redis.values[event_key] == "pending_payment"
    assert await redis.llen(pending_key) == 1


@pytest.mark.asyncio
async def test_stripe_processing_claim_returns_retryable_status(monkeypatch):
    event = {
        "id": "evt_processing",
        "type": "charge.refunded",
        "livemode": True,
        "data": {"object": {
            "payment_intent": "pi_processing",
            "currency": "eur",
            "amount_refunded": 500,
        }},
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    redis = _SuccessRedis()
    redis.values[f"{payments.R_STRIPE_EVENT_PREFIX}evt_processing"] = "processing"

    async def fake_get_redis():
        return redis

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    with pytest.raises(HTTPException) as exc:
        await payments.stripe_webhook(_Request(signature="test-signature"))

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_stripe_expired_claim_race_returns_retryable_status(monkeypatch):
    class _ExpiredClaimRedis(_SuccessRedis):
        async def set(self, key, value, **kwargs):
            if kwargs.get("nx"):
                return None
            return await super().set(key, value, **kwargs)

        async def get(self, _key):
            return None

    event = {
        "id": "evt_expired_claim",
        "type": "charge.refunded",
        "livemode": True,
        "data": {"object": {
            "payment_intent": "pi_expired_claim",
            "currency": "eur",
            "amount_refunded": 500,
        }},
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    redis = _ExpiredClaimRedis()

    async def fake_get_redis():
        return redis

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    with pytest.raises(HTTPException) as exc:
        await payments.stripe_webhook(_Request(signature="test-signature"))

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_stripe_capture_processing_claim_returns_retryable_status(monkeypatch):
    event = {
        "id": "evt_capture_processing",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_capture_processing",
            "payment_status": "paid",
            "mode": "payment",
            "currency": "eur",
            "metadata": {"payment_purpose": "infrastructure_support"},
            "amount_total": 1500,
            "payment_intent": "pi_capture_processing",
        }},
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    redis = _SuccessRedis()
    redis.values[f"{payments.R_STRIPE_SESSION_PREFIX}cs_capture_processing"] = "processing"

    async def fake_get_redis():
        return redis

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    with pytest.raises(HTTPException) as exc:
        await payments.stripe_webhook(_Request(signature="test-signature"))

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_paid_stripe_checkout_requires_eur_payment_mode_and_explicit_purpose(monkeypatch):
    event = {
        "id": "evt_test_wrong_currency",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_wrong_currency",
            "payment_status": "paid",
            "mode": "payment",
            "currency": "usd",
            "amount_total": 1000,
            "payment_intent": "pi_test_wrong_currency",
            "metadata": {},
        }},
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)

    with pytest.raises(HTTPException) as exc:
        await payments.stripe_webhook(_Request(signature="test-signature"))

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_hlr_provider_credits_cannot_be_sold_through_donation_intake(monkeypatch):
    event = {
        "id": "evt_test_hlr",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_hlr",
            "payment_status": "paid",
            "mode": "payment",
            "currency": "eur",
            "amount_total": 1500,
            "payment_intent": "pi_test_hlr",
            "metadata": {"payment_purpose": "hlr_credits"},
        }},
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    allocation_called = False

    async def fake_allocate(_amount, _redis):
        nonlocal allocation_called
        allocation_called = True
        return {}

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    with pytest.raises(HTTPException) as exc:
        await payments.stripe_webhook(_Request(signature="test-signature"))

    assert exc.value.status_code == 400
    assert allocation_called is False


@pytest.mark.asyncio
async def test_stripe_dispute_emits_adjustment_without_customer_data(monkeypatch):
    event = {
        "id": "evt_test_dispute",
        "type": "charge.dispute.created",
        "data": {"object": {
            "payment_intent": "pi_test_hlr",
            "currency": "eur",
            "amount": 1500,
        }},
    }
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: event),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    redis = _SuccessRedis()

    async def fake_get(key):
        if key == f"{payments.R_STRIPE_PAYMENT_PREFIX}pi_test_hlr":
            return "cs_test_hlr"
        return None

    redis.get = fake_get

    async def fake_get_redis():
        return redis

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    result = await payments.stripe_webhook(_Request(signature="test-signature"))

    assert result == {"received": True, "processed": True, "requires_manual_review": False}
    finance_event = __import__("json").loads(redis.pushed[0][1])
    assert finance_event["adjustment_state"] == "dispute_open"
    assert "customer" not in __import__("json").dumps(finance_event).lower()


@pytest.mark.asyncio
async def test_stripe_refunds_update_public_projection_monotonically(monkeypatch):
    events = [
        {
            "id": "evt_live_payment",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_live_payment",
                "payment_status": "paid",
                "mode": "payment",
                "currency": "eur",
                "amount_total": 1500,
                "payment_intent": "pi_live_payment",
                "livemode": True,
                "metadata": {"payment_purpose": "infrastructure_support"},
            }},
        },
        *[
            {
                "id": event_id,
                "type": "charge.refunded",
                "livemode": True,
                "data": {"object": {
                    "payment_intent": "pi_live_payment",
                    "currency": "eur",
                    "amount_refunded": cumulative,
                }},
            }
            for event_id, cumulative in (
                ("evt_live_partial_refund", 500),
                ("evt_live_full_refund", 1500),
                ("evt_live_stale_refund", 500),
            )
        ],
    ]
    events = [events[1], events[0], *events[2:]]
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(construct_event=lambda *_args: events.pop(0)),
        error=SimpleNamespace(SignatureVerificationError=ValueError),
    )
    redis = _SuccessRedis()

    async def fake_get_redis():
        return redis

    async def fake_allocate(amount, _target):
        return {"server": amount, "domain": 0.0, "reserve": 0.0}

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setitem(sys.modules, "stripe", stripe_module)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    pending = await payments.stripe_webhook(_Request(signature="test-signature"))
    assert pending == {"received": True, "processed": False, "requires_manual_review": True}
    assert payments.R_PUBLIC_SERVER_RECEIVED not in redis.values

    await payments.stripe_webhook(_Request(signature="test-signature"))
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "10.0"
    assert redis.values[payments.R_PUBLIC_PAYMENT_COUNT] == "1"
    partial_last = __import__("json").loads(redis.values[payments.R_PUBLIC_LAST_PAYMENT])
    assert partial_last["amount"] == 10.0

    await payments.stripe_webhook(_Request(signature="test-signature"))
    await payments.stripe_webhook(_Request(signature="test-signature"))
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "0.0"
    assert redis.values[payments.R_PUBLIC_PAYMENT_COUNT] == "0"
    assert payments.R_PUBLIC_LAST_PAYMENT not in redis.values
    assert redis.values[payments.R_SERVER_RECEIVED] == "0.0"


@pytest.mark.asyncio
async def test_projection_combines_refund_and_dispute_and_ignores_stale_open():
    redis = _SuccessRedis()
    record = {
        **_verified_public_record(amount=15.0),
        "stripe_session": "cs_live_combined",
    }
    await payments._append_payment_record(redis, record)

    await payments._apply_public_payment_adjustment(
        redis, "stripe:cs_live_combined", 500, "stripe_refund_cumulative", "evt_combined_refund",
    )
    await payments._apply_public_payment_adjustment(
        redis, "stripe:cs_live_combined", 700, "stripe_dispute_open", "evt_combined_open",
    )
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "3.0"

    await payments._apply_public_payment_adjustment(
        redis, "stripe:cs_live_combined", 700, "stripe_dispute_won", "evt_combined_won",
    )
    stale = await payments._apply_public_payment_adjustment(
        redis, "stripe:cs_live_combined", 700, "stripe_dispute_open", "evt_combined_stale_open",
    )
    assert stale == {"applied": False, "reason": "terminal_dispute_state"}
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "10.0"


@pytest.mark.asyncio
async def test_paypal_ipn_requires_bound_receiver_and_explicit_purpose(monkeypatch):
    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "owner@example.test")
    payload = (
        b"payment_status=Completed&txn_id=txn_test&mc_gross=15.00&mc_currency=EUR"
        b"&receiver_email=attacker%40example.test&custom=hlr_credits"
    )

    with pytest.raises(HTTPException) as exc:
        await payments.paypal_ipn_webhook(_Request(body=payload))

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_paypal_donation_is_logged_without_payer_data(monkeypatch):
    redis = _SuccessRedis()
    payload = (
        b"payment_status=Completed&txn_id=txn_donation&mc_gross=15.00&mc_currency=EUR"
        b"&receiver_email=owner%40example.test&custom=developer_support"
        b"&payer_email=person%40example.test"
    )

    async def fake_get_redis():
        return redis

    async def fake_allocate(amount, _redis):
        return {"server": amount, "domain": 0.0, "reserve": 0.0}

    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "owner@example.test")
    monkeypatch.setattr(payments, "PAYPAL_IPN_URL", payments.PAYPAL_IPN_PRODUCTION_URL)

    async def verified(_payload):
        return True

    monkeypatch.setattr(payments, "_verify_paypal_ipn", verified)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    result = await payments.paypal_ipn_webhook(_Request(body=payload))

    assert result["processed"] is True
    record = __import__("json").loads(redis.pushed[0][1])
    assert record["category"] == "donation"
    assert record["provider_mode"] == "live"
    assert redis.values[payments.R_PUBLIC_PAYMENT_COUNT] == "1"
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "15.0"
    assert "payer" not in __import__("json").dumps(record).lower()
    assert "person@example.test" not in __import__("json").dumps(redis.pushed)
    assert redis.values[f"{payments.R_PAYPAL_TXN}txn_donation"] == "processed"

    pushed_before_replay = len(redis.pushed)
    duplicate = await payments.paypal_ipn_webhook(_Request(body=payload))
    assert duplicate["reason"] == "duplicate"
    assert len(redis.pushed) == pushed_before_replay


@pytest.mark.asyncio
async def test_paypal_non_finite_amount_fails_closed(monkeypatch):
    redis = _SuccessRedis()
    payload = (
        b"payment_status=Completed&txn_id=txn_nan&mc_gross=NaN&mc_currency=EUR"
        b"&receiver_email=owner%40example.test&custom=developer_support"
    )

    async def verified(_payload):
        return True

    async def fake_get_redis():
        return redis

    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "owner@example.test")
    monkeypatch.setattr(payments, "PAYPAL_IPN_URL", payments.PAYPAL_IPN_PRODUCTION_URL)
    monkeypatch.setattr(payments, "_verify_paypal_ipn", verified)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    result = await payments.paypal_ipn_webhook(_Request(body=payload))

    assert result == {"received": True, "processed": False, "reason": "invalid_amount"}
    assert redis.pushed == []


@pytest.mark.asyncio
async def test_closed_intake_blocks_verified_paypal_capture(monkeypatch):
    payload = (
        b"payment_status=Completed&txn_id=txn_gate_closed&mc_gross=15.00&mc_currency=EUR"
        b"&receiver_email=owner%40example.test&custom=developer_support"
    )

    async def verified(_payload):
        return True

    monkeypatch.delenv("PAYMENTS_INTAKE_GATE", raising=False)
    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "owner@example.test")
    monkeypatch.setattr(payments, "_verify_paypal_ipn", verified)

    with pytest.raises(HTTPException) as exc:
        await payments.paypal_ipn_webhook(_Request(body=payload))

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_closed_intake_still_processes_verified_paypal_adjustments(monkeypatch):
    redis = _SuccessRedis()
    await payments._append_payment_record(redis, {
        **_verified_public_record(amount=15.0),
        "method": "paypal",
        "txn_id": "txn_gate_parent",
    })
    payload = (
        b"payment_status=Refunded&txn_id=txn_gate_refund&parent_txn_id=txn_gate_parent"
        b"&mc_gross=-5.00&mc_currency=EUR&receiver_email=owner%40example.test"
    )

    async def verified(_payload):
        return True

    async def fake_get_redis():
        return redis

    monkeypatch.delenv("PAYMENTS_INTAKE_GATE", raising=False)
    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "owner@example.test")
    monkeypatch.setattr(payments, "PAYPAL_IPN_URL", payments.PAYPAL_IPN_PRODUCTION_URL)
    monkeypatch.setattr(payments, "_verify_paypal_ipn", verified)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    result = await payments.paypal_ipn_webhook(_Request(body=payload))

    assert result["processed"] is True
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "10.0"


@pytest.mark.asyncio
async def test_paypal_adjustment_resumes_after_accounting_review_failure(monkeypatch):
    redis = _SuccessRedis()
    await payments._append_payment_record(redis, {
        **_verified_public_record(amount=15.0),
        "method": "paypal",
        "txn_id": "txn_retry_parent",
    })
    txn_key = f"{payments.R_PAYPAL_TXN}txn_retry_refund"
    redis.values[txn_key] = "accounting_review_required"
    payload = (
        b"payment_status=Refunded&txn_id=txn_retry_refund&parent_txn_id=txn_retry_parent"
        b"&mc_gross=-5.00&mc_currency=EUR&receiver_email=owner%40example.test"
    )

    async def verified(_payload):
        return True

    async def fake_get_redis():
        return redis

    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "owner@example.test")
    monkeypatch.setattr(payments, "PAYPAL_IPN_URL", payments.PAYPAL_IPN_PRODUCTION_URL)
    monkeypatch.setattr(payments, "_verify_paypal_ipn", verified)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    result = await payments.paypal_ipn_webhook(_Request(body=payload))

    assert result["processed"] is True
    assert redis.values[txn_key] == "processed"
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "10.0"


@pytest.mark.asyncio
async def test_paypal_processing_claim_returns_retryable_status(monkeypatch):
    redis = _SuccessRedis()
    redis.values[f"{payments.R_PAYPAL_TXN}txn_processing"] = "processing"
    payload = (
        b"payment_status=Refunded&txn_id=txn_processing&parent_txn_id=txn_parent"
        b"&mc_gross=-5.00&mc_currency=EUR&receiver_email=owner%40example.test"
    )

    async def verified(_payload):
        return True

    async def fake_get_redis():
        return redis

    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "owner@example.test")
    monkeypatch.setattr(payments, "PAYPAL_IPN_URL", payments.PAYPAL_IPN_PRODUCTION_URL)
    monkeypatch.setattr(payments, "_verify_paypal_ipn", verified)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    with pytest.raises(HTTPException) as exc:
        await payments.paypal_ipn_webhook(_Request(body=payload))

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_paypal_capture_recovers_after_atomic_record_commit(monkeypatch):
    redis = _SuccessRedis()
    await payments._append_payment_record(redis, {
        **_verified_public_record(amount=15.0),
        "method": "paypal",
        "txn_id": "txn_recovery",
    })
    redis.values[f"{payments.R_PAYPAL_TXN}txn_recovery"] = "accounting_review_required"
    await payments._append_finance_event(redis, {
        "event_id": "paypal:txn_recovery",
        "event_type": "payment_captured",
    })
    payload = (
        b"payment_status=Completed&txn_id=txn_recovery&mc_gross=15.00&mc_currency=EUR"
        b"&receiver_email=owner%40example.test&custom=developer_support"
    )
    allocation_called = False

    async def verified(_payload):
        return True

    async def fake_get_redis():
        return redis

    async def fake_allocate(_amount, _target):
        nonlocal allocation_called
        allocation_called = True
        return {}

    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "owner@example.test")
    monkeypatch.setattr(payments, "PAYPAL_IPN_URL", payments.PAYPAL_IPN_PRODUCTION_URL)
    monkeypatch.setattr(payments, "_verify_paypal_ipn", verified)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    result = await payments.paypal_ipn_webhook(_Request(body=payload))

    assert result == {
        "received": True, "processed": True, "allocation": None, "recovered": True,
    }
    assert allocation_called is False
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "15.0"
    assert redis.values[payments.R_PUBLIC_PAYMENT_COUNT] == "1"
    assert len([item for item in redis.pushed if item[0] == payments.R_PAYMENTS]) == 1
    assert len([item for item in redis.pushed if item[0] == payments.R_FINANCE_EVENTS]) == 1


@pytest.mark.asyncio
async def test_paypal_reversal_and_cancellation_restore_projection_once(monkeypatch):
    redis = _SuccessRedis()
    completed = (
        b"payment_status=Completed&txn_id=txn_original&mc_gross=15.00&mc_currency=EUR"
        b"&receiver_email=owner%40example.test&custom=developer_support"
    )
    reversed_payload = (
        b"payment_status=Reversed&txn_id=txn_reversal&parent_txn_id=txn_original"
        b"&mc_gross=-15.00&mc_currency=EUR&receiver_email=owner%40example.test"
    )
    cancelled = (
        b"payment_status=Canceled_Reversal&txn_id=txn_reversal_cancelled&parent_txn_id=txn_original"
        b"&mc_gross=15.00&mc_currency=EUR&receiver_email=owner%40example.test"
    )

    async def verified(_payload):
        return True

    async def fake_get_redis():
        return redis

    async def fake_allocate(amount, _target):
        return {"server": amount, "domain": 0.0, "reserve": 0.0}

    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "owner@example.test")
    monkeypatch.setattr(payments, "PAYPAL_IPN_URL", payments.PAYPAL_IPN_PRODUCTION_URL)
    monkeypatch.setattr(payments, "_verify_paypal_ipn", verified)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    pending = await payments.paypal_ipn_webhook(_Request(body=reversed_payload))
    assert pending["requires_manual_review"] is True
    assert payments.R_PUBLIC_SERVER_RECEIVED not in redis.values

    await payments.paypal_ipn_webhook(_Request(body=completed))
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "0.0"
    assert redis.values[payments.R_PUBLIC_PAYMENT_COUNT] == "0"
    assert redis.values[payments.R_PAYPAL_DONATIONS] == "0.0"
    assert redis.values[payments.R_PAYPAL_COUNT] == "0"

    await payments.paypal_ipn_webhook(_Request(body=cancelled))
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "15.0"
    assert redis.values[payments.R_PUBLIC_PAYMENT_COUNT] == "1"
    assert redis.values[payments.R_PAYPAL_DONATIONS] == "15.0"
    assert redis.values[payments.R_PAYPAL_COUNT] == "1"


@pytest.mark.asyncio
async def test_paypal_refund_emits_finance_adjustment(monkeypatch):
    redis = _SuccessRedis()
    payload = (
        b"payment_status=Refunded&txn_id=txn_refund&parent_txn_id=txn_donation"
        b"&mc_gross=-15.00&mc_currency=EUR&receiver_email=owner%40example.test"
    )

    async def fake_get_redis():
        return redis

    async def verified(_payload):
        return True

    monkeypatch.setenv("PAYPAL_RECEIVER_EMAIL", "owner@example.test")
    monkeypatch.setattr(payments, "_verify_paypal_ipn", verified)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)

    result = await payments.paypal_ipn_webhook(_Request(body=payload))

    assert result["adjustment_state"] == "refund_reported"
    event = __import__("json").loads(next(
        value for key, value in redis.pushed if key == payments.R_FINANCE_EVENTS
    ))
    assert event["event_type"] == "refunded"
    assert event["amount_cents_reported"] == 1500
