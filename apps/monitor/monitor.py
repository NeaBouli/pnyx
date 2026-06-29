"""
ekklesia.gr Business Logic Monitor — 3-Tier Auto-Recovery
Runs every 30 minutes (daemon) or once daily at 06:00 UTC (cron).
18 rules. Recovery: T1 API → T2 Docker Restart → T3 Telegram Escalation.
"""
import hashlib
import json
import os
import time
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
import psycopg2
import redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("monitor")

_TELEGRAM_BOT_URL_RE = re.compile(r"(https://api\.telegram\.org/bot)[^/\s\"']+")


def _redact_log_secrets(value: Any) -> Any:
    if isinstance(value, str):
        return _TELEGRAM_BOT_URL_RE.sub(r"\1<redacted>", value)
    return value


def _redact_log_arg(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_log_secrets(value)
    rendered = str(value)
    redacted = _redact_log_secrets(rendered)
    if redacted != rendered:
        return redacted
    return value


class SecretRedactionFilter(logging.Filter):
    """Redact bearer-style secrets from third-party request logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_log_secrets(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_log_arg(arg) for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: _redact_log_arg(value) for key, value in record.args.items()}
        return True


def _install_secret_redaction_filter() -> None:
    redaction_filter = SecretRedactionFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redaction_filter)
    for name in ("httpx", "httpcore", "monitor"):
        logging.getLogger(name).addFilter(redaction_filter)


_install_secret_redaction_filter()

# ─── Config ──────────────────────────────────────────────────────────────────

DB_URL = os.getenv("DATABASE_URL", "postgresql://ekklesia:devpassword@db:5432/ekklesia_prod")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
CHECK_INTERVAL = int(os.getenv("MONITOR_INTERVAL_SECONDS", "1800"))
STARTUP_GRACE_SECONDS = max(0, int(os.getenv("MONITOR_STARTUP_GRACE_SECONDS", "90")))
REPAIR_VERIFY_WAIT_SECONDS = max(0, int(os.getenv("MONITOR_REPAIR_VERIFY_WAIT_SECONDS", "30")))
API_URL = os.getenv("API_URL", "http://api:8000")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")
AUTO_RECOVERY_T2 = os.getenv("AUTO_RECOVERY_T2", "false").lower() == "true"
PARLIAMENT_SOURCE_FRESHNESS_ENABLED = os.getenv("PARLIAMENT_SOURCE_FRESHNESS_ENABLED", "true").lower() == "true"
PARLIAMENT_SOURCE_MAX_LAG_HOURS = int(os.getenv("PARLIAMENT_SOURCE_MAX_LAG_HOURS", "36"))
PARLIAMENT_SOURCE_SAMPLE_LIMIT = min(20, max(5, int(os.getenv("PARLIAMENT_SOURCE_SAMPLE_LIMIT", "20"))))
PARLIAMENT_SOURCE_HTTP_RETRIES = max(1, int(os.getenv("PARLIAMENT_SOURCE_HTTP_RETRIES", "2")))
PARLIAMENT_SOURCE_HTTP_RETRY_DELAY_SECONDS = max(
    0,
    int(os.getenv("PARLIAMENT_SOURCE_HTTP_RETRY_DELAY_SECONDS", "5")),
)
ZK_PENDING_MAX_HOURS = int(os.getenv("ZK_PENDING_MAX_HOURS", "24"))
ZK_ARWEAVE_PUBLICATION_ENABLED = os.getenv("ZK_ARWEAVE_PUBLICATION_ENABLED", "false").lower() == "true"
ZK_ARWEAVE_SCOPE_ALLOWLIST = {
    value.strip()
    for value in os.getenv("ZK_ARWEAVE_SCOPE_ALLOWLIST", "").split(",")
    if value.strip()
}
ALERT_NOTIFY_COOLDOWN_SECONDS = max(0, int(os.getenv("ALERT_NOTIFY_COOLDOWN_SECONDS", "21600")))
ALERT_RESOLVED_NOTIFICATIONS_ENABLED = (
    os.getenv("ALERT_RESOLVED_NOTIFICATIONS_ENABLED", "true").lower() == "true"
)
ALERT_STATE_SET_KEY = "monitor:alerts:active"
ALERT_STATE_TTL_SECONDS = max(ALERT_NOTIFY_COOLDOWN_SECONDS * 2, 86400)

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


def _alert_scope(alert: Alert) -> str:
    """Return the stable affected object for alert dedupe without hashing volatile text."""
    if alert.type in {"lifecycle_stuck", "lifecycle_fast_forward", "forum_missing"}:
        match = re.search(r"\bBill\s+([A-Za-z0-9_-]+)", alert.message)
        if match:
            return match.group(1)
    if alert.type == "web_down":
        match = re.search(r"\bWeb\s+([^:]+)", alert.message)
        if match:
            return match.group(1).strip()
    if alert.type == "scraper_job_errors":
        match = re.search(r"\bJob\s+([^:]+)", alert.message)
        if match:
            return match.group(1).strip()
    return alert.service or "_global"


def alert_identity(alert: Alert) -> str:
    """Stable identity used for cooldown/resolved tracking.

    The message is intentionally excluded: disk free GB and lag hours can wobble
    between checks, but that is still the same active incident.
    """
    return f"{alert.type}|{alert.service or '_'}|{_alert_scope(alert)}"


def _alert_state_key(alert_key: str) -> str:
    digest = hashlib.sha256(alert_key.encode("utf-8")).hexdigest()[:20]
    return f"monitor:alert:{digest}"


def _safe_redis_get(r, key: str) -> str | None:
    try:
        return r.get(key)
    except Exception as exc:
        logger.warning("[ALERT_DEDUPE] Redis get failed for %s: %s", key, exc)
        return None


def _safe_redis_set(r, key: str, value: str, *, ex: int | None = None) -> bool:
    try:
        r.set(key, value, ex=ex)
        return True
    except Exception as exc:
        logger.warning("[ALERT_DEDUPE] Redis set failed for %s: %s", key, exc)
        return False


def _safe_redis_delete(r, *keys: str) -> None:
    try:
        if keys:
            r.delete(*keys)
    except Exception as exc:
        logger.warning("[ALERT_DEDUPE] Redis delete failed: %s", exc)


def _safe_redis_smembers(r, key: str) -> set[str]:
    try:
        values = r.smembers(key)
        return {str(value) for value in values}
    except Exception as exc:
        logger.warning("[ALERT_DEDUPE] Redis smembers failed for %s: %s", key, exc)
        return set()


def _safe_redis_sadd(r, key: str, *values: str) -> None:
    try:
        if values:
            r.sadd(key, *values)
    except Exception as exc:
        logger.warning("[ALERT_DEDUPE] Redis sadd failed for %s: %s", key, exc)


def _safe_redis_srem(r, key: str, *values: str) -> None:
    try:
        if values:
            r.srem(key, *values)
    except Exception as exc:
        logger.warning("[ALERT_DEDUPE] Redis srem failed for %s: %s", key, exc)


def _alert_state_payload(alert: Alert, now: datetime) -> dict[str, str]:
    return {
        "identity": alert_identity(alert),
        "type": alert.type,
        "service": alert.service or "—",
        "severity": alert.severity,
        "message": alert.message,
        "last_seen": now.isoformat(),
    }


def _load_alert_state(r, alert_key: str) -> dict[str, str] | None:
    raw = _safe_redis_get(r, _alert_state_key(alert_key))
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if isinstance(payload, dict):
        return {str(key): str(value) for key, value in payload.items()}
    return None


def prepare_alert_notifications(
    alerts: list[Alert],
    r,
    now: datetime | None = None,
) -> dict[str, bool]:
    """Decide which incidents deserve Telegram now.

    This intentionally does not mark alerts active. Recovery may repair a
    condition in the same run; only unresolved alerts are persisted later.
    """
    now = now or datetime.now(timezone.utc)
    notification_due: dict[str, bool] = {}

    for alert in alerts:
        identity = alert_identity(alert)
        state = _load_alert_state(r, identity)
        last_sent_key = f"{_alert_state_key(identity)}:last_sent"
        cooldown_active = bool(_safe_redis_get(r, last_sent_key))
        severity_changed = bool(state and state.get("severity") != alert.severity)
        due = not cooldown_active or severity_changed

        notification_due[identity] = due
        if due and ALERT_NOTIFY_COOLDOWN_SECONDS > 0:
            _safe_redis_set(r, last_sent_key, "1", ex=ALERT_NOTIFY_COOLDOWN_SECONDS)

    return notification_due


def record_active_alerts(
    current_alerts: list[Alert],
    r,
    now: datetime | None = None,
) -> None:
    """Persist only alerts that remain unresolved after recovery attempts."""
    now = now or datetime.now(timezone.utc)
    current_keys = {alert_identity(alert) for alert in current_alerts}
    previous_keys = _safe_redis_smembers(r, ALERT_STATE_SET_KEY)

    for stale_key in previous_keys - current_keys:
        _safe_redis_srem(r, ALERT_STATE_SET_KEY, stale_key)

    for alert in current_alerts:
        identity = alert_identity(alert)
        _safe_redis_set(
            r,
            _alert_state_key(identity),
            json.dumps(_alert_state_payload(alert, now), ensure_ascii=False),
            ex=ALERT_STATE_TTL_SECONDS,
        )
        _safe_redis_sadd(r, ALERT_STATE_SET_KEY, identity)


def send_resolved_notifications(
    current_alerts: list[Alert],
    r,
    now: datetime | None = None,
    previous_keys: set[str] | None = None,
) -> None:
    """Send one-time Entwarnung messages for alerts that disappeared."""
    if not ALERT_RESOLVED_NOTIFICATIONS_ENABLED:
        return

    now = now or datetime.now(timezone.utc)
    current_keys = {alert_identity(alert) for alert in current_alerts}
    if previous_keys is None:
        previous_keys = _safe_redis_smembers(r, ALERT_STATE_SET_KEY)
    resolved_keys = previous_keys - current_keys

    for identity in sorted(resolved_keys):
        state_key = _alert_state_key(identity)
        state = _load_alert_state(r, identity) or {}
        msg = (
            "🟢 <b>Monitor Entwarnung</b>\n\n"
            f"<b>Type:</b> {state.get('type', identity)}\n"
            f"<b>Service:</b> {state.get('service', '—')}\n"
            f"<b>Vorher:</b> {state.get('message', identity)}\n"
            f"\n<i>{now.strftime('%Y-%m-%d %H:%M UTC')}</i>"
        )
        send_telegram(msg)
        logger.info("[RESOLVED] Alert cleared: %s", identity)
        _safe_redis_srem(r, ALERT_STATE_SET_KEY, identity)
        _safe_redis_delete(r, state_key, f"{state_key}:last_sent")


# ─── T1 Mapping: alert.type → API endpoint ───────────────────────────────────

T1_MAPPING = {
    "scraper_parliament_stale": "/api/v1/admin/scraper/catch-up",
    "parliament_source_lag":     "/api/v1/admin/scraper/catch-up?force=parliament",
    "scraper_diavgeia_stale":   "/api/v1/admin/scraper/catch-up",
    "forum_sync_errors":        "/api/v1/admin/forum/sync-new",
    "forum_content_empty":      "/api/v1/admin/forum/sync-new",
}

# Longer cooldown for expensive operations
T1_LOCK_TTL = {
    "/api/v1/admin/forum/resync-all": 7200,  # 2h
    "/api/v1/admin/forum/sync-new": 1800,    # 30m
}
T1_DEFAULT_LOCK_TTL = 3600  # 1h

# Verified repairs are intentionally tiny and allowlisted. They may only call
# idempotent admin endpoints, then prove the exact alert condition is gone.
VERIFIED_T1_ALERTS = {"parliament_source_lag"}


def _parliament_freshness_url() -> str:
    return f"{API_URL}/api/v1/scraper/parliament/freshness?limit={PARLIAMENT_SOURCE_SAMPLE_LIMIT}"


def _get_parliament_freshness_response(timeout: int = 45) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, PARLIAMENT_SOURCE_HTTP_RETRIES + 1):
        try:
            return httpx.get(_parliament_freshness_url(), timeout=timeout)
        except Exception as exc:
            last_exc = exc
            if attempt >= PARLIAMENT_SOURCE_HTTP_RETRIES:
                break
            logger.warning(
                "[PARLIAMENT_SOURCE] Probe attempt %d/%d failed: %s; retrying in %ds",
                attempt,
                PARLIAMENT_SOURCE_HTTP_RETRIES,
                str(exc)[:120],
                PARLIAMENT_SOURCE_HTTP_RETRY_DELAY_SECONDS,
            )
            if PARLIAMENT_SOURCE_HTTP_RETRY_DELAY_SECONDS:
                time.sleep(PARLIAMENT_SOURCE_HTTP_RETRY_DELAY_SECONDS)
    raise last_exc or RuntimeError("Parliament source probe failed")


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

def attempt_tier1(alert: Alert, r) -> str:
    """Tier 1: Trigger API recovery endpoint."""
    endpoint = T1_MAPPING.get(alert.type)
    if not endpoint or not ADMIN_KEY:
        return "unavailable"

    lock_key = f"lock:recovery:{alert.type}"
    ttl = T1_LOCK_TTL.get(endpoint, T1_DEFAULT_LOCK_TTL)
    if not r.set(lock_key, "1", ex=ttl, nx=True):
        logger.info("[T1] Lock active for %s — skipping (cooldown %ds)", alert.type, ttl)
        return "locked"

    try:
        resp = httpx.post(
            f"{API_URL}{endpoint}",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            timeout=30,
        )
        if resp.status_code in (200, 202):
            logger.info("[T1] Recovery OK: %s → %s → HTTP %d", alert.type, endpoint, resp.status_code)
            return "ok"
        logger.warning("[T1] Recovery FAILED: %s → %s → HTTP %d", alert.type, endpoint, resp.status_code)
    except Exception as e:
        logger.error("[T1] Recovery ERROR: %s → %s: %s", alert.type, endpoint, e)

    # Remove lock on failure so next cycle can retry
    r.delete(lock_key)
    return "failed"


def verify_parliament_source_lag_repaired(conn) -> tuple[bool, str]:
    """Prove Parliament source freshness no longer exceeds the alert threshold."""
    try:
        resp = _get_parliament_freshness_response(timeout=45)
        if resp.status_code != 200:
            return False, f"source_check_http_{resp.status_code}"

        payload = resp.json()
        source_latest = _as_utc_datetime(payload.get("source_latest"))
        if source_latest is None:
            source_latest = _latest_source_activity(payload.get("bills", []))
        if not source_latest:
            return False, "source_has_no_dated_bills"

        db_latest = _db_latest_parliament_activity(conn)
        if not db_latest:
            return False, "db_has_no_parliament_activity"

        lag_h = (source_latest - db_latest).total_seconds() / 3600
        if lag_h <= PARLIAMENT_SOURCE_MAX_LAG_HOURS:
            return True, (
                f"source={source_latest.strftime('%Y-%m-%d')} "
                f"db={db_latest.strftime('%Y-%m-%d')} lag={lag_h:.0f}h"
            )
        return False, (
            f"source={source_latest.strftime('%Y-%m-%d')} "
            f"db={db_latest.strftime('%Y-%m-%d')} lag={lag_h:.0f}h"
        )
    except Exception as exc:
        return False, f"verify_error:{str(exc)[:120]}"


def verify_tier1_repair(alert: Alert, conn) -> tuple[bool, str]:
    if alert.type == "parliament_source_lag":
        if REPAIR_VERIFY_WAIT_SECONDS:
            logger.info(
                "[T1V] Waiting %ds before verifying %s",
                REPAIR_VERIFY_WAIT_SECONDS,
                alert.type,
            )
            time.sleep(REPAIR_VERIFY_WAIT_SECONDS)
        return verify_parliament_source_lag_repaired(conn)
    return False, "no_verified_runbook"


def send_verified_recovery(alert: Alert, detail: str) -> None:
    msg = (
        "🟢 <b>Auto-Recovery verified</b>\n\n"
        f"<b>Type:</b> {alert.type}\n"
        f"<b>Service:</b> {alert.service or '—'}\n"
        f"<b>Message:</b> {alert.message}\n"
        f"<b>Proof:</b> {detail}\n"
        f"\n<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>"
    )
    send_telegram(msg)
    logger.info("[T1V] Verified recovery for %s — %s", alert.type, detail)


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


def escalate_tier3(alert: Alert, recovery_result: str = "", *, notify: bool = True):
    """Tier 3: Telegram escalation, cooldown-gated per active incident."""
    if not notify:
        logger.warning("[T3] Suppressed by cooldown: %s — %s", alert.type, alert.message)
        return

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


def attempt_recovery(alert: Alert, r, conn=None, *, notify: bool = True):
    """Dispatcher: T1 → T2 → T3."""
    if not alert.recovery_allowed:
        escalate_tier3(alert, "Direct T3 — no auto-recovery for this type", notify=notify)
        return "T3"

    # Tier 1
    if alert.type in T1_MAPPING:
        t1_result = attempt_tier1(alert, r)
        if t1_result == "ok" and alert.type in VERIFIED_T1_ALERTS and conn is not None:
            verified, detail = verify_tier1_repair(alert, conn)
            if verified:
                send_verified_recovery(alert, detail)
                return "T1V"
            logger.warning("[T1V] Verification failed for %s — %s", alert.type, detail)
            return "T1"
        if t1_result == "locked" and alert.type in VERIFIED_T1_ALERTS:
            return "T1L"
        if t1_result in ("ok", "locked"):
            return "T1"

    # Tier 2
    if alert.service:
        if attempt_tier2(alert, r):
            return "T2"

    # Tier 3
    escalate_tier3(alert, "T1+T2 failed or not applicable", notify=notify)
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
        resp = _get_parliament_freshness_response(timeout=45)
        if resp.status_code != 200:
            alerts.append(Alert(
                "parliament_source_check_failed", "ekklesia-api", "warning",
                f"Parliament source freshness check failed: HTTP {resp.status_code}", False,
            ))
            return alerts

        payload = resp.json()
        source_latest = _as_utc_datetime(payload.get("source_latest"))
        if source_latest is None:
            source_latest = _latest_source_activity(payload.get("bills", []))
        if not source_latest:
            count = payload.get("count", 0)
            dated_count = payload.get("dated_count", 0)
            alerts.append(Alert(
                "parliament_source_check_failed", "ekklesia-api", "warning",
                (
                    "Parliament source freshness check returned no dated bills "
                    f"(count={count}, dated_count={dated_count})"
                ),
                False,
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
              AND COALESCE(updated_at, TIMESTAMP '1970-01-01') < %s
              AND status IN ('ANNOUNCED', 'ACTIVE', 'WINDOW_24H')
        """, (now - timedelta(days=1), now - timedelta(minutes=30)))
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


