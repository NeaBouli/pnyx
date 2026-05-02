"""
MOD-22: Hybrid RAG Agent — Citizen Q&A
POST /api/v1/agent/ask — Ollama first, Claude fallback for complex questions
Rate limited: 5 requests/minute per IP
Strategy: Ollama (local, fast, free) → Claude Haiku (API, smart, costs tokens)
"""
import os
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
import httpx
import redis.asyncio as aioredis

from database import get_db
from models import ParliamentBill, BillStatus, KnowledgeBase
from services.ollama_service import answer_citizen_question, ollama_available

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "20"))


def _get_real_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_get_real_ip)
router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    lang: str = "el"


_DISCLAIMER_EL = (
    "\n\n---\n"
    "⚠️ Αυτή η πλατφόρμα δεν είναι κρατική υπηρεσία. "
    "Οι ψηφοφορίες δεν έχουν νομική δεσμευτικότητα. "
    "Είναι μια ανεξάρτητη πρωτοβουλία πολιτών."
)
_DISCLAIMER_EN = (
    "\n\n---\n"
    "⚠️ This is not a government platform. "
    "Votes have no legal binding force."
)

_SAFETY_PATTERNS = [
    "admin key", "admin_key", "bypass", "verification bypass", "fake vote",
    "fake votes", "create votes", "create fake", "manipulate vote",
    "vote manipulation", "stuff ballot", "ballot stuffing", "forge vote",
    "forged vote", "ψεύτικες ψήφ", "πλαστές ψήφ", "παράκαμψη",
    "κλειδί admin", "admin κλειδί", "χειραγώγηση ψήφ",
]

_BILL_QUERY_PATTERNS = [
    r"\bGR-\d{4}",
    r"\bbill(s)?\b",
    r"\bparliamentary bill(s)?\b",
    r"\blegislation\b",
    r"\blaw(s)?\b",
    r"νομοσχ",
    r"νόμ",
    r"βουλ",
]


def _is_greek(lang: str) -> bool:
    return (lang or "el").lower().startswith("el")


def _with_disclaimer(answer: str, lang: str) -> str:
    return answer + (_DISCLAIMER_EL if _is_greek(lang) else _DISCLAIMER_EN)


def _safety_response(question: str, lang: str) -> dict | None:
    """Block unsafe voting/admin/security-bypass requests before any LLM call."""
    q = (question or "").lower()
    if not any(pattern in q for pattern in _SAFETY_PATTERNS):
        return None

    if _is_greek(lang):
        answer = (
            "Δεν μπορώ να βοηθήσω με δημιουργία ψεύτικων ψήφων, παράκαμψη "
            "επαλήθευσης, admin keys ή χειραγώγηση ψηφοφορίας. Για νόμιμες "
            "δοκιμές χρησιμοποιήστε μόνο επίσημο test/staging περιβάλλον, "
            "test fixtures ή εργαλεία που έχει εγκρίνει ο διαχειριστής."
        )
    else:
        answer = (
            "I cannot help create fake votes, bypass verification, obtain admin "
            "keys, or manipulate voting. For legitimate testing, use only an "
            "official test/staging environment, approved test fixtures, or admin "
            "tools designed for non-production data."
        )

    return {
        "question": question,
        "answer": _with_disclaimer(answer, lang),
        "model": "safety-filter",
        "sources": [],
        "lang": lang,
    }


