"""
Newsletter Service — Brevo API direkt (Listmonk v6 API bug workaround).
Handles: welcome emails, monthly reports, bill notifications.
"""
import os
import json
import html
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from services.bill_visibility import public_bill_filter
from services.mail_policy import OPERATOR_EMAIL, operator_reply_to
from services.small_cell import small_cell_k
from services.newsletter_lock import newsletter_lock, NewsletterLockUnavailable
from services.newsletter_consent import preference_attributes

logger = logging.getLogger(__name__)

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_API = "https://api.brevo.com/v3"
SENDER = {"name": "εκκλησία", "email": "newsletter@ekklesia.gr"}
LIST_ID = int(os.getenv("BREVO_LIST_ID", "2"))  # Πολίτες ekklesia.gr


class ContactSuppressed(Exception):
    """Provider suppression detected before attempting an enrollment write."""


class ContactNotWritten(Exception):
    """Enrollment failed before send or was definitively rejected by the provider."""


class _ContactRequestLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # httpcore traces raw response headers (e.g. Location) without a URL.
        # Suppress transport debug records even when application DEBUG is on.
        if record.name.startswith("httpcore.") and record.levelno <= logging.DEBUG:
            return False
        # Contact lookup URLs contain addresses, including when httpx logs redirects.
        message = record.getMessage()
        return "/contacts/" not in message and "/api/subscribers?" not in message


for _log_name in ("httpx", "httpcore.http11", "httpcore.http2"):
    logging.getLogger(_log_name).addFilter(_ContactRequestLogFilter())

# Base template with logo + social buttons
_HEADER = """<div style="text-align:center;padding:20px 0;border-bottom:2px solid #e2e8f0;margin-bottom:24px">
<img src="https://ekklesia.gr/pnx.png" alt="ekklesia.gr" width="64" style="border-radius:12px">
<div style="font-size:22px;font-weight:900;color:#2563eb;margin-top:8px">εκκλησία<span style="font-size:0.55em;color:#9ca3af;font-weight:400;margin-left:4px">του έθνους</span></div>
</div>"""

_FOOTER = """<hr style="border:none;border-top:1px solid #e2e8f0;margin:32px 0 16px">
<div style="text-align:center;padding:16px 0">
<a href="https://t.me/ekklesia_gr" style="display:inline-block;margin:4px;padding:8px 16px;background:#2CA5E0;color:#fff;border-radius:6px;text-decoration:none;font-size:12px;font-weight:700">Telegram</a>
<a href="https://www.facebook.com/share/1MbLJG6eth/" style="display:inline-block;margin:4px;padding:8px 16px;background:#1877F2;color:#fff;border-radius:6px;text-decoration:none;font-size:12px;font-weight:700">Facebook</a>
<a href="https://pnyx.ekklesia.gr" style="display:inline-block;margin:4px;padding:8px 16px;background:#2563eb;color:#fff;border-radius:6px;text-decoration:none;font-size:12px;font-weight:700">Forum</a>
<a href="https://github.com/NeaBouli/pnyx" style="display:inline-block;margin:4px;padding:8px 16px;background:#24292e;color:#fff;border-radius:6px;text-decoration:none;font-size:12px;font-weight:700">GitHub</a>
<a href="https://ekklesia.gr/download" style="display:inline-block;margin:4px;padding:8px 16px;background:#22c55e;color:#fff;border-radius:6px;text-decoration:none;font-size:12px;font-weight:700">APK</a>
</div>
<p style="color:#94a3b8;font-size:11px;text-align:center;margin-top:12px">© 2026 V-Labs Development | MIT License<br>εκκλησία του έθνους — ekklesia.gr</p>"""


def _wrap(body: str, *, language: str = "el") -> str:
    return f'<html lang="{language}"><body style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#0f172a">{_HEADER}{body}{_FOOTER}</body></html>'


