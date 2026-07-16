"""
MOD-18: Community Donations / Spenden
POST /api/v1/payments/webhook         — Stripe Webhook (signature-verified)
POST /api/v1/payments/webhook/paypal  — PayPal IPN Webhook (auto-verified)
GET  /api/v1/payments/status          — Öffentlicher Transparenz-Endpoint
GET  /api/v1/admin/payments/logs      — Admin: Zahlungs-Log

Verteilungslogik:
  Eingehende Spenden werden automatisch priorisiert:
  1. Server (10€/Monat) — höchste Priorität, läuft ständig
  2. Domain (9,30€/Jahr) — niedrigere Frequenz
  3. Reserve — Überschuss als Puffer

PayPal IPN:
  - Automatische Verifizierung gegen PayPal Server
  - Nur freiwillige Spenden ohne Gegenleistung
  - Idempotency via txn_id in Redis

Alles in Redis gespeichert — kein DB-Schema nötig.
"""
import json
import logging
import os
import secrets
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from urllib.parse import parse_qs
from fastapi import APIRouter, Depends, Request, HTTPException
import httpx
import redis.asyncio as aioredis
from dependencies import verify_admin_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/payments", tags=["MOD-18 Donations"])

# ── Redis ─────────────────────────────────────────────────────────────────────

_redis: aioredis.Redis | None = None

async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis = aioredis.from_url(url, decode_responses=True)
    return _redis

# ── Config ────────────────────────────────────────────────────────────────────

SERVER_COST_MONTHLY = 10.00
SERVER_START = "2026-04-16"
DOMAIN_COST_YEARLY = 9.30
DOMAIN_EXPIRY = "2028-03-29"
INITIAL_SERVER_FUNDING = os.getenv("INITIAL_SERVER_FUNDING_EUR", "0")
INITIAL_DOMAIN_FUNDING = os.getenv("INITIAL_DOMAIN_FUNDING_EUR", "0")

# Redis keys
R_PAYMENTS = "donations:log"          # List of JSON payment records
R_SERVER_RECEIVED = "donations:server:received"  # float
R_DOMAIN_RECEIVED = "donations:domain:received"  # float
R_RESERVE = "donations:reserve"       # float
R_STRIPE_SESSION_PREFIX = "donations:stripe:session:"
R_STRIPE_EVENT_PREFIX = "payments:stripe:event:"
R_STRIPE_PAYMENT_PREFIX = "payments:stripe:payment_intent:"
R_FINANCE_EVENTS = "payments:finance_events"
R_ADJUSTMENT_STATE_PREFIX = "payments:adjustment_state:"
R_PUBLIC_SERVER_RECEIVED = "donations:public:server:received"
R_PUBLIC_DOMAIN_RECEIVED = "donations:public:domain:received"
R_PUBLIC_RESERVE = "donations:public:reserve"
R_PUBLIC_PAYMENT_COUNT = "donations:public:count"
R_PUBLIC_LAST_PAYMENT = "donations:public:last"
R_PUBLIC_PAYMENT_STATE_PREFIX = "donations:public:payment:v2:"
R_PUBLIC_PAYMENT_LOCK_PREFIX = "donations:public:payment-lock:v2:"
R_PENDING_STRIPE_ADJUSTMENT_PREFIX = "payments:pending-adjustment:stripe:"
R_PENDING_PAYPAL_ADJUSTMENT_PREFIX = "payments:pending-adjustment:paypal:"
R_CAPTURE_STATE_PREFIX = "payments:capture-state:v2:"
R_PENDING_DRAIN_LOCK_PREFIX = "payments:pending-adjustment-drain-lock:v2:"
R_ADJUSTMENT_APPLIED_PREFIX = "payments:adjustment-applied:v2:"

PROJECTION_ADJUSTMENT_COMMIT_SCRIPT = """
-- payment_projection_commit_v2
if redis.call('get', KEYS[1]) ~= ARGV[1] then
  return 0
end
if redis.call('exists', KEYS[2]) == 1 then
  return 2
end
for index = 1, 3 do
  local delta = ARGV[index + 1]
  if delta ~= '0' then
    redis.call('incrbyfloat', KEYS[index + 2], delta)
    redis.call('incrbyfloat', KEYS[index + 5], delta)
  end
end
local count_delta = tonumber(ARGV[5])
if count_delta ~= 0 then
  redis.call('incrby', KEYS[9], count_delta)
end
if ARGV[6] ~= 'none' then
  local current_last = redis.call('get', KEYS[10])
  local valid_last, decoded_last = pcall(cjson.decode, current_last or '')
  if valid_last and decoded_last['projection_reference'] == ARGV[11] then
    if ARGV[6] == 'delete' then
      redis.call('del', KEYS[10])
    elseif ARGV[6] == 'set' then
      redis.call('set', KEYS[10], ARGV[7])
    end
  end
end
local paypal_delta = ARGV[9]
if paypal_delta ~= '0' then
  redis.call('incrbyfloat', KEYS[12], paypal_delta)
end
local paypal_count_delta = tonumber(ARGV[10])
if paypal_count_delta ~= 0 then
  redis.call('incrby', KEYS[13], paypal_count_delta)
end
redis.call('set', KEYS[11], ARGV[8])
redis.call('set', KEYS[2], 'processed')
return 1
"""

SUPPORT_PURPOSES = {"infrastructure_support", "developer_support"}
ALLOWED_PAYMENT_PURPOSES = SUPPORT_PURPOSES
MIN_PAYMENT_CENTS = 100
MAX_PAYMENT_CENTS = 1_000_000


def _payment_intake_enabled() -> bool:
    return os.getenv("PAYMENTS_INTAKE_GATE", "") == "legal_recipient_confirmed"


def _payment_purpose(value: str) -> str | None:
    normalized = value.strip().lower()
    return normalized if normalized in ALLOWED_PAYMENT_PURPOSES else None


def _payment_category(purpose: str) -> str:
    return "donation"


def _validate_payment_amount(purpose: str, amount_cents: int) -> bool:
    return purpose in SUPPORT_PURPOSES and MIN_PAYMENT_CENTS <= amount_cents <= MAX_PAYMENT_CENTS


async def _append_finance_event(r: aioredis.Redis, event: dict) -> None:
    """Append a PII-free event for private finance/provider ingestion."""
    await r.rpush(R_FINANCE_EVENTS, json.dumps(event, separators=(",", ":")))


def _stripe_adjustment_kind(event_type: str, adjustment: dict) -> str:
    if event_type == "charge.refunded":
        return "stripe_refund_cumulative"
    if event_type == "charge.dispute.created":
        return "stripe_dispute_open"
    return (
        "stripe_dispute_won"
        if str(adjustment.get("status", "")).lower() == "won"
        else "stripe_dispute_lost"
    )


