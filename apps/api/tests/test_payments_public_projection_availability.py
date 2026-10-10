"""Invalid public funding snapshots must not masquerade as verified zeros."""

from collections.abc import Awaitable, Callable
from typing import NoReturn

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from routers import payments


VALID = ("100.00", "9.30", "5.00", "1", None)
INVALID = [
    pytest.param((None, "9.30", "5.00", "1", None), id="missing-server"),
    pytest.param(("100.00", None, "5.00", "1", None), id="missing-domain"),
    pytest.param(("100.00", "9.30", None, "1", None), id="missing-reserve"),
    pytest.param(("bad", "9.30", "5.00", "1", None), id="invalid-server"),
    pytest.param(("100.00", "NaN", "5.00", "1", None), id="nan-domain"),
    pytest.param(("100.00", "9.30", "Infinity", "1", None), id="infinite-reserve"),
    pytest.param(("-1.00", "9.30", "5.00", "1", None), id="negative-total"),
    pytest.param(("100.00", "9.30", "5.00", None, None), id="missing-count"),
    pytest.param(("100.00", "9.30", "5.00", "bad", None), id="invalid-count"),
    pytest.param(("100.00", "9.30", "5.00", "1.5", None), id="fractional-count"),
    pytest.param(("100.00", "9.30", "5.00", "-1", None), id="negative-count"),
    pytest.param((None, None, None, "1", None), id="missing-totals-positive-count"),
    pytest.param((None, None, None, "bad", None), id="missing-totals-invalid-count"),
    pytest.param((None, None, None, "-1", None), id="missing-totals-negative-count"),
    pytest.param((None, None, None, None, '{"amount":25}'), id="missing-totals-receipt"),
    pytest.param((None, None, None, "0", "bad-json"), id="missing-totals-malformed-receipt"),
]
EMPTY = [
    pytest.param((None, None, None, None, None), id="untouched"),
    pytest.param((None, None, None, "0", None), id="untouched-zero-count"),
    pytest.param(("0", "0.00", "0", "0", None), id="verified-zero"),
]


class ProjectionRedis:
    def __init__(self, snapshot: tuple[object, ...]) -> None:
        self.snapshot = snapshot

    async def mget(self, *keys: str) -> list[object]:
        assert keys == (
            payments.R_PUBLIC_SERVER_RECEIVED, payments.R_PUBLIC_DOMAIN_RECEIVED,
            payments.R_PUBLIC_RESERVE, payments.R_PUBLIC_PAYMENT_COUNT,
            payments.R_PUBLIC_LAST_PAYMENT,
        )
        return list(self.snapshot)

    async def get(self, key: str) -> str:
        assert key == "hlr:hlrlookupcom:used"
        return "0"


@pytest.fixture(autouse=True)
def no_external_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_client(*_args: object, **_kwargs: object) -> NoReturn:
        pytest.fail("Availability tests use only mocked Redis and in-process HTTP", pytrace=False)

    monkeypatch.setattr(payments.aioredis, "from_url", unexpected_client)
    monkeypatch.setattr(payments.httpx, "AsyncClient", unexpected_client)
    monkeypatch.setattr(payments, "_months_elapsed", lambda _start: 3)


def install_snapshot(monkeypatch: pytest.MonkeyPatch, snapshot: tuple[object, ...]) -> None:
    async def fake_get_redis() -> ProjectionRedis:
        return ProjectionRedis(snapshot)

    monkeypatch.setattr(payments, "_get_redis", fake_get_redis)


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", [payments.payment_status, payments.public_finance_overview])
@pytest.mark.parametrize("snapshot", INVALID)
async def test_invalid_projection_returns_503_without_financial_values(
    monkeypatch: pytest.MonkeyPatch, endpoint: Callable[[], Awaitable[dict]],
    snapshot: tuple[object, ...],
) -> None:
    install_snapshot(monkeypatch, snapshot)
    with pytest.raises(HTTPException) as raised:
        await endpoint()
    assert raised.value.status_code == 503
    assert raised.value.detail == "Public funding data is currently unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize("snapshot", EMPTY)
async def test_legitimately_empty_projection_is_available_zero(
    monkeypatch: pytest.MonkeyPatch, snapshot: tuple[object, ...],
) -> None:
    install_snapshot(monkeypatch, snapshot)
    status = await payments.payment_status()
    finance = await payments.public_finance_overview()
    assert status["available"] is True
    assert finance["available"] is True
    assert status["total_received"] == status["reserve"] == status["payment_count"] == 0
    assert status["server"]["received"] == status["domain"]["received"] == 0
    assert status["last_payment"] is None
    assert finance["spenden_gesamt"] == 0


@pytest.mark.asyncio
async def test_valid_projection_preserves_values_and_announces_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_snapshot(monkeypatch, VALID)
    status = await payments.payment_status()
    finance = await payments.public_finance_overview()
    assert status["available"] is finance["available"] is True
    assert status["server"]["received"] == 100
    assert status["server"]["balance"] == 25
    assert status["domain"]["received"] == 9.3
    assert status["reserve"] == 5
    assert status["total_received"] == 114.3
    assert status["payment_count"] == finance["spenden_gesamt"] == 1


@pytest.mark.parametrize("path", ["/api/v1/payments/status", "/api/v1/payments/public/finance"])
@pytest.mark.parametrize("snapshot", [VALID, (None,) * 5, (None, "9.30", "5", "1", None)])
def test_actual_public_routes_expose_availability_or_generic_503(
    monkeypatch: pytest.MonkeyPatch, path: str, snapshot: tuple[object, ...],
) -> None:
    install_snapshot(monkeypatch, snapshot)
    app = FastAPI()
    app.include_router(payments.router)
    with TestClient(app) as client:
        response = client.get(path)
    if snapshot[0] is None and snapshot[1] is not None:
        assert response.status_code == 503
        assert response.json() == {"detail": "Public funding data is currently unavailable"}
    else:
        assert response.status_code == 200
        assert response.json()["available"] is True
