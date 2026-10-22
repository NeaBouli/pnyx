"""Stripe webhook through the real stripe library (no construct_event stub), T-610.

Since stripe 15, ``construct_event`` returns a ``stripe.Event`` that is not a
dict. The handler must convert it before its dict-style access; the stubbed
tests in test_payments_webhook_safety.py cannot catch that.
"""
import hashlib
import hmac
import json
import logging
import os
import sys
import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import stripe
from fastapi import FastAPI, HTTPException

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
            "metadata": {"source": "ekklesia", "payment_purpose": "infrastructure_support"},
        }},
    }


@pytest.fixture(autouse=True)
def _real_stripe(monkeypatch):
    monkeypatch.setenv("PAYMENTS_INTAKE_GATE", "legal_recipient_confirmed")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.delenv("STRIPE_EKKLESIA_PAYMENT_LINKS", raising=False)
    monkeypatch.setitem(sys.modules, "stripe", stripe)


@pytest.fixture
async def webhook_client() -> AsyncIterator[httpx.AsyncClient]:
    app = FastAPI()
    app.include_router(payments.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.parametrize("intake_open", [False, True])
@pytest.mark.parametrize("allowlist", [None, "", " , , ", " , plink_ours , , plink_also_ours, "])
@pytest.mark.parametrize("metadata,payment_link", [
    (None, None),
    ({}, ""),
    ({"payment_purpose": "infrastructure_support"}, "plink_foreign"),
    ({"payment_purpose": "developer_support"}, {"id": "plink_foreign"}),
    ({"source": "other", "payment_purpose": "infrastructure_support"}, "plink_foreign"),
    ({"source": "Ekklesia", "payment_purpose": "developer_support"}, "plink_foreign"),
    ({"source": "", "payment_purpose": "infrastructure_support"}, None),
    pytest.param({"source": " ekklesia"}, None, id="leading-space"),
    pytest.param({"source": "ekklesia "}, None, id="trailing-space"),
    pytest.param({"source": "ekklesia\u200b"}, None, id="zero-width-space"),
    pytest.param({"source": "\uff45\uff4b\uff4b\uff4c\uff45\uff53\uff49\uff41"}, None, id="full-width"),
    pytest.param({"source": "\u0435kklesia"}, None, id="cyrillic-lookalike"),
    pytest.param("ekklesia", None, id="string-metadata"),
    pytest.param([{"source": "ekklesia"}], None, id="list-metadata"),
    pytest.param(1, None, id="numeric-metadata"),
    pytest.param(True, None, id="boolean-metadata"),
    pytest.param({"source": {"source": "ekklesia"}}, None, id="object-source"),
    pytest.param({"source": ["ekklesia"]}, None, id="list-source"),
    pytest.param({"nested": {"source": "ekklesia"}}, None, id="nested-source"),
    pytest.param({}, {"id": "plink_foreign", "object": "payment_link"}, id="expanded-unlisted-link"),
    pytest.param({}, {"id": " plink_ours "}, id="expanded-link-id-with-spaces"),
    pytest.param({}, {"id": {"id": "plink_ours"}}, id="nested-link-id"),
    pytest.param({}, {"id": ["plink_ours"]}, id="list-link-id"),
    pytest.param({}, {"id": ""}, id="empty-link-id"),
])
async def test_foreign_signed_checkout_is_ignored_before_intake_and_storage(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    webhook_client: httpx.AsyncClient,
    intake_open: bool,
    allowlist: str | None,
    metadata: object,
    payment_link: str | dict | None,
) -> None:
    monkeypatch.setenv("PAYMENTS_INTAKE_GATE", "legal_recipient_confirmed" if intake_open else "")
    if allowlist is not None:
        monkeypatch.setenv("STRIPE_EKKLESIA_PAYMENT_LINKS", allowlist)
    event = _checkout_event(livemode=True)
    session = event["data"]["object"]
    session["payment_link"] = payment_link
    session["customer_details"] = {"email": "foreign@example.invalid"}
    session["metadata"] = metadata
    get_redis = AsyncMock(side_effect=AssertionError("foreign checkout accessed storage"))
    intake = Mock(side_effect=AssertionError("foreign checkout reached intake"))
    monkeypatch.setattr(payments, "_get_redis", get_redis)
    monkeypatch.setattr(payments, "_payment_intake_enabled", intake)
    caplog.set_level(logging.INFO, logger=payments.__name__)
    request = _signed(event)

    response = await webhook_client.post(
        "/api/v1/payments/webhook", content=request._body, headers=request.headers
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored_foreign"}
    get_redis.assert_not_called()
    intake.assert_not_called()
    assert [record.getMessage() for record in caplog.records if record.name == payments.__name__] == [
        "[MOD-18] Stripe webhook ignored_foreign count=1"
    ]


async def test_foreign_checkout_still_requires_a_valid_signature(
    monkeypatch: pytest.MonkeyPatch, webhook_client: httpx.AsyncClient,
) -> None:
    event = _checkout_event()
    event["data"]["object"]["metadata"] = {"source": "other"}
    request = _signed(event)
    request.headers["stripe-signature"] = request.headers["stripe-signature"].replace("v1=", "v1=00")
    ownership = Mock(side_effect=AssertionError("unverified event reached ownership check"))
    get_redis = AsyncMock(side_effect=AssertionError("unverified event accessed storage"))
    monkeypatch.setattr(payments, "_stripe_checkout_is_ours", ownership)
    monkeypatch.setattr(payments, "_get_redis", get_redis)

    response = await webhook_client.post(
        "/api/v1/payments/webhook", content=request._body, headers=request.headers
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid signature"}
    ownership.assert_not_called()
    get_redis.assert_not_called()


@pytest.mark.parametrize("intake_open", [False, True])
@pytest.mark.parametrize("source,payment_link,allowlist", [
    ("ekklesia", None, None),
    ("ekklesia", None, ""),
    ("ekklesia", None, " , , "),
    (None, "plink_ours", " , plink_other, plink_ours , ,"),
    ("other", "plink_ours", "plink_ours"),
    (None, {"id": "plink_ours", "object": "payment_link"}, "plink_ours"),
    (None, {"id": "plink_ours", "object": "payment_link"}, " , plink_other, plink_ours , ,"),
])
async def test_owned_signed_checkout_preserves_intake_behavior(
    monkeypatch: pytest.MonkeyPatch,
    webhook_client: httpx.AsyncClient,
    intake_open: bool,
    source: str | None,
    payment_link: str | dict | None,
    allowlist: str | None,
) -> None:
    monkeypatch.setenv("PAYMENTS_INTAKE_GATE", "legal_recipient_confirmed" if intake_open else "")
    if allowlist is not None:
        monkeypatch.setenv("STRIPE_EKKLESIA_PAYMENT_LINKS", allowlist)
    event = _checkout_event()
    session = event["data"]["object"]
    session["metadata"] = {"payment_purpose": "infrastructure_support"}
    if source is not None:
        session["metadata"]["source"] = source
    session["payment_link"] = payment_link
    redis = _SuccessRedis()
    get_redis = AsyncMock(return_value=redis)
    monkeypatch.setattr(payments, "_get_redis", get_redis)
    request = _signed(event)

    response = await webhook_client.post(
        "/api/v1/payments/webhook", content=request._body, headers=request.headers
    )

    if intake_open:
        assert response.status_code == 200
        assert response.json()["processed"] is True
        assert len([key for key, _ in redis.pushed if key == payments.R_PAYMENTS]) == 1
        assert redis.values[f"{payments.R_STRIPE_OWNED_PAYMENT_PREFIX}pi_t610_paid"] == "cs_t610_paid"
        assert f"{payments.R_STRIPE_PAYMENT_PREFIX}pi_t610_paid" not in redis.values
    else:
        assert response.status_code == 503
        assert response.json() == {"detail": "Payment intake is awaiting legal recipient approval"}
        get_redis.assert_not_called()
        assert redis.set_calls == []
        assert redis.pushed == []


@pytest.mark.parametrize("allowlist", [None, "", " , , "])
@pytest.mark.parametrize("payment_link", ["plink_ours", {"id": "plink_ours", "object": "payment_link"}])
async def test_unconfigured_payment_link_is_ignored_before_intake_and_storage(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    webhook_client: httpx.AsyncClient,
    allowlist: str | None,
    payment_link: str | dict,
) -> None:
    if allowlist is not None:
        monkeypatch.setenv("STRIPE_EKKLESIA_PAYMENT_LINKS", allowlist)
    event = _checkout_event(livemode=True)
    event["data"]["object"]["metadata"].pop("source")
    event["data"]["object"]["payment_link"] = payment_link
    get_redis = AsyncMock(side_effect=AssertionError("checkout accessed storage"))
    intake = Mock(side_effect=AssertionError("checkout reached intake"))
    monkeypatch.setattr(payments, "_get_redis", get_redis)
    monkeypatch.setattr(payments, "_payment_intake_enabled", intake)
    caplog.set_level(logging.INFO, logger=payments.__name__)
    request = _signed(event)

    response = await webhook_client.post(
        "/api/v1/payments/webhook", content=request._body, headers=request.headers
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored_foreign"}
    get_redis.assert_not_called()
    intake.assert_not_called()
    assert [record.getMessage() for record in caplog.records if record.name == payments.__name__] == [
        "[MOD-18] Stripe webhook ignored_foreign count=1"
    ]


@pytest.mark.parametrize("event_type", [
    "charge.refunded", "charge.dispute.created", "charge.dispute.closed",
])
@pytest.mark.parametrize("claim_state", [None, "processing", "processed", "pending_payment", "accounting_review_required"])
@pytest.mark.parametrize("owned_mapping", [None, "", "invalid_session"])
async def test_legacy_signed_adjustment_is_ignored_without_claim_or_writes(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    webhook_client: httpx.AsyncClient,
    event_type: str,
    claim_state: str | None,
    owned_mapping: str | None,
) -> None:
    redis = _SuccessRedis()
    # Older captures could have a recognized purpose without an ownership check.
    await payments._append_payment_record(redis, {
        "date": "2026-10-01 12:00", "amount": 15.0, "currency": "EUR",
        "allocation": {"server": 15.0, "domain": 0.0, "reserve": 0.0},
        "method": "stripe", "purpose": "infrastructure_support", "category": "donation",
        "provider_mode": "live", "fulfillment_state": "not_applicable",
        "requires_accounting_review": True,
        "stripe_session": "cs_legacy", "payment_intent": "pi_legacy",
    })
    legacy_key = f"{payments.R_STRIPE_PAYMENT_PREFIX}pi_legacy"
    owned_key = f"{payments.R_STRIPE_OWNED_PAYMENT_PREFIX}pi_legacy"
    redis.values[legacy_key] = "cs_legacy"
    if owned_mapping is not None:
        redis.values[owned_key] = owned_mapping
    if claim_state is not None:
        redis.values[f"{payments.R_STRIPE_EVENT_PREFIX}evt_legacy_adjustment"] = claim_state
    before_values, before_pushed = redis.values.copy(), redis.pushed.copy()
    redis.set_calls.clear()
    reads = []

    async def mapping_only_get(key):
        reads.append(key)
        assert key in {legacy_key, owned_key}
        return redis.values.get(key)

    redis.get = mapping_only_get
    intake = Mock(side_effect=AssertionError("legacy adjustment reached intake"))
    monkeypatch.setattr(payments, "_get_redis", AsyncMock(return_value=redis))
    monkeypatch.setattr(payments, "_payment_intake_enabled", intake)
    caplog.set_level(logging.INFO, logger=payments.__name__)
    request = _signed({
        "id": "evt_legacy_adjustment", "object": "event", "type": event_type, "livemode": True,
        "data": {"object": {
            "id": "ch_legacy", "payment_intent": "pi_legacy", "currency": "eur",
            "amount_refunded": 500, "amount": 500, "status": "won",
            "metadata": {"source": "ekklesia"},
            "billing_details": {"email": "legacy@example.invalid"},
        }},
    })

    response = await webhook_client.post(
        "/api/v1/payments/webhook", content=request._body, headers=request.headers
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored_foreign"}
    assert reads == [owned_key, legacy_key]
    intake.assert_not_called()
    assert redis.values == before_values
    assert redis.pushed == before_pushed
    assert redis.set_calls == []
    assert [record.getMessage() for record in caplog.records if record.name == payments.__name__] == [
        "[MOD-18] Stripe webhook ignored_foreign legacy_mapping count=1"
    ]


@pytest.mark.parametrize("intake_open", [False, True])
@pytest.mark.parametrize("event_type", [
    "charge.refunded", "charge.dispute.created", "charge.dispute.closed",
])
@pytest.mark.parametrize("payment_intent,currency", [
    ("pi_foreign", "eur"), ("pi_foreign", "usd"), (None, "eur"),
])
async def test_foreign_signed_adjustment_has_no_writes(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    webhook_client: httpx.AsyncClient,
    intake_open: bool,
    event_type: str,
    payment_intent: str | None,
    currency: str,
) -> None:
    monkeypatch.setenv("PAYMENTS_INTAKE_GATE", "legal_recipient_confirmed" if intake_open else "")
    # Adjustment metadata cannot substitute for a mapping with ownership provenance.
    monkeypatch.setenv("STRIPE_EKKLESIA_PAYMENT_LINKS", "plink_ours")
    event = {
        "id": "evt_foreign_adjustment", "object": "event", "type": event_type,
        "livemode": True,
        "data": {"object": {
            "id": "ch_foreign", "payment_intent": payment_intent,
            "currency": currency, "amount_refunded": 500, "amount": 500,
            "metadata": {"source": "ekklesia"}, "payment_link": "plink_ours",
            "billing_details": {"email": "foreign@example.invalid"},
        }},
    }
    redis = _SuccessRedis()
    # Even an old event claim cannot authorize a foreign adjustment.
    redis.values[f"{payments.R_STRIPE_EVENT_PREFIX}evt_foreign_adjustment"] = "processing"
    before = redis.values.copy()
    get_redis = AsyncMock(return_value=redis)
    mapping_get = AsyncMock(wraps=redis.get)
    redis.get = mapping_get
    intake = Mock(side_effect=AssertionError("adjustment reached intake"))
    monkeypatch.setattr(payments, "_get_redis", get_redis)
    monkeypatch.setattr(payments, "_payment_intake_enabled", intake)
    caplog.set_level(logging.INFO, logger=payments.__name__)
    request = _signed(event)

    response = await webhook_client.post(
        "/api/v1/payments/webhook", content=request._body, headers=request.headers
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored_foreign"}
    intake.assert_not_called()
    if payment_intent is None:
        get_redis.assert_not_called()
        mapping_get.assert_not_called()
    else:
        assert [call.args for call in mapping_get.call_args_list] == [
            (f"{payments.R_STRIPE_OWNED_PAYMENT_PREFIX}{payment_intent}",),
            (f"{payments.R_STRIPE_PAYMENT_PREFIX}{payment_intent}",),
        ]
    assert redis.values == before
    assert redis.set_calls == []
    assert redis.pushed == []
    assert [record.getMessage() for record in caplog.records if record.name == payments.__name__] == [
        "[MOD-18] Stripe webhook ignored_foreign count=1"
    ]


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
        if key == f"{payments.R_STRIPE_OWNED_PAYMENT_PREFIX}pi_t610_dispute":
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