async def _process_stripe_adjustment(event: dict, event_type: str) -> dict:
    event_id = event.get("id", "")
    adjustment = event.get("data", {}).get("object", {})
    payment_intent = adjustment.get("payment_intent", "")
    currency = str(adjustment.get("currency", "")).upper()
    amount_field = "amount_refunded" if event_type == "charge.refunded" else "amount"
    amount_cents = adjustment.get(amount_field)

    if not isinstance(event_id, str) or not event_id.startswith("evt_"):
        raise HTTPException(status_code=400, detail="Invalid Stripe event")
    if not isinstance(payment_intent, str) or not payment_intent.startswith("pi_"):
        raise HTTPException(status_code=400, detail="Invalid Stripe payment reference")
    if currency != "EUR" or not isinstance(amount_cents, int) or amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Invalid Stripe adjustment")

    r = await _get_redis()
    event_key = f"{R_STRIPE_EVENT_PREFIX}{event_id}"
    pending_key = f"{R_PENDING_STRIPE_ADJUSTMENT_PREFIX}{payment_intent}"
    claimed = await r.set(event_key, "processing", nx=True, ex=900)
    if not claimed:
        existing_claim = await r.get(event_key)
        if existing_claim == "pending_payment":
            session_id = await r.get(f"{R_STRIPE_PAYMENT_PREFIX}{payment_intent}")
            if session_id:
                processed = await _drain_pending_adjustments(
                    r,
                    pending_key,
                    f"stripe:{session_id}",
                )
                if processed == 0:
                    raise HTTPException(status_code=503, detail="Payment projection retry is pending")
                return {
                    "received": True,
                    "processed": True,
                    "requires_manual_review": False,
                }
        return {"received": True, "processed": False, "duplicate": True}

    session_id = await r.get(f"{R_STRIPE_PAYMENT_PREFIX}{payment_intent}")
    live_mode = event.get("livemode") is True
    adjustment_kind = _stripe_adjustment_kind(event_type, adjustment)
    state = {
        "charge.refunded": "refund_reported",
        "charge.dispute.created": "dispute_open",
        "charge.dispute.closed": "dispute_closed",
    }[event_type]
    try:
        projection_result = {"applied": False, "reason": "test_mode"}
        if session_id:
            await r.set(f"{R_ADJUSTMENT_STATE_PREFIX}{session_id}", state)
            if live_mode:
                projection_result = await _apply_public_payment_adjustment(
                    r,
                    f"stripe:{session_id}",
                    amount_cents,
                    adjustment_kind,
                    event_id,
                )
                if projection_result.get("reason") in {"payment_projection_missing", "payment_projection_busy"}:
                    await _queue_pending_adjustment(r, pending_key, {
                        "event_key": event_key,
                        "adjustment_id": event_id,
                        "amount_cents": amount_cents,
                        "adjustment_kind": adjustment_kind,
                    })
        elif live_mode:
            await _queue_pending_adjustment(r, pending_key, {
                "event_key": event_key,
                "adjustment_id": event_id,
                "amount_cents": amount_cents,
                "adjustment_kind": adjustment_kind,
            })
            projection_result = {"applied": False, "reason": "payment_projection_pending"}
            late_session_id = await r.get(f"{R_STRIPE_PAYMENT_PREFIX}{payment_intent}")
            if late_session_id:
                session_id = late_session_id
                await _drain_pending_adjustments(r, pending_key, f"stripe:{session_id}")
                projection_result = {"applied": True, "reason": "reconciled"}
        projection_pending = live_mode and projection_result.get("reason") in {
            "payment_projection_missing", "payment_projection_pending", "payment_projection_busy",
        }
        retry_required = live_mode and projection_result.get("reason") == "payment_projection_busy"
        requires_manual_review = not bool(session_id) or projection_pending
        await _append_finance_event(r, {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "provider": "stripe",
            "provider_mode": "live" if live_mode else "test",
            "provider_reference": session_id,
            "payment_reference": payment_intent,
            "amount_cents_reported": amount_cents,
            "currency": currency,
            "adjustment_state": state,
            "requires_manual_review": requires_manual_review,
        })
        await r.set(
            event_key,
            "pending_payment" if projection_pending else "processed" if session_id else "accounting_review_required",
        )
    except Exception:
        await r.set(event_key, "accounting_review_required")
        raise

    if retry_required:
        raise HTTPException(status_code=503, detail="Payment projection is busy")

    return {
        "received": True,
        "processed": bool(session_id) and not projection_pending,
        "requires_manual_review": requires_manual_review,
    }


def _public_payment_record(record: dict | None) -> dict | None:
    """Return transparency fields without donor or processor identifiers."""
    if not record:
        return None
    allowed = ("amount", "allocation", "to")
    return {key: record[key] for key in allowed if key in record}


def _projection_reference(record: dict) -> str | None:
    if (
        record.get("method") == "stripe"
        and isinstance(record.get("stripe_session"), str)
        and record["stripe_session"].startswith("cs_")
    ):
        return f"stripe:{record['stripe_session']}"
    if (
        record.get("method") == "paypal"
        and isinstance(record.get("txn_id"), str)
        and 1 <= len(record["txn_id"]) <= 127
    ):
        return f"paypal:{record['txn_id']}"
    return None


def _amount_to_cents(value: object) -> int | None:
    amount = _public_allocation_amount(value)
    if amount is None:
        return None
    cents = amount * 100
    return int(cents) if cents == cents.to_integral_value() else None


def _projection_state(record: dict) -> tuple[str, dict] | None:
    if not _is_public_support_record(record):
        return None
    reference = _projection_reference(record)
    amount_cents = _amount_to_cents(record.get("amount"))
    allocation_cents = {
        key: _amount_to_cents(record["allocation"].get(key))
        for key in ("server", "domain", "reserve")
    }
    if not reference or amount_cents is None or any(value is None for value in allocation_cents.values()):
        return None
    if sum(allocation_cents.values()) != amount_cents:
        return None
    return reference, {
        "schema": "ekklesia.public-payment-state.v2",
        "reference": reference,
        "provider": record["method"],
        "amount_cents": amount_cents,
        "original_allocation_cents": allocation_cents,
        "remaining_allocation_cents": allocation_cents,
        "refund_cents": 0,
        "dispute_cents": 0,
        "dispute_terminal": False,
        "adjusted_cents": 0,
    }


def _public_support_amount(value: object) -> Decimal | None:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None
    return amount if amount.is_finite() and amount > 0 else None


def _public_allocation_amount(value: object) -> Decimal | None:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def _is_public_support_record(record: object) -> bool:
    """Accept only current, processor-verified support records for public totals."""
    if not isinstance(record, dict):
        return False
    if record.get("method") not in {"stripe", "paypal"}:
        return False
    if record.get("category") != "donation":
        return False
    if record.get("purpose") not in SUPPORT_PURPOSES:
        return False
    if record.get("currency") != "EUR":
        return False
    if record.get("fulfillment_state") != "not_applicable":
        return False
    if record.get("provider_mode") != "live":
        return False
    if _public_support_amount(record.get("amount")) is None:
        return False
    allocation = record.get("allocation")
    if not isinstance(allocation, dict):
        return False
    allocated = [_public_allocation_amount(allocation.get(key)) for key in ("server", "domain", "reserve")]
    if any(value is None for value in allocated):
        return False
    return sum(allocated, Decimal("0")) == _public_support_amount(record.get("amount"))


def _empty_public_projection() -> dict:
    return {
        "server": 0.0,
        "domain": 0.0,
        "reserve": 0.0,
        "received": 0.0,
        "count": 0,
        "last_payment": None,
    }


