import hashlib
import hmac
import json
import os
import sys
from typing import Any

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import finance_export


class _Response:
    def __init__(self, status_code: int, data: Any) -> None:
        self.status_code = status_code
        self._data = data

    def json(self) -> Any:
        return self._data


class _Redis:
    def __init__(self, events: list[str]) -> None:
        self.events = list(events)
        self.lock = None
        self.trim_calls = []

    async def set(self, _key: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool:
        assert nx is True
        assert ex == finance_export.FINANCE_EXPORT_LOCK_SECONDS
        if self.lock is not None:
            return False
        self.lock = value
        return True

    async def lrange(self, _key: str, start: int, end: int) -> list[str]:
        return self.events[start:end + 1]

    async def ltrim(self, _key: str, start: int, end: int) -> None:
        self.trim_calls.append((start, end))
        self.events = self.events[start:]

    async def eval(self, _script: str, _keys: int, _key: str, token: str) -> int:
        if self.lock == token:
            self.lock = None
            return 1
        return 0


def _capture_event() -> str:
    return json.dumps({
        "event_id": "evt_test_capture",
        "event_type": "payment_captured",
        "occurred_at": "2026-07-13T00:00:00+00:00",
        "provider": "stripe",
        "provider_reference": "cs_test_private",
        "payment_reference": "pi_test_private",
        "purpose": "infrastructure_support",
        "category": "donation",
        "amount_cents": 500,
        "currency": "EUR",
        "fulfillment_state": "not_applicable",
    })


@pytest.fixture(autouse=True)
def _closed_export(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FINANCE_EXPORT_ENABLED", raising=False)
    monkeypatch.delenv("FINANCE_EXPORT_URL", raising=False)
    monkeypatch.delenv("FINANCE_EXPORT_SECRET", raising=False)


@pytest.mark.asyncio
async def test_export_is_default_off_before_queue_or_network_access() -> None:
    class NoAccessRedis:
        def __getattr__(self, _name: str) -> Any:
            raise AssertionError("Redis must not be accessed while export is disabled")

    async def no_post(_url: str, _headers: dict[str, str], _body: bytes) -> _Response:
        raise AssertionError("Network must not be accessed while export is disabled")

    result = await finance_export.export_pending_finance_events(NoAccessRedis(), post=no_post)

    assert result == finance_export.FinanceExportResult(status="disabled")


@pytest.mark.asyncio
async def test_successful_export_is_signed_pii_free_and_trimmed_after_exact_ack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "x" * 32
    redis = _Redis([_capture_event()])
    captured: dict[str, Any] = {}
    monkeypatch.setenv("FINANCE_EXPORT_ENABLED", "true")
    monkeypatch.setenv("FINANCE_EXPORT_URL", "https://private.example.test/api/finance/ingest")
    monkeypatch.setenv("FINANCE_EXPORT_SECRET", secret)

    async def post(url: str, headers: dict[str, str], body: bytes) -> _Response:
        captured.update(url=url, headers=headers, body=body)
        payload = json.loads(body)
        return _Response(200, {"ok": True, "acceptedIds": [payload["records"][0]["id"]]})

    result = await finance_export.export_pending_finance_events(redis, post=post, now_ms=1_720_000_000_000)

    assert result == finance_export.FinanceExportResult(status="exported", exported=1)
    assert redis.events == []
    assert redis.trim_calls == [(1, -1)]
    payload = json.loads(captured["body"])
    record = payload["records"][0]
    assert record["kind"] == "donation"
    assert record["fields"]["considerationProvided"] is False
    assert record["fields"]["requiresManualReview"] is True
    assert record["fields"]["grossAmountMinor"] == 500
    assert "reportedAmountMinor" not in record["fields"]
    serialized = json.dumps(payload).lower()
    assert "customer" not in serialized
    assert "email" not in serialized
    assert "cs_test_private" not in serialized
    assert "pi_test_private" not in serialized
    expected_signature = hmac.new(
        secret.encode(),
        b"1720000000000." + captured["body"],
        hashlib.sha256,
    ).hexdigest()
    assert captured["headers"]["x-vlabs-signature"] == expected_signature
    assert captured["headers"]["x-vlabs-source"] == "ekklesia"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,data", [(503, {}), (200, {"ok": True, "acceptedIds": []})])
async def test_receiver_failure_or_inexact_ack_preserves_queue(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    data: dict[str, Any],
) -> None:
    original = _capture_event()
    redis = _Redis([original])
    monkeypatch.setenv("FINANCE_EXPORT_ENABLED", "true")
    monkeypatch.setenv("FINANCE_EXPORT_URL", "https://private.example.test/api/finance/ingest")
    monkeypatch.setenv("FINANCE_EXPORT_SECRET", "x" * 32)

    async def post(_url: str, _headers: dict[str, str], _body: bytes) -> _Response:
        return _Response(status, data)

    with pytest.raises(finance_export.FinanceExportError):
        await finance_export.export_pending_finance_events(redis, post=post)

    assert redis.events == [original]
    assert redis.trim_calls == []
    assert redis.lock is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://private.example.test/api/finance/ingest",
        "https://private.example.test/wrong",
        "https://user:password@private.example.test/api/finance/ingest",
        "https://private.example.test/api/finance/ingest?debug=true",
    ],
)
async def test_invalid_receiver_url_fails_before_redis_or_network(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
) -> None:
    monkeypatch.setenv("FINANCE_EXPORT_ENABLED", "true")
    monkeypatch.setenv("FINANCE_EXPORT_URL", url)
    monkeypatch.setenv("FINANCE_EXPORT_SECRET", "x" * 32)

    with pytest.raises(finance_export.FinanceExportError, match="finance_export_url_invalid"):
        await finance_export.export_pending_finance_events(object())


