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
import unicodedata
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
from services.claude_usage import (
    MODEL as CLAUDE_MODEL,
    charge_reservation,
    release_budget,
    reservation_size,
    reserve_budget,
    track_usage,
)
from rate_limit import limiter
from services.agent_prompt import (
    AgentPrompt,
    UnsafeModelOutputError,
    bill_record,
    build_agent_prompt,
    fail_closed_answer,
    is_unsafe_model_output,
    knowledge_record,
    retained_record_count,
)
from services.ollama_service import (
    _DISCLAIMER_EL as _SERVICE_DISCLAIMER_EL,
    _DISCLAIMER_EN as _SERVICE_DISCLAIMER_EN,
    answer_citizen_question,
    ollama_available,
)

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

# EKA-60: payment/donation/support intake is paused (docs/community.html,
# payments.py::_payment_intake_enabled); answer before any KB or model call.
# Only intent aimed at the platform counts: bill topics such as sponsors,
# social-security contributions, pensions or public funding must reach the
# normal answer path. Patterns run on _match_text() (NFC, casefolded, Greek
# accents removed, final sigma folded to σ).
# Known limit (accepted, fail-safe): "εκκλησία" is also "church", so a
# first-person question about supporting or donating to the Church can get
# the payments-paused notice instead of a model answer; it never yields a
# payment instruction.
_PAY_TARGET_EN = (
    r"(?:ekklesia(?:\.gr)?|the (?:platform|project|initiative|team|site|app)"
    r"|(?:this|your) (?:platform|project|initiative|site|app|team|work)|you)"
)
_PROCESSORS = r"pay ?pal|stripe|iban|patreon|ko-?fi|buy ?me ?a ?coffee|revolut"
_PAY_TARGET_EL = (
    r"(?:(?:την|το|στην|στο|σε)\s+)?"
    r"(?:εκκλησια|πλατφορμα|εργο|πρωτοβουλια|ομαδα|εσασ|ekklesia(?:\.gr)?)"
)
_PAYMENT_PATTERNS = [
    # named payment processors / instruments, only in a paying context
    # ("pay with Stripe", "PayPal donate link", "IBAN for donations"); a bill
    # question that merely mentions Stripe or PayPal reaches the normal path
    rf"\b(?:pay|donate|send money|contribute|support (?:you|us)|πληρωσω|δωρισω|στειλω)\s+(?:\S+\s+){{0,2}}?(?:with|via|through|by|on|με|μεσω)\s+(?:{_PROCESSORS})\b",
    rf"\b(?:{_PROCESSORS})\s+(?:\S+\s+){{0,1}}?(?:link|button|page|account|address|donat\w*|συνδεσμοσ|λογαριασμοσ|δωρε\w*)\b",
    r"\b(?:iban|account number|bank details)\b\s+(?:\S+\s+){0,2}?(?:for|to|για|στην|στο)\s+(?:\S+\s+){0,1}?(?:donat\w*|support|δωρε\w*|ενισχυσ\w*|ekklesia|εκκλησια|πλατφορμα|you|σασ)\b",
    r"\b(?:your|σασ)\s+(?:iban|paypal|stripe|bank (?:account|details)|τραπεζικ\w* λογαριασμ\w*)\b",
    # donation/payment links or buttons
    r"\b(?:donat\w*|payment)\s+(?:link|button|page)\b",
    r"\b(?:συνδεσμοσ|link)\s+(?:\S+\s+){0,2}?(?:δωρεα|δωρεων|δωρεεσ|πληρωμη|πληρωμων)\b",
    # "do you accept donations/payments/sponsorship?"
    r"\b(?:accept|take)s?\s+(?:any\s+)?(?:donations?|payments?|sponsorships?)\b",
    r"\bδεχεστε\s+(?:\S+\s+)?(?:δωρεεσ|πληρωμεσ|χορηγιεσ|εισφορεσ)\b",
    # donate/pay/contribute to the platform
    rf"\b(?:donat\w*|pay|payments?|send money|contribut\w*|give money)\s+(?:\w+\s+){{0,3}}?(?:to|for)\s+{_PAY_TARGET_EN}\b",
    rf"\b(?:support|fund|sponsor)\s+{_PAY_TARGET_EN}\b",
    r"\b(?:i|we)\s+(?:\w+\s+){0,3}?(?:support|contribute|help)\s+(?:\w+\s+){0,3}?financially\b",
    # bare first-person intent with nothing (or only the platform) after it:
    # "Can I donate?", "Where can I donate?", "I want to donate"
    rf"\b(?:(?:how|where) (?:can|do|could) i|(?:can|could|may) i|i(?:'d| would)? (?:want|like|wish) to)"
    rf" (?:donate|make a donation|make a payment|contribute money)"
    rf"(?:\s+(?:to|for)\s+{_PAY_TARGET_EN})?\s*[?.!]*$",
    # Greek: first-person intent aimed at the platform
    rf"\b(?:δωρισω|δωρισουμε|στηριξω|στηριξουμε|υποστηριξω|ενισχυσω|πληρωσω|συνεισφερω)\s+(?:\S+\s+){{0,2}}?{_PAY_TARGET_EL}\b",
    r"\b(?:στηριξω|υποστηριξω|ενισχυσω|συνεισφερω)\s+(?:\S+\s+){0,2}?οικονομικα\b",
    rf"\bοικονομικ\w*\s+(?:στηριξη|υποστηριξη|ενισχυση|συνεισφορα)\s+(?:\S+\s+){{0,2}}?(?:στην|στο|της|του|σε)\s+(?:εκκλησια|πλατφορμα|εργο|πρωτοβουλια)",
    rf"\bκανω\s+(?:μια\s+)?δωρεα(?:\s*[;?.!]*\s*$|\s+{_PAY_TARGET_EL}\b)",
    # clitic before the verb: "Πώς μπορώ να σας στηρίξω;"
    r"\bνα\s+σασ\s+(?:στηριξω|υποστηριξω|ενισχυσω|πληρωσω|δωρισω)\b",
]
_PAYMENT_RES = [re.compile(pattern) for pattern in _PAYMENT_PATTERNS]