async def _load_public_support_projection(r: aioredis.Redis) -> dict:
    """Read the bounded projection maintained atomically with verified records."""
    snapshot = await r.mget(
        R_PUBLIC_SERVER_RECEIVED,
        R_PUBLIC_DOMAIN_RECEIVED,
        R_PUBLIC_RESERVE,
        R_PUBLIC_PAYMENT_COUNT,
        R_PUBLIC_LAST_PAYMENT,
    )
    raw_totals = snapshot[:3]
    if all(value is None for value in raw_totals):
        return _empty_public_projection()
    if any(value is None for value in raw_totals):
        logger.error("[MOD-18] Public support projection is incomplete")
        return _empty_public_projection()

    totals = [_public_allocation_amount(value) for value in raw_totals]
    if any(value is None for value in totals):
        logger.error("[MOD-18] Public support projection contains invalid totals")
        return _empty_public_projection()

    raw_count = snapshot[3]
    if raw_count is None:
        logger.error("[MOD-18] Public support projection count is missing")
        return _empty_public_projection()
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        return _empty_public_projection()
    if count < 0:
        return _empty_public_projection()

    last_payment = None
    raw_last = snapshot[4]
    if count > 0 and raw_last:
        try:
            candidate = json.loads(raw_last)
        except (TypeError, json.JSONDecodeError):
            candidate = None
        if isinstance(candidate, dict):
            amount = _public_support_amount(candidate.get("amount"))
            allocation = candidate.get("allocation")
            allocated = [
                _public_allocation_amount(allocation.get(key)) if isinstance(allocation, dict) else None
                for key in ("server", "domain", "reserve")
            ]
            if (
                amount is not None
                and all(value is not None for value in allocated)
                and sum(allocated, Decimal("0")) == amount
            ):
                last_payment = _public_payment_record(candidate)

    server, domain, reserve = totals
    received = server + domain + reserve
    return {
        "server": float(server),
        "domain": float(domain),
        "reserve": float(reserve),
        "received": float(received),
        "count": count,
        "last_payment": last_payment,
    }


async def _append_payment_record(r: aioredis.Redis, record: dict) -> None:
    """Append the private record and its verified public projection atomically."""
    payload = json.dumps(record)
    pipe = r.pipeline(transaction=True)
    pipe.rpush(R_PAYMENTS, payload)
    reference = _projection_reference(record)
    if not reference:
        raise ValueError("invalid_payment_reference")
    pipe.set(f"{R_CAPTURE_STATE_PREFIX}{reference}", "recorded", nx=True)
    if _is_public_support_record(record):
        allocation = record["allocation"]
        public_allocation = {
            key: _public_allocation_amount(allocation[key])
            for key in ("server", "domain", "reserve")
        }
        pipe.incrbyfloat(R_SERVER_RECEIVED, format(public_allocation["server"], "f"))
        pipe.incrbyfloat(R_DOMAIN_RECEIVED, format(public_allocation["domain"], "f"))
        pipe.incrbyfloat(R_RESERVE, format(public_allocation["reserve"], "f"))
        if record["method"] == "paypal":
            pipe.incrbyfloat(R_PAYPAL_DONATIONS, format(_public_support_amount(record["amount"]), "f"))
            pipe.incr(R_PAYPAL_COUNT)
        pipe.incrbyfloat(R_PUBLIC_SERVER_RECEIVED, format(public_allocation["server"], "f"))
        pipe.incrbyfloat(R_PUBLIC_DOMAIN_RECEIVED, format(public_allocation["domain"], "f"))
        pipe.incrbyfloat(R_PUBLIC_RESERVE, format(public_allocation["reserve"], "f"))
        pipe.incr(R_PUBLIC_PAYMENT_COUNT)
        state_entry = _projection_state(record)
        if state_entry is None:
            raise ValueError("invalid_public_projection_state")
        reference, state = state_entry
        public_last = {
            **_public_payment_record(record),
            "projection_reference": reference,
        }
        pipe.set(R_PUBLIC_LAST_PAYMENT, json.dumps(public_last, separators=(",", ":")))
        pipe.set(
            f"{R_PUBLIC_PAYMENT_STATE_PREFIX}{reference}",
            json.dumps(state, separators=(",", ":")),
            nx=True,
        )
    await pipe.execute()


def _target_remaining_allocation(state: dict, adjusted_cents: int) -> dict[str, int]:
    amount_cents = state["amount_cents"]
    remaining_total = max(0, amount_cents - adjusted_cents)
    original = state["original_allocation_cents"]
    keys = ("server", "domain", "reserve")
    numerators = {key: int(original[key]) * remaining_total for key in keys}
    target = {key: numerators[key] // amount_cents for key in keys}
    residual = remaining_total - sum(target.values())
    ranked = sorted(keys, key=lambda key: (numerators[key] % amount_cents, -keys.index(key)), reverse=True)
    for key in ranked[:residual]:
        target[key] += 1
    return target


def _validated_projection_state(state: object, reference: str) -> dict:
    if not isinstance(state, dict) or state.get("schema") != "ekklesia.public-payment-state.v2":
        raise ValueError("invalid_projection_state")
    if state.get("reference") != reference or state.get("provider") not in {"stripe", "paypal"}:
        raise ValueError("invalid_projection_state")
    total_cents = state.get("amount_cents")
    refund_cents = state.get("refund_cents", 0)
    dispute_cents = state.get("dispute_cents", 0)
    dispute_terminal = state.get("dispute_terminal", False)
    adjusted_cents = state.get("adjusted_cents", 0)
    if (
        not isinstance(total_cents, int) or not MIN_PAYMENT_CENTS <= total_cents <= MAX_PAYMENT_CENTS
        or any(not isinstance(value, int) or not 0 <= value <= total_cents
               for value in (refund_cents, dispute_cents, adjusted_cents))
        or not isinstance(dispute_terminal, bool)
        or adjusted_cents != min(total_cents, refund_cents + dispute_cents)
    ):
        raise ValueError("invalid_projection_state")
    try:
        original = {key: state["original_allocation_cents"][key] for key in ("server", "domain", "reserve")}
        remaining = {key: state["remaining_allocation_cents"][key] for key in ("server", "domain", "reserve")}
    except (KeyError, TypeError):
        raise ValueError("invalid_projection_state")
    if (
        any(not isinstance(value, int) or value < 0 for value in (*original.values(), *remaining.values()))
        or sum(original.values()) != total_cents
        or sum(remaining.values()) != total_cents - adjusted_cents
    ):
        raise ValueError("invalid_projection_state")
    return state


async def _release_projection_lock(r: aioredis.Redis, lock_key: str, token: str) -> None:
    script = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) else return 0 end"
    )
    await r.eval(script, 1, lock_key, token)


async def _recover_projection_state(r: aioredis.Redis, reference: str) -> dict | None:
    """Backfill adjustment state for verified records created before state v2."""
    record_count = await r.llen(R_PAYMENTS)
    end = record_count - 1
    while end >= 0:
        start = max(0, end - 999)
        raw_records = await r.lrange(R_PAYMENTS, start, end)
        for raw_record in reversed(raw_records):
            try:
                record = json.loads(raw_record)
            except (TypeError, json.JSONDecodeError):
                continue
            state_entry = _projection_state(record) if isinstance(record, dict) else None
            if state_entry and state_entry[0] == reference:
                state = state_entry[1]
                await r.set(
                    f"{R_PUBLIC_PAYMENT_STATE_PREFIX}{reference}",
                    json.dumps(state, separators=(",", ":")),
                    nx=True,
                )
                return state
        end = start - 1
    return None


