"""
Community Telegram Bot — Bill lifecycle events to channel + group.
Bot: @ekklesia_news_bot
"""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

NEWS_TOKEN = os.getenv("TELEGRAM_NEWS_BOT_TOKEN", "")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID", "")


async def send_community_update(message: str) -> bool:
    """Send message to both channel and group."""
    if not NEWS_TOKEN:
        logger.debug("[TG-NEWS] Token not set — skipping")
        return False

    sent = 0
    for chat_id in [CHANNEL_ID, GROUP_ID]:
        if not chat_id:
            continue
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"https://api.telegram.org/bot{NEWS_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": message, "parse_mode": "HTML",
                          "disable_web_page_preview": True},
                )
                if r.status_code == 200:
                    sent += 1
                else:
                    logger.warning("[TG-NEWS] Send failed to %s: %s", chat_id, r.text[:100])
        except Exception as e:
            logger.warning("[TG-NEWS] Error sending to %s: %s", chat_id, e)

    return sent > 0


async def notify_announced(bill_id: str, title: str, submitted_date: str | None = None) -> None:
    date_str = submitted_date or "—"
    await send_community_update(
        f"<b>📋 Νέο Νομοσχέδιο</b>\n\n"
        f"{title}\n\n"
        f"📅 Κατατέθηκε: {date_str}\n"
        f"👉 <a href=\"https://ekklesia.gr/el/bills/{bill_id}\">ekklesia.gr</a>"
    )


async def notify_active(bill_id: str, title: str, vote_date: str | None = None) -> None:
    date_str = vote_date or "—"
    await send_community_update(
        f"<b>🗳 Ψηφοφορία ανοιχτή!</b>\n\n"
        f"{title}\n\n"
        f"⏰ Ψηφίστε έως: {date_str}\n"
        f"👉 <a href=\"https://ekklesia.gr/el/bills/{bill_id}\">Ψηφίστε τώρα</a>"
    )


async def notify_window_24h(bill_id: str, title: str) -> None:
    await send_community_update(
        f"<b>⚠️ Τελευταίες 24 ώρες!</b>\n\n"
        f"{title}\n\n"
        f"⏰ Η ψηφοφορία κλείνει αύριο\n"
        f"👉 <a href=\"https://ekklesia.gr/el/bills/{bill_id}\">Ψηφίστε τώρα</a>"
    )


async def notify_parliament_voted(bill_id: str, title: str, citizen_votes: int = 0) -> None:
    await send_community_update(
        f"<b>🏛 Η Βουλή ψήφισε</b>\n\n"
        f"{title}\n\n"
        f"📊 Πολίτες: {citizen_votes} ψήφοι\n"
        f"👉 <a href=\"https://ekklesia.gr/el/results\">Αποτελέσματα</a>"
    )


async def notify_arweave(bill_id: str, title: str, tx_id: str) -> None:
    await send_community_update(
        f"<b>⛓ Αρχειοθετήθηκε στο Arweave</b>\n\n"
        f"{title}\n\n"
        f"🔗 <a href=\"https://arweave.net/{tx_id}\">arweave.net/{tx_id[:12]}…</a>\n"
        f"📋 Bill: {bill_id}"
    )