# Model output guard: no payment links or instruments may reach the citizen.
_PAYMENT_LINK_RE = re.compile(
    r"(?:https?://|www\.)\S*(?:paypal|stripe|buymeacoffee|patreon|ko-fi|revolut)\S*"
    # any domain with a donation term in host or path (donate.example.org,
    # example.org/donate); generic "pay" stays allowed so official pages such as
    # tax-payment guidance on gov.gr are not replaced
    r"|(?:https?://|www\.)[^\s/]*\b(?:donat\w*|contribut\w*|checkout|sponsor\w*|fundrais\w*)\b\S*"
    r"|(?:https?://|www\.)\S*/(?:donat\w*|contribut\w*|checkout|sponsor\w*|fundrais\w*)\b\S*"
    r"|\b(?:paypal\.(?:com|me)|(?:buy|donate|checkout)\.stripe\.com|buymeacoffee\.com"
    r"|patreon\.com|ko-fi\.com|revolut\.me)\b"
    r"|\b(?:iban|ιβαν)\s*:?\s*[a-z]{2}\d{2}",
    re.IGNORECASE,
)
# Unlabelled IBAN in any letter case: country letters, check digits and
# 4-character groups with at least 10 digits overall, so ordinary prose such as
# "id12 have been made into laws" is not mistaken for an account number.
_IBAN_RE = re.compile(r"\b[a-z]{2}\d{2}(?: ?[a-z0-9]{4}){3,7}(?: ?[a-z0-9]{1,4})?\b", re.IGNORECASE)


def _has_payment_link(text: str) -> bool:
    if _PAYMENT_LINK_RE.search(text or ""):
        return True
    return any(sum(ch.isdigit() for ch in m.group(0)) >= 10 for m in _IBAN_RE.finditer(text or ""))


def _match_text(text: str) -> str:
    """NFC + casefold + Greek accents removed, for intent matching only."""
    folded = unicodedata.normalize("NFD", unicodedata.normalize("NFC", text or "").casefold())
    return unicodedata.normalize(
        "NFC", "".join(ch for ch in folded if unicodedata.category(ch) != "Mn"),
    )