def _canonical_response(question: str, lang: str) -> dict | None:
    """Deterministic answers for safety/privacy concepts that must not drift."""
    q = (question or "").lower()
    greek = _is_greek(lang)

    def resp(answer_el: str, answer_en: str, topic: str) -> dict:
        return {
            "question": question,
            "answer": _with_disclaimer(answer_el if greek else answer_en, lang),
            "model": "knowledge-base",
            "sources": [{"type": "knowledge_base", "topic": topic}],
            "lang": lang,
        }

    if "private key" in q or "ιδιωτικό κλειδί" in q:
        return resp(
            "Το ιδιωτικό κλειδί αποθηκεύεται μόνο στη συσκευή σας. Ο server δεν "
            "το γνωρίζει και δεν μπορεί να το ανακτήσει. Αν χαθεί, ακολουθείτε "
            "μόνο την επίσημη ροή επαλήθευσης/επανέκδοσης που παρέχει η εφαρμογή· "
            "δεν υπάρχει μυστική ανάκτηση από τον server.",
            "Your private key is stored only on your device. The server does not "
            "know it and cannot recover it. If it is lost, use only the official "
            "app re-verification/key-rotation flow; there is no hidden server-side "
            "recovery process.",
            "private_key",
        )

    if "nullifier" in q or "μηδενισ" in q or "κατακερματισ" in q:
        return resp(
            "Το nullifier hash είναι ένας μη αναστρέψιμος κρυπτογραφικός "
            "αναγνωριστής που επιτρέπει στο σύστημα να ελέγχει μοναδικότητα "
            "χωρίς να αποθηκεύει τον αριθμό τηλεφώνου. Το Ed25519 χρησιμοποιείται "
            "για ψηφιακές υπογραφές ψήφων, όχι ως γεννήτρια του nullifier.",
            "A nullifier hash is a non-reversible cryptographic identifier used "
            "to enforce uniqueness without storing the phone number. Ed25519 is "
            "used for vote signatures; it is not the mechanism that generates the "
            "nullifier hash.",
            "nullifier_hash",
        )

    if "cplm" in q or "liquid mirror" in q or "πολιτικό καθρέφ" in q:
        return resp(
            "Το CPLM (Citizens Political Liquid Mirror) είναι δημόσιο, ανώνυμο "
            "συγκεντρωτικό σήμα που δείχνει τη συνολική πολιτική θέση των "
            "συμμετεχόντων πολιτών με βάση τις ψήφους τους. Δεν αποκαλύπτει "
            "μεμονωμένες ψήφους ή ταυτότητες.",
            "CPLM (Citizens Political Liquid Mirror) is a public, anonymous "
            "aggregate signal showing the overall political position of "
            "participating citizens based on their votes. It does not reveal "
            "individual votes or identities.",
            "cplm",
        )

    if "gov.gr" in q or "govgr" in q or "oauth" in q:
        return resp(
            "Η σύνδεση gov.gr είναι τεχνικά προβλεπόμενη αλλά δεν θεωρείται "
            "ενεργή παραγωγικά. Είναι deferred/gated και χρειάζεται επίσημη "
            "έγκριση/ενεργοποίηση. Μέχρι τότε χρησιμοποιείται η επαλήθευση HLR "
            "όπου είναι διαθέσιμη.",
            "gov.gr OAuth is technically planned but must not be treated as "
            "active in production. It is deferred/gated and requires official "
            "approval/activation. Until then, HLR verification is used where "
            "available.",
            "govgr",
        )

    if "municipal" in q or "municipalities" in q or "diavgeia" in q or "δήμ" in q or "διαύγ" in q:
        return resp(
            "Η πλατφόρμα περιλαμβάνει και δημοτικό/περιφερειακό πεδίο μέσω "
            "Διαύγειας: οι πολίτες μπορούν να βλέπουν σχετικές αποφάσεις και, "
            "όπου η λειτουργία είναι ενεργή, να συμμετέχουν σε μη δεσμευτικές "
            "ψηφοφορίες για τοπικά θέματα.",
            "The platform includes municipal/regional scope through Diavgeia: "
            "citizens can view relevant decisions and, where the feature is "
            "active, participate in non-binding votes on local issues.",
            "municipal",
        )

    if "android" in q or "download" in q or "κατεβάζ" in q or "εφαρμογή" in q:
        return resp(
            "Η εφαρμογή Android διανέμεται μέσω των επίσημων καναλιών που "
            "ανακοινώνει το ekklesia.gr, όπως η άμεση λήψη APK, F-Droid/IzzyOnDroid "
            "ή Google Play όταν είναι διαθέσιμο. Χρησιμοποιείτε μόνο συνδέσμους "
            "από το ekklesia.gr ή το επίσημο repository.",
            "The Android app is distributed through official channels announced "
            "by ekklesia.gr, such as direct APK download, F-Droid/IzzyOnDroid, "
            "or Google Play when available. Use only links from ekklesia.gr or "
            "the official repository.",
            "android_download",
        )

    if "change my vote" in q or "correct" in q or "vote twice" in q or "αλλάξ" in q or "διόρθ" in q:
        return resp(
            "Δεν μπορείτε να ψηφίσετε δύο φορές στο ίδιο νομοσχέδιο. Αν είναι "
            "ενεργό το παράθυρο διόρθωσης, η εφαρμογή μπορεί να επιτρέπει μία "
            "διόρθωση ψήφου σύμφωνα με την κατάσταση του νομοσχεδίου. Εκτός "
            "αυτού του παραθύρου η ψήφος δεν αλλάζει.",
            "You cannot vote twice on the same bill. If the correction window is "
            "active, the app may allow one vote correction depending on the bill "
            "status. Outside that window, the vote cannot be changed.",
            "vote_correction",
        )

    return None


