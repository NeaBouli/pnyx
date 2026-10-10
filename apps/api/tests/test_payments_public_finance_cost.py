"""Public finance and status must use the same funding cost basis."""

import runpy

import pytest

from routers import payments
from tests.test_payments_webhook_safety import _PublicProjectionRedis, _SuccessRedis


@pytest.fixture(autouse=True)
def _block_external_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_client(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Cost tests must use only in-memory Redis and no provider client", pytrace=False)

    monkeypatch.setattr(payments.aioredis, "from_url", unexpected_client)
    monkeypatch.setattr(payments.httpx, "AsyncClient", unexpected_client)


@pytest.mark.parametrize("override, expected", [(None, 25.0), ("15.00", 15.0), ("0", 0.0)])
def test_hetzner_monthly_default_and_explicit_overrides(
    monkeypatch: pytest.MonkeyPatch, override: str | None, expected: float,
) -> None:
    if override is None:
        monkeypatch.delenv("HETZNER_MONTHLY_COST", raising=False)
    else:
        monkeypatch.setenv("HETZNER_MONTHLY_COST", override)
    # Import-time configuration from controlled test values, never a live env.
    config = runpy.run_path(payments.__file__)
    assert config["HETZNER_MONTHLY"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_monthly_cost", [25.0, 15.0, 0.0])
@pytest.mark.parametrize("monthly_cost, expected_positive_runway", [(25.0, 1), (12.5, 2)])
@pytest.mark.parametrize("support_balance", [25.0, 0.0, -5.0])
async def test_public_finance_runway_matches_status_cost_basis(
    monkeypatch: pytest.MonkeyPatch,
    provider_monthly_cost: float,
    monthly_cost: float,
    support_balance: float,
    expected_positive_runway: int,
) -> None:
    months_elapsed = 3
    server_received = months_elapsed * monthly_cost + support_balance
    allocation = {"server": server_received, "domain": 0.0, "reserve": 0.0}
    redis = _PublicProjectionRedis(
        server=str(server_received),
        domain="9.30",
        reserve="15.00",
        count="3",
        last={
            "amount": server_received,
            "allocation": allocation,
            "from": "donor@example.invalid",
            "stripe_session": "cs_fixture_private",
            "paypal_txn_id": "txn_fixture_private",
        },
    )
    redis.values["hlr:hlrlookupcom:used"] = "49"

    async def fake_get_redis() -> _PublicProjectionRedis:
        return redis

    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "_months_elapsed", lambda _start: months_elapsed)
    monkeypatch.setattr(payments, "SERVER_COST_MONTHLY", monthly_cost)
    monkeypatch.setattr(payments, "HETZNER_MONTHLY", provider_monthly_cost)

    status = await payments.payment_status()
    finance = await payments.public_finance_overview()
    expected_runway = expected_positive_runway if support_balance > 0 else 0

    assert status["server"]["cost_monthly"] == monthly_cost
    assert status["server"]["cost_total"] == months_elapsed * monthly_cost
    assert status["server"]["balance"] == support_balance
    assert status["last_payment"] == {"amount": server_received, "allocation": allocation}
    assert finance == {
        "server_gedeckt_monate": expected_runway,
        "hlr_verifikationen_moeglich": 2450,
        "spenden_gesamt": status["payment_count"],
        "transparenz": "Alle Einnahmen und Ausgaben sind oeffentlich einsehbar auf community.html",
    }


@pytest.mark.asyncio
async def test_default_server_cost_is_25_in_status_and_public_finance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = _PublicProjectionRedis(server="100.00", domain="9.30", reserve="0.00", count="1")

    async def fake_get_redis() -> _PublicProjectionRedis:
        return redis

    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)
    monkeypatch.setattr(payments, "_months_elapsed", lambda _start: 3)
    monkeypatch.setattr(payments, "HETZNER_MONTHLY", 15.0)

    # Leave SERVER_COST_MONTHLY unchanged: this verifies the product default.
    status = await payments.payment_status()
    finance = await payments.public_finance_overview()

    assert status["server"] == {
        "received": 100.0,
        "cost_total": 75.0,
        "balance": 25.0,
        "cost_monthly": 25.0,
        "months_elapsed": 3,
    }
    assert finance["server_gedeckt_monate"] == 1
    assert status["domain"]["cost_yearly"] == 9.3


@pytest.mark.asyncio
@pytest.mark.parametrize("months_elapsed", [1, 3])
@pytest.mark.parametrize(
    "server_balance, donation, expected_server, expected_domain",
    [(0.0, 50.0, 50.0, 0.0), (49.0, 10.0, 1.0, 9.0), (50.0, 9.3, 0.0, 9.3)],
)
async def test_default_allocation_fills_a_50_eur_two_month_server_target(
    monkeypatch: pytest.MonkeyPatch,
    months_elapsed: int,
    server_balance: float,
    donation: float,
    expected_server: float,
    expected_domain: float,
) -> None:
    redis = _SuccessRedis()
    redis.values[payments.R_SERVER_RECEIVED] = str(months_elapsed * 25.0 + server_balance)
    monkeypatch.setattr(payments, "_months_elapsed", lambda _start: months_elapsed)

    allocation = await payments.allocate_donation(donation, redis)

    assert allocation == pytest.approx({
        "server": expected_server,
        "domain": expected_domain,
        "reserve": 0.0,
    })
    assert sum(allocation.values()) == pytest.approx(donation)
    assert redis.set_calls == []
