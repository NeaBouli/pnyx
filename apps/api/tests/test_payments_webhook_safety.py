import os
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers import payments


class _Request:
    def __init__(self, body: bytes = b"{}", signature: str = ""):
        self._body = body
        self.headers = {"stripe-signature": signature} if signature else {}

    async def body(self) -> bytes:
        return self._body


class _DuplicateRedis:
    async def exists(self, _key):
        return True

    async def set(self, _key, _value, **_kwargs):
        return None


class _SuccessRedis:
    def __init__(self):
        self.set_calls = []
        self.pushed = []

    async def exists(self, _key):
        return True

    async def set(self, key, value, **kwargs):
        self.set_calls.append((key, value, kwargs))
        return True

    async def rpush(self, key, value):
        self.pushed.append((key, value))


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
        "date": "2026-07-11",
        "amount": 10.0,
        "allocation": {"server": 10.0},
        "method": "stripe",
    }


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
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_duplicate",
                "payment_status": "paid",
                "amount_total": 1000,
                "customer_details": {"email": "donor@example.com"},
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
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_paid",
                "payment_status": "paid",
                "amount_total": 2500,
                "customer_details": {"email": "donor@example.com"},
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
    assert len(redis.pushed) == 1
    key, raw_record = redis.pushed[0]
    assert key == payments.R_PAYMENTS
    record = __import__("json").loads(raw_record)
    assert record["amount"] == 25.0
    assert record["from"] == "donor@example.com"
    assert record["stripe_session"] == "cs_test_paid"