async def _apply_public_payment_adjustment(
    r: aioredis.Redis,
    reference: str,
    amount_cents: int,
    adjustment_kind: str,
    adjustment_id: str,
) -> dict:
    """Apply a refund/reversal to private balances and the public projection once."""
    if not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError("invalid_adjustment_amount")
    if not isinstance(adjustment_id, str) or not 1 <= len(adjustment_id) <= 255:
        raise ValueError("invalid_adjustment_id")
    state_key = f"{R_PUBLIC_PAYMENT_STATE_PREFIX}{reference}"
    lock_key = f"{R_PUBLIC_PAYMENT_LOCK_PREFIX}{reference}"
    applied_key = f"{R_ADJUSTMENT_APPLIED_PREFIX}{adjustment_id}"
    token = secrets.token_hex(16)
    if not await r.set(lock_key, token, nx=True, ex=120):
        return {"applied": False, "reason": "payment_projection_busy"}
    try:
        if await r.get(applied_key):
            return {"applied": False, "reason": "duplicate_adjustment"}
        raw_state = await r.get(state_key)
        recovered_state = None
        if not raw_state:
            recovered_state = await _recover_projection_state(r, reference)
            if not recovered_state:
                return {"applied": False, "reason": "payment_projection_missing"}
        try:
            state = _validated_projection_state(recovered_state or json.loads(raw_state), reference)
            total_cents = int(state["amount_cents"])
            previous_adjusted = int(state.get("adjusted_cents", 0))
            previous_remaining = {
                key: int(state["remaining_allocation_cents"][key])
                for key in ("server", "domain", "reserve")
            }
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=503, detail="Payment projection state is invalid")

        refund_cents = int(state.get("refund_cents", 0))
        dispute_cents = int(state.get("dispute_cents", 0))
        dispute_terminal = state.get("dispute_terminal", False)
        if adjustment_kind == "stripe_refund_cumulative":
            refund_cents = max(refund_cents, min(total_cents, amount_cents))
        elif adjustment_kind == "paypal_refund_delta":
            refund_cents = min(total_cents, refund_cents + amount_cents)
        elif adjustment_kind in {"stripe_dispute_open", "paypal_reversal"}:
            if dispute_terminal:
                await r.set(applied_key, "processed")
                return {"applied": False, "reason": "terminal_dispute_state"}
            dispute_cents = max(dispute_cents, min(total_cents, amount_cents))
        elif adjustment_kind in {"stripe_dispute_won", "paypal_reversal_cancelled"}:
            dispute_cents = 0
            dispute_terminal = True
        elif adjustment_kind == "stripe_dispute_lost":
            dispute_cents = max(dispute_cents, min(total_cents, amount_cents))
            dispute_terminal = True
        else:
            raise ValueError("invalid_adjustment_kind")

        adjusted_cents = min(total_cents, refund_cents + dispute_cents)
        target_remaining = _target_remaining_allocation(state, adjusted_cents)
        allocation_delta = {
            key: previous_remaining[key] - target_remaining[key]
            for key in ("server", "domain", "reserve")
        }
        previous_full = previous_adjusted >= total_cents
        current_full = adjusted_cents >= total_cents
        count_delta = 1 if previous_full and not current_full else -1 if not previous_full and current_full else 0

        state.update({
            "remaining_allocation_cents": target_remaining,
            "refund_cents": refund_cents,
            "dispute_cents": dispute_cents,
            "dispute_terminal": dispute_terminal,
            "adjusted_cents": adjusted_cents,
        })
        raw_last = await r.get(R_PUBLIC_LAST_PAYMENT)
        try:
            last = json.loads(raw_last) if raw_last else None
        except (TypeError, json.JSONDecodeError):
            last = None
        last_action = "none"
        last_payload = ""
        if isinstance(last, dict) and last.get("projection_reference") == reference:
            if current_full:
                last_action = "delete"
            else:
                last.update({
                    "amount": (total_cents - adjusted_cents) / 100,
                    "allocation": {key: target_remaining[key] / 100 for key in target_remaining},
                })
                last_action = "set"
                last_payload = json.dumps(last, separators=(",", ":"))

        paypal_delta = Decimal("0")
        paypal_count_delta = 0
        if state.get("provider") == "paypal":
            payment_delta_cents = adjusted_cents - previous_adjusted
            if payment_delta_cents:
                paypal_delta = Decimal(-payment_delta_cents) / 100
            if count_delta:
                paypal_count_delta = count_delta

        allocation_deltas = [
            format(Decimal(-allocation_delta[key]) / 100, "f")
            for key in ("server", "domain", "reserve")
        ]
        commit_result = await r.eval(
            PROJECTION_ADJUSTMENT_COMMIT_SCRIPT,
            13,
            lock_key,
            applied_key,
            R_PUBLIC_SERVER_RECEIVED,
            R_PUBLIC_DOMAIN_RECEIVED,
            R_PUBLIC_RESERVE,
            R_SERVER_RECEIVED,
            R_DOMAIN_RECEIVED,
            R_RESERVE,
            R_PUBLIC_PAYMENT_COUNT,
            R_PUBLIC_LAST_PAYMENT,
            state_key,
            R_PAYPAL_DONATIONS,
            R_PAYPAL_COUNT,
            token,
            *allocation_deltas,
            str(count_delta),
            last_action,
            last_payload,
            json.dumps(state, separators=(",", ":")),
            format(paypal_delta, "f"),
            str(paypal_count_delta),
            reference,
        )
        if commit_result == 0:
            raise HTTPException(status_code=503, detail="Payment projection lock expired")
        if commit_result == 2:
            return {"applied": False, "reason": "duplicate_adjustment"}
        return {
            "applied": adjusted_cents != previous_adjusted,
            "adjusted_cents": adjusted_cents,
            "fully_adjusted": current_full,
        }
    finally:
        await _release_projection_lock(r, lock_key, token)


async def _queue_pending_adjustment(r: aioredis.Redis, key: str, adjustment: dict) -> None:
    await r.rpush(key, json.dumps(adjustment, separators=(",", ":")))


async def _drain_pending_adjustments(r: aioredis.Redis, key: str, reference: str) -> int:
    processing_key = f"{key}:processing"
    lock_key = f"{R_PENDING_DRAIN_LOCK_PREFIX}{reference}"
    token = secrets.token_hex(16)
    if not await r.set(lock_key, token, nx=True, ex=120):
        return 0
    try:
        while await r.lmove(processing_key, key, "RIGHT", "LEFT") is not None:
            pass
        processed = 0
        while True:
            raw = await r.lmove(key, processing_key, "LEFT", "RIGHT")
            if raw is None:
                return processed
            adjustment = json.loads(raw)
            result = await _apply_public_payment_adjustment(
                r,
                reference,
                adjustment["amount_cents"],
                adjustment["adjustment_kind"],
                adjustment["adjustment_id"],
            )
            if result.get("reason") == "payment_projection_busy":
                raise HTTPException(status_code=503, detail="Payment projection is busy")
            event_key = adjustment.get("event_key")
            if isinstance(event_key, str) and event_key:
                await r.set(event_key, "processed")
            await r.lrem(processing_key, 1, raw)
            processed += 1
    finally:
        await _release_projection_lock(r, lock_key, token)


def _admin_payment_record(record: dict) -> dict:
    """Project legacy rows onto an explicit PII-free admin schema."""
    allowed = (
        "date", "amount", "currency", "allocation", "method", "purpose",
        "category", "fulfillment_state", "requires_accounting_review",
        "provider_mode", "stripe_session", "payment_intent", "txn_id",
    )
    return {key: record[key] for key in allowed if key in record}


async def _init_operating_funding(r: aioredis.Redis) -> None:
    """Initialize private operator funding without creating payment records."""
    keys = (R_SERVER_RECEIVED, R_DOMAIN_RECEIVED, R_RESERVE)
    current = await r.mget(*keys)
    if all(value is not None for value in current):
        return
    pipe = r.pipeline(transaction=True)
    pipe.set(R_SERVER_RECEIVED, INITIAL_SERVER_FUNDING, nx=True)
    pipe.set(R_DOMAIN_RECEIVED, INITIAL_DOMAIN_FUNDING, nx=True)
    pipe.set(R_RESERVE, "0.00", nx=True)
    initialized = await pipe.execute()
    if any(initialized):
        logger.info("[MOD-18] Initialized private operator funding balances")


# ── Verteilungsalgorithmus ────────────────────────────────────────────────────

