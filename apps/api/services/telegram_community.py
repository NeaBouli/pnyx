"""
Community Telegram Bot — Bill lifecycle events routed to specific topics.
Bot: @ekklesia_news_bot
Channel: Εκκλησία του Έθνους (broadcast)
Group: Forum with topic routing
"""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

NEWS_TOKEN = os.getenv("TELEGRAM_NEWS_BOT_TOKEN", "")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID", "")

# Topic thread_ids (forum group)
TOPICS = {
    "parliament":   int(os.getenv("TELEGRAM_TOPIC_PARLIAMENT", "8")),
    "region":       int(os.getenv("TELEGRAM_TOPIC_REGION", "9")),
    "municipality": int(os.getenv("TELEGRAM_TOPIC_MUNICIPALITY", "10")),
    "arweave":      int(os.getenv("TELEGRAM_TOPIC_ARWEAVE", "11")),
    "agenda":       int(os.getenv("TELEGRAM_TOPIC_AGENDA", "12")),
    "app":          int(os.getenv("TELEGRAM_TOPIC_APP", "13")),
    "platform":     int(os.getenv("TELEGRAM_TOPIC_PLATFORM", "14")),
    "urgent":       int(os.getenv("TELEGRAM_TOPIC_URGENT", "19")),
    "dev":          int(os.getenv("TELEGRAM_TOPIC_DEV", "20")),
    "parlay":       int(os.getenv("TELEGRAM_TOPIC_PARLAY", "31")),
    "bills":        int(os.getenv("TELEGRAM_TOPIC_BILLS", "36")),
}


def _topic_for_governance(level: str | None) -> int:
    """Map governance_level to the correct group topic."""
    if level == "REGIONAL":
        return TOPICS["region"]
    if level in ("MUNICIPAL", "COMMUNITY"):
        return TOPICS["municipality"]
    return TOPICS["parliament"]


async def _send(message: str, group_thread_id: int | None = None) -> bool:
    """Send to channel (always) + group topic (if thread_id given)."""
    if not NEWS_TOKEN:
        return False

    targets = []
    if CHANNEL_ID:
        targets.append({"chat_id": CHANNEL_ID})
    if GROUP_ID and group_thread_id:
        targets.append({"chat_id": GROUP_ID, "message_thread_id": group_thread_id})

    sent = 0
    for target in targets:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"https://api.telegram.org/bot{NEWS_TOKEN}/sendMessage",
                    json={**target, "text": message, "parse_mode": "HTML",
                          "disable_web_page_preview": True},
                )
                if r.status_code == 200:
                    sent += 1
                else:
                    logger.warning("[TG-NEWS] Failed %s: %s", target.get("chat_id"), r.text[:80])
        except Exception as e:
            logger.warning("[TG-NEWS] Error %s: %s", target.get("chat_id"), e)

    return sent > 0


async def notify_announced(bill_id: str, title: str, submitted_date: str | None = None,
                           governance_level: str | None = None) -> None:
    topic = _topic_for_governance(governance_level)
    date_str = submitted_date or "—"
    await _send(
        f"<b>📋 Νέο Νομοσχέδιο</b>\n\n"
        f"{title}\n\n"
        f"📅 Κατατέθηκε: {date_str}\n"
        f"👉 <a href=\"https://ekklesia.gr/el/bills/{bill_id}\">ekklesia.gr</a>",
        group_thread_id=topic,
    )


async def notify_active(bill_id: str, title: str, vote_date: str | None = None,
                        governance_level: str | None = None) -> None:
    topic = _topic_for_governance(governance_level)
    date_str = vote_date or "—"
    await _send(
        f"<b>🗳 Ψηφοφορία ανοιχτή!</b>\n\n"
        f"{title}\n\n"
        f"⏰ Ψηφίστε έως: {date_str}\n"
        f"👉 <a href=\"https://ekklesia.gr/el/bills/{bill_id}\">Ψηφίστε τώρα</a>",
        group_thread_id=topic,
    )


async def notify_window_24h(bill_id: str, title: str) -> None:
    await _send(
        f"<b>⚠️ Τελευταίες 24 ώρες!</b>\n\n"
        f"{title}\n\n"
        f"⏰ Η ψηφοφορία κλείνει αύριο\n"
        f"👉 <a href=\"https://ekklesia.gr/el/bills/{bill_id}\">Ψηφίστε τώρα</a>",
        group_thread_id=TOPICS["agenda"],
    )


async def notify_parliament_voted(bill_id: str, title: str, citizen_votes: int = 0) -> None:
    await _send(
        f"<b>🏛 Η Βουλή ψήφισε</b>\n\n"
        f"{title}\n\n"
        f"📊 Πολίτες: {citizen_votes} ψήφοι\n"
        f"👉 <a href=\"https://ekklesia.gr/el/results\">Αποτελέσματα</a>",
        group_thread_id=TOPICS["parliament"],
    )


async def notify_arweave(bill_id: str, title: str, tx_id: str) -> None:
    await _send(
        f"<b>⛓ Αρχειοθετήθηκε στο Arweave</b>\n\n"
        f"{title}\n\n"
        f"🔗 <a href=\"https://arweave.net/{tx_id}\">arweave.net/{tx_id[:12]}…</a>\n"
        f"📋 Bill: {bill_id}",
        group_thread_id=TOPICS["arweave"],
    )
