"""
ekklesia.gr Business Logic Monitor — 3-Tier Auto-Recovery
Runs every 30 minutes (daemon) or once daily at 06:00 UTC (cron).
17 rules. Recovery: T1 API → T2 Docker Restart → T3 Telegram Escalation.
"""
import os
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import httpx
import psycopg2
import redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("monitor")

# ─── Config ──────────────────────────────────────────────────────────────────

DB_URL = os.getenv("DATABASE_URL", "postgresql://ekklesia:devpassword@db:5432/ekklesia_prod")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
CHECK_INTERVAL = int(os.getenv("MONITOR_INTERVAL_SECONDS", "1800"))
API_URL = os.getenv("API_URL", "http://api:8000")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")
AUTO_RECOVERY_T2 = os.getenv("AUTO_RECOVERY_T2", "false").lower() == "true"
PARLIAMENT_SOURCE_FRESHNESS_ENABLED = os.getenv("PARLIAMENT_SOURCE_FRESHNESS_ENABLED", "true").lower() == "true"
PARLIAMENT_SOURCE_MAX_LAG_HOURS = int(os.getenv("PARLIAMENT_SOURCE_MAX_LAG_HOURS", "36"))
ZK_PENDING_MAX_HOURS = int(os.getenv("ZK_PENDING_MAX_HOURS", "24"))

# T2 Allowlist — HARDCODED, never restart DB/Redis/Traefik/Discourse
T2_ALLOWED_SERVICES = {"ekklesia-api", "ekklesia-web"}
T2_MAX_RESTARTS_PER_HOUR = 2


# ─── Alert Dataclass ─────────────────────────────────────────────────────────

@dataclass
class Alert:
    type: str
    service: str
    severity: str       # "warning" | "critical"
    message: str
    recovery_allowed: bool


# ─── T1 Mapping: alert.type → API endpoint ───────────────────────────────────

T1_MAPPING = {
    "scraper_parliament_stale": "/api/v1/admin/scraper/catch-up",
    "parliament_source_lag":     "/api/v1/admin/scraper/catch-up",
    "scraper_diavgeia_stale":   "/api/v1/admin/scraper/catch-up",
    "forum_sync_errors":        "/api/v1/admin/forum/resync-all",
    "forum_content_empty":      "/api/v1/admin/forum/resync-all",
}

# Longer cooldown for expensive operations
T1_LOCK_TTL = {
    "/api/v1/admin/forum/resync-all": 7200,  # 2h
}
T1_DEFAULT_LOCK_TTL = 3600  # 1h


# ─── Telegram ────────────────────────────────────────────────────────────────

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


# ─── Connections ─────────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(DB_URL)


def get_redis():
    return redis.from_url(REDIS_URL, decode_responses=True)


# ─── 3-Tier Recovery ────────────────────────────────────────────────────────

def attempt_tier1(alert: Alert, r) -> bool:
    """Tier 1: Trigger API recovery endpoint."""
    endpoint = T1_MAPPING.get(alert.type)
    if not endpoint or not ADMIN_KEY:
        return False

    lock_key = f"lock:recovery:{alert.type}"
    ttl = T1_LOCK_TTL.get(endpoint, T1_DEFAULT_LOCK_TTL)
    if not r.set(lock_key, "1", ex=ttl, nx=True):
        logger.info("[T1] Lock active for %s — skipping (cooldown %ds)", alert.type, ttl)
        return True  # Already attempted recently, treat as handled

    try:
        resp = httpx.post(
            f"{API_URL}{endpoint}",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            timeout=30,
        )
        if resp.status_code in (200, 202):
            logger.info("[T1] Recovery OK: %s → %s → HTTP %d", alert.type, endpoint, resp.status_code)
            return True
        logger.warning("[T1] Recovery FAILED: %s → %s → HTTP %d", alert.type, endpoint, resp.status_code)
    except Exception as e:
        logger.error("[T1] Recovery ERROR: %s → %s: %s", alert.type, endpoint, e)

    # Remove lock on failure so next cycle can retry
    r.delete(lock_key)
    return False