def _is_payment_intent(question: str) -> bool:
    text = _match_text(question)
    return any(pattern.search(text) for pattern in _PAYMENT_RES)


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


# EKA-63 canonical topics. Matched against the accent-folded, punctuation-free
# question so Greek with or without tonos behaves the same. Patterns require a
# topic phrase, never a bare generic word such as "delete" or "results".
_EKA63_TOPIC_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "data_deletion": tuple(re.compile(p) for p in (
        r"\b(delete|erase|remove|wipe)\s+(all\s+)?(of\s+)?(my|our)\s+(personal\s+)?"
        r"(data|account|identity|profile|information|info)\b",
        r"\b(account|data|identity)\s+deletion\b",
        r"\bdeletion\s+of\s+(all\s+)?(my|our)\s+(personal\s+)?(data|account|identity)\b",
        r"\brevok\w*\s+(my\s+)?(identity|key|verification)\b",
        r"\b(identity|key|verification)\s+revocation\b",
        r"(διαγραφ|διαγραψ|σβησ)\w*\s+(ολα\s+)?(τα\s+|τον\s+|την\s+|το\s+)?(προσωπικα\s+)?"
        r"(δεδομενα|λογαριασμο|ταυτοτητα|στοιχεια|προφιλ)\s+μου\b",
        r"διαγραφη\s+(του\s+|των\s+|της\s+)?(λογαριασμου|δεδομενων|ταυτοτητας|στοιχειων)\b",
        r"ανακ(αλ|λη)\w*\s+(την\s+|του\s+|της\s+|το\s+)?(ταυτοτητ|κλειδι|επαληθευσ)",
    )),
    "zk_semaphore": tuple(re.compile(p) for p in (
        r"\b(zk|zkp|zk\s+proofs?|zk\s+snarks?|semaphore|groth16)\b",
        r"\bzero\s+knowledge\b",
        r"μηδενικ\w*\s+γνωσ",
        r"σεμαφορ",
    )),
    "representative_verification": tuple(re.compile(p) for p in (
        r"\b(verify|verification|register|registration|sign\s+up|log\s+in|login)\b"
        r"[\w\s]{0,30}\b(representative|elected\s+official|mayor|councillor|councilor)s?\b",
        r"\b(representative|elected\s+official|mayor|councillor|councilor)s?\b[\w\s]{0,30}"
        r"\b(verify|verified|verification|register|registration|invite|invitation|sign\s+up|log\s+in|login)\b",
        r"\binvite\s+code\b",
        r"(επαληθευ|πιστοποι|εγγραφ|εγγραψ|συνδε)\w*[\w\s]{0,30}"
        r"(εκπροσωπ|αιρετ|δημαρχ|δημοτικ\w*\s+συμβουλ|περιφερειαρχ)",
        r"(εκπροσωπ|αιρετ|δημαρχ|δημοτικ\w*\s+συμβουλ|περιφερειαρχ)\w*[\w\s]{0,30}"
        r"(επαληθευ|πιστοποι|εγγραφ|εγγραψ|συνδε|προσκλησ)",
        r"κωδικ\w*\s+προσκλησ",
    )),
    "results_visibility": tuple(re.compile(p) for p in (
        r"\bresults?\b[\w\s]{0,40}\b(visible|invisible|hidden|shown|revealed|zero|zeroed|zeros)\b",
        r"\b(see|view)\b[\w\s]{0,20}\bresults?\b[\w\s]{0,20}\b(before|during|while|until|yet)\b",
        r"\bresults?\s+visibility\b",
        r"\bhidden\s+results?\b",
        r"αποτελεσμ\w*[\w\s]{0,40}(ορατ|κρυφ|κρυμμεν|εμφανιζ|εμφανιστ|φαινοντ|μηδεν)",
        r"(ορατ|κρυφ|κρυμμεν|εμφανιζ|εμφανιστ|φαινοντ)\w*[\w\s]{0,20}αποτελεσμ",
    )),
}
# Topics where a bill/law reference means the citizen is asking about content,
# not about the platform mechanism (e.g. a bill on deleting bank accounts).
_EKA63_BILL_EXCLUDED_TOPICS = {"data_deletion", "representative_verification"}
# Only references to a bill, not generic "law" (e.g. "delete my data under privacy law").
_EKA63_BILL_CONTEXT = re.compile(r"\bgr\s+\d{4}|\bbills?\b|νομοσχ")


