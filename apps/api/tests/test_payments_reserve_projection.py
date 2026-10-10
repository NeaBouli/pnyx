"""Reserve-positive donation adjustments using real helpers and in-memory Redis."""

from decimal import Decimal
from typing import Literal, NoReturn

import pytest

from routers import payments
from tests.test_payments_webhook_safety import _SuccessRedis


CATEGORIES = ("server", "domain", "reserve")
ORIGINAL = (5000, 930, 4070)
AFTER_REFUND_25 = (3750, 698, 3052)
EMPTY = (0, 0, 0)
PRIVATE_SERVER_SEED = 7500


@pytest.fixture(autouse=True)
def _fixed_costs_and_no_external_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_client(*_args: object, **_kwargs: object) -> NoReturn:
        pytest.fail("Reserve projection tests require in-memory Redis and no HTTP client", pytrace=False)

    monkeypatch.setattr(payments, "SERVER_COST_MONTHLY", 25.0)
    monkeypatch.setattr(payments, "DOMAIN_COST_YEARLY", 9.30)
    monkeypatch.setattr(payments, "_months_elapsed", lambda _start: 3)
    monkeypatch.setattr(payments.aioredis, "from_url", unexpected_client)
    monkeypatch.setattr(payments.httpx, "AsyncClient", unexpected_client)


def _cents(value: object) -> int:
    return int(Decimal(str(value)).quantize(Decimal("0.01")) * 100)


async def _assert_projection(
    redis: _SuccessRedis, expected: tuple[int, int, int], count: int,
) -> None:
    public_keys = (
        payments.R_PUBLIC_SERVER_RECEIVED, payments.R_PUBLIC_DOMAIN_RECEIVED, payments.R_PUBLIC_RESERVE,
    )
    private_keys = (payments.R_SERVER_RECEIVED, payments.R_DOMAIN_RECEIVED, payments.R_RESERVE)
    public = [_cents(await redis.get(key) or 0) for key in public_keys]
    private = [_cents(await redis.get(key) or 0) for key in private_keys]
    assert tuple(public) == expected
    assert tuple(private) == (expected[0] + PRIVATE_SERVER_SEED, expected[1], expected[2])
    assert int(await redis.get(payments.R_PUBLIC_PAYMENT_COUNT)) == count

    projection = await payments._load_public_support_projection(redis)
    status = await payments.payment_status()
    finance = await payments.public_finance_overview()
    assert _cents(projection["received"]) == sum(expected)
    assert _cents(projection["reserve"]) == expected[2]
    assert _cents(status["server"]["received"]) == expected[0]
    assert _cents(status["domain"]["received"]) == expected[1]
    assert _cents(status["reserve"]) == expected[2]
    assert _cents(status["total_received"]) == sum(expected)
    assert status["payment_count"] == count
    assert finance["spenden_gesamt"] == count
    receipt = status["last_payment"]
    if count == 0:
        assert projection["last_payment"] is None
        assert receipt is None
    else:
        assert receipt is not None
        assert set(receipt) == {"amount", "allocation"}
        assert _cents(receipt["amount"]) == sum(expected)
        assert tuple(_cents(receipt["allocation"][category]) for category in CATEGORIES) == expected


async def _setup(
    monkeypatch: pytest.MonkeyPatch, method: Literal["stripe", "paypal"] = "stripe",
) -> tuple[_SuccessRedis, str]:
    redis = _SuccessRedis()
    redis.values[payments.R_SERVER_RECEIVED] = "75.00"

    async def fake_get_redis() -> _SuccessRedis:
        return redis

    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    allocation = await payments.allocate_donation(100.0, redis)
    assert tuple(_cents(allocation[category]) for category in CATEGORIES) == ORIGINAL
    assert sum(_cents(value) for value in allocation.values()) == 10000
    record: dict[str, object] = {
        "date": "2026-10-10 00:00",
        "amount": 100.0,
        "allocation": allocation,
        "method": method,
        "category": "donation",
        "purpose": "infrastructure_support",
        "currency": "EUR",
        "provider_mode": "live",
        "fulfillment_state": "not_applicable",
        "requires_accounting_review": True,
    }
    if method == "stripe":
        record["stripe_session"] = "cs_dummy"
        reference = "stripe:cs_dummy"
    else:
        record["txn_id"] = "txn_dummy"
        reference = "paypal:txn_dummy"
    await payments._append_payment_record(redis, record)
    await _assert_projection(redis, ORIGINAL, 1)
    return redis, reference