async def _brevo_post(endpoint: str, data: dict, *, track_enrollment: bool = False) -> dict | None:
    if not BREVO_API_KEY:
        logger.warning("[NEWSLETTER] BREVO_API_KEY not set")
        if track_enrollment:
            raise ContactNotWritten()
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{BREVO_API}/{endpoint}",
                headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
                json=data,
            )
            if r.status_code in (200, 201, 202, 204):
                return r.json() if r.text else {}
            logger.warning("[NEWSLETTER] Brevo request failed: status=%s", r.status_code)
            if track_enrollment and 300 <= r.status_code < 500:
                raise ContactNotWritten()
    except ContactNotWritten:
        raise
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
        logger.error("[NEWSLETTER] Brevo request failed before send")
        if track_enrollment:
            raise ContactNotWritten() from None
    except Exception:
        logger.error("[NEWSLETTER] Brevo request failed")
    return None


async def contact_status(
    email: str, *, for_removal: bool = False, attributes: dict[str, str | bool] | None = None,
) -> str:
    """Read membership and suppression without exposing provider data or identity."""
    if not BREVO_API_KEY:
        return "failed"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get(
                f"{BREVO_API}/contacts/{quote(email, safe='')}",
                headers={"api-key": BREVO_API_KEY},
            )
        if response.status_code == 404:
            return "to_add"
        if response.status_code != 200:
            return "failed"
        data = response.json()
        if not isinstance(data, dict) or str(data.get("email", "")).casefold() != email.casefold():
            return "failed"
        lists = data.get("listIds")
        unsubscribed = data.get("listUnsubscribed", [])
        if not for_removal and (data.get("emailBlacklisted") is True
                                or (isinstance(unsubscribed, list) and LIST_ID in unsubscribed)):
            return "suppressed"
        if (type(data.get("emailBlacklisted")) is not bool or not isinstance(lists, list)
                or not isinstance(unsubscribed, list)
                or any(type(value) is not int for value in lists + unsubscribed)):
            return "failed"
        if LIST_ID not in lists:
            return "to_add"
        if attributes is not None:
            saved = data.get("attributes", {})
            if not isinstance(saved, dict) or any(
                type(saved.get(key)) is not type(value) or saved.get(key) != value
                for key, value in attributes.items()
            ):
                return "to_update"
        return "already_present"
    except Exception:
        logger.error("[NEWSLETTER] Brevo contact lookup failed")
        return "failed"


async def add_contact(email: str, name: str = "", *, preferences: dict[str, Any] | None = None) -> bool:
    attributes = preference_attributes(preferences) if preferences is not None else None
    status = await contact_status(email, attributes=attributes) if attributes is not None else await contact_status(email)
    if status == "suppressed":
        raise ContactSuppressed()
    if status == "already_present":
        return True
    if status not in {"to_add", "to_update"}:
        raise ContactNotWritten()
    result = await _brevo_post("contacts", {
        "email": email,
        "attributes": {**({"FIRSTNAME": name} if name else {}), **(attributes or {})},
        "listIds": [LIST_ID],
        "updateEnabled": True,
    }, track_enrollment=True)
    return result is not None


async def remove_contact(email: str, *, require_present: bool = False) -> bool:
    """Unlink only the campaign list; retain provider history and suppression."""
    status = await contact_status(email, for_removal=True)
    if status == "failed":
        return False
    # A missing contact or an existing contact outside the list is already removed.
    if status == "to_add":
        return not require_present
    result = await _brevo_post(f"contacts/lists/{LIST_ID}/contacts/remove", {"emails": [email]})
    if result is None:
        return False
    contacts = result.get("contacts", {})
    return not contacts.get("failure", [])


async def send_transactional(to_email: str, subject: str, html_body: str, *, neutral: bool = False) -> bool:
    result = await _brevo_post("smtp/email", {
        "sender": SENDER,
        "to": [{"email": to_email}],
        "replyTo": operator_reply_to(),
        "subject": subject,
        "htmlContent": html_body if neutral else _wrap(html_body),
    })
    return result is not None


