"""
MOD-18: Community Donations / Spenden
POST /api/v1/payments/webhook — Stripe Webhook (signature-verified)
GET  /api/v1/payments/status  — Öffentlicher Transparenz-Endpoint

Verteilungslogik:
  Eingehende Spenden werden automatisch priorisiert:
  1. Server (10€/Monat) — höchste Priorität, läuft ständig
  2. Domain (9,30€/Jahr) — niedrigere Frequenz
  3. Reserve — Überschuss als Puffer

Alles in Redis gespeichert — kein DB-Schema nötig.
"""
import json
import logging
import os
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
import redis.asyncio as aioredis

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

# Redis keys
R_PAYMENTS = "donations:log"          # List of JSON payment records
R_SERVER_RECEIVED = "donations:server:received"  # float
R_DOMAIN_RECEIVED = "donations:domain:received"  # float
R_RESERVE = "donations:reserve"       # float


async def _init_seed_payments(r: aioredis.Redis) -> None:
    """Seed initial payments if Redis is empty (first boot)."""
    exists = await r.exists(R_SERVER_RECEIVED)
    if not exists:
        # Seed: 20€ initial for server, 9.30€ for domain
        await r.set(R_SERVER_RECEIVED, "20.00")
        await r.set(R_DOMAIN_RECEIVED, "9.30")
        await r.set(R_RESERVE, "0.00")
        seed = [
            {"date": "2026-04-16", "amount": 20.00, "to": "server", "from": "Vendetta Labs (Seed)", "method": "manual"},
            {"date": "2026-03-29", "amount": 9.30, "to": "domain", "from": "Vendetta Labs (Registration)", "method": "manual"},
        ]
        for p in seed:
            await r.rpush(R_PAYMENTS, json.dumps(p))
        logger.info("[MOD-18] Seeded initial donation records")


# ── Verteilungsalgorithmus ────────────────────────────────────────────────────

async def allocate_donation(amount: float, r: aioredis.Redis) -> dict:
    """
    Verteilt eine Spende nach Priorität:
    1. Server: wenn Kontostand < 2 Monate Deckung → auffüllen
    2. Domain: wenn < 1 Jahr Deckung → auffüllen
    3. Rest → Reserve
    """
    now = datetime.utcnow()
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

    # Redis aktualisieren
    if allocation["server"] > 0:
        await r.incrbyfloat(R_SERVER_RECEIVED, allocation["server"])
    if allocation["domain"] > 0:
        await r.incrbyfloat(R_DOMAIN_RECEIVED, allocation["domain"])
    if allocation["reserve"] > 0:
        await r.incrbyfloat(R_RESERVE, allocation["reserve"])

    return allocation


def _months_elapsed(start_str: str) -> int:
    start = datetime.strptime(start_str, "%Y-%m-%d")
    now = datetime.utcnow()
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
    import stripe

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # Signatur verifizieren
    if webhook_secret:
        if not sig_header:
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.error.SignatureVerificationError:
            logger.warning("[MOD-18] Stripe signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid signature")
        except Exception as e:
            logger.error(f"[MOD-18] Webhook error: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # Kein Secret → parse raw (dev/testing)
        event = json.loads(payload)

    # Nur completed sessions verarbeiten
    event_type = event.get("type", "")
    if event_type != "checkout.session.completed":
        return {"received": True, "processed": False}

    session = event.get("data", {}).get("object", {})
    amount_total = session.get("amount_total", 0) / 100  # Cents → EUR
    customer_email = session.get("customer_details", {}).get("email", "anonym")

    if amount_total <= 0:
        return {"received": True, "processed": False}

    r = await _get_redis()
    await _init_seed_payments(r)

    # Spende verteilen
    allocation = await allocate_donation(amount_total, r)

    # Log
    record = {
        "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        "amount": amount_total,
        "allocation": allocation,
        "from": customer_email,
        "method": "stripe",
        "stripe_session": session.get("id", ""),
    }
    await r.rpush(R_PAYMENTS, json.dumps(record))

    logger.info(f"[MOD-18] Donation {amount_total}€ allocated: {allocation}")
    return {"received": True, "processed": True, "allocation": allocation}


# ── Public Status Endpoint ────────────────────────────────────────────────────

@router.get("/status")
async def payment_status():
    """
    Öffentlicher Transparenz-Endpoint — kein Auth.
    Liefert aktuelle Kontostände für community.html Kacheln.
    """
    r = await _get_redis()
    await _init_seed_payments(r)

    server_received = float(await r.get(R_SERVER_RECEIVED) or "0")
    domain_received = float(await r.get(R_DOMAIN_RECEIVED) or "0")
    reserve = float(await r.get(R_RESERVE) or "0")

    months_elapsed = _months_elapsed(SERVER_START)
    server_cost_total = months_elapsed * SERVER_COST_MONTHLY
    server_balance = round(server_received - server_cost_total, 2)

    domain_cost_total = DOMAIN_COST_YEARLY
    domain_balance = round(domain_received - domain_cost_total, 2)

    # Letzte Zahlung
    last_payment = None
    log_len = await r.llen(R_PAYMENTS)
    if log_len > 0:
        last_raw = await r.lindex(R_PAYMENTS, -1)
        if last_raw:
            last_payment = json.loads(last_raw)

    # Alle Zahlungen summieren
    total_received = server_received + domain_received + reserve

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