async def allocate_donation(amount: float, r: aioredis.Redis) -> dict:
    """
    Verteilt eine Spende nach Priorität:
    1. Server: wenn Kontostand < 2 Monate Deckung → auffüllen
    2. Domain: wenn < 1 Jahr Deckung → auffüllen
    3. Rest → Reserve
    """
    now = datetime.now(timezone.utc)
    remaining = amount
    allocation = {"server": 0.0, "domain": 0.0, "reserve": 0.0}

    # Server-Bedarf berechnen
    server_received = float(await r.get(R_SERVER_RECEIVED) or "0")
    months_since_start = _months_elapsed(SERVER_START)
    server_cost_total = months_since_start * SERVER_COST_MONTHLY
    server_balance = server_received - server_cost_total
    server_target = SERVER_COST_MONTHLY * 2  # 2 Monate Puffer
    server_need = max(0, server_target - server_balance)

    if remaining > 0 and server_need > 0:
        server_alloc = min(remaining, server_need)
        allocation["server"] = server_alloc
        remaining -= server_alloc

    # Domain-Bedarf (Schulden ausgleichen, kein extra Puffer nötig da jährlich)
    domain_received = float(await r.get(R_DOMAIN_RECEIVED) or "0")
    domain_cost_total = DOMAIN_COST_YEARLY
    domain_balance = domain_received - domain_cost_total
    # Bedarf = nur Schulden tilgen (balance auf 0 bringen)
    domain_need = max(0, -domain_balance)
    if remaining > 0 and domain_need > 0:
        domain_alloc = min(remaining, domain_need)
        allocation["domain"] = domain_alloc
        remaining -= domain_alloc

    # Rest → Reserve (oder extra Server)
    if remaining > 0:
        # Overflow geht primär an Server
        allocation["server"] += remaining
        remaining = 0

    return allocation


def _months_elapsed(start_str: str) -> int:
    start = datetime.strptime(start_str, "%Y-%m-%d")
    now = datetime.now(timezone.utc)
    months = (now.year - start.year) * 12 + (now.month - start.month)
    if now.day >= int(start_str.split("-")[2]):
        months += 1
    return max(1, months)