@pytest.mark.asyncio
async def test_adjustment_uses_hashed_references_and_never_becomes_donation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adjustment = json.dumps({
        "event_id": "evt_test_refund",
        "event_type": "charge.refunded",
        "occurred_at": "2026-07-13T00:00:00+00:00",
        "provider": "stripe",
        "provider_reference": "cs_test_private",
        "payment_reference": "pi_test_private",
        "amount_cents_reported": 500,
        "currency": "EUR",
        "adjustment_state": "refund_reported",
    })
    redis = _Redis([adjustment])
    monkeypatch.setenv("FINANCE_EXPORT_ENABLED", "true")
    monkeypatch.setenv("FINANCE_EXPORT_URL", "https://private.example.test/api/finance/ingest")
    monkeypatch.setenv("FINANCE_EXPORT_SECRET", "x" * 32)

    async def post(_url: str, _headers: dict[str, str], body: bytes) -> _Response:
        record = json.loads(body)["records"][0]
        assert record["kind"] == "adjustment"
        assert record["fields"]["reportedAmountMinor"] == 500
        assert record["fields"]["amountBasis"] == "cumulative_refunded"
        assert record["fields"]["requiresManualReview"] is True
        assert record["fields"]["providerReferenceHash"] == hashlib.sha256(b"cs_test_private").hexdigest()
        assert "cs_test_private" not in json.dumps(record)
        return _Response(200, {"ok": True, "acceptedIds": [record["id"]]})

    result = await finance_export.export_pending_finance_events(redis, post=post)

    assert result.exported == 1


@pytest.mark.asyncio
async def test_malformed_queue_event_is_retained(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _Redis(["not-json"])
    monkeypatch.setenv("FINANCE_EXPORT_ENABLED", "true")
    monkeypatch.setenv("FINANCE_EXPORT_URL", "https://private.example.test/api/finance/ingest")
    monkeypatch.setenv("FINANCE_EXPORT_SECRET", "x" * 32)

    with pytest.raises(finance_export.FinanceExportError, match="finance_event_invalid_json"):
        await finance_export.export_pending_finance_events(redis)

    assert redis.events == ["not-json"]
    assert redis.lock is None