def _fold_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _eka63_topic(normalized_q: str) -> str | None:
    """Return the EKA-63 topic id for a question, or None."""
    folded = " ".join(_fold_accents(normalized_q).split())
    is_bill_query = bool(_EKA63_BILL_CONTEXT.search(folded))
    for topic, patterns in _EKA63_TOPIC_PATTERNS.items():
        if topic in _EKA63_BILL_EXCLUDED_TOPICS and is_bill_query:
            continue
        if any(p.search(folded) for p in patterns):
            return topic
    return None


def _is_greek(lang: str) -> bool:
    return (lang or "el").lower().startswith("el")


def _with_disclaimer(answer: str, lang: str) -> str:
    return answer + (_DISCLAIMER_EL if _is_greek(lang) else _DISCLAIMER_EN)


def _safety_response(question: str, lang: str) -> dict | None:
    """Block unsafe voting/admin/security-bypass requests before any LLM call."""
    q = unicodedata.normalize("NFC", question or "").lower()
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


_PAYMENTS_PAUSED_EL = (
    "Η αποδοχή δωρεών και πληρωμών, καθώς και οι σχετικοί δημόσιοι σύνδεσμοι, "
    "έχουν προσωρινά ανασταλεί. Ο βοηθός δεν δέχεται πληρωμές και δεν παραπέμπει "
    "σε Stripe, PayPal ή άλλον πάροχο πληρωμών. Μη στέλνετε χρήματα μέσω "
    "συνδέσμων που λαμβάνετε σε συνομιλίες."
)
_PAYMENTS_PAUSED_EN = (
    "Public donation/payment links and payment intake are currently "
    "paused and unavailable. The assistant does not accept payments and "
    "does not refer you to Stripe, PayPal or any other payment processor. "
    "Do not send money through links received in a chat."
)


def _payments_paused_response(question: str, lang: str) -> dict:
    """Deterministic EKA-60 answer; also replaces model output that carries payment links."""
    return {
        "question": question,
        "answer": _with_disclaimer(
            _PAYMENTS_PAUSED_EL if _is_greek(lang) else _PAYMENTS_PAUSED_EN, lang,
        ),
        "model": "knowledge-base",
        "sources": [{"type": "knowledge_base", "topic": "payments_paused"}],
        "lang": lang,
    }


