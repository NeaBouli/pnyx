"""Stripe webhook through the real stripe library (no construct_event stub), T-610.

Since stripe 15, ``construct_event`` returns a ``stripe.Event`` that is not a
dict. The handler must convert it before its dict-style access; the stubbed
tests in test_payments_webhook_safety.py cannot catch that.
"""
import hashlib
import hmac
import json
import os
import sys
import time

import pytest
import stripe
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers import payments
from tests.test_payments_webhook_safety import _Request, _SuccessRedis

SECRET = "whsec_t610_test_only"


def _signed(event: dict) -> _Request:
    payload = json.dumps(event, separators=(",", ":"))
    timestamp = int(time.time())
    digest = hmac.new(SECRET.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return _Request(body=payload.encode(), signature=f"t={timestamp},v1={digest}")


def _checkout_event(event_id: str = "evt_t610_paid", amount: int = 2500, livemode: bool = False) -> dict:
    return {
        "id": event_id,
        "object": "event",
        "type": "checkout.session.completed",
        "livemode": livemode,
        "data": {"object": {
            "id": "cs_t610_paid",
            "object": "checkout.session",
            "payment_status": "paid",
            "mode": "payment",
            "currency": "eur",
            "amount_total": amount,
            "payment_intent": "pi_t610_paid",
            "livemode": livemode,
            "metadata": {"payment_purpose": "infrastructure_support"},
        }},
    }


@pytest.fixture(autouse=True)
def _real_stripe(monkeypatch):
    monkeypatch.setenv("PAYMENTS_INTAKE_GATE", "legal_recipient_confirmed")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.setitem(sys.modules, "stripe", stripe)


def test_real_construct_event_returns_a_non_dict_object():
    request = _signed(_checkout_event())
    event = stripe.Webhook.construct_event(request._body, request.headers["stripe-signature"], SECRET)
    assert not isinstance(event, dict)
    with pytest.raises(AttributeError):
        event.get("type")


@pytest.mark.asyncio
async def test_real_signed_checkout_is_processed(monkeypatch):
    redis = _SuccessRedis()

    async def fake_get_redis():
        return redis

    async def fake_allocate(amount, _redis):
        return {"server": amount, "domain": 0.0, "reserve": 0.0}

    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    result = await payments.stripe_webhook(_signed(_checkout_event()))

    assert result == {
        "received": True,
        "processed": True,
        "allocation": {"server": 25.0, "domain": 0.0, "reserve": 0.0},
    }
    record = json.loads(redis.pushed[0][1])
    assert redis.pushed[0][0] == payments.R_PAYMENTS
    assert record["stripe_session"] == "cs_t610_paid"
    assert record["payment_intent"] == "pi_t610_paid"
    assert record["amount"] == 25.0
    finance_event = json.loads(redis.pushed[1][1])
    assert finance_event["event_id"] == "evt_t610_paid"
    assert finance_event["event_type"] == "payment_captured"
    assert finance_event["amount_cents"] == 2500

    # A redelivery of the same signed event stays idempotent.
    duplicate = await payments.stripe_webhook(_signed(_checkout_event()))
    assert duplicate["processed"] is False
    assert len([key for key, _ in redis.pushed if key == payments.R_PAYMENTS]) == 1


@pytest.mark.asyncio
async def test_real_signed_dispute_reaches_adjustment_path(monkeypatch):
    redis = _SuccessRedis()

    async def fake_get(key):
        if key == f"{payments.R_STRIPE_PAYMENT_PREFIX}pi_t610_dispute":
            return "cs_t610_dispute"
        return None

    redis.get = fake_get

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    event = {
        "id": "evt_t610_dispute",
        "object": "event",
        "type": "charge.dispute.created",
        "livemode": False,
        "data": {"object": {
            "id": "dp_t610",
            "object": "dispute",
            "payment_intent": "pi_t610_dispute",
            "currency": "eur",
            "amount": 1500,
            "status": "needs_response",
        }},
    }

    result = await payments.stripe_webhook(_signed(event))

    assert result == {"received": True, "processed": True, "requires_manual_review": False}
    finance_event = json.loads(redis.pushed[0][1])
    assert finance_event["adjustment_state"] == "dispute_open"


@pytest.mark.asyncio
async def test_real_signed_refund_updates_projection(monkeypatch):
    redis = _SuccessRedis()

    async def fake_get_redis():
        return redis

    async def fake_allocate(amount, _target):
        return {"server": amount, "domain": 0.0, "reserve": 0.0}

    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    await payments.stripe_webhook(_signed(_checkout_event("evt_t610_live_paid", 1500, livemode=True)))
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "15.0"

    refund = {
        "id": "evt_t610_refund",
        "object": "event",
        "type": "charge.refunded",
        "livemode": True,
        "data": {"object": {
            "id": "ch_t610",
            "object": "charge",
            "payment_intent": "pi_t610_paid",
            "currency": "eur",
            "amount_refunded": 500,
        }},
    }
    result = await payments.stripe_webhook(_signed(refund))

    assert result["received"] is True
    assert result["processed"] is True
    assert redis.values[payments.R_PUBLIC_SERVER_RECEIVED] == "10.0"


@pytest.mark.asyncio
async def test_real_stripe_rejects_wrong_signature():
    request = _signed(_checkout_event())
    request.headers["stripe-signature"] = request.headers["stripe-signature"].replace("v1=", "v1=00")

    with pytest.raises(HTTPException) as exc:
        await payments.stripe_webhook(request)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid signature"


@pytest.mark.asyncio
async def test_real_signed_lost_dispute_after_partial_refund_reconciles_once(monkeypatch):
    redis = _SuccessRedis()

    async def fake_get_redis():
        return redis

    async def fake_allocate(_amount, _target):
        return {"server": 12.0, "domain": 4.0, "reserve": 4.0}

    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    await payments.stripe_webhook(_signed(_checkout_event("evt_t9081_paid", 2000, livemode=True)))
    refund = {
        "id": "evt_t9081_refund", "object": "event", "type": "charge.refunded", "livemode": True,
        "data": {"object": {"id": "ch_t9081", "object": "charge", "payment_intent": "pi_t610_paid",
                            "currency": "eur", "amount_refunded": 500}},
    }
    await payments.stripe_webhook(_signed(refund))
    buckets = (payments.R_PUBLIC_SERVER_RECEIVED, payments.R_PUBLIC_DOMAIN_RECEIVED, payments.R_PUBLIC_RESERVE,
               payments.R_SERVER_RECEIVED, payments.R_DOMAIN_RECEIVED, payments.R_RESERVE)
    assert [float(redis.values[key]) for key in buckets] == [9.0, 3.0, 3.0, 9.0, 3.0, 3.0]
    assert redis.values[payments.R_PUBLIC_PAYMENT_COUNT] == "1"

    # Lost dispute without a prior charge.dispute.created, for the remaining 15 EUR.
    lost = {
        "id": "evt_t9081_lost", "object": "event", "type": "charge.dispute.closed", "livemode": True,
        "data": {"object": {"id": "dp_t9081", "object": "dispute", "payment_intent": "pi_t610_paid",
                            "currency": "eur", "amount": 1500, "status": "lost"}},
    }
    result = await payments.stripe_webhook(_signed(lost))

    assert result == {"received": True, "processed": True, "requires_manual_review": False}
    assert [float(redis.values[key]) for key in buckets] == [0.0] * 6
    assert redis.values[payments.R_PUBLIC_PAYMENT_COUNT] == "0"
    assert payments.R_PUBLIC_LAST_PAYMENT not in redis.values
    state = json.loads(redis.values[f"{payments.R_PUBLIC_PAYMENT_STATE_PREFIX}stripe:cs_t610_paid"])
    assert (state["refund_cents"], state["dispute_cents"], state["adjusted_cents"]) == (500, 1500, 2000)
    assert state["dispute_terminal"] is True
    assert state["remaining_allocation_cents"] == {"server": 0, "domain": 0, "reserve": 0}
    assert redis.values[f"{payments.R_ADJUSTMENT_STATE_PREFIX}cs_t610_paid"] == "dispute_closed"
    lost_events = [json.loads(raw) for key, raw in redis.pushed
                   if key == payments.R_FINANCE_EVENTS and json.loads(raw)["event_id"] == "evt_t9081_lost"]
    assert [event["adjustment_state"] for event in lost_events] == ["dispute_closed"]

    duplicate = await payments.stripe_webhook(_signed(lost))

    assert duplicate == {"received": True, "processed": False, "duplicate": True}
    assert [float(redis.values[key]) for key in buckets] == [0.0] * 6
    assert redis.values[payments.R_PUBLIC_PAYMENT_COUNT] == "0"
