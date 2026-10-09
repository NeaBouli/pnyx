"""Donation allocation: surplus beyond the server target and domain need goes to
the reserve, as publicly stated (coordinator decision (a), 2026-10-10, T-658)."""

import pytest

from routers import payments


class _Redis:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


@pytest.fixture(autouse=True)
def _fixed_costs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(payments, "SERVER_COST_MONTHLY", 10.0)
    monkeypatch.setattr(payments, "DOMAIN_COST_YEARLY", 9.30)
    monkeypatch.setattr(payments, "_months_elapsed", lambda _start: 3)


def _redis(server_received: float, domain_received: float) -> _Redis:
    return _Redis({
        payments.R_SERVER_RECEIVED: str(server_received),
        payments.R_DOMAIN_RECEIVED: str(domain_received),
    })


@pytest.mark.asyncio
async def test_surplus_beyond_targets_goes_to_reserve() -> None:
    # Server: 3 months × 10 = 30 cost, received 30 → balance 0, target 20 → need 20.
    # Domain: received 9.30 → no debt. 50 − 20 = 30 surplus.
    allocation = await payments.allocate_donation(50.0, _redis(30.0, 9.30))
    assert allocation == {"server": 20.0, "domain": 0.0, "reserve": 30.0}


@pytest.mark.asyncio
async def test_donation_exactly_at_server_target_leaves_reserve_empty() -> None:
    allocation = await payments.allocate_donation(20.0, _redis(30.0, 9.30))
    assert allocation == {"server": 20.0, "domain": 0.0, "reserve": 0.0}


@pytest.mark.asyncio
async def test_one_cent_above_target_goes_to_reserve() -> None:
    allocation = await payments.allocate_donation(20.01, _redis(30.0, 9.30))
    assert allocation["server"] == 20.0
    assert allocation["domain"] == 0.0
    assert allocation["reserve"] == pytest.approx(0.01)


@pytest.mark.asyncio
async def test_domain_debt_is_paid_before_reserve() -> None:
    # Server already at target (received 50 → balance 20); domain received 0 → debt 9.30.
    allocation = await payments.allocate_donation(15.0, _redis(50.0, 0.0))
    assert allocation["server"] == 0.0
    assert allocation["domain"] == pytest.approx(9.30)
    assert allocation["reserve"] == pytest.approx(5.70)


@pytest.mark.asyncio
async def test_full_targets_send_everything_to_reserve() -> None:
    allocation = await payments.allocate_donation(7.5, _redis(50.0, 9.30))
    assert allocation == {"server": 0.0, "domain": 0.0, "reserve": 7.5}


@pytest.mark.asyncio
async def test_allocation_never_loses_or_creates_money() -> None:
    for amount in (0.01, 5.0, 20.0, 29.3, 100.0):
        allocation = await payments.allocate_donation(amount, _redis(30.0, 0.0))
        assert sum(allocation.values()) == pytest.approx(amount)
        assert all(value >= 0 for value in allocation.values())
