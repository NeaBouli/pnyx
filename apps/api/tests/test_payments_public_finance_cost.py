"""Public finance and status must use the same funding cost basis."""

import pytest

from routers import payments
from tests.test_payments_webhook_safety import _PublicProjectionRedis


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_monthly_cost", [15.0, 0.0])
@pytest.mark.parametrize("monthly_cost", [10.0, 12.5])
@pytest.mark.parametrize(
    "support_balance, expected_runway",
    [(25.0, 2), (0.0, 0), (-5.0, 0)],
)
async def test_public_finance_runway_matches_status_cost_basis(
    monkeypatch: pytest.MonkeyPatch,
    provider_monthly_cost: float,
    monthly_cost: float,
    support_balance: float,
    expected_runway: int,
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
