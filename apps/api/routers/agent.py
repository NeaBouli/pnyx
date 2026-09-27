"""
MOD-22: Hybrid RAG Agent — Citizen Q&A
POST /api/v1/agent/ask — Ollama first, Claude fallback for complex questions
Rate limited: 5 requests/minute per IP
Strategy: Ollama (local, fast, free) → Claude Haiku (API, smart, costs tokens)
Trust boundary (EKA-58): retrieved KB/bill text is untrusted data serialised by
services.agent_prompt; model output passes an output guard that fails closed.
See docs/security/AGENT_PROMPT_TRUST_BOUNDARY.md.
"""
import os
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import redis.asyncio as aioredis

from database import get_db
from models import ParliamentBill, BillStatus, KnowledgeBase
from services.bill_visibility import public_bill_filter
from services.claude_usage import MODEL as CLAUDE_MODEL, track_usage
from rate_limit import limiter
from services.agent_prompt import (
    UnsafeModelOutputError,
    bill_record,
    build_agent_prompt,
    fail_closed_answer,
    is_unsafe_model_output,
    knowledge_record,
)
from services.ollama_service import answer_citizen_question, ollama_available

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")


router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

# `el`/`en` plus optional region/script subtags (el-GR, en_US, en-Latn-GB).
_LANG_TAG = re.compile(r"(el|en)(?:[-_][a-z0-9]{1,8})*")
_MAX_LANG_TAG = 35


def canonical_lang(value: object) -> str:
    """Canonicalise a request language to exactly `el` or `en`.

    The primary subtag decides (el-GR -> el, en-US -> en) so KB language and
    disclaimer always agree. Any other value is rejected (HTTP 422); there is
    no silent default for unsupported languages.
    """
    if not isinstance(value, str):
        raise ValueError("lang must be a string")
    tag = value.strip().lower()
    match = _LANG_TAG.fullmatch(tag) if len(tag) <= _MAX_LANG_TAG else None
    if not match:
        raise ValueError("lang must be 'el' or 'en' (optionally with a region, e.g. el-GR)")
    return match.group(1)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    # Omitted -> "el"; always canonical ("el" | "en") after validation.
    lang: str = "el"

    @field_validator("lang", mode="before")
    @classmethod
    def _canonical_lang(cls, value: object) -> str:
        return canonical_lang(value)


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
    normalized_q = re.sub(r"[^\w\u0370-\u03ff]+", " ", q, flags=re.UNICODE).strip()
    greek = _is_greek(lang)

    def resp(answer_el: str, answer_en: str, topic: str) -> dict:
        return {
            "question": question,
            "answer": _with_disclaimer(answer_el if greek else answer_en, lang),
            "model": "knowledge-base",
            "sources": [{"type": "knowledge_base", "topic": topic}],
            "lang": lang,
        }

    if normalized_q in {
        "hallo", "hello", "hello there", "hey", "good morning",
        "good evening", "γεια", "γεια σου", "γεια σας", "γειά", "γειά σου",
        "γειά σας", "χαίρετε", "καλημέρα", "καλησπέρα", "καληνύχτα",
    }:
        return resp(
            "Γεια σας! Μπορώ να βοηθήσω με νομοσχέδια, ψηφοφορίες, "
            "επαλήθευση, το Forum και τη λειτουργία της πλατφόρμας. "
            "Τι θα θέλατε να μάθετε;",
            "Hello! I can help with bills, voting, verification, the Forum, "
            "and how the platform works. What would you like to know?",
            "assistant_help",
        )

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
            "Το nullifier hash επιτρέπει στο σύστημα να ελέγχει μοναδικότητα "
            "χωρίς να αποθηκεύει τον αριθμό τηλεφώνου. Στη Beta παράγεται ως "
            "server-salted hash, επομένως το server salt είναι κρίσιμο μυστικό. "
            "Το Ed25519 χρησιμοποιείται για ψηφιακές υπογραφές ψήφων, όχι ως "
            "γεννήτρια του nullifier.",
            "A nullifier hash lets the system enforce uniqueness without storing "
            "the phone number. In Beta it is generated as a server-salted hash, "
            "so the server salt is a critical secret. Ed25519 is used for vote "
            "signatures; it is not the mechanism that generates the nullifier hash.",
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
    return [
        {"type": "parliament_bill", "bill_id": b.id, "title": b.title_el or b.title_en}
        for b in bills[:5]
    ]


def _kb_sources(entries: list, lang: str) -> list[dict]:
    """Public references to the KB rows given to the model: id, category and
    title only. Content, keywords and prompt text are never exposed."""
    sources = []
    for e in entries:
        title = (e.title_en if lang == "en" else None) or e.title_el
        sources.append({
            "type": "knowledge_base", "id": e.id, "category": e.category, "title": title,
        })
    return sources


def _sources(kb_entries: list, bills: list, include_bills: bool, lang: str) -> list[dict]:
    return _kb_sources(kb_entries, lang) + _bill_sources(bills, include_bills)