def _canonical_response(question: str, lang: str) -> dict | None:
    """Deterministic answers for safety/privacy concepts that must not drift."""
    q = unicodedata.normalize("NFC", question or "").lower()
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

    if _is_payment_intent(question):
        return _payments_paused_response(question, lang)

    # EKA-63: checked before the broad substring topics below so that e.g.
    # "διαύγ"/"δήμ" (municipal) or "nullifier" cannot pre-empt these facts.
    eka63_topic = _eka63_topic(normalized_q)

    if eka63_topic == "data_deletion":
        return resp(
            "Στον server υπάρχει μηχανισμός ανάκλησης ταυτότητας: με τον αριθμό "
            "τηλεφώνου και το αντίστοιχο nullifier hash, η εγγραφή ταυτότητας "
            "σημειώνεται ως ανακληθείσα (REVOKED) και μπορείτε στη συνέχεια να "
            "επαληθευτείτε ξανά. Η ανάκληση αλλάζει μόνο την κατάσταση του "
            "κλειδιού· δεν είναι γενική διαγραφή όλων των δεδομένων. Αυτή τη "
            "στιγμή η εφαρμογή και ο ιστότοπος δεν προσφέρουν κουμπί ανάκλησης ή "
            "διαγραφής. Το ιδιωτικό κλειδί υπάρχει μόνο στη συσκευή σας.",
            "The server has an identity revocation mechanism: with your phone "
            "number and the matching nullifier hash, the identity record is marked "
            "as revoked (REVOKED) and you can then verify again. Revocation only "
            "changes the key status; it is not a general deletion of all data. "
            "At the moment the app and the website do not offer a revocation or "
            "deletion button. Your private key exists only on your device.",
            "data_deletion",
        )

    if eka63_topic == "zk_semaphore":
        return resp(
            "Η ψηφοφορία με αποδείξεις μηδενικής γνώσης (ZK, Semaphore) είναι "
            "προστατευμένη λειτουργία και δεν είναι γενικά διαθέσιμη. Ο server "
            "επαληθεύει μόνο δημόσιες αποδείξεις Semaphore και μόνο όταν η "
            "λειτουργία έχει ενεργοποιηθεί ρητά για εγκεκριμένα πεδία ψηφοφορίας. "
            "Εκτός ελεγχόμενων δοκιμών, αφορά μόνο δημόσια νομοσχέδια της Βουλής "
            "σε κατάσταση ACTIVE, WINDOW_24H ή OPEN_END· σε κάθε άλλη περίπτωση το "
            "αίτημα απορρίπτεται. Η δημοσίευση στο Arweave γίνεται μόνο όταν είναι "
            "ενεργοποιημένη και η ομάδα έχει φτάσει ένα ελάχιστο μέγεθος. "
            "Από 03/10/2026 η ZK ψηφοφορία βρίσκεται σε παύση για έλεγχο ασφαλείας· "
            "η κανονική ψηφοφορία (Tier 1) λειτουργεί κανονικά.",
            "Zero-knowledge (ZK, Semaphore) voting is a guarded feature and is not "
            "generally available. The server verifies only public Semaphore proofs "
            "and only when the feature has been explicitly enabled for approved "
            "voting scopes. Outside controlled tests, it applies only to public "
            "Parliament bills in ACTIVE, WINDOW_24H or OPEN_END status; any other "
            "request is rejected. Publication to Arweave happens only when it is "
            "enabled and the group has reached a minimum size. Since 2026-10-03 "
            "ZK voting has been paused for a security review; regular (Tier 1) "
            "voting is unaffected.",
            "zk_semaphore",
        )

    if eka63_topic == "representative_verification":
        return resp(
            "Η επαλήθευση εκπροσώπων δεν είναι ανοιχτή εγγραφή. Απαιτεί έγκυρο "
            "κωδικό πρόσκλησης από τον διαχειριστή, που δεν έχει χρησιμοποιηθεί "
            "και δεν έχει λήξει, καθώς και αριθμό ΑΔΑ που επαληθεύεται στη "
            "Διαύγεια. Ο ΑΔΑ μόνος του δεν αρκεί. Μετά την επιτυχή επαλήθευση "
            "εκδίδεται token πρόσβασης με ισχύ 24 ωρών και ο κωδικός πρόσκλησης "
            "θεωρείται χρησιμοποιημένος. Εξαίρεση αποτελεί μόνο μια περιορισμένη "
            "ροή επίδειξης, που δεν ελέγχει τη Διαύγεια.",
            "Representative verification is not open registration. It requires a "
            "valid admin-issued invite code that is unused and not expired, plus an "
            "ADA number that is verified on Diavgeia. An ADA number alone is not "
            "enough. After successful verification, a 24-hour access token is "
            "issued and the invite code is marked as used. The only exception is a "
            "restricted demonstration flow, which does not check Diavgeia.",
            "representative_verification",
        )

    if eka63_topic == "results_visibility":
        return resp(
            "Στη σελίδα του νομοσχεδίου, η ορατότητα των αποτελεσμάτων ακολουθεί "
            "την κατάσταση του νομοσχεδίου. Σε νομοσχέδιο ACTIVE με την προεπιλεγμένη ρύθμιση "
            "κρυφών αποτελεσμάτων, οι μετρήσεις εμφανίζονται μηδενικές και "
            "σημειώνονται ως κρυφές μέχρι το νομοσχέδιο να περάσει σε κατάσταση "
            "με ορατά αποτελέσματα. Στις "
            "καταστάσεις WINDOW_24H, PARLIAMENT_VOTED και OPEN_END τα "
            "συγκεντρωτικά αποτελέσματα είναι ορατά. Νομοσχέδια που δεν είναι "
            "δημόσια δεν εμφανίζουν αποτελέσματα. Για τους τρέχοντες αριθμούς "
            "δείτε τη σελίδα του νομοσχεδίου.",
            "On the bill page, result visibility follows the bill status. For an ACTIVE bill with "
            "the default hidden-results setting, the counts are shown as zero and "
            "marked as hidden until the bill enters a results-visible lifecycle "
            "state. In WINDOW_24H, PARLIAMENT_VOTED "
            "and OPEN_END status, the aggregate results are visible. Bills that "
            "are not public do not show results. For current numbers, see the "
            "bill page.",
            "results_visibility",
        )

    if "private key" in q or "signing key" in q or ("ιδιωτικ" in q and "κλειδ" in q):
        return resp(
            "Το σημείο αποθήκευσης του ιδιωτικού κλειδιού εξαρτάται από την "
            "πλατφόρμα. Web Beta: φυλάσσεται στο localStorage του browser — απλή "
            "αποθήκευση browser, όχι iOS Keychain ή Android Keystore. Εφαρμογή "
            "κινητού: αποθηκεύεται μέσω Expo SecureStore, που χρησιμοποιεί Android "
            "Keystore και, στην υλοποιημένη διαδρομή κώδικα iOS, iOS Keychain. "
            "Ο server δημιουργεί το ζεύγος κλειδιών μία φορά κατά την επαλήθευση "
            "και σας παραδίδει το ιδιωτικό κλειδί μόνο μία φορά· δεν το αποθηκεύει "
            "και δεν μπορεί να το ανακτήσει αργότερα. Αν χαθεί, ακολουθείτε μόνο την επίσημη ροή "
            "επαλήθευσης/επανέκδοσης που παρέχει η εφαρμογή· δεν υπάρχει μυστική "
            "ανάκτηση από τον server.",
            "Where your private key is stored depends on the platform. Web Beta: "
            "it is kept in the browser's localStorage — plain browser storage, "
            "not iOS Keychain or Android Keystore. Mobile app: it is stored via "
            "Expo SecureStore, which uses Android Keystore and, in the implemented "
            "iOS code path, iOS Keychain. The server creates the key pair once during "
            "verification and hands you the private key a single time; it does "
            "not store it and cannot recover it later. If it is lost, use only the official app "
            "re-verification/key-rotation flow; there is no hidden server-side "
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
        for b in bills
    ]