def attempt_tier2(alert: Alert, r) -> bool:
    """Tier 2: Docker container restart via socket proxy."""
    if not AUTO_RECOVERY_T2:
        logger.info("[T2] Disabled (AUTO_RECOVERY_T2=false) — skipping")
        return False

    service = alert.service
    if not service or service not in T2_ALLOWED_SERVICES:
        logger.info("[T2] Service '%s' not in allowlist — skipping", service)
        return False

    lock_key = f"lock:restart:{service}"
    if not r.set(lock_key, "1", ex=3600, nx=True):
        logger.info("[T2] Restart lock active for %s — skipping", service)
        return True  # Already restarted recently

    counter_key = f"restart_count:{service}"
    count = r.incr(counter_key)
    if count == 1:
        r.expire(counter_key, 3600)

    if count > T2_MAX_RESTARTS_PER_HOUR:
        logger.warning("[T2] Max restarts exceeded for %s (%d/%d) — escalating", service, count, T2_MAX_RESTARTS_PER_HOUR)
        return False

    try:
        import docker
        client = docker.DockerClient(base_url=os.getenv("DOCKER_HOST", "tcp://docker-proxy:2375"))
        container = client.containers.get(service)
        container.restart(timeout=30)
        logger.info("[T2] Restarted %s (attempt %d/%d)", service, count, T2_MAX_RESTARTS_PER_HOUR)
        return True
    except Exception as e:
        logger.error("[T2] Restart FAILED for %s: %s", service, e)
        r.delete(lock_key)
    return False


def escalate_tier3(alert: Alert, recovery_result: str = ""):
    """Tier 3: Telegram escalation — always fires as last resort."""
    severity_icon = "🔴" if alert.severity == "critical" else "🟡"
    msg = (
        f"{severity_icon} <b>T3 Escalation</b>\n\n"
        f"<b>Type:</b> {alert.type}\n"
        f"<b>Service:</b> {alert.service or '—'}\n"
        f"<b>Severity:</b> {alert.severity}\n"
        f"<b>Message:</b> {alert.message}\n"
    )
    if recovery_result:
        msg += f"<b>Recovery:</b> {recovery_result}\n"
    msg += f"\n<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>"
    send_telegram(msg)
    logger.warning("[T3] Escalated: %s — %s", alert.type, alert.message)


def attempt_recovery(alert: Alert, r):
    """Dispatcher: T1 → T2 → T3."""
    if not alert.recovery_allowed:
        escalate_tier3(alert, "Direct T3 — no auto-recovery for this type")
        return "T3"

    # Tier 1
    if alert.type in T1_MAPPING:
        if attempt_tier1(alert, r):
            return "T1"

    # Tier 2
    if alert.service:
        if attempt_tier2(alert, r):
            return "T2"

    # Tier 3
    escalate_tier3(alert, "T1+T2 failed or not applicable")
    return "T3"


# ─── Health Checks (return Alert objects) ───────────────────────────────────

def check_scraper_stale(r) -> list[Alert]:
    alerts = []
    last_success = r.get("scraper:parliament:last_success")
    if last_success:
        age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last_success)).total_seconds() / 3600
        if age_h > 48:
            alerts.append(Alert("scraper_parliament_stale", "ekklesia-api", "warning",
                                f"Parliament Scraper: kein Erfolg seit {age_h:.0f}h", True))
    return alerts


def check_no_new_bills(conn) -> list[Alert]:
    alerts = []
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(created_at) FROM parliament_bills")
        latest = cur.fetchone()[0]
        if latest:
            age = (datetime.now() - latest).days
            if age > 7:
                alerts.append(Alert("no_new_bills", "", "warning",
                                    f"Keine neuen Bills seit {age} Tagen", False))
    return alerts


def _as_utc_datetime(value) -> datetime | None:
    """Normalize source/DB timestamps to aware UTC datetimes."""
    if not value:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            value = datetime.fromisoformat(text)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _bill_source_activity(bill: dict) -> datetime | None:
    """Return the official activity date from a scraped Parliament bill."""
    return _as_utc_datetime(bill.get("date") or bill.get("submitted_date"))


def _latest_source_activity(bills: list[dict]) -> datetime | None:
    dates = [_bill_source_activity(bill) for bill in bills]
    dates = [dt for dt in dates if dt is not None]
    return max(dates) if dates else None