def check_lifecycle_fast_forward(conn) -> list[Alert]:
    """Detect bills whose public voting window was skipped too quickly.

    This is intentionally alert-only. Rewinding vote lifecycle state is a
    governance decision, not an automatic recovery action.
    """
    alerts = []
    with conn.cursor() as cur:
        cur.execute("""
            WITH lifecycle AS (
                SELECT
                    l.bill_id,
                    MIN(l.changed_at) FILTER (
                        WHERE l.from_status = 'ANNOUNCED'
                          AND l.to_status = 'ACTIVE'
                    ) AS active_at,
                    MIN(l.changed_at) FILTER (
                        WHERE l.from_status = 'ACTIVE'
                          AND l.to_status = 'WINDOW_24H'
                    ) AS window_at,
                    MIN(l.changed_at) FILTER (
                        WHERE l.from_status = 'WINDOW_24H'
                          AND l.to_status = 'PARLIAMENT_VOTED'
                    ) AS voted_at
                FROM bill_status_logs l
                JOIN parliament_bills b ON b.id = l.bill_id
                WHERE l.changed_at > NOW() - INTERVAL '24 hours'
                  AND b.id NOT LIKE 'DEMO-%%'
                  AND COALESCE(b.admin_hidden, FALSE) = FALSE
                  AND COALESCE(b.source, 'PARLIAMENT') = 'PARLIAMENT'
                GROUP BY l.bill_id
            )
            SELECT bill_id, active_at, window_at, voted_at
            FROM lifecycle
            WHERE active_at IS NOT NULL
              AND window_at IS NOT NULL
              AND voted_at IS NOT NULL
              AND voted_at - window_at < INTERVAL '24 hours'
            ORDER BY voted_at DESC
            LIMIT 10
        """)
        for bill_id, active_at, window_at, voted_at in cur.fetchall():
            minutes = int((voted_at - window_at).total_seconds() / 60)
            alerts.append(Alert(
                "lifecycle_fast_forward",
                "ekklesia-api",
                "warning",
                (
                    f"Bill {bill_id} skipped public WINDOW_24H "
                    f"({minutes} min from WINDOW_24H to PARLIAMENT_VOTED)"
                ),
                False,
            ))
    return alerts


