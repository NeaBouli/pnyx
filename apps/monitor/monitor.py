"""
ekklesia.gr Business Logic Monitor
Runs every 30 minutes. Checks 6 rules. Alerts via Telegram.
"""
import os
import time
import logging
from datetime import datetime, timezone, timedelta

import httpx
import psycopg2
import redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("monitor")

# Config from environment
DB_URL = os.getenv("DATABASE_URL", "postgresql://ekklesia:devpassword@db:5432/ekklesia_prod")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
CHECK_INTERVAL = int(os.getenv("MONITOR_INTERVAL_SECONDS", "1800"))  # 30 min
API_URL = os.getenv("API_URL", "http://api:8000")


def send_telegram(message: str) -> bool:
    if not TG_TOKEN or not TG_CHAT:
        logger.warning("[TG] Token or chat_id not set — skipping alert")
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.status_code == 200:
            logger.info("[TG] Alert sent")
            return True
        logger.warning("[TG] Send failed: %s", r.text[:200])
    except Exception as e:
        logger.error("[TG] Error: %s", e)
    return False


def get_db():
    return psycopg2.connect(DB_URL)


def get_redis():
    return redis.from_url(REDIS_URL, decode_responses=True)


def check_scraper_stale(r) -> list[str]:
    """Rule 1: Scraper 2x consecutive 0 bills."""
    alerts = []
    last_success = r.get("scraper:parliament:last_success")
    if not last_success:
        return alerts
    age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last_success)).total_seconds() / 3600
    if age_h > 48:
        alerts.append(f"Parliament Scraper: kein Erfolg seit {age_h:.0f}h")
    return alerts


def check_no_new_bills(conn) -> list[str]:
    """Rule 2: 7+ days no new bills."""
    alerts = []
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(created_at) FROM parliament_bills")
        latest = cur.fetchone()[0]
        if latest:
            age = (datetime.now() - latest).days
            if age > 7:
                alerts.append(f"Keine neuen Bills seit {age} Tagen (letzter: {latest.strftime('%d.%m')})")
    return alerts


def check_lifecycle_stuck(conn) -> list[str]:
    """Rule 3: Bills with past vote_date still in wrong status."""
    alerts = []
    now = datetime.now()
    with conn.cursor() as cur:
        # Bills that should have transitioned but didn't
        cur.execute("""
            SELECT id, status, parliament_vote_date FROM parliament_bills
            WHERE parliament_vote_date IS NOT NULL
              AND parliament_vote_date < %s
              AND status IN ('ANNOUNCED', 'ACTIVE', 'WINDOW_24H')
        """, (now - timedelta(days=1),))
        stuck = cur.fetchall()
        for bill_id, status, vote_date in stuck:
            alerts.append(f"Bill {bill_id} stuck in {status} (vote_date: {vote_date.strftime('%d.%m.%Y')})")
    return alerts


def check_forum_missing(conn) -> list[str]:
    """Rule 4: ACTIVE bill without forum thread."""
    alerts = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title_el FROM parliament_bills
            WHERE status = 'ACTIVE' AND forum_topic_id IS NULL
        """)
        for bill_id, title in cur.fetchall():
            alerts.append(f"Bill {bill_id} ACTIVE aber kein Forum-Thread: {title[:50]}")
    return alerts


def check_arweave_pending(conn) -> list[str]:
    """Rule 5: PARLIAMENT_VOTED/OPEN_END without arweave_tx_id for 24h+."""
    alerts = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, status, status_changed_at FROM parliament_bills
            WHERE status IN ('PARLIAMENT_VOTED', 'OPEN_END')
              AND arweave_tx_id IS NULL
              AND (status_changed_at IS NULL OR status_changed_at < NOW() - INTERVAL '24 hours')
        """)
        for bill_id, status, changed_at in cur.fetchall():
            alerts.append(f"Bill {bill_id} ({status}) — Arweave ausstehend")
    return alerts


def check_hlr_credits() -> list[str]:
    """Rule 6: HLR credits < 100."""
    alerts = []
    try:
        r = httpx.get(f"{API_URL}/api/v1/admin/hlr/credits", timeout=5)
        if r.status_code == 200:
            data = r.json()
            credits = data.get("primary", {}).get("credits", 9999)
            if credits < 100:
                alerts.append(f"HLR Credits niedrig: {credits} verbleibend")
    except Exception:
        pass  # HLR check is best-effort
    return alerts


def run_checks():
    logger.info("Running 6 business logic checks...")
    all_alerts = []

    r = get_redis()
    conn = get_db()

    try:
        all_alerts.extend(check_scraper_stale(r))
        all_alerts.extend(check_no_new_bills(conn))
        all_alerts.extend(check_lifecycle_stuck(conn))
        all_alerts.extend(check_forum_missing(conn))
        all_alerts.extend(check_arweave_pending(conn))
        all_alerts.extend(check_hlr_credits())
    finally:
        conn.close()
        r.close()

    if all_alerts:
        msg = "<b>ekklesia.gr Monitor Alert</b>\n\n"
        for i, alert in enumerate(all_alerts, 1):
            msg += f"{i}. {alert}\n"
        msg += f"\n<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>"
        send_telegram(msg)
        logger.warning("ALERTS: %d issues found", len(all_alerts))
    else:
        logger.info("All checks passed — no alerts")

    return all_alerts


if __name__ == "__main__":
    logger.info("ekklesia.gr Monitor started (interval: %ds)", CHECK_INTERVAL)
    while True:
        try:
            run_checks()
        except Exception as e:
            logger.error("Monitor error: %s", e)
        time.sleep(CHECK_INTERVAL)