def _db_latest_parliament_activity(conn) -> datetime | None:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT MAX(GREATEST(
                COALESCE(parliament_vote_date, TIMESTAMP '1970-01-01'),
                COALESCE(submitted_date, TIMESTAMP '1970-01-01')
            ))
            FROM parliament_bills
            WHERE source = 'PARLIAMENT'
              AND id NOT LIKE 'DEMO-%%'
        """)
        return _as_utc_datetime(cur.fetchone()[0])


def check_parliament_source_freshness(conn) -> list[Alert]:
    """Compare live Parliament source freshness with DB freshness.

    This catches the failure mode where the scraper still "runs" but misses a
    newer official Parliament index format.
    """
    alerts = []
    if not PARLIAMENT_SOURCE_FRESHNESS_ENABLED:
        return alerts

    try:
        resp = httpx.get(f"{API_URL}/api/v1/scraper/parliament/latest?limit=5", timeout=45)
        if resp.status_code != 200:
            alerts.append(Alert(
                "parliament_source_check_failed", "ekklesia-api", "warning",
                f"Parliament source freshness check failed: HTTP {resp.status_code}", False,
            ))
            return alerts

        payload = resp.json()
        source_latest = _latest_source_activity(payload.get("bills", []))
        if not source_latest:
            alerts.append(Alert(
                "parliament_source_check_failed", "ekklesia-api", "warning",
                "Parliament source freshness check returned no dated bills", False,
            ))
            return alerts

        db_latest = _db_latest_parliament_activity(conn)
        if not db_latest:
            alerts.append(Alert(
                "parliament_source_lag", "ekklesia-api", "warning",
                f"Parliament-DB leer, Quelle hat Bills bis {source_latest.strftime('%d.%m.%Y')}", True,
            ))
            return alerts

        lag_h = (source_latest - db_latest).total_seconds() / 3600
        if lag_h > PARLIAMENT_SOURCE_MAX_LAG_HOURS:
            alerts.append(Alert(
                "parliament_source_lag", "ekklesia-api", "warning",
                (
                    "Parliament-DB hinter Quelle: "
                    f"Quelle {source_latest.strftime('%d.%m.%Y')}, "
                    f"DB {db_latest.strftime('%d.%m.%Y')} ({lag_h:.0f}h)"
                ),
                True,
            ))
    except Exception as e:
        alerts.append(Alert(
            "parliament_source_check_failed", "ekklesia-api", "warning",
            f"Parliament source freshness check error: {str(e)[:120]}", False,
        ))
    return alerts


def check_lifecycle_stuck(conn, r=None) -> list[Alert]:
    alerts = []
    now = datetime.now()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, status, parliament_vote_date FROM parliament_bills
            WHERE parliament_vote_date IS NOT NULL
              AND parliament_vote_date < %s
              AND status IN ('ANNOUNCED', 'ACTIVE', 'WINDOW_24H')
        """, (now - timedelta(days=1),))
        for bill_id, status, vote_date in cur.fetchall():
            # Cooldown: suppress same bill alert for 1h
            if r:
                lock_key = f"lock:alert:lifecycle_stuck:{bill_id}"
                if not r.set(lock_key, "1", ex=3600, nx=True):
                    logger.info("[COOLDOWN] lifecycle_stuck suppressed for %s", bill_id)
                    continue
            alerts.append(Alert("lifecycle_stuck", "ekklesia-api", "warning",
                                f"Bill {bill_id} stuck in {status} (vote: {vote_date.strftime('%d.%m.%Y')})", False))
    return alerts


def check_forum_missing(conn) -> list[Alert]:
    alerts = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title_el FROM parliament_bills
            WHERE status = 'ACTIVE' AND forum_topic_id IS NULL
        """)
        for bill_id, title in cur.fetchall():
            alerts.append(Alert("forum_missing", "ekklesia-api", "warning",
                                f"Bill {bill_id} ACTIVE ohne Forum: {title[:50]}", False))
    return alerts


def check_arweave_pending(conn) -> list[Alert]:
    alerts = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM parliament_bills
            WHERE status IN ('PARLIAMENT_VOTED', 'OPEN_END')
              AND arweave_tx_id IS NULL
              AND party_votes_parliament IS NOT NULL
              AND id NOT LIKE 'DEMO-%%'
              AND source = 'PARLIAMENT'
              AND (status_changed_at IS NULL OR status_changed_at < NOW() - INTERVAL '24 hours')
        """)
        count = cur.fetchone()[0]
        if count > 0:
            alerts.append(Alert("arweave_pending", "", "warning",
                                f"Arweave: {count} Parliament-Bills ohne Archivierung (>24h)", False))
    return alerts


def check_hlr_credits() -> list[Alert]:
    alerts = []
    try:
        r = httpx.get(f"{API_URL}/api/v1/admin/hlr/credits", timeout=5)
        if r.status_code == 200:
            credits = r.json().get("primary", {}).get("credits", 9999)
            if credits < 100:
                alerts.append(Alert("hlr_low", "", "critical",
                                    f"HLR Credits niedrig: {credits}", False))
    except Exception:
        pass
    return alerts


def check_forum_sync_errors(r) -> list[Alert]:
    alerts = []
    try:
        count = int(r.get("scraper:forum_sync:error_count") or 0)
    except (ValueError, TypeError):
        count = 0
    if count > 10:
        last_err = r.get("scraper:forum_sync:last_error") or "unknown"
        alerts.append(Alert("forum_sync_errors", "ekklesia-api", "warning",
                            f"Forum Sync: {count} Fehler — {last_err[:80]}", True))
    return alerts