# ── Stripe Webhook ────────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe Webhook — verarbeitet checkout.session.completed Events.
    Signatur wird verifiziert wenn STRIPE_WEBHOOK_SECRET gesetzt ist.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    if not _payment_intake_enabled():
        raise HTTPException(status_code=503, detail="Payment intake is awaiting legal recipient approval")
    if not webhook_secret:
        logger.error("[MOD-18] Stripe webhook disabled: STRIPE_WEBHOOK_SECRET missing")
        raise HTTPException(status_code=503, detail="Stripe webhook is not configured")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    import stripe

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        logger.warning("[MOD-18] Stripe signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error("[MOD-18] Stripe webhook payload rejected: %s", type(e).__name__)
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook payload")

    event_type = event.get("type", "")
    if event_type in {"charge.refunded", "charge.dispute.created", "charge.dispute.closed"}:
        return await _process_stripe_adjustment(event, event_type)

    # Nur completed sessions verarbeiten
    if event_type != "checkout.session.completed":
        return {"received": True, "processed": False}

    session = event.get("data", {}).get("object", {})
    if session.get("payment_status") != "paid":
        return {"received": True, "processed": False}
    if session.get("mode") != "payment" or str(session.get("currency", "")).lower() != "eur":
        raise HTTPException(status_code=400, detail="Invalid Stripe payment mode or currency")

    purpose = _payment_purpose((session.get("metadata") or {}).get("payment_purpose", ""))
    if not purpose:
        raise HTTPException(status_code=400, detail="Missing or invalid payment purpose")

    session_id = session.get("id", "")
    if not isinstance(session_id, str) or not session_id.startswith("cs_"):
        raise HTTPException(status_code=400, detail="Invalid Stripe Checkout Session")

    amount_cents = session.get("amount_total")
    if not isinstance(amount_cents, int) or not MIN_PAYMENT_CENTS <= amount_cents <= MAX_PAYMENT_CENTS:
        raise HTTPException(status_code=400, detail="Invalid Stripe payment amount")
    amount_total = amount_cents / 100  # Cents → EUR
    if not _validate_payment_amount(purpose, amount_cents):
        raise HTTPException(status_code=400, detail="Invalid amount for payment purpose")

    event_id = event.get("id", "")
    if not isinstance(event_id, str) or not event_id.startswith("evt_"):
        raise HTTPException(status_code=400, detail="Invalid Stripe event")

    payment_intent = session.get("payment_intent", "")
    if not isinstance(payment_intent, str) or not payment_intent.startswith("pi_"):
        raise HTTPException(status_code=400, detail="Invalid Stripe payment reference")

    r = await _get_redis()
    await _init_operating_funding(r)

    idempotency_key = f"{R_STRIPE_SESSION_PREFIX}{session_id}"
    capture_key = f"{R_CAPTURE_STATE_PREFIX}stripe:{session_id}"
    claimed = await r.set(idempotency_key, "processing", nx=True, ex=900)
    if not claimed:
        existing_claim = await r.get(idempotency_key)
        capture_state = await r.get(capture_key)
        if existing_claim == "accounting_review_required" and capture_state == "recorded":
            await r.set(idempotency_key, "processing", ex=900)
        else:
            return {"received": True, "processed": False, "duplicate": True}

    capture_state = await r.get(capture_key)
    if capture_state == "processed":
        await r.set(idempotency_key, "processed")
        return {"received": True, "processed": False, "duplicate": True}

    durable_mutation_applied = False
    try:
        category = _payment_category(purpose)
        fulfillment_state = "not_applicable"
        allocation = None
        if capture_state != "recorded":
            allocation = await allocate_donation(amount_total, r)
            record = {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                "amount": amount_total,
                "allocation": allocation,
                "method": "stripe",
                "stripe_session": session_id,
                "payment_intent": payment_intent,
                "currency": "EUR",
                "purpose": purpose,
                "category": category,
                "provider_mode": "live" if session.get("livemode") is True else "test",
                "fulfillment_state": fulfillment_state,
                "requires_accounting_review": True,
            }
            await _append_payment_record(r, record)
            durable_mutation_applied = True
        else:
            durable_mutation_applied = True
        await _append_finance_event(r, {
            "event_id": event_id,
            "event_type": "payment_captured",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "provider": "stripe",
            "provider_reference": session_id,
            "payment_reference": payment_intent,
            "purpose": purpose,
            "category": category,
            "provider_mode": "live" if session.get("livemode") is True else "test",
            "amount_cents": amount_cents,
            "currency": "EUR",
            "fulfillment_state": fulfillment_state,
        })
        await r.set(f"{R_STRIPE_PAYMENT_PREFIX}{payment_intent}", session_id)
        if session.get("livemode") is True:
            await _drain_pending_adjustments(
                r,
                f"{R_PENDING_STRIPE_ADJUSTMENT_PREFIX}{payment_intent}",
                f"stripe:{session_id}",
            )
        await r.set(capture_key, "processed")
        await r.set(f"{R_STRIPE_EVENT_PREFIX}{event_id}", "processed")
        await r.set(idempotency_key, "processed")
    except Exception:
        if durable_mutation_applied:
            await r.set(idempotency_key, "accounting_review_required")
        else:
            await r.delete(idempotency_key)
        raise

    logger.info(f"[MOD-18] Donation {amount_total}€ allocated: {allocation}")
    result = {"received": True, "processed": True, "allocation": allocation}
    if capture_state == "recorded":
        result["recovered"] = True
    return result


# ── Public Status Endpoint ────────────────────────────────────────────────────

@router.get("/status")
async def payment_status():
    """
    Öffentlicher Transparenz-Endpoint — kein Auth.
    Liefert aktuelle Kontostände für community.html Kacheln.
    """
    r = await _get_redis()
    projection = await _load_public_support_projection(r)
    server_received = projection["server"]
    domain_received = projection["domain"]
    reserve = projection["reserve"]

    months_elapsed = _months_elapsed(SERVER_START)
    server_cost_total = months_elapsed * SERVER_COST_MONTHLY
    server_balance = round(server_received - server_cost_total, 2)

    domain_cost_total = DOMAIN_COST_YEARLY
    domain_balance = round(domain_received - domain_cost_total, 2)

    # Letzte Zahlung
    last_payment = projection["last_payment"]
    log_len = projection["count"]

    # Alle Zahlungen summieren
    total_received = projection["received"]

    return {
        "server": {
            "received": round(server_received, 2),
            "cost_total": round(server_cost_total, 2),
            "balance": server_balance,
            "cost_monthly": SERVER_COST_MONTHLY,
            "months_elapsed": months_elapsed,
        },
        "domain": {
            "received": round(domain_received, 2),
            "cost_total": round(domain_cost_total, 2),
            "balance": domain_balance,
            "expires": DOMAIN_EXPIRY,
            "cost_yearly": DOMAIN_COST_YEARLY,
        },
        "reserve": round(reserve, 2),
        "total_received": round(total_received, 2),
        "last_payment": last_payment,
        "payment_count": log_len,
    }


# ── PayPal IPN Webhook ───────────────────────────────────────────────────────

R_PAYPAL_TXN = "paypal:txn:"  # Set of processed txn_ids
R_PAYPAL_DONATIONS = "paypal:donations:total"
R_PAYPAL_COUNT = "paypal:donations:count"

PAYPAL_IPN_PRODUCTION_URL = "https://ipnpb.paypal.com/cgi-bin/webscr"
PAYPAL_IPN_URL = os.getenv(
    "PAYPAL_IPN_URL",
    PAYPAL_IPN_PRODUCTION_URL,
)

async def _verify_paypal_ipn(payload: bytes) -> bool:
    """Verify IPN by sending it back to PayPal with cmd=_notify-validate."""
    verify_payload = b"cmd=_notify-validate&" + payload
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                PAYPAL_IPN_URL,
                content=verify_payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            return resp.text.strip() == "VERIFIED"
    except Exception as e:
        logger.error("[PayPal] IPN verification failed: %s", e)
        return False


@router.post("/webhook/paypal")
async def paypal_ipn_webhook(request: Request):
    """
    PayPal IPN Webhook.
    1. Verify IPN mit PayPal Server
    2. Empfaenger, EUR, Betrag und expliziten Zahlungszweck pruefen
    3. Support versus HLR-Kauf fuer Accounting-Review trennen
    4. Idempotency: txn_id atomar nur einmal verarbeiten
    """
    payload = await request.body()
    if not _payment_intake_enabled():
        raise HTTPException(status_code=503, detail="Payment intake is awaiting legal recipient approval")
    try:
        form = {key: values[-1] for key, values in parse_qs(payload.decode("utf-8"), keep_blank_values=True).items()}
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid PayPal IPN encoding")

    # Parse IPN fields
    payment_status = form.get("payment_status", "")
    txn_id = form.get("txn_id", "")
    mc_gross = form.get("mc_gross", "0")
    mc_currency = form.get("mc_currency", "EUR")
    receiver_email = form.get("receiver_email", "").strip().lower()
    receiver_id = form.get("receiver_id", "").strip()
    purpose = _payment_purpose(form.get("custom", ""))
    provider_mode = (
        "live"
        if PAYPAL_IPN_URL == PAYPAL_IPN_PRODUCTION_URL and form.get("test_ipn") != "1"
        else "test"
    )

    logger.info("[PayPal] IPN received: txn=%s status=%s amount=%s %s",
                txn_id, payment_status, mc_gross, mc_currency)

    allowed_statuses = {"Completed", "Refunded", "Reversed", "Canceled_Reversal"}
    if payment_status not in allowed_statuses:
        return {"received": True, "processed": False, "reason": "not_completed"}

    if not txn_id:
        return {"received": True, "processed": False, "reason": "no_txn_id"}

    expected_receiver_email = os.getenv("PAYPAL_RECEIVER_EMAIL", "").strip().lower()
    expected_receiver_id = os.getenv("PAYPAL_MERCHANT_ID", "").strip()
    if not expected_receiver_email and not expected_receiver_id:
        raise HTTPException(status_code=503, detail="PayPal merchant binding is not configured")
    if (expected_receiver_email and receiver_email != expected_receiver_email) or (
        expected_receiver_id and receiver_id != expected_receiver_id
    ):
        raise HTTPException(status_code=400, detail="PayPal receiver mismatch")
    if mc_currency.upper() != "EUR":
        raise HTTPException(status_code=400, detail="Invalid PayPal currency")
    if payment_status == "Completed" and not purpose:
        raise HTTPException(status_code=400, detail="Invalid PayPal payment purpose")

    # Verify with PayPal
    verified = await _verify_paypal_ipn(payload)
    if not verified:
        logger.warning("[PayPal] IPN verification FAILED for txn=%s", txn_id)
        return {"received": True, "processed": False, "reason": "verification_failed"}

    r = await _get_redis()

    # Idempotency: atomically claim before any accounting mutation.
    txn_key = f"{R_PAYPAL_TXN}{txn_id}"
    capture_key = f"{R_CAPTURE_STATE_PREFIX}paypal:{txn_id}"
    claimed = await r.set(txn_key, "processing", nx=True, ex=900)
    if not claimed:
        existing_claim = await r.get(txn_key)
        capture_state = await r.get(capture_key)
        resumable_capture = (
            payment_status == "Completed"
            and existing_claim == "accounting_review_required"
            and capture_state == "recorded"
        )
        resumable_adjustment = (
            payment_status in {"Refunded", "Reversed", "Canceled_Reversal"}
            and provider_mode == "live"
            and existing_claim == "pending_payment"
        )
        if resumable_capture or resumable_adjustment:
            await r.set(txn_key, "processing", ex=900)
        else:
            logger.info("[PayPal] Duplicate IPN for txn=%s — skipping", txn_id)
            return {"received": True, "processed": False, "reason": "duplicate"}

    if payment_status in {"Refunded", "Reversed", "Canceled_Reversal"}:
        parent_txn_id = form.get("parent_txn_id", "").strip()
        try:
            adjustment_amount = Decimal(mc_gross).quantize(Decimal("0.01"))
            adjustment_cents = abs(int(adjustment_amount * 100)) if adjustment_amount.is_finite() else 0
        except (InvalidOperation, ValueError, OverflowError):
            adjustment_cents = 0
        if not parent_txn_id or adjustment_cents <= 0:
            await r.delete(txn_key)
            return {"received": True, "processed": False, "reason": "invalid_adjustment"}

        state = {
            "Refunded": "refund_reported",
            "Reversed": "reversal_reported",
            "Canceled_Reversal": "reversal_cancelled",
        }[payment_status]
        try:
            await r.set(f"{R_ADJUSTMENT_STATE_PREFIX}{parent_txn_id}", state)
            projection_result = await _apply_public_payment_adjustment(
                r,
                f"paypal:{parent_txn_id}",
                adjustment_cents,
                {
                    "Refunded": "paypal_refund_delta",
                    "Reversed": "paypal_reversal",
                    "Canceled_Reversal": "paypal_reversal_cancelled",
                }[payment_status],
                f"paypal:{txn_id}",
            ) if provider_mode == "live" else {"applied": False, "reason": "test_mode"}
            pending_key = f"{R_PENDING_PAYPAL_ADJUSTMENT_PREFIX}{parent_txn_id}"
            if projection_result.get("reason") in {"payment_projection_missing", "payment_projection_busy"}:
                await _queue_pending_adjustment(
                    r,
                    pending_key,
                    {
                        "event_key": txn_key,
                        "adjustment_id": f"paypal:{txn_id}",
                        "amount_cents": adjustment_cents,
                        "adjustment_kind": {
                            "Refunded": "paypal_refund_delta",
                            "Reversed": "paypal_reversal",
                            "Canceled_Reversal": "paypal_reversal_cancelled",
                        }[payment_status],
                    },
                )
            elif provider_mode == "live":
                await _drain_pending_adjustments(
                    r,
                    pending_key,
                    f"paypal:{parent_txn_id}",
                )
            projection_pending = (
                provider_mode == "live"
                and projection_result.get("reason") in {
                    "payment_projection_missing", "payment_projection_busy",
                }
            )
            retry_required = (
                provider_mode == "live"
                and projection_result.get("reason") == "payment_projection_busy"
            )
            await _append_finance_event(r, {
                "event_id": f"paypal:{txn_id}",
                "event_type": payment_status.lower(),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "provider": "paypal",
                "provider_mode": provider_mode,
                "provider_reference": parent_txn_id,
                "adjustment_reference": txn_id,
                "amount_cents_reported": adjustment_cents,
                "currency": "EUR",
                "adjustment_state": state,
                "requires_manual_review": projection_pending,
            })
            await r.set(txn_key, "pending_payment" if projection_pending else "processed")
        except Exception:
            await r.set(txn_key, "accounting_review_required")
            raise
        if retry_required:
            await r.set(txn_key, "pending_payment")
            raise HTTPException(status_code=503, detail="Payment projection is busy")
        return {
            "received": True,
            "processed": not projection_pending,
            "adjustment_state": state,
            "requires_manual_review": projection_pending,
        }

    # Parse amount
    try:
        amount_decimal = Decimal(mc_gross).quantize(Decimal("0.01"))
        if not amount_decimal.is_finite():
            raise InvalidOperation
        amount_cents = int(amount_decimal * 100)
    except (InvalidOperation, ValueError, OverflowError):
        amount_decimal = Decimal("0")
        amount_cents = 0
    if not purpose or not _validate_payment_amount(purpose, amount_cents):
        await r.delete(txn_key)
        return {"received": True, "processed": False, "reason": "invalid_amount"}
    amount = float(amount_decimal)
    category = _payment_category(purpose)
    capture_state = await r.get(capture_key)
    if capture_state == "processed":
        await r.set(txn_key, "processed")
        return {"received": True, "processed": False, "reason": "duplicate"}

    accounting_mutated = False
    try:
        await _init_operating_funding(r)
        fulfillment_state = "not_applicable"
        allocation = None
        if capture_state != "recorded":
            allocation = await allocate_donation(amount, r)
            record = {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                "amount": amount,
                "currency": "EUR",
                "allocation": allocation,
                "method": "paypal",
                "txn_id": txn_id,
                "purpose": purpose,
                "category": category,
                "provider_mode": provider_mode,
                "fulfillment_state": fulfillment_state,
                "requires_accounting_review": True,
            }
            await _append_payment_record(r, record)
            accounting_mutated = True
        else:
            accounting_mutated = True
        await _append_finance_event(r, {
            "event_id": f"paypal:{txn_id}",
            "event_type": "payment_captured",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "provider": "paypal",
            "provider_reference": txn_id,
            "purpose": purpose,
            "category": category,
            "provider_mode": provider_mode,
            "amount_cents": amount_cents,
            "currency": "EUR",
            "fulfillment_state": fulfillment_state,
        })
        if provider_mode == "live":
            await _drain_pending_adjustments(
                r,
                f"{R_PENDING_PAYPAL_ADJUSTMENT_PREFIX}{txn_id}",
                f"paypal:{txn_id}",
            )
        await r.set(capture_key, "processed")
        await r.set(txn_key, "processed")
    except Exception:
        if accounting_mutated:
            await r.set(txn_key, "accounting_review_required")
        else:
            await r.delete(txn_key)
        raise

    logger.info("[PayPal] Payment %.2f %s classified as %s", amount, mc_currency, category)

    result = {"received": True, "processed": True, "allocation": allocation}
    if capture_state == "recorded":
        result["recovered"] = True
    return result


# ── Admin Payment Logs ───────────────────────────────────────────────────────

@router.get("/admin/logs")
async def admin_payment_logs(_auth: bool = Depends(verify_admin_key)):
    """Admin: Alle Zahlungen (letzte 50)."""
    r = await _get_redis()
    log_len = await r.llen(R_PAYMENTS)
    start = max(0, log_len - 50)
    raw_logs = await r.lrange(R_PAYMENTS, start, -1)
    logs = [_admin_payment_record(json.loads(x)) for x in raw_logs]
    logs.reverse()  # Neueste zuerst

    paypal_total = float(await r.get(R_PAYPAL_DONATIONS) or "0")
    paypal_count = int(await r.get(R_PAYPAL_COUNT) or "0")

    pending_reload = await r.get("hlr:paypal:pending_reload")

    return {
        "payments": logs,
        "total_count": log_len,
        "paypal": {
            "total_eur": round(paypal_total, 2),
            "count": paypal_count,
            "pending_hlr_reload": json.loads(pending_reload) if pending_reload else None,
        },
    }


@router.get("/admin/finance/events")
async def admin_finance_events(_auth: bool = Depends(verify_admin_key)):
    """PII-free provider events for the private finance integration."""
    r = await _get_redis()
    event_count = await r.llen(R_FINANCE_EVENTS)
    start = max(0, event_count - 200)
    raw_events = await r.lrange(R_FINANCE_EVENTS, start, -1)
    return {
        "events": [json.loads(item) for item in raw_events],
        "count": event_count,
        "contains_customer_data": False,
    }


# ── Blockchain Balance Endpoints ──────────────────────────────────────────────

BTC_ADDRESS = os.getenv("BTC_ADDRESS", "")
LTC_ADDRESS = os.getenv("LTC_ADDRESS", "")
ARWEAVE_ADDRESS = os.getenv("ARWEAVE_ADDRESS", "")
HETZNER_API_TOKEN = os.getenv("HETZNER_API_TOKEN", "")
HETZNER_MONTHLY = float(os.getenv("HETZNER_MONTHLY_COST", "15.00"))


@router.get("/admin/finance/server")
async def server_costs(_auth: bool = Depends(verify_admin_key)):
    """Hetzner Server Kosten — echte Daten via API (1h Redis cache)."""
    r = await _get_redis()
    cached = await r.get("finance:hetzner:cache")
    if cached:
        return json.loads(cached)
    if not HETZNER_API_TOKEN:
        return {"error": "HETZNER_API_TOKEN nicht gesetzt", "monthly_eur": HETZNER_MONTHLY, "source": "hardcoded"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.hetzner.cloud/v1/servers",
                headers={"Authorization": f"Bearer {HETZNER_API_TOKEN}"}
            )
            data = resp.json()
            servers = data.get("servers", [])
            total_monthly = 0.0
            server_list = []
            for s in servers:
                st = s.get("server_type", {})
                prices = st.get("prices", [])
                monthly = 0.0
                for p in prices:
                    if p.get("location") == s.get("datacenter", {}).get("location", {}).get("name"):
                        monthly = float(p.get("price_monthly", {}).get("gross", "0"))
                        break
                if not monthly and prices:
                    monthly = float(prices[0].get("price_monthly", {}).get("gross", "0"))
                total_monthly += monthly
                server_list.append({
                    "name": s.get("name"),
                    "type": st.get("name"),
                    "cores": st.get("cores"),
                    "ram_gb": st.get("memory"),
                    "disk_gb": st.get("disk"),
                    "status": s.get("status"),
                    "location": s.get("datacenter", {}).get("location", {}).get("name"),
                    "monthly_eur": round(monthly, 2),
                    "ipv4": s.get("public_net", {}).get("ipv4", {}).get("ip"),
                })
            result = {
                "servers": server_list,
                "total_monthly_eur": round(total_monthly, 2),
                "count": len(server_list),
                "source": "hetzner_api",
            }
            await r.setex("finance:hetzner:cache", 3600, json.dumps(result))
            return result
    except Exception as e:
        return {"error": str(e), "monthly_eur": HETZNER_MONTHLY, "source": "fallback"}


@router.get("/admin/finance/btc")
async def btc_balance(_auth: bool = Depends(verify_admin_key)):
    """BTC Wallet Balance via Blockstream API (30min Redis cache)."""
    if not BTC_ADDRESS:
        return {"error": "BTC_ADDRESS is not configured"}
    r = await _get_redis()
    cached = await r.get("finance:btc:cache")
    if cached:
        return json.loads(cached)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://blockstream.info/api/address/{BTC_ADDRESS}")
            data = resp.json()
            funded = data.get("chain_stats", {}).get("funded_txo_sum", 0)
            spent = data.get("chain_stats", {}).get("spent_txo_sum", 0)
            balance_sat = funded - spent
            balance_btc = balance_sat / 1e8
            tx_count = data.get("chain_stats", {}).get("tx_count", 0)
            # EUR price from CoinGecko
            price_resp = await client.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur")
            btc_eur = price_resp.json().get("bitcoin", {}).get("eur", 0)
            result = {"address": BTC_ADDRESS, "balance_btc": round(balance_btc, 8), "balance_eur": round(balance_btc * btc_eur, 2), "btc_eur": btc_eur, "tx_count": tx_count}
            await r.setex("finance:btc:cache", 1800, json.dumps(result))
            return result
    except Exception as e:
        return {"address": BTC_ADDRESS, "error": str(e), "balance_btc": 0, "balance_eur": 0}


@router.get("/admin/finance/ltc")
async def ltc_balance(_auth: bool = Depends(verify_admin_key)):
    """LTC Wallet Balance via Blockcypher API (30min Redis cache)."""
    if not LTC_ADDRESS:
        return {"error": "LTC_ADDRESS is not configured"}
    r = await _get_redis()
    cached = await r.get("finance:ltc:cache")
    if cached:
        return json.loads(cached)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://api.blockcypher.com/v1/ltc/main/addrs/{LTC_ADDRESS}/balance")
            data = resp.json()
            balance_sat = data.get("balance", 0)
            balance_ltc = balance_sat / 1e8
            tx_count = data.get("n_tx", 0)
            price_resp = await client.get("https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=eur")
            ltc_eur = price_resp.json().get("litecoin", {}).get("eur", 0)
            result = {"address": LTC_ADDRESS, "balance_ltc": round(balance_ltc, 8), "balance_eur": round(balance_ltc * ltc_eur, 2), "ltc_eur": ltc_eur, "tx_count": tx_count}
            await r.setex("finance:ltc:cache", 1800, json.dumps(result))
            return result
    except Exception as e:
        return {"address": LTC_ADDRESS, "error": str(e), "balance_ltc": 0, "balance_eur": 0}


@router.get("/admin/finance/overview")
async def finance_overview(_auth: bool = Depends(verify_admin_key)):
    """Vollstaendige Finanzuebersicht — alle Quellen kombiniert."""
    r = await _get_redis()
    await _init_operating_funding(r)

    # Einnahmen
    server_received = float(await r.get(R_SERVER_RECEIVED) or "0")
    domain_received = float(await r.get(R_DOMAIN_RECEIVED) or "0")
    reserve = float(await r.get(R_RESERVE) or "0")
    paypal_total = float(await r.get(R_PAYPAL_DONATIONS) or "0")
    paypal_count = int(await r.get(R_PAYPAL_COUNT) or "0")

    # BTC + LTC (aus Cache)
    btc_cache = json.loads(await r.get("finance:btc:cache") or "{}")
    ltc_cache = json.loads(await r.get("finance:ltc:cache") or "{}")
    btc_eur = btc_cache.get("balance_eur", 0)
    ltc_eur = ltc_cache.get("balance_eur", 0)

    # HLR Credits
    hlr_primary_remaining = int(await r.get("hlr:hlrlookupcom:used") or "0")
    hlr_primary_remaining = max(0, 2499 - hlr_primary_remaining)
    hlr_fallback_remaining = int(await r.get("hlr:used") or "0")
    hlr_fallback_remaining = max(0, 1000 - hlr_fallback_remaining)
    hlr_primary_eur = round(hlr_primary_remaining * 0.006, 2)

    # Ausgaben — echte Hetzner-Kosten wenn verfuegbar
    months = _months_elapsed(SERVER_START)
    hetzner_cache = json.loads(await r.get("finance:hetzner:cache") or "{}")
    actual_monthly = hetzner_cache.get("total_monthly_eur", HETZNER_MONTHLY)
    server_cost_total = months * actual_monthly

    # Arweave (aus eigener API)
    ar_cache = None
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            ar_resp = await client.get("http://localhost:8000/api/v1/arweave/status")
            ar_cache = ar_resp.json()
    except Exception:
        pass
    ar_balance = ar_cache.get("balance_ar", 0) if ar_cache else 0

    total_einnahmen = server_received + domain_received + reserve + btc_eur + ltc_eur
    total_ausgaben_monatlich = HETZNER_MONTHLY
    saldo = total_einnahmen - server_cost_total
    runway_monate = int(saldo / HETZNER_MONTHLY) if HETZNER_MONTHLY > 0 and saldo > 0 else 0

    return {
        "einnahmen": {
            "paypal_gesamt": paypal_total,
            "paypal_count": paypal_count,
            "server_received": server_received,
            "domain_received": domain_received,
            "btc_eur": btc_eur,
            "ltc_eur": ltc_eur,
            "reserve": reserve,
            "gesamt": round(total_einnahmen, 2),
        },
        "ausgaben": {
            "server_monatlich": actual_monthly,
            "server_gesamt": round(server_cost_total, 2),
            "hlr_verbraucht_credits": 2499 - hlr_primary_remaining,
            "gesamt_monatlich": round(total_ausgaben_monatlich, 2),
        },
        "wallets": {
            "btc": btc_cache,
            "ltc": ltc_cache,
            "arweave": {"balance_ar": ar_balance, "address": ARWEAVE_ADDRESS},
            "hlr_primary": {"remaining": hlr_primary_remaining, "eur": hlr_primary_eur},
            "hlr_fallback": {"remaining": hlr_fallback_remaining},
        },
        "saldo": round(saldo, 2),
        "runway_monate": runway_monate,
        "server_gedeckt_bis": f"{months + runway_monate} Monate ab Start",
        "letztes_update": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/public/finance")
async def public_finance_overview():
    """Oeffentlicher Transparenz-Endpoint — nur Summen, keine Details."""
    r = await _get_redis()
    projection = await _load_public_support_projection(r)
    server_received = projection["server"]
    months = _months_elapsed(SERVER_START)
    server_cost = months * HETZNER_MONTHLY
    server_balance = round(server_received - server_cost, 2)
    runway = int(server_balance / HETZNER_MONTHLY) if server_balance > 0 else 0

    hlr_remaining = max(0, 2499 - int(await r.get("hlr:hlrlookupcom:used") or "0"))
    payment_count = projection["count"]

    return {
        "server_gedeckt_monate": runway,
        "hlr_verifikationen_moeglich": hlr_remaining,
        "spenden_gesamt": payment_count,
        "transparenz": "Alle Einnahmen und Ausgaben sind oeffentlich einsehbar auf community.html",
    }