async def send_reconfirmation(email: str, token: str) -> bool:
    """One neutral transactional invitation, without promotional template links."""
    url = f"https://api.ekklesia.gr/api/v1/newsletter/confirm/{token}"
    subject = "Επιβεβαιώστε την εγγραφή σας στο ενημερωτικό δελτίο του ekklesia.gr"
    body = (
        '<html lang="el"><body><p>' + subject + '.</p>'
        f'<p><a href="{url}">Επιβεβαίωση εγγραφής</a></p>'
        '<p>Ο σύνδεσμος ισχύει για 30 ημέρες και μπορεί να χρησιμοποιηθεί μία φορά.</p>'
        '<p>Χωρίς επιβεβαίωση δεν θα σας σταλούν άλλα email και η εγγραφή σας '
        'στο ενημερωτικό δελτίο θα διαγραφεί μετά από 30 ημέρες.</p></body></html>'
    )
    return await send_transactional(email, subject, body, neutral=True)


async def ensure_reconfirmations_paused() -> bool:
    """Fail closed before campaigns if a pending pause cannot be reconciled."""
    from routers.newsletter import _get_redis, _remove_ineligible_contact, _reconcile_consent_aliases
    from services.newsletter_consent import RECONFIRM_KEY, parse_consent, has_doi_evidence

    try:
        store = await _get_redis()
        for identity, raw in (await store.hgetall(RECONFIRM_KEY)).items():
            data = json.loads(raw)
            email = data["email"]
            if parse_consent(email, raw, include_expired=True) is None or identity != email.casefold():
                return False
            if await store.hget(RECONFIRM_KEY, identity) != raw:
                continue
            now = datetime.now(timezone.utc)
            chosen = await _reconcile_consent_aliases(store, identity, now)
            if chosen and has_doi_evidence(chosen[2], now):
                continue
            if not await _remove_ineligible_contact(store, email):
                return False
        return True
    except Exception:
        logger.error("[NEWSLETTER] Campaign paused; reconfirmation check unavailable")
        return False


async def send_welcome(email: str) -> bool:
    body = """<h2 style="color:#2563eb">Καλωσήρθατε στο ekklesia.gr!</h2>
<p style="font-size:15px;line-height:1.7">Το <strong>ekklesia.gr</strong> είναι η πρώτη πλατφόρμα ψηφιακής άμεσης δημοκρατίας για τους Έλληνες πολίτες.</p>
<ul style="font-size:14px;line-height:2">
<li>Ψηφίστε <strong>ανώνυμα</strong> για τα νομοσχέδια της Βουλής</li>
<li>Δείτε πόσο οι βουλευτές εκπροσωπούν τις απόψεις σας</li>
<li>Μηδενική αποθήκευση προσωπικών δεδομένων</li>
<li>Ανοιχτός κώδικας — MIT License</li>
</ul>
<p style="text-align:center;margin:24px 0">
<a href="https://ekklesia.gr/download" style="display:inline-block;padding:14px 28px;background:#2563eb;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold;font-size:15px">Κατεβάστε την εφαρμογή →</a>
</p>"""
    return await send_transactional(email, "Καλωσήρθατε στο ekklesia.gr", body)


_MONTHLY_EN = {
    "Μηνιαία Αναφορά": "Monthly Report",
    "Νέα νομοσχέδια": "New bills",
    "Ψήφοι πολιτών": "Citizen votes",
    "Arweave αρχεία": "Arweave archives",
    "Ψηφισμένα": "Completed votes",
    "Νέα Νομοσχέδια": "New Bills",
    "Επόμενες Ψηφοφορίες": "Upcoming Votes",
    "Top Ψηφοφορίες": "Top Votes",
    "Νομοσχέδιο": "Bill",
    "ΝΑΙ": "YES",
    "ΟΧΙ": "NO",
    "Σύνολο": "Total",
    "Αποτελέσματα ψηφοφοριών": "Vote results",
    "Δείτε τα νομοσχέδια": "View bills",
}


