"""Fail-closed, PII-free export of payment events to the private finance receiver."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx


FINANCE_EVENTS_KEY = "payments:finance_events"
FINANCE_DEAD_LETTER_KEY = "payments:finance_events:dead_letter"
FINANCE_EXPORT_LOCK_KEY = "payments:finance_export_lock"
FINANCE_EXPORT_FAILURE_PREFIX = "payments:finance_export_failure:"
FINANCE_EXPORT_SOURCE = "ekklesia"
FINANCE_EXPORT_SCHEMA = "vlabs.finance.ingest.v1"
FINANCE_EXPORT_BATCH_SIZE = 25
FINANCE_EXPORT_LOCK_SECONDS = 120
MAX_FINANCE_AMOUNT_MINOR = 1_000_000
FINANCE_EXPORT_QUARANTINE_THRESHOLD = 3
FINANCE_EXPORT_FAILURE_TTL_SECONDS = 7 * 24 * 60 * 60

PostFunction = Callable[[str, dict[str, str], bytes], Awaitable[Any]]


@dataclass(frozen=True)
class FinanceExportResult:
    status: str
    exported: int = 0
    quarantined: int = 0


class FinanceExportError(RuntimeError):
    """Raised when an export cannot be acknowledged safely."""

    def __init__(self, code: str, *, event_index: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.event_index = event_index


def _export_enabled() -> bool:
    return os.getenv("FINANCE_EXPORT_ENABLED", "").strip().lower() == "true"


def _receiver_config() -> tuple[str, str]:
    url = os.getenv("FINANCE_EXPORT_URL", "").strip()
    secret = os.getenv("FINANCE_EXPORT_SECRET", "").strip()
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != "/api/finance/ingest"
    ):
        raise FinanceExportError("finance_export_url_invalid")
    if len(secret) < 32:
        raise FinanceExportError("finance_export_secret_invalid")
    return url, secret


def _hash_reference(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _required_text(event: dict[str, Any], key: str, maximum: int = 120) -> str:
    value = event.get(key)
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise FinanceExportError("finance_event_invalid")
    return value


def _event_record(event: dict[str, Any]) -> dict[str, Any]:
    event_id = _required_text(event, "event_id", 240)
    event_type = _required_text(event, "event_type", 80)
    occurred_at = _required_text(event, "occurred_at", 80)
    provider = _required_text(event, "provider", 20).lower()
    currency = _required_text(event, "currency", 3).upper()
    if provider not in {"stripe", "paypal"} or currency != "EUR":
        raise FinanceExportError("finance_event_invalid")

    is_capture = event_type == "payment_captured"
    amount_key = "amount_cents" if is_capture else "amount_cents_reported"
    amount_minor = event.get(amount_key)
    if (
        not isinstance(amount_minor, int)
        or isinstance(amount_minor, bool)
        or amount_minor <= 0
        or amount_minor > MAX_FINANCE_AMOUNT_MINOR
    ):
        raise FinanceExportError("finance_event_invalid")

    if is_capture:
        purpose = event.get("purpose")
        if (
            purpose not in {"infrastructure_support", "developer_support"}
            or event.get("category") != "donation"
            or event.get("fulfillment_state") != "not_applicable"
        ):
            raise FinanceExportError("finance_event_invalid")
        kind = "donation"
    elif event_type in {
        "charge.refunded",
        "charge.dispute.created",
        "charge.dispute.closed",
        "refunded",
        "reversed",
    }:
        purpose = None
        kind = "adjustment"
    else:
        raise FinanceExportError("finance_event_unsupported")

    fields: dict[str, str | int | bool] = {
        "processor": provider,
        "eventType": event_type,
        "occurredAt": occurred_at,
        "currency": currency,
        "considerationProvided": False,
        "requiresManualReview": True,
    }
    if is_capture:
        fields["grossAmountMinor"] = amount_minor
    else:
        fields["reportedAmountMinor"] = amount_minor
        fields["amountBasis"] = (
            "cumulative_refunded" if event_type == "charge.refunded" else "provider_event_amount"
        )
    if purpose:
        fields["purpose"] = purpose
    adjustment_state = event.get("adjustment_state")
    if isinstance(adjustment_state, str) and adjustment_state:
        fields["adjustmentState"] = adjustment_state[:80]
    for source_key, target_key in (
        ("provider_reference", "providerReferenceHash"),
        ("payment_reference", "paymentReferenceHash"),
        ("adjustment_reference", "adjustmentReferenceHash"),
    ):
        digest = _hash_reference(event.get(source_key))
        if digest:
            fields[target_key] = digest

    record_digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()
    return {
        "id": f"ekklesia_{record_digest}",
        "kind": kind,
        "source": FINANCE_EXPORT_SOURCE,
        "fields": fields,
    }


def _payload(raw_events: list[str]) -> tuple[bytes, list[str]]:
    records: list[dict[str, Any]] = []
    for index, raw_event in enumerate(raw_events):
        try:
            event = json.loads(raw_event)
        except (json.JSONDecodeError, TypeError) as exc:
            raise FinanceExportError("finance_event_invalid_json", event_index=index) from exc
        if not isinstance(event, dict):
            raise FinanceExportError("finance_event_invalid", event_index=index)
        try:
            records.append(_event_record(event))
        except FinanceExportError as exc:
            raise FinanceExportError(exc.code, event_index=index) from exc

    body = json.dumps(
        {"schema": FINANCE_EXPORT_SCHEMA, "source": FINANCE_EXPORT_SOURCE, "records": records},
        separators=(",", ":"),
    ).encode("utf-8")
    return body, [record["id"] for record in records]


async def _http_post(url: str, headers: dict[str, str], body: bytes) -> httpx.Response:
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        return await client.post(url, headers=headers, content=body)


async def _release_lock(redis: Any, token: str) -> None:
    script = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) else return 0 end"
    )
    await redis.eval(script, 1, FINANCE_EXPORT_LOCK_KEY, token)


def _failure_key(raw_event: str) -> str:
    return f"{FINANCE_EXPORT_FAILURE_PREFIX}{hashlib.sha256(raw_event.encode('utf-8')).hexdigest()}"


async def _register_invalid_event(
    redis: Any,
    raw_events: list[str],
    error: FinanceExportError,
) -> bool:
    if error.event_index is None or error.event_index >= len(raw_events):
        return False
    raw_event = raw_events[error.event_index]
    failure_key = _failure_key(raw_event)
    failures = await redis.incr(failure_key)
    await redis.expire(failure_key, FINANCE_EXPORT_FAILURE_TTL_SECONDS)
    if failures < FINANCE_EXPORT_QUARANTINE_THRESHOLD:
        return False

    marker = f"__finance_quarantine__{secrets.token_hex(24)}"
    script = (
        "if redis.call('lindex', KEYS[1], ARGV[1]) == ARGV[2] then "
        "redis.call('lset', KEYS[1], ARGV[1], ARGV[3]); "
        "redis.call('lrem', KEYS[1], 1, ARGV[3]); "
        "redis.call('rpush', KEYS[2], ARGV[2]); return 1 else return 0 end"
    )
    moved = await redis.eval(
        script,
        2,
        FINANCE_EVENTS_KEY,
        FINANCE_DEAD_LETTER_KEY,
        error.event_index,
        raw_event,
        marker,
    )
    if moved != 1:
        raise FinanceExportError("finance_event_quarantine_conflict")
    await redis.delete(failure_key)
    return True


async def export_pending_finance_events(
    redis: Any,
    *,
    post: PostFunction | None = None,
    now_ms: int | None = None,
) -> FinanceExportResult:
    """Export one queue batch and trim it only after an exact receiver ACK."""
    if not _export_enabled():
        return FinanceExportResult(status="disabled")

    url, secret = _receiver_config()
    lock_token = secrets.token_hex(24)
    acquired = await redis.set(
        FINANCE_EXPORT_LOCK_KEY,
        lock_token,
        nx=True,
        ex=FINANCE_EXPORT_LOCK_SECONDS,
    )
    if not acquired:
        return FinanceExportResult(status="busy")

    try:
        raw_events = await redis.lrange(FINANCE_EVENTS_KEY, 0, FINANCE_EXPORT_BATCH_SIZE - 1)
        if not raw_events:
            return FinanceExportResult(status="empty")

        try:
            body, expected_ids = _payload(raw_events)
        except FinanceExportError as exc:
            if await _register_invalid_event(redis, raw_events, exc):
                return FinanceExportResult(status="quarantined", quarantined=1)
            raise
        timestamp = now_ms if now_ms is not None else int(time.time() * 1000)
        signature = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp}.".encode("utf-8") + body,
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "content-type": "application/json",
            "x-vlabs-source": FINANCE_EXPORT_SOURCE,
            "x-vlabs-timestamp": str(timestamp),
            "x-vlabs-signature": signature,
        }
        response = await (post or _http_post)(url, headers, body)
        if response.status_code < 200 or response.status_code >= 300:
            raise FinanceExportError("finance_receiver_rejected")
        try:
            response_data = response.json()
        except (ValueError, TypeError) as exc:
            raise FinanceExportError("finance_receiver_invalid_ack") from exc
        if (
            not isinstance(response_data, dict)
            or response_data.get("ok") is not True
            or response_data.get("acceptedIds") != expected_ids
        ):
            raise FinanceExportError("finance_receiver_invalid_ack")

        failure_keys = [_failure_key(raw_event) for raw_event in raw_events]
        await redis.delete(*failure_keys)
        await redis.ltrim(FINANCE_EVENTS_KEY, len(raw_events), -1)
        return FinanceExportResult(status="exported", exported=len(raw_events))
    finally:
        await _release_lock(redis, lock_token)