def check_api_health() -> list[Alert]:
    alerts = []
    try:
        resp = httpx.get(f"{API_URL}/api/v1/bills?limit=1", timeout=10)
        if resp.status_code != 200:
            alerts.append(Alert("api_unhealthy", "ekklesia-api", "critical",
                                f"API Health-Check FAIL: HTTP {resp.status_code}", True))
    except Exception as e:
        alerts.append(Alert("api_unhealthy", "ekklesia-api", "critical",
                            f"API nicht erreichbar: {e}", True))
    return alerts


def check_disk_usage() -> list[Alert]:
    alerts = []
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        pct = used / total * 100
        if pct > 90:
            free_gb = free / (1024**3)
            alerts.append(Alert("disk_critical", "", "critical",
                                f"Disk {pct:.0f}% voll — {free_gb:.1f} GB frei", False))
    except Exception:
        pass
    return alerts


def check_db_consistency(conn) -> list[Alert]:
    alerts = []
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM parliament_bills WHERE source IS NULL AND id NOT LIKE 'DEMO-%%'")
        null_source = cur.fetchone()[0]
        if null_source > 0:
            alerts.append(Alert("db_inconsistent", "", "warning",
                                f"DB: {null_source} Bills ohne source", False))
        cur.execute("SELECT COUNT(*) FROM parliament_bills WHERE governance_level IS NULL AND id NOT LIKE 'DEMO-%%'")
        null_gov = cur.fetchone()[0]
        if null_gov > 0:
            alerts.append(Alert("db_inconsistent", "", "warning",
                                f"DB: {null_gov} Bills ohne governance_level", False))
    return alerts


def check_diavgeia_scraper(r) -> list[Alert]:
    alerts = []
    last_run = r.get("scraper:diavgeia_municipal:last_run")
    if last_run:
        try:
            age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last_run)).total_seconds() / 3600
            if age_h > 96:
                alerts.append(Alert("scraper_diavgeia_stale", "ekklesia-api", "warning",
                                    f"Diavgeia Scraper: kein Run seit {age_h:.0f}h", True))
        except (ValueError, TypeError):
            pass
    return alerts


def check_web_urls() -> list[Alert]:
    alerts = []
    urls = [
        ("Landing", "https://ekklesia.gr/"),
        ("Bills", "https://ekklesia.gr/el/bills"),
        ("Results", "https://ekklesia.gr/el/results"),
        ("API Bills", f"{API_URL}/api/v1/bills?limit=1"),
    ]
    for name, url in urls:
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code != 200:
                alerts.append(Alert("web_down", "ekklesia-web", "critical",
                                    f"Web {name}: HTTP {resp.status_code}", True))
        except Exception as e:
            alerts.append(Alert("web_down", "ekklesia-web", "critical",
                                f"Web {name} nicht erreichbar: {e}", True))
    return alerts


def check_arweave_wallet() -> list[Alert]:
    alerts = []
    try:
        resp = httpx.get(f"{API_URL}/api/v1/scraper/status", timeout=10)
        if resp.status_code == 200:
            balance = resp.json().get("arweave_balance_ar", 999)
            if isinstance(balance, (int, float)) and balance < 0.1:
                alerts.append(Alert("arweave_low", "", "critical",
                                    f"Arweave Wallet niedrig: {balance:.4f} AR", False))
    except Exception:
        pass
    return alerts