def _should_include_bills(question: str) -> bool:
    q = question or ""
    q_lower = q.lower()
    return any(re.search(pattern, q_lower) for pattern in _BILL_QUERY_PATTERNS)


def _bill_sources(bills: list, include_bills: bool) -> list[dict]:
    if not include_bills:
        return []
    return [{"bill_id": b.id, "title": b.title_el or b.title_en} for b in bills[:5]]


async def _build_context(question: str, lang: str, db: AsyncSession) -> tuple[str, list, bool]:
    """Build RAG context from Knowledge Base + Bills."""
    # Knowledge Base — full-text search (all entries, ranked by relevance)
    q_lower = question.lower()
    q_words = [w for w in q_lower.split() if len(w) > 2]

    kb_result = await db.execute(
        select(KnowledgeBase).order_by(KnowledgeBase.priority).limit(20)
    )
    kb_entries = kb_result.scalars().all()

    # Score each entry by keyword + title match
    scored = []
    for entry in kb_entries:
        score = 0
        keywords = entry.keywords or []
        title = (entry.title_el or "").lower()
        content = (entry.content_el or "").lower()
        for kw in keywords:
            if kw.lower() in q_lower:
                score += 3
        for w in q_words:
            if w in title:
                score += 2
            if w in content:
                score += 1
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: -x[0])
    relevant = [e for _, e in scored[:5]]

    # If no keyword match, include top-priority entries as fallback
    if not relevant:
        relevant = [e for e in kb_entries if e.priority == 1][:3]

    kb_parts = []
    for e in relevant:
        title = e.title_en if lang == "en" else e.title_el
        content = e.content_en if lang == "en" else e.content_el
        kb_parts.append(f"### {title}\n{content}")
    kb_context = "\n\n".join(kb_parts)

    # Bills context: only attach live bills when the question actually asks
    # about bills/laws. Generic platform/privacy questions should cite KB only.
    include_bills = _should_include_bills(question)
    bills = []
    bill_parts = []
    if include_bills:
        result = await db.execute(
            select(ParliamentBill)
            .where(ParliamentBill.status.in_([
                BillStatus.ACTIVE, BillStatus.ANNOUNCED, BillStatus.WINDOW_24H,
                BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END,
            ]))
            .order_by(ParliamentBill.created_at.desc())
            .limit(10)
        )
        bills = result.scalars().all()
        for b in bills:
            title = b.title_el or b.title_en or b.id
            line = f"- {b.id}: {title} (Status: {b.status.value})"
            if b.pill_el:
                line += f" — {b.pill_el[:200]}"
            bill_parts.append(line)

    parts = []
    if kb_context:
        parts.append("=== KNOWLEDGE BASE ===\n" + kb_context)
    if bill_parts:
        parts.append("=== ACTIVE BILLS ===\n" + "\n".join(bill_parts))

    context = "\n\n".join(parts) if parts else "No data available."
    return context, bills, include_bills