def check_forum_missing(conn) -> list[Alert]:
    alerts = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title_el FROM parliament_bills
            WHERE status = 'ACTIVE' AND forum_topic_id IS NULL
              AND COALESCE(admin_hidden, FALSE) = FALSE
              AND (source IS NULL OR source != 'ZK_CANARY')
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
              AND COALESCE(admin_hidden, FALSE) = FALSE
              AND (source IS NULL OR source != 'ZK_CANARY')
              AND (
                  (COALESCE(source, 'PARLIAMENT') = 'PARLIAMENT'
                   AND created_at < NOW() - INTERVAL '1 hour')
                  OR
                  (COALESCE(source, 'PARLIAMENT') != 'PARLIAMENT'
                   AND created_at < NOW() - INTERVAL '6 hours')
              )
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
            if ZK_ARWEAVE_PUBLICATION_ENABLED and not ZK_ARWEAVE_SCOPE_ALLOWLIST:
                alerts.append(Alert(
                    "zk_publication_config",
                    "ekklesia-api",
                    "warning",
                    "ZK Arweave publication enabled without scope allowlist",
                    False,
                ))
            elif ZK_ARWEAVE_PUBLICATION_ENABLED:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM zk_vote_receipts r
                    LEFT JOIN parliament_bills b
                      ON r.vote_scope_id = ('bill:' || b.id)
                    WHERE r.arweave_pending = TRUE
                      AND r.created_at < NOW() - (%s * INTERVAL '1 hour')
                      AND r.vote_scope_id = ANY(%s)
                      AND COALESCE(b.admin_hidden, FALSE) IS NOT TRUE
                      AND COALESCE(b.source, '') <> 'ZK_CANARY'
                    """,
                    (ZK_PENDING_MAX_HOURS, list(ZK_ARWEAVE_SCOPE_ALLOWLIST)),
                )
                pending_count = cur.fetchone()[0]
                if pending_count > 0:
                    alerts.append(Alert(
                        "zk_receipts_pending",
                        "ekklesia-api",
                        "warning",
                        (
                            f"ZK: {pending_count} allowlisted vote receipts pending "
                            f"Arweave/publication >{ZK_PENDING_MAX_HOURS}h"
                        ),
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
    logger.info("Running 18 business logic checks...")
    all_alerts: list[Alert] = []
    recovery_results: dict[str, str] = {}
    notification_due: dict[str, bool] = {}
    previous_active_alerts: set[str] = set()

    r = get_redis()
    conn = get_db()

    try:
        previous_active_alerts = _safe_redis_smembers(r, ALERT_STATE_SET_KEY)

        all_alerts.extend(check_scraper_stale(r))
        all_alerts.extend(check_no_new_bills(conn))
        all_alerts.extend(check_parliament_source_freshness(conn))
        all_alerts.extend(check_lifecycle_stuck(conn, r))
        all_alerts.extend(check_lifecycle_fast_forward(conn))
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

        notification_due = prepare_alert_notifications(all_alerts, r)

        # Recovery pass
        for alert in all_alerts:
            tier = attempt_recovery(
                alert,
                r,
                conn,
                notify=notification_due.get(alert_identity(alert), True),
            )
            recovery_results[alert.type] = tier

        unresolved_alerts = [
            alert for alert in all_alerts
            if recovery_results.get(alert.type) != "T1V"
        ]

        send_resolved_notifications(
            unresolved_alerts,
            r,
            previous_keys=previous_active_alerts,
        )
        record_active_alerts(unresolved_alerts, r)

        alerts_for_summary = [
            alert for alert in unresolved_alerts
            if notification_due.get(alert_identity(alert), True)
        ]

        if unresolved_alerts and alerts_for_summary:
            msg = f"<b>ekklesia.gr Monitor — {len(unresolved_alerts)} Alerts</b>\n\n"
            for i, alert in enumerate(unresolved_alerts, 1):
                tier = recovery_results.get(alert.type, "—")
                icon = "✓" if tier in ("T1", "T2") else "✗"
                msg += f"{i}. [{icon}{tier}] {alert.message}\n"
            msg += f"\n<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>"
            if len(msg) > 4000:
                msg = msg[:3950] + f"\n\n... (+{len(unresolved_alerts)} total)"
            send_telegram(msg)
            logger.warning("ALERTS: %d issues found", len(unresolved_alerts))
        elif unresolved_alerts:
            logger.warning(
                "ALERTS: %d active issues found; Telegram suppressed by cooldown",
                len(unresolved_alerts),
            )
        else:
            if all_alerts:
                logger.info("All alerts were repaired and verified")
            else:
                logger.info("All checks passed — no alerts")

        return unresolved_alerts

    finally:
        conn.close()
        r.close()


def apply_startup_grace() -> None:
    """Delay the first daemon check so planned deploy restarts do not trigger recovery."""
    if STARTUP_GRACE_SECONDS <= 0:
        return
    logger.info("Startup grace active (%ds); delaying first monitor check", STARTUP_GRACE_SECONDS)
    time.sleep(STARTUP_GRACE_SECONDS)


if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        logger.info("ekklesia.gr Health-Check (single run)")
        alerts = run_checks()
        sys.exit(1 if alerts else 0)
    else:
        logger.info(
            "ekklesia.gr Monitor started (interval: %ds, startup_grace: %ds, T2: %s)",
            CHECK_INTERVAL,
            STARTUP_GRACE_SECONDS,
            AUTO_RECOVERY_T2,
        )
        apply_startup_grace()
        while True:
            try:
                run_checks()
            except Exception as e:
                logger.error("Monitor error: %s", e)
            time.sleep(CHECK_INTERVAL)