async def _adjust(
    redis: _SuccessRedis, reference: str, amount: int, kind: str, event: str,
) -> dict[str, object]:
    return await payments._apply_public_payment_adjustment(redis, reference, amount, kind, event)


@pytest.mark.asyncio
async def test_stripe_cumulative_refunds_preserve_reserve_cents_and_ignore_replays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis, reference = await _setup(monkeypatch)
    kind = "stripe_refund_cumulative"
    await _adjust(redis, reference, 2500, kind, "evt_dummy_partial")
    await _assert_projection(redis, AFTER_REFUND_25, 1)

    duplicate = await _adjust(redis, reference, 2500, kind, "evt_dummy_partial")
    assert duplicate["reason"] == "duplicate_adjustment"
    await _assert_projection(redis, AFTER_REFUND_25, 1)
    for amount, event in ((2500, "evt_dummy_same_amount"), (500, "evt_dummy_stale")):
        await _adjust(redis, reference, amount, kind, event)
        await _assert_projection(redis, AFTER_REFUND_25, 1)

    await _adjust(redis, reference, 10000, kind, "evt_dummy_full")
    await _assert_projection(redis, EMPTY, 0)
    await _adjust(redis, reference, 2500, kind, "evt_dummy_stale_after_full")
    await _assert_projection(redis, EMPTY, 0)


@pytest.mark.asyncio
async def test_stripe_dispute_won_restores_reserve_after_refund_without_stale_revival(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis, reference = await _setup(monkeypatch)
    await _adjust(redis, reference, 2500, "stripe_refund_cumulative", "evt_dummy_refund")
    await _assert_projection(redis, AFTER_REFUND_25, 1)
    await _adjust(redis, reference, 2000, "stripe_dispute_open", "evt_dummy_open")
    await _assert_projection(redis, (2750, 512, 2238), 1)
    await _adjust(redis, reference, 2000, "stripe_dispute_won", "evt_dummy_won")
    await _assert_projection(redis, AFTER_REFUND_25, 1)

    duplicate = await _adjust(redis, reference, 2000, "stripe_dispute_won", "evt_dummy_won")
    assert duplicate["reason"] == "duplicate_adjustment"
    await _assert_projection(redis, AFTER_REFUND_25, 1)
    stale = await _adjust(redis, reference, 2000, "stripe_dispute_open", "evt_dummy_stale_open")
    assert stale == {"applied": False, "reason": "terminal_dispute_state"}
    await _assert_projection(redis, AFTER_REFUND_25, 1)


@pytest.mark.asyncio
async def test_paypal_refund_deltas_reversal_and_cancellation_preserve_reserve_cents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis, reference = await _setup(monkeypatch, "paypal")
    await _adjust(redis, reference, 1000, "paypal_refund_delta", "txn_dummy_refund_10")
    await _assert_projection(redis, (4500, 837, 3663), 1)
    await _adjust(redis, reference, 1500, "paypal_refund_delta", "txn_dummy_refund_15")
    await _assert_projection(redis, AFTER_REFUND_25, 1)
    duplicate = await _adjust(redis, reference, 1500, "paypal_refund_delta", "txn_dummy_refund_15")
    assert duplicate["reason"] == "duplicate_adjustment"
    await _assert_projection(redis, AFTER_REFUND_25, 1)

    await _adjust(redis, reference, 4000, "paypal_reversal", "txn_dummy_reversal")
    await _assert_projection(redis, (1750, 326, 1424), 1)
    await _adjust(redis, reference, 4000, "paypal_reversal_cancelled", "txn_dummy_cancel")
    await _assert_projection(redis, AFTER_REFUND_25, 1)
    await _adjust(redis, reference, 7500, "paypal_refund_delta", "txn_dummy_refund_rest")
    await _assert_projection(redis, EMPTY, 0)