async def _claude_answer(question: str, context: str, lang: str) -> str | None:
    """Fallback to Claude Haiku for complex questions."""
    if not ANTHROPIC_API_KEY:
        return None

    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    # Check credit status
    last_error = await r.get("claude:last_error") or ""
    if last_error == "credit_balance":
        return None

    now = datetime.now(timezone.utc)
    system = (
        "You are the ekklesia.gr AI assistant — a Greek digital democracy platform.\n\n"
        "CONTEXT (use this as primary source of truth):\n"
        f"{context}\n\n"
        "RULES:\n"
        "- Answer in the same language as the question\n"
        "- Be concise, factual, politically neutral\n"
        "- If the answer is in the context, use it directly\n"
        "- If not in context, say you don't have enough data\n"
        "- NEVER invent facts about the platform\n"
        f"- Today: {now.strftime('%d %B %Y')}. Year: 2026.\n"
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 400,
                    "system": system,
                    "messages": [{"role": "user", "content": question}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

            usage = data.get("usage", {})
            total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

            # Track tokens
            today_key = f"claude:tokens:{now.strftime('%Y-%m-%d')}"
            month_key = f"claude:tokens:{now.strftime('%Y-%m')}"
            await r.incrby(today_key, total_tokens)
            await r.expire(today_key, 86400 * 2)
            await r.incrby(month_key, total_tokens)
            await r.expire(month_key, 86400 * 35)

            logger.info("[Hybrid] Claude answered (%d tokens)", total_tokens)
            return data["content"][0]["text"]

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400 and "credit" in e.response.text.lower():
            await r.set("claude:last_error", "credit_balance")
        logger.warning("[Hybrid] Claude error: %s", e.response.status_code)
        return None
    except Exception as e:
        logger.warning("[Hybrid] Claude failed: %s", e)
        return None


def _is_answer_poor(answer: str) -> bool:
    """Detect if Ollama gave a poor/confused answer."""
    if not answer or len(answer) < 30:
        return True
    low = answer.lower()
    bad_signals = [
        "δεν έχω αρκετά δεδομένα",
        "i don't have enough",
        "δεν μπορώ",
        "i cannot",
        "μπρίκι",  # confused Greek word
        "not available in my",
        "δεν εμφανίζεται",
        "i'm not sure what",
    ]
    return any(sig in low for sig in bad_signals)


@router.post("/ask")
@limiter.limit("5/minute")
async def ask_agent(
    request: Request,
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Hybrid RAG Agent — Ollama first, Claude Haiku fallback.
    Strategy:
    1. Build context from Knowledge Base + Bills
    2. Try Ollama (local, free, fast)
    3. If Ollama fails or gives poor answer → Claude Haiku (API, smart)
    4. Always append disclaimer
    """
    safety = _safety_response(req.question, req.lang)
    if safety:
        return safety

    canonical = _canonical_response(req.question, req.lang)
    if canonical:
        return canonical

    context, bills, include_bills = await _build_context(req.question, req.lang, db)
    disclaimer = _DISCLAIMER_EL if req.lang == "el" else _DISCLAIMER_EN
    model_used = "ollama"

    # Step 1: Try Ollama (with reduced timeout)
    ollama_answer = ""
    if await ollama_available():
        ollama_answer = await answer_citizen_question(req.question, context, req.lang)

    # Step 2: If Ollama failed or gave poor answer → Claude fallback
    if _is_answer_poor(ollama_answer):
        claude_answer = await _claude_answer(req.question, context, req.lang)
        if claude_answer:
            model_used = "claude-haiku"
            return {
                "question": req.question,
                "answer": claude_answer + disclaimer,
                "model": model_used,
                "sources": _bill_sources(bills, include_bills),
                "lang": req.lang,
            }

    # Step 3: Return Ollama answer (or error)
    if not ollama_answer:
        fallback = (
            "Ο βοηθός δεν είναι διαθέσιμος αυτή τη στιγμή. Δοκιμάστε ξανά αργότερα."
            if req.lang == "el"
            else "Assistant is currently unavailable. Please try again later."
        )
        return {
            "question": req.question,
            "answer": fallback + disclaimer,
            "model": "none",
            "sources": [],
            "lang": req.lang,
        }

    return {
        "question": req.question,
        "answer": ollama_answer,
        "model": model_used,
        "sources": _bill_sources(bills, include_bills),
        "lang": req.lang,
    }
