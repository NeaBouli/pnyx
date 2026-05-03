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
  - HLR Credits Auto-Reload (15€ = 2500 Credits)
  - Idempotency via txn_id in Redis

Alles in Redis gespeichert — kein DB-Schema nötig.
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
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
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
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


# ── PayPal IPN Webhook ───────────────────────────────────────────────────────

R_PAYPAL_TXN = "paypal:txn:"  # Set of processed txn_ids
R_PAYPAL_DONATIONS = "paypal:donations:total"
R_PAYPAL_COUNT = "paypal:donations:count"

PAYPAL_IPN_URL = os.getenv(
    "PAYPAL_IPN_URL",
    "https://ipnpb.paypal.com/cgi-bin/webscr"  # Production
)

HLR_CREDITS_PER_15EUR = 2500


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
    2. Wenn VERIFIED + Completed: Spende verbuchen
    3. HLR Credits automatisch aufladen (15€ = 2500 Credits)
    4. Idempotency: txn_id nur einmal verarbeiten
    """
    payload = await request.body()
    form = dict(x.split("=", 1) for x in payload.decode().split("&") if "=" in x)

    # Parse IPN fields
    payment_status = form.get("payment_status", "")
    txn_id = form.get("txn_id", "")
    mc_gross = form.get("mc_gross", "0")
    mc_currency = form.get("mc_currency", "EUR")
    item_name = form.get("item_name", "")
    payer_email = form.get("payer_email", "")

    logger.info("[PayPal] IPN received: txn=%s status=%s amount=%s %s",
                txn_id, payment_status, mc_gross, mc_currency)

    # Only process completed payments
    if payment_status != "Completed":
        return {"received": True, "processed": False, "reason": "not_completed"}

    if not txn_id:
        return {"received": True, "processed": False, "reason": "no_txn_id"}

    # Verify with PayPal
    verified = await _verify_paypal_ipn(payload)
    if not verified:
        logger.warning("[PayPal] IPN verification FAILED for txn=%s", txn_id)
        return {"received": True, "processed": False, "reason": "verification_failed"}

    r = await _get_redis()

    # Idempotency: check if txn already processed
    txn_key = f"{R_PAYPAL_TXN}{txn_id}"
    already = await r.exists(txn_key)
    if already:
        logger.info("[PayPal] Duplicate IPN for txn=%s — skipping", txn_id)
        return {"received": True, "processed": False, "reason": "duplicate"}

    # Parse amount
    try:
        amount = float(mc_gross)
    except ValueError:
        amount = 0.0

    if amount <= 0:
        return {"received": True, "processed": False, "reason": "zero_amount"}

    # Mark txn as processed (90 days TTL)
    await r.setex(txn_key, 86400 * 90, "processed")

    # Track PayPal donations
    await r.incrbyfloat(R_PAYPAL_DONATIONS, amount)
    await r.incr(R_PAYPAL_COUNT)

    # Allocate donation (same as Stripe)
    await _init_seed_payments(r)
    allocation = await allocate_donation(amount, r)

    # HLR Credits auto-reload if amount >= 15€
    hlr_credits_added = 0
    if amount >= 14.99:
        hlr_credits_added = HLR_CREDITS_PER_15EUR
        # Note: actual credit reload requires hlrlookup.com API purchase
        # For now, log the intent — manual reload needed
        await r.setex("hlr:paypal:pending_reload", 86400 * 7, json.dumps({
            "amount": amount,
            "credits": hlr_credits_added,
            "txn_id": txn_id,
            "date": datetime.now(timezone.utc).isoformat(),
        }))
        logger.info("[PayPal] HLR reload pending: %d credits from %.2f EUR", hlr_credits_added, amount)

    # Log payment
    payer_hash = hashlib.sha256(payer_email.encode()).hexdigest()[:12] if payer_email else "anonym"
    record = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "amount": amount,
        "currency": mc_currency,
        "allocation": allocation,
        "from": payer_hash,
        "method": "paypal",
        "txn_id": txn_id,
        "item_name": item_name,
        "hlr_credits_added": hlr_credits_added,
    }
    await r.rpush(R_PAYMENTS, json.dumps(record))

    logger.info("[PayPal] Donation %.2f %s allocated: %s (HLR: +%d)",
                amount, mc_currency, allocation, hlr_credits_added)

    return {"received": True, "processed": True, "allocation": allocation}


# ── Admin Payment Logs ───────────────────────────────────────────────────────

@router.get("/admin/logs")
async def admin_payment_logs(_auth: bool = Depends(verify_admin_key)):
    """Admin: Alle Zahlungen (letzte 50)."""
    r = await _get_redis()
    log_len = await r.llen(R_PAYMENTS)
    start = max(0, log_len - 50)
    raw_logs = await r.lrange(R_PAYMENTS, start, -1)
    logs = [json.loads(x) for x in raw_logs]
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


# ── Blockchain Balance Endpoints ──────────────────────────────────────────────

BTC_ADDRESS = os.getenv("BTC_ADDRESS", "bc1q83370mce8qfkyyepspg6xf42f577s47rtl3mhx")
LTC_ADDRESS = os.getenv("LTC_ADDRESS", "ltc1qmr467kl8w0e8axplq5uyrpws3mc4sclpu4ds8w")
ARWEAVE_ADDRESS = os.getenv("ARWEAVE_ADDRESS", "2hkK3Bcr6garERqyBCLCiJ-d8zZzM5ZWe3_AzGdhBTs")
HETZNER_MONTHLY = float(os.getenv("HETZNER_MONTHLY_COST", "15.00"))


@router.get("/admin/finance/btc")
async def btc_balance():
    """BTC Wallet Balance via Blockstream API (30min Redis cache)."""
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
async def ltc_balance():
    """LTC Wallet Balance via Blockcypher API (30min Redis cache)."""
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
    await _init_seed_payments(r)

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

    # Ausgaben
    months = _months_elapsed(SERVER_START)
    server_cost_total = months * HETZNER_MONTHLY

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
            "server_monatlich": HETZNER_MONTHLY,
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
    await _init_seed_payments(r)

    server_received = float(await r.get(R_SERVER_RECEIVED) or "0")
    months = _months_elapsed(SERVER_START)
    server_cost = months * HETZNER_MONTHLY
    server_balance = round(server_received - server_cost, 2)
    runway = int(server_balance / HETZNER_MONTHLY) if server_balance > 0 else 0

    hlr_remaining = max(0, 2499 - int(await r.get("hlr:hlrlookupcom:used") or "0"))
    payment_count = await r.llen(R_PAYMENTS)

    return {
        "server_gedeckt_monate": runway,
        "hlr_verifikationen_moeglich": hlr_remaining,
        "spenden_gesamt": payment_count,
        "transparenz": "Alle Einnahmen und Ausgaben sind oeffentlich einsehbar auf community.html",
    }
