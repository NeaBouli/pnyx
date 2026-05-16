"""
Newsletter Service — Brevo API direkt (Listmonk v6 API bug workaround).
Handles: welcome emails, monthly reports, bill notifications.
"""
import os
import logging
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

logger = logging.getLogger(__name__)

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_API = "https://api.brevo.com/v3"
SENDER = {"name": "εκκλησία", "email": "newsletter@ekklesia.gr"}
LIST_ID = 2  # Πολίτες ekklesia.gr

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


def _wrap(body: str) -> str:
    return f'<html><body style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#0f172a">{_HEADER}{body}{_FOOTER}</body></html>'


async def _brevo_post(endpoint: str, data: dict) -> dict | None:
    if not BREVO_API_KEY:
        logger.warning("[NEWSLETTER] BREVO_API_KEY not set")
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
            logger.warning("[NEWSLETTER] Brevo %s failed: %s %s", endpoint, r.status_code, r.text[:100])
    except Exception as e:
        logger.error("[NEWSLETTER] Brevo error: %s", e)
    return None


async def add_contact(email: str, name: str = "") -> bool:
    result = await _brevo_post("contacts", {
        "email": email,
        "attributes": {"FIRSTNAME": name} if name else {},
        "listIds": [LIST_ID],
        "updateEnabled": True,
    })
    return result is not None


async def send_transactional(to_email: str, subject: str, html_body: str) -> bool:
    result = await _brevo_post("smtp/email", {
        "sender": SENDER,
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": _wrap(html_body),
    })
    return result is not None


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


async def send_monthly_report(db: AsyncSession) -> bool:
    """Generate and send monthly report to all subscribers."""
    from models import ParliamentBill, BillStatus, CitizenVote

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Neue Bills diesen Monat
    new_bills = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.created_at >= month_start
        )
    ) or 0

    # Bills in OPEN_END (abgestimmt)
    voted = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.status == BillStatus.OPEN_END
        )
    ) or 0

    # Gesamte Stimmen
    total_votes = await db.scalar(select(func.count(CitizenVote.id))) or 0

    # Arweave archiviert
    archived = await db.scalar(
        select(func.count(ParliamentBill.id)).where(
            ParliamentBill.arweave_tx_id.isnot(None)
        )
    ) or 0

    month_name = now.strftime("%B %Y")
    body = f"""<h2 style="color:#2563eb">Μηνιαία Αναφορά — {month_name}</h2>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0">
<div style="background:#f1f5f9;border-radius:8px;padding:16px;text-align:center">
<div style="font-size:28px;font-weight:900;color:#2563eb">{new_bills}</div>
<div style="font-size:12px;color:#64748b">Νέα νομοσχέδια</div>
</div>
<div style="background:#f1f5f9;border-radius:8px;padding:16px;text-align:center">
<div style="font-size:28px;font-weight:900;color:#22c55e">{total_votes}</div>
<div style="font-size:12px;color:#64748b">Ψήφοι πολιτών</div>
</div>
<div style="background:#f1f5f9;border-radius:8px;padding:16px;text-align:center">
<div style="font-size:28px;font-weight:900;color:#a855f7">{archived}</div>
<div style="font-size:12px;color:#64748b">Arweave αρχεία</div>
</div>
<div style="background:#f1f5f9;border-radius:8px;padding:16px;text-align:center">
<div style="font-size:28px;font-weight:900;color:#0f172a">{voted}</div>
<div style="font-size:12px;color:#64748b">Ψηφισμένα νομοσχέδια</div>
</div>
</div>
<p style="text-align:center;margin:24px 0">
<a href="https://ekklesia.gr/el/bills" style="display:inline-block;padding:12px 24px;background:#2563eb;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px">Δείτε τα νομοσχέδια →</a>
</p>"""

    # Send as campaign to list
    result = await _brevo_post("emailCampaigns", {
        "name": f"Monthly Report {month_name}",
        "subject": f"ekklesia.gr — Μηνιαία Αναφορά {month_name}",
        "sender": SENDER,
        "type": "classic",
        "recipients": {"listIds": [LIST_ID]},
        "htmlContent": _wrap(body),
    })
    if result and result.get("id"):
        # Send immediately
        await _brevo_post(f"emailCampaigns/{result['id']}/sendNow", {})
        logger.info("[NEWSLETTER] Monthly report sent — campaign %s", result["id"])
        return True
    return False