async def _build_context(
    question: str, lang: str, db: AsyncSession,
) -> tuple[list[dict[str, str]], list, bool, list]:
    """Build RAG context records (untrusted data) from Knowledge Base + Bills."""
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

    records = []
    for e in relevant:
        title = e.title_en if lang == "en" else e.title_el
        content = e.content_en if lang == "en" else e.content_el
        records.append(knowledge_record(title, content))

    # Bills context: only attach live bills when the question actually asks
    # about bills/laws. Generic platform/privacy questions should cite KB only.
    include_bills = _should_include_bills(question)
    bills = []
    if include_bills:
        result = await db.execute(
            select(ParliamentBill)
            .where(ParliamentBill.status.in_([
                BillStatus.ACTIVE, BillStatus.ANNOUNCED, BillStatus.WINDOW_24H,
                BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END,
            ]))
            .where(public_bill_filter())
            .order_by(ParliamentBill.created_at.desc())
            .limit(10)
        )
        bills = result.scalars().all()
        for b in bills:
            title = b.title_el or b.title_en or b.id
            records.append(bill_record(b.id, title, b.status.value, b.pill_el))

    return records, bills, include_bills, relevant


async def _claude_answer(question: str, context: list[dict[str, str]], lang: str) -> str | None:
    """Fallback to Claude Haiku for complex questions."""
    if not ANTHROPIC_API_KEY:
        return None

    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    # Check credit status
    last_error = await r.get("claude:last_error") or ""
    if last_error == "credit_balance":
        return None

    # Same builder as the Ollama path: rules in `system`, untrusted data only
    # inside the escaped block in the user turn.
    prompt = build_agent_prompt(question, context, datetime.now(timezone.utc))

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
                    "model": CLAUDE_MODEL,
                    "max_tokens": 400,
                    "system": prompt.system,
                    "messages": [{"role": "user", "content": prompt.user}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

            usage = data.get("usage", {})
            total_tokens = await track_usage(r, usage, purpose="chat")

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
        "δεν διαθέτω αρκετά στοιχεία",
        "δεν διαθέτω αρκετές πληροφορίες",
        "i don't have enough",
        "not enough information",
        "δεν μπόρεσα να απαντήσω",
        "i couldn't answer",
        "δεν μπορώ",
        "i cannot",
        "μπρίκι",  # confused Greek word
        "not available in my",
        "δεν εμφανίζεται",
        "i'm not sure what",
    ]
    return any(sig in low for sig in bad_signals)


def _output_guard_response(question: str, lang: str) -> dict:
    """Neutral fail-closed reply; never echoes the rejected model text."""
    return {
        "question": question,
        "answer": _with_disclaimer(fail_closed_answer(lang), lang),
        "model": "output-guard",
        "sources": [],
        "lang": lang,
    }


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
    4. Output guard: instruction echo / rule leak / role override → fail closed
    5. Always append disclaimer
    """
    safety = _safety_response(req.question, req.lang)
    if safety:
        return safety

    canonical = _canonical_response(req.question, req.lang)
    if canonical:
        return canonical

    context, bills, include_bills, kb_entries = await _build_context(req.question, req.lang, db)
    sources = _sources(kb_entries, bills, include_bills, req.lang)
    model_used = "ollama"

    # Step 1: Try Ollama (bounded by OLLAMA_TIMEOUT inside ollama_service)
    ollama_answer = ""
    if await ollama_available():
        try:
            ollama_answer = await answer_citizen_question(req.question, context, req.lang)
        except UnsafeModelOutputError:
            return _output_guard_response(req.question, req.lang)
        if is_unsafe_model_output(ollama_answer):
            logger.warning("[Hybrid] Ollama answer rejected by output guard")
            return _output_guard_response(req.question, req.lang)

    # Step 2: If Ollama failed or gave poor answer → Claude fallback
    if _is_answer_poor(ollama_answer):
        claude_answer = await _claude_answer(req.question, context, req.lang)
        if claude_answer and is_unsafe_model_output(claude_answer):
            logger.warning("[Hybrid] Claude answer rejected by output guard")
            return _output_guard_response(req.question, req.lang)
        if claude_answer:
            model_used = "claude-haiku"
            return {
                "question": req.question,
                "answer": _with_disclaimer(claude_answer, req.lang),
                "model": model_used,
                "sources": sources,
                "lang": req.lang,
            }
        ollama_answer = ""

    # Step 3: Return Ollama answer (or error)
    if not ollama_answer:
        fallback = (
            "Ο βοηθός δεν είναι διαθέσιμος αυτή τη στιγμή. Δοκιμάστε ξανά αργότερα."
            if req.lang == "el"
            else "Assistant is currently unavailable. Please try again later."
        )
        return {
            "question": req.question,
            "answer": _with_disclaimer(fallback, req.lang),
            "model": "none",
            "sources": [],
            "lang": req.lang,
        }

    return {
        "question": req.question,
        "answer": ollama_answer,
        "model": model_used,
        "sources": sources,
        "lang": req.lang,
    }