def _kb_record(entry: KnowledgeBase, lang: str) -> dict[str, str]:
    """Build the exact localized, sanitized KB record used by prompt and source."""
    if lang == "en":
        primary_title, fallback_title = entry.title_en, entry.title_el
        primary_content, fallback_content = entry.content_en, entry.content_el
    else:
        primary_title, fallback_title = entry.title_el, entry.title_en
        primary_content, fallback_content = entry.content_el, entry.content_en
    record = knowledge_record(primary_title, primary_content)
    if not record["title"]:
        record["title"] = knowledge_record(fallback_title, "")["title"]
    if not record["content"]:
        record["content"] = knowledge_record("", fallback_content)["content"]
    return record


def _kb_sources(entries: list, lang: str) -> list[dict]:
    """Public references to the KB rows given to the model: id, category and
    title only. Content, keywords and prompt text are never exposed."""
    sources = []
    for e in entries:
        title = _kb_record(e, lang)["title"]
        sources.append({
            "type": "knowledge_base", "id": e.id, "category": e.category, "title": title,
        })
    return sources


def _sources(
    kb_entries: list, bills: list, include_bills: bool, lang: str, retained: int,
) -> list[dict]:
    """Cite only the records the model received. Sources align 1:1 with the
    context records (KB rows first, then bills); `retained` is the prefix
    length build_data_block kept under MAX_DATA_BLOCK_CHARS."""
    return (_kb_sources(kb_entries, lang) + _bill_sources(bills, include_bills))[:retained]


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
        records.append(_kb_record(e, lang))

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


CLAUDE_MAX_OUTPUT_TOKENS = 400