async def send_monthly_report(db: AsyncSession) -> bool:
    """Send separate Greek and English digests to verified monthly audiences."""
    from models import ParliamentBill, BillStatus, CitizenVote
    threshold = small_cell_k()

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── Stats ──────────────────────────────────────────────────────
    new_bills_count = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.created_at >= month_start,
            public_bill_filter(),
        )
    ) or 0

    voted_count = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.status == BillStatus.OPEN_END,
            public_bill_filter(),
        )
    ) or 0

    from services.bill_visibility import results_visible_filter
    total_votes = await db.scalar(
        select(func.count(CitizenVote.id))
        .join(ParliamentBill, CitizenVote.bill_id == ParliamentBill.id)
        .where(public_bill_filter(), results_visible_filter())
    ) or 0

    archived_count = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.arweave_tx_id.isnot(None),
            public_bill_filter(),
        )
    ) or 0

    # ── Neue Bills (Titel-Liste) ──────────────────────────────────
    new_bills_result = await db.execute(
        select(ParliamentBill.id, ParliamentBill.title_el, ParliamentBill.title_en)
        .where(ParliamentBill.created_at >= month_start, public_bill_filter())
        .order_by(ParliamentBill.created_at.desc())
        .limit(10)
    )
    new_bills_list = new_bills_result.all()

    # ── Nächste Abstimmungen (ACTIVE + ANNOUNCED mit vote_date) ───
    upcoming_result = await db.execute(
        select(ParliamentBill.id, ParliamentBill.title_el, ParliamentBill.title_en, ParliamentBill.parliament_vote_date)
        .where(
            ParliamentBill.status.in_([BillStatus.ACTIVE, BillStatus.ANNOUNCED]),
            public_bill_filter(),
            ParliamentBill.parliament_vote_date.isnot(None),
            ParliamentBill.parliament_vote_date >= now.replace(tzinfo=None),
        )
        .order_by(ParliamentBill.parliament_vote_date)
        .limit(5)
    )
    upcoming_list = upcoming_result.all()

    # ── Top-Abstimmungen mit Ergebnis (diesen Monat) ─────────────
    from sqlalchemy import text
    from services.bill_visibility import results_visible_raw_sql
    top_votes_result = await db.execute(text(f"""
        SELECT b.id, b.title_el, b.title_en,
            COUNT(*) FILTER (WHERE cv.vote='YES') as yes,
            COUNT(*) FILTER (WHERE cv.vote='NO') as no,
            COUNT(*) as total
        FROM citizen_votes cv
        JOIN parliament_bills b ON b.id = cv.bill_id
        WHERE cv.created_at >= :month_start
          AND b.admin_hidden IS NOT TRUE
          AND {results_visible_raw_sql('b')}
        GROUP BY b.id, b.title_el, b.title_en
        ORDER BY total DESC LIMIT 5
    """), {"month_start": month_start})
    top_votes_list = top_votes_result.all()

    # Older monthly queries use a different population/window from public
    # results. While suppression is enabled, link to those guarded results
    # instead of publishing a second, subtractable set of counts.
    if threshold:
        total_votes = "—"
        top_votes_list = []

    # ── Build HTML ────────────────────────────────────────────────
    month_name = now.strftime("%B %Y")

    def render(language: str) -> str:
        def label(value: str) -> str:
            return _MONTHLY_EN.get(value, value) if language == "en" else value

        # Stats grid
        stats_html = f"""<h2 style="color:#2563eb">{label("Μηνιαία Αναφορά")} — {month_name}</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0">
    <div style="background:#f1f5f9;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:28px;font-weight:900;color:#2563eb">{new_bills_count}</div>
    <div style="font-size:12px;color:#64748b">{label("Νέα νομοσχέδια")}</div>
    </div>
    <div style="background:#f1f5f9;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:28px;font-weight:900;color:#22c55e">{total_votes}</div>
    <div style="font-size:12px;color:#64748b">{label("Ψήφοι πολιτών")}</div>
    </div>
    <div style="background:#f1f5f9;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:28px;font-weight:900;color:#a855f7">{archived_count}</div>
    <div style="font-size:12px;color:#64748b">{label("Arweave αρχεία")}</div>
    </div>
    <div style="background:#f1f5f9;border-radius:8px;padding:16px;text-align:center">
    <div style="font-size:28px;font-weight:900;color:#0f172a">{voted_count}</div>
    <div style="font-size:12px;color:#64748b">{label("Ψηφισμένα")}</div>
    </div>
    </div>"""

        # New bills list
        bills_html = ""
        if new_bills_list:
            bills_html = f'<h3 style="color:#0f172a;margin-top:24px">{label("Νέα Νομοσχέδια")}</h3><ul style="font-size:13px;line-height:2;color:#334155">'
            for bill_id, title_el, title_en in new_bills_list:
                title = html.escape((title_en if language == "en" else title_el) or label("Νομοσχέδιο"))
                bills_html += f'<li><a href="https://ekklesia.gr/el/bills/{bill_id}" style="color:#2563eb;text-decoration:none">{title[:80]}</a></li>'
            bills_html += '</ul>'

        # Upcoming votes
        upcoming_html = ""
        if upcoming_list:
            upcoming_html = f'<h3 style="color:#0f172a;margin-top:24px">{label("Επόμενες Ψηφοφορίες")}</h3><ul style="font-size:13px;line-height:2;color:#334155">'
            for bill_id, title_el, title_en, vote_date in upcoming_list:
                title = html.escape((title_en if language == "en" else title_el) or label("Νομοσχέδιο"))
                date_str = vote_date.strftime("%d.%m") if vote_date else "—"
                upcoming_html += f'<li>{date_str} — {title[:60]}</li>'
            upcoming_html += '</ul>'

        # Top votes
        top_html = ""
        if top_votes_list:
            top_html = f'<h3 style="color:#0f172a;margin-top:24px">{label("Top Ψηφοφορίες")}</h3><table style="width:100%;font-size:12px;border-collapse:collapse">'
            top_html += f'<tr style="background:#f1f5f9"><th style="padding:6px;text-align:left">{label("Νομοσχέδιο")}</th><th style="padding:6px">{label("ΝΑΙ")}</th><th style="padding:6px">{label("ΟΧΙ")}</th><th style="padding:6px">{label("Σύνολο")}</th></tr>'
            for bill_id, title_el, title_en, yes, no, total in top_votes_list:
                title = html.escape((title_en if language == "en" else title_el) or label("Νομοσχέδιο"))
                top_html += f'<tr><td style="padding:6px">{title[:40]}</td><td style="padding:6px;text-align:center;color:#22c55e">{yes}</td><td style="padding:6px;text-align:center;color:#ef4444">{no}</td><td style="padding:6px;text-align:center;font-weight:700">{total}</td></tr>'
            top_html += '</table>'
        if threshold:
            top_html = f'<p><a href="https://ekklesia.gr/el/results">{label("Αποτελέσματα ψηφοφοριών")}</a></p>'

        body = stats_html + bills_html + upcoming_html + top_html + f"""
    <p style="text-align:center;margin:24px 0">
    <a href="https://ekklesia.gr/el/bills" style="display:inline-block;padding:12px 24px;background:#2563eb;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px">{label("Δείτε τα νομοσχέδια")} →</a>
    </p>"""

        body = body.replace("/el/", f"/{language}/")
        return _wrap(body, language=language)

    from services.newsletter_audience import CampaignPlan, campaign_recipients, prepare_audience
    # Keep one lease across both language snapshots and provider dispatches.
    try:
        async with newsletter_lock() as lease:
            plans = [CampaignPlan(language=language) for language in ("el", "en")]
            audiences = [await prepare_audience(lease.store, plan) for plan in plans]
            for plan, audience in zip(plans, audiences):
                if not audience.selected:
                    continue
                await audience.check(lease.store)
                await lease.check()
                result = await _brevo_post("emailCampaigns", {
                    "name": f"Monthly Report {month_name} ({plan.language})",
                    "subject": f"ekklesia.gr — {'Monthly Report' if plan.language == 'en' else 'Μηνιαία Αναφορά'} {month_name}",
                    "sender": SENDER,
                    "replyTo": OPERATOR_EMAIL,
                    "type": "classic",
                    "tag": plan.tag,
                    "recipients": campaign_recipients(plan),
                    "htmlContent": render(plan.language),
                })
                if not result or not result.get("id"):
                    return False
                await audience.check(lease.store)
                await lease.check()
                sent = await _brevo_post(f"emailCampaigns/{result['id']}/sendNow", {})
                if sent is None:
                    return False
                logger.info("[NEWSLETTER] Monthly report dispatched: selected=%d", audience.counts["selected"])
            return True
    except Exception:
        logger.warning("[NEWSLETTER] Campaign paused; retry")
    return False
