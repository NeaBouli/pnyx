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

    async def get(self, _key):
        return None

    async def setex(self, key, ttl, value):
        self.set_calls.append((key, value, {"ex": ttl}))

    async def delete(self, key):
        self.set_calls.append((key, None, {"delete": True}))

    async def incrbyfloat(self, _key, _value):
        return 1.0

    async def incr(self, _key):
        return 1


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


def test_public_community_page_keeps_payment_links_paused():
    community = (Path(__file__).parents[3] / "docs" / "community.html").read_text(encoding="utf-8")
    assert "donate.stripe.com" not in community
    assert "paypal.com/paypalme" not in community.lower()
    assert 'id="payment-intake-paused"' in community
    assert "HLR credits are procured privately" in community
    assert "BTC → HLR" not in community
    assert "LTC → HLR" not in community


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
    assert record["requires_accounting_review"] is True
    finance_key, raw_event = redis.pushed[1]
    assert finance_key == payments.R_FINANCE_EVENTS
    finance_event = __import__("json").loads(raw_event)
    assert finance_event["event_id"] == "evt_test_paid"
    assert finance_event["event_type"] == "payment_captured"
    assert finance_event["amount_cents"] == 2500


@pytest.mark.asyncio
async def test_payment_intake_gate_blocks_before_stripe_processing(monkeypatch):
    monkeypatch.delenv("PAYMENTS_INTAKE_GATE", raising=False)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

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

    async def verified(_payload):
        return True

    monkeypatch.setattr(payments, "_verify_paypal_ipn", verified)
    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "allocate_donation", fake_allocate)

    result = await payments.paypal_ipn_webhook(_Request(body=payload))

    assert result["processed"] is True
    record = __import__("json").loads(redis.pushed[0][1])
    assert record["category"] == "donation"
    assert "payer" not in __import__("json").dumps(record).lower()
    assert "person@example.test" not in __import__("json").dumps(redis.pushed)


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
    event = __import__("json").loads(redis.pushed[0][1])
    assert event["event_type"] == "refunded"
    assert event["amount_cents_reported"] == 1500