def check_forum_completeness(conn) -> list[Alert]:
    alerts = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM parliament_bills
            WHERE status IN ('ACTIVE', 'WINDOW_24H', 'OPEN_END')
              AND forum_topic_id IS NULL
              AND id NOT LIKE 'DEMO-%%'
              AND created_at < NOW() - INTERVAL '1 hour'
        """)
        count = cur.fetchone()[0]
        if count > 0:
            alerts.append(Alert("forum_content_empty", "ekklesia-api", "warning",
                                f"Forum: {count} Bills ohne Topic", True))
    return alerts


def check_scraper_jobs(r) -> list[Alert]:
    alerts = []
    job_names = ["parliament", "diavgeia_municipal", "bill_lifecycle",
                 "cplm_refresh", "greek_topics", "notify_new_bills", "notify_results"]
    for name in job_names:
        try:
            count = int(r.get(f"scraper:{name}:error_count") or 0)
        except (ValueError, TypeError):
            count = 0
        if count > 20:
            alerts.append(Alert("scraper_job_errors", "ekklesia-api", "warning",
                                f"Job {name}: {count} Fehler", False))
    return alerts


def _rollback_if_possible(conn) -> None:
    rollback = getattr(conn, "rollback", None)
    if callable(rollback):
        rollback()


def _is_missing_zk_schema_error(exc: Exception) -> bool:
    name = exc.__class__.__name__
    if name in {"UndefinedTable", "UndefinedColumn"}:
        return True
    text = str(exc).lower()
    return (
        ("zk_vote_receipts" in text and "does not exist" in text)
        or ("zk_merkle_roots" in text and "does not exist" in text)
    )


def check_zk_canary_health(conn) -> list[Alert]:
    """Surface stuck ZK canary/publication states without auto-recovery."""
    alerts = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM zk_vote_receipts
                WHERE arweave_pending = TRUE
                  AND created_at < NOW() - (%s * INTERVAL '1 hour')
                """,
                (ZK_PENDING_MAX_HOURS,),
            )
            pending_count = cur.fetchone()[0]
            if pending_count > 0:
                alerts.append(Alert(
                    "zk_receipts_pending",
                    "ekklesia-api",
                    "warning",
                    f"ZK: {pending_count} vote receipts pending Arweave/publication >{ZK_PENDING_MAX_HOURS}h",
                    False,
                ))

            cur.execute(
                """
                SELECT COUNT(*)
                FROM zk_merkle_roots
                WHERE status NOT IN ('OPEN', 'CLOSED', 'ARCHIVED')
                """
            )
            invalid_roots = cur.fetchone()[0]
            if invalid_roots > 0:
                alerts.append(Alert(
                    "zk_root_invalid",
                    "ekklesia-api",
                    "critical",
                    f"ZK: {invalid_roots} Merkle roots have invalid status",
                    False,
                ))
    except Exception as exc:
        if _is_missing_zk_schema_error(exc):
            _rollback_if_possible(conn)
            logger.info("[ZK] Monitoring skipped; ZK storage schema is not present yet")
            return []
        raise
    return alerts


# ─── Main Loop ───────────────────────────────────────────────────────────────

def run_checks():
    logger.info("Running 17 business logic checks...")
    all_alerts: list[Alert] = []
    recovery_results: dict[str, str] = {}

    r = get_redis()
    conn = get_db()

    try:
        all_alerts.extend(check_scraper_stale(r))
        all_alerts.extend(check_no_new_bills(conn))
        all_alerts.extend(check_parliament_source_freshness(conn))
        all_alerts.extend(check_lifecycle_stuck(conn, r))
        all_alerts.extend(check_forum_missing(conn))
        all_alerts.extend(check_arweave_pending(conn))
        all_alerts.extend(check_hlr_credits())
        all_alerts.extend(check_forum_sync_errors(r))
        all_alerts.extend(check_api_health())
        all_alerts.extend(check_disk_usage())
        all_alerts.extend(check_db_consistency(conn))
        all_alerts.extend(check_diavgeia_scraper(r))
        all_alerts.extend(check_web_urls())
        all_alerts.extend(check_arweave_wallet())
        all_alerts.extend(check_forum_completeness(conn))
        all_alerts.extend(check_scraper_jobs(r))
        all_alerts.extend(check_zk_canary_health(conn))

        # Recovery pass
        for alert in all_alerts:
            tier = attempt_recovery(alert, r)
            recovery_results[alert.type] = tier

    finally:
        conn.close()
        r.close()

    if all_alerts:
        msg = f"<b>ekklesia.gr Monitor — {len(all_alerts)} Alerts</b>\n\n"
        for i, alert in enumerate(all_alerts, 1):
            tier = recovery_results.get(alert.type, "—")
            icon = "✓" if tier in ("T1", "T2") else "✗"
            msg += f"{i}. [{icon}{tier}] {alert.message}\n"
        msg += f"\n<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>"
        if len(msg) > 4000:
            msg = msg[:3950] + f"\n\n... (+{len(all_alerts)} total)"
        send_telegram(msg)
        logger.warning("ALERTS: %d issues found", len(all_alerts))
    else:
        logger.info("All checks passed — no alerts")

    return all_alerts


if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        logger.info("ekklesia.gr Health-Check (single run)")
        alerts = run_checks()
        sys.exit(1 if alerts else 0)
    else:
        logger.info("ekklesia.gr Monitor started (interval: %ds, T2: %s)", CHECK_INTERVAL, AUTO_RECOVERY_T2)
        while True:
            try:
                run_checks()
            except Exception as e:
                logger.error("Monitor error: %s", e)
            time.sleep(CHECK_INTERVAL)