async def _claude_answer(question: str, context: list[dict[str, str]], lang: str) -> str | None:
    """Fallback to Claude Haiku, only inside the enforced token/cost budget."""
    if not ANTHROPIC_API_KEY:
        return None

    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        # Check credit status
        last_error = await r.get("claude:last_error") or ""
    except Exception as e:
        logger.warning("[Hybrid] Claude skipped, Redis unavailable: %s", e)
        return None
    if last_error == "credit_balance":
        return None

    # Same builder as the Ollama path: rules in `system`, untrusted data only
    # inside the escaped block in the user turn.
    prompt = build_agent_prompt(question, context, datetime.now(timezone.utc))

    # Reserve a proven upper bound of this call's tokens and cost atomically
    # before paying for it; fail closed when the budget or Redis says no.
    tokens, cost = reservation_size(prompt.system, prompt.user, CLAUDE_MAX_OUTPUT_TOKENS)
    reservation = await reserve_budget(r, tokens, cost)
    if reservation is None:
        logger.info("[Hybrid] Claude skipped: budget gate closed")
        return None

    answer, cost_booked = await _claude_request(r, prompt)
    if not cost_booked and not await charge_reservation(r, reservation, purpose="chat"):
        # Cost of a possibly billed call is unknown and could not be booked:
        # keep the reservation so it keeps blocking until it expires.
        logger.warning("[Hybrid] Claude cost unknown; reservation kept")
        return answer
    await release_budget(r, reservation)
    return answer


async def _claude_request(r: aioredis.Redis, prompt: AgentPrompt) -> tuple[str | None, bool]:
    """Perform the paid Claude Haiku call.

    Returns (answer, cost_booked). cost_booked is True only when the real usage
    was tracked or the request was rejected by the API before generation (4xx).
    """
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
                    "max_tokens": CLAUDE_MAX_OUTPUT_TOKENS,
                    "system": prompt.system,
                    "messages": [{"role": "user", "content": prompt.user}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 400 and "credit" in e.response.text.lower():
            try:
                await r.set("claude:last_error", "credit_balance")
            except Exception:
                pass
        logger.warning("[Hybrid] Claude error: %s", status)
        return None, status < 500
    except Exception as e:
        logger.warning("[Hybrid] Claude failed: %s", e)
        return None, False

    try:
        total_tokens = await track_usage(r, data.get("usage", {}), purpose="chat")
    except Exception as e:
        logger.warning("[Hybrid] Claude usage not tracked: %s", e)
        total_tokens = 0
    try:
        answer = data["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        answer = None
    logger.info("[Hybrid] Claude answered (%d tokens)", total_tokens)
    return answer, total_tokens > 0


def _is_answer_poor(answer: str) -> bool:
    """Detect if Ollama gave a poor/confused answer.

    answer_citizen_question() already appends the legal disclaimer, so judge only
    the model text: strip exactly that appended suffix (inner Markdown rules in the
    model text stay), otherwise the disclaimer alone passes the length check.
    """
    body = answer or ""
    for suffix in (_SERVICE_DISCLAIMER_EL, _SERVICE_DISCLAIMER_EN):
        if body.endswith(suffix):
            body = body[: -len(suffix)]
            break
    body = body.strip()
    if len(body) < 30:
        return True
    low = body.lower()
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
    sources = _sources(
        kb_entries, bills, include_bills, req.lang, retained_record_count(context),
    )
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
        if _has_payment_link(ollama_answer):
            logger.warning("[Hybrid] Ollama answer carried a payment link; replaced")
            return _payments_paused_response(req.question, req.lang)

    # Step 2: If Ollama failed or gave poor answer → Claude fallback
    if _is_answer_poor(ollama_answer):
        claude_answer = await _claude_answer(req.question, context, req.lang)
        if claude_answer and is_unsafe_model_output(claude_answer):
            logger.warning("[Hybrid] Claude answer rejected by output guard")
            return _output_guard_response(req.question, req.lang)
        if claude_answer and _has_payment_link(claude_answer):
            logger.warning("[Hybrid] Claude answer carried a payment link; replaced")
            return _payments_paused_response(req.question, req.lang)
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
