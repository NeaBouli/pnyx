"""
MOD-22: Citizen FAQ — deterministic by default, hybrid only for rollback
POST /api/v1/agent/ask — canonical answers, then verbatim curated FAQ blocks
Rate limited: 5 requests/minute per IP
AGENT_MODE=hybrid restores Ollama → Claude; unset/invalid values use deterministic.
Hybrid trust boundary (EKA-58): retrieved KB/bill text is untrusted data serialised
by services.agent_prompt; model output passes an output guard that fails closed.
See docs/security/AGENT_PROMPT_TRUST_BOUNDARY.md.
"""
import json
import os
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

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
from rate_limit import enforce_route_limit, generate, limiter
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
    rf" (?:anonymously donate|donate|make (?:a donation|an anonymous donation)|make a payment|contribute money)"
    rf"(?:\s+(?:to|for)\s+{_PAY_TARGET_EN})?(?:\s+anonymously)?\s*[?.!]*$",
    # Greek: first-person intent aimed at the platform
    rf"\b(?:δωρισω|δωρισουμε|στηριξω|στηριξουμε|υποστηριξω|ενισχυσω|πληρωσω|συνεισφερω)\s+(?:\S+\s+){{0,2}}?{_PAY_TARGET_EL}\b",
    r"\b(?:στηριξω|υποστηριξω|ενισχυσω|συνεισφερω)\s+(?:\S+\s+){0,2}?οικονομικα\b",
    rf"\bοικονομικ\w*\s+(?:στηριξη|υποστηριξη|ενισχυση|συνεισφορα)\s+(?:\S+\s+){{0,2}}?(?:στην|στο|της|του|σε)\s+(?:εκκλησια|πλατφορμα|εργο|πρωτοβουλια)",
    rf"\bκανω\s+(?:μια\s+)?(?:ανωνυμη\s+)?δωρεα(?:\s+ανωνυμα)?"
    rf"(?:\s*[;?.!]*\s*$|\s+{_PAY_TARGET_EL}\b)",
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


# Load the reviewed bilingual text and compile keywords once, without I/O on
# the request path. Only keywords ending in '*' are intentional word stems;
# all others must match whole words. Text is never translated or summarised.
_FACTS = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "agent_facts.json").read_text(encoding="utf-8")
)
_FACT_KEYWORDS = {
    topic: tuple(
        re.compile(
            r"(?<!\w)" + re.escape(keyword.removesuffix("*"))
            + ("" if keyword.endswith("*") else r"(?!\w)")
        )
        for keyword in sorted({_match_text(word) for word in block["kw"]})
    )
    for topic, block in _FACTS.items()
}
_FAQ_URL = "https://ekklesia.gr/wiki/faq.html"
_SUPPORT_URL = "https://ekklesia.gr/tickets/index.html"
_FAQ_LEAD_IN = {
    "el": "Επιβεβαιωμένες πληροφορίες:",
    "en": "Verified information:",
}
_FAQ_FALLBACK = {
    "el": (
        "Δεν έχω επιβεβαιωμένη πληροφορία για αυτό. "
        f"Δείτε τις Συχνές Ερωτήσεις: {_FAQ_URL}\n"
        f"Υποστήριξη: {_SUPPORT_URL}"
    ),
    "en": (
        "I don't have verified information on this. "
        f"Please see the FAQ: {_FAQ_URL}\n"
        f"Support: {_SUPPORT_URL}"
    ),
}


def _select_fact_blocks(question: str) -> list[str]:
    """Rank by keyword hits as in the evaluation; return at most two tied best.

    Accent-equivalent keywords count once. Whole words have both boundaries;
    explicit '*' stems match at word starts. Topic ids break ties stably.
    """
    forum_route = _forum_privacy_route(question)
    folded = _match_text(question)
    if forum_route == "forum":
        return ["forum"]
    if forum_route == "feedback":
        return ["contact"] if any(p.search(folded) for p in _FACT_KEYWORDS["contact"]) else []
    canonical_topic = _eka63_topic(question)
    scored = sorted(
        ((sum(bool(pattern.search(folded)) for pattern in patterns), topic)
         for topic, patterns in _FACT_KEYWORDS.items()
         if topic != "anonymity" or canonical_topic == "anonymity"),
        key=lambda item: (-item[0], item[1]),
    )
    best = scored[0][0]
    return [topic for score, topic in scored[:2] if score > 0 and score == best]


def _deterministic_response(question: str, lang: str) -> dict:
    topics = _select_fact_blocks(question)
    if topics:
        faq_label = "Συχνές Ερωτήσεις" if lang == "el" else "FAQ"
        answer = "\n\n".join([
            _FAQ_LEAD_IN[lang],
            *(_FACTS[topic][lang] for topic in topics),
            f"{faq_label}: {_FAQ_URL}",
        ])
    else:
        answer = _FAQ_FALLBACK[lang]
    return {
        "question": question,
        "answer": _with_disclaimer(answer, lang),
        "model": "faq-deterministic",
        "sources": [{"type": "knowledge_base", "topic": topic} for topic in topics],
        "lang": lang,
    }


# EKA-63 canonical topics. Matched against the accent-folded, punctuation-free
# question so Greek with or without tonos behaves the same. Patterns require a
# topic phrase, never a bare generic word such as "delete" or "results".
_EKA63_TOPIC_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
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
}
# Topics where a bill/law reference means the citizen is asking about content,
# not about the platform mechanism (e.g. a bill on deleting bank accounts).
_EKA63_BILL_EXCLUDED_TOPICS = {"representative_verification"}


def _fold_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


_BILL_IDENTIFIER = re.compile(r"\b(?:gr-\d{4}-\d+|diav-[\w-]+)\b", re.IGNORECASE)
_LEADING_BILL_CONTEXT = re.compile(
    r"^(?:for\s+(?:the\s+)?[^,]{0,100}?\bbills?[^,]{0,80},|"
    r"regarding\s+(?:this|the)\s+bill\s*,|"
    r"για\s+το\s+νομοσχεδιο\b[^,]{0,100},|"
    r"σχετικα\s+με\s+το\s+νομοσχεδιο\b[^,]{0,100},)\s*"
)
_PRIVACY_VOCAB = {
    # Keep the same vote forms available to both subject and linkage matching.
    "own_vote": (
        r"my\s+(?:own\s+)?votes?",
        r"my\s+(?:own\s+)?ballot(?:\s+(?:choices?|choice))?",
        r"my\s+voting\s+(?:history|record)",
        r"my\s+vote\s+(?:history|record)",
        r"(?:how|what)\s+i\s+voted(?:\s+for)?",
        r"which\s+(?:way\s+)?i\s+voted(?:\s+for)?",
        r"the\s+way\s+i\s+voted",
        r"which\s+(?:(?:choice|option)\s+i\s+(?:made|chose)|way\s+i\s+voted)"
        r"(?:\s+when\s+voting)?",
        r"am\s+i\s+anonymous\s+when\s+i\s+vote",
        r"(?:η|την|στην)\s+ψηφοσ?\s+μου",
        r"το\s+ψηφοδελτιο\s+μου",
        r"ψηφ(?:ο|ων)\s+μου\s+ιστορικ\w*",
        r"(?:τι|πωσ)\s+ψηφισα",
        r"ποια\s+επιλογη\s+(?:εκανα|εχω\s+κανει)"
        r"(?:\s+στην\s+ψηφοφορια)?",
    ),
    "vote_object": (
        r"votes?",
        r"ballots?(?:\s+choices?)?",
        r"voting\s+(?:history|record)",
        r"vote\s+(?:history|record|receipt)",
        r"(?:η|την|στην)\s+ψηφοσ?",
        r"το\s+ψηφοδελτιο",
        r"ψηφ(?:ο|ων)\s+μου\s+ιστορικ\w*",
        r"(?:τι|πωσ)\s+ψηφισα",
        r"ποια\s+επιλογη\s+(?:εκανα|εχω\s+κανει)"
        r"(?:\s+στην\s+ψηφοφορια)?",
    ),
    "identity": (
        r"(?:e[\s-]?mail|electronic\s+mail)",
        r"identity",
        r"name",
        r"account",
        r"phone(?:\s+number)?",
        r"mobile(?:\s+number)?",
        r"number",
        r"ηλεκτρονικ\w*\s+ταχυδρομ\w*",
        r"τηλεφων\w*",
        r"κινητ\w*",
        r"αριθμ\w*",
        r"ονομα\w*",
        r"λογαριασμ\w*",
        r"ταυτοτητ\w*",
    ),
    "exposure": (
        r"see(?:s|n|ing)?",
        r"view\w*",
        r"visible|visibility",
        r"know\w*",
        r"find(?:s|ing)?(?:\s+out)?",
        r"learn\w*",
        r"discover\w*",
        r"infer\w*|guess\w*|deduc\w*",
        r"identify|identifies|identified|identifying|identification",
        r"associate\w*",
        r"tie\w*",
        r"reveal\w*",
        r"access\w*|acces\w*",
        r"trace\w*|track\w*",
        r"stor\w*|keep|collect|retain|save",
        r"show(?:s|ed|ing)?(?:\s+up)?",
        r"public\w*|private|secret|confidential",
        r"anonymous|annonimous|anonimous|anonymus|annonymous|anomymous|anonymity",
        r"βλεπ\w*|δει|δουν|φαινετ\w*|μαθ\w*|ξερ\w*|μαντεψ\w*|συμπερ\w*",
        r"βρ\w*|ανακαλυπτ\w*|ανακαλυψ\w*|ταυτοποι\w*",
        r"προσβασ\w*|συνδε\w*|συσχετ\w*|παρακολουθ\w*",
        r"αποθηκευ\w*|αποκαλυπτ\w*|κρατ\w*|συλλεγ\w*|διατηρ\w*|δημοσι\w*",
        r"ιδιωτικ(?:η|ο|οσ|εσ)|μυστικ\w*|απορρητ\w*|ανωνυμ\w*",
    ),
}


def _vocab_alternation(key: str) -> str:
    return "(?:" + "|".join(_PRIVACY_VOCAB[key]) + ")"


_OWN_VOTE_SUBJECT = re.compile(
    r"\b(?:" + _vocab_alternation("own_vote") + r")\b"
)
_VOTED_CHOICE = re.compile(
    r"\b(?:the\s+)?choice\s+i\s+(?:made|chose)\b|"
    r"\b(?:την\s+)?επιλογη\s+μου\b"
)
_VOTE_VERB = re.compile(r"\b(?:vot\w*|ψηφ\w*)\b")
_GENERIC_VOTES_ANONYMOUS = re.compile(
    r"\b(?:are|were|will|can|could|would)\s+(?:the\s+)?votes?\b.{0,50}\b"
    r"(?:anonymous|annonimous|anonimous|anonymus|annonymous|anomymous|confidential|secret|private)\b|"
    r"\bειναι\s+(?:οι\s+)?ψηφοι\b.{0,50}\b"
    r"(?:ανωνυμ\w*|απορρητ\w*|μυστικ\w*|ιδιωτικ\w*)\b|"
    r"\bειναι\s+(?:ανωνυμ\w*|απορρητ\w*|μυστικ\w*|ιδιωτικ\w*)\b"
    r".{0,30}\b(?:οι\s+)?ψηφοι\b"
)
_VOTE_LINK_VERB = re.compile(
    r"\b(?:link(?:s|ed|ing)?|tie(?:s|d|ing)?|connect(?:s|ed|ing)?|associat(?:e|es|ed|ing)|"
    r"trac(?:e|es|ed|ing)|track(?:s|ed|ing)|συνδε\w*|συσχετ\w*|"
    r"ταυτοποι\w*|παρακολουθ\w*)\b"
)
_VOTE_OBJECT = re.compile(
    r"\b(?:" + _vocab_alternation("own_vote") + r"|"
    + _vocab_alternation("vote_object") + r")\b"
)
_LINK_DESTINATION = re.compile(
    r"\b(?:to|with)\s+me\b|"
    r"\b(?:to|with)\s+(?:my\s+)?" + _vocab_alternation("identity") + r"\b|"
    r"\bμε\s+(?:(?:το|τη|την)\s+)?(?:εμενα|"
    + _vocab_alternation("identity") + r")\b"
)
_LINK_SOURCE = re.compile(
    r"\b(?:my\s+)?(?:identity|" + _vocab_alternation("identity") + r")\b"
)
_VOTE_EXPOSURE = re.compile(r"\b" + _vocab_alternation("exposure") + r"\b")
_SELF_VIEW = re.compile(
    r"\b(?:how|where)\s+(?:do|can|could|may)\s+i\b.{0,55}\b(?:see|view|access|find|open)\b.{0,45}"
    r"\bmy\s+(?:vote|votes|ballot|voting\s+(?:history|record)|vote\s+(?:history|record|receipt))\b|"
    r"\b(?:can|could|may)\s+i\b.{0,45}\b(?:see|view|access|find|open)\b.{0,45}"
    r"\bmy\s+(?:vote|votes|ballot|voting\s+(?:history|record)|vote\s+(?:history|record|receipt))\b|"
    r"\bwhere\b.{0,35}\b(?:can|could|may|do)\s+i\b.{0,35}"
    r"\b(?:see|view|access|find|open)\b.{0,45}"
    r"\bmy\s+(?:vote|votes|ballot|voting\s+(?:history|record)|vote\s+(?:history|record|receipt))\b|"
    r"\bcan\s+you\s+(?:please\s+)?help\s+me\s+see\b.{0,40}"
    r"\bmy\s+(?:vote|votes|ballot|voting\s+(?:history|record)|vote\s+(?:history|record|receipt))\b|"
    r"\b(?:does|can|could)\s+(?:this\s+)?(?:link|url)\b.{0,35}"
    r"\b(?:let|allow|enable)s?\s+me\s+(?:to\s+)?(?:see|view|access|open)\b.{0,40}"
    r"\bmy\s+(?:own\s+)?(?:votes?|ballot|voting\s+(?:history|record)|vote\s+(?:history|record|receipt))\b|"
    r"\bcan\s+you\b.{0,35}\b(?:send|give)\s+me\s+(?:a\s+)?(?:link|url)\b"
    r".{0,20}\bto\s+(?:see|view)\b.{0,35}\bmy\s+(?:vote|votes|ballot)\b|"
    r"\bcan\s+you\s+(?:please\s+)?show\s+me\b.{0,35}"
    r"\bmy\s+(?:vote|votes|ballot)\b|"
    r"\bμπορω\s+να\s+(?:δω|βλεπω|βρω|ανοιξω|εχω\s+προσβαση)\b.{0,55}"
    r"\b(?:ψηφο|ψηφοδελτιο|ιστορικ\w*\s+ψηφ)\w*\b|"
    r"\b(?:πωσ|που)\b.{0,25}\b(?:βλεπω|βρω|ανοιξω|εχω\s+προσβαση)\b.{0,45}"
    r"\b(?:ψηφο|ψηφοδελτιο|ιστορικ\w*\s+ψηφ)\w*\b"
)
_RESULTS_WORD = re.compile(r"\bresults?\b|\btotals?\b|\bαποτελεσμα\w*\b|\bσυνολ\w*\b")
_RESULTS_EXPOSURE = re.compile(
    r"\b(?:see|view|show|visible|visibility|hidden|invisible|display\w*|"
    r"reveal\w*|anonymous|secret|public|zero(?:ed|s)?)\b|"
    r"\b(?:βλεπ\w*|δει|δουν|ορατ\w*|κρυφ\w*|εμφανιζ\w*|"
    r"εμφανιστ\w*|φαινοντ\w*|μηδεν\w*)\b"
)
_RESULTS_WINDOW = re.compile(
    r"\b(?:before|until)\s+(?:voting|the\s+poll)\s+(?:ends?|closes?)\b|"
    r"\b(?:πριν|μεχρι)\s+(?:τελειωσει|κλεισει|κλεισει)\b"
)
_PRIVATE_KEY_PHRASE = re.compile(
    r"\b(?:private|signing)\s+keys?\b|\bkeys?\b.{0,25}\bsigning\b|"
    r"\bιδιωτικ\w*(?:\s+μου)?\s+κλειδι\w*\b|"
    r"\bκλειδι\w*\b.{0,25}\bυπογραφ\w*\b"
)
_ANDROID_PRODUCT = (
    r"\b(?:android\b.{0,30}\b(?:app|application|version|εφαρμογ\w*)\b|"
    r"(?:app|application|εφαρμογ\w*)\b.{0,30}\bandroid\b)"
)
_ANDROID_PRIVACY_POLICY = re.compile(
    r"\bprivacy\s+polic(?:y|ies)\b|"
    r"\bπολιτικ\w*\s+(?:ιδιωτικ\w*|απορρητ\w*)\b|"
    r"\b(?:ιδιωτικ\w*|απορρητ\w*)\s+πολιτικ\w*\b"
)
_ANDROID_DOWNLOAD = re.compile(
    r"(?=.*" + _ANDROID_PRODUCT + r")(?=.*\b(?:download\w*|install\w*|get|find|"
    r"where|available|availability|version|what|which|how|can|could|does|do|is|use|work|"
    r"link|url|κατεβ\w*|εγκαταστ\w*|εγκαθιστ\w*|βρω|παρω|συνδεσμ\w*)\b)"
)
_DELETE_ACTION = re.compile(
    r"\b(?:delet\w*|eras\w*|remov\w*|wipe\w*|revok\w*|revocation|"
    r"διαγραφ\w*|διαγραψ\w*|σβησ\w*|ανακαλ\w*|ανακλη\w*)\b"
)
_DELETE_TARGET = re.compile(
    r"\b(?:personal\s+)?(?:data|information|info)\b|\baccounts?\b|"
    r"\bidentit(?:y|ies)\b|\b(?:phone\s+|hlr\s+)?verification\b|"
    r"\bhlr\s+verification\b|\bphone\s+verification\b|"
    r"\b(?:προσωπικ\w*\s+)?(?:δεδομεν\w*|στοιχει\w*|πληροφορι\w*)\b|"
    r"\bλογαριασμ\w*\b|\bταυτοτητ\w*\b|\bεπαληθευσ\w*\b|"
    r"\bκλειδι\w*\b"
)
_DELETE_CONTEXT_GAP = re.compile(r"\b(?:after|before|following|μετα|πριν|κατοπιν)\b")
_LAW_REQUIREMENT = re.compile(
    r"\b(?:what\s+)?(?:does|do|will|would|should|can)\b.{0,100}"
    r"\b(?:bill|law|legislation|act)\b.{0,80}"
    r"\b(?:require|allow|permit|make|change|say|state|provide|stipulat|mean|cover)\w*\b|"
    r"\b(?:νομοσ|νομοθεσια|νομοσχεδιο)\b.{0,60}"
    r"\b(?:απαιτ\w*|επιτρεπ\w*|προβλεπ\w*|καν\w*|λε\w*)\b|"
    r"\b(?:τι\s+)?(?:προβλεπ\w*|απαιτ\w*|επιτρεπ\w*)\b.{0,50}"
    r"\b(?:νομοσ|νομοθεσια|νομοσχεδιο)\b|"
    r"\b(?:για\s+)?το\s+νομοσχεδιο\b.{0,100}\bτι\s+γινετ\w*\b"
)
_FORUM_WORD = re.compile(r"\b(?:forum|φορουμ|pnyx|πνυκα)\b")
_FEEDBACK_WORD = re.compile(r"\b(?:feedback|complaints?|καταγγελι\w*|παραπον\w*)\b")
_PRIVACY_ACTION_WORD = re.compile(
    r"\b(?:anon\w*|private|privacy|secret|confidential|delet\w*|eras\w*|"
    r"revok\w*|διαγραφ\w*|ανακαλ\w*|ανωνυμ\w*|ιδιωτικ\w*|μυστικ\w*)\b"
)


def _privacy_match_text(question: str) -> str:
    """Normalize matching text and remove bill context that is only a qualifier."""
    text = _fold_accents((question or "").casefold()).replace("ς", "σ")
    text = _BILL_IDENTIFIER.sub(" ", text)
    text = " ".join(text.split())
    while (match := _LEADING_BILL_CONTEXT.match(text)):
        text = text[match.end():]
    return " ".join(text.split())


def _has_own_vote_subject(text: str) -> bool:
    if _OWN_VOTE_SUBJECT.search(text) or _GENERIC_VOTES_ANONYMOUS.search(text):
        return True
    # "the choice I made" / "την επιλογή μου" denotes a ballot choice only
    # when a voting verb nearby makes that context explicit.
    for choice in _VOTED_CHOICE.finditer(text):
        nearby = text[max(0, choice.start() - 55):choice.end() + 55]
        if _VOTE_VERB.search(nearby):
            return True
    # In Greek, the vote linked to a phone is an implicit first-person vote.
    return bool(
        re.search(r"\bψηφο(?:σ|ς)?\b", text)
        and _VOTE_LINK_VERB.search(text)
        and re.search(r"\b(?:τηλεφων\w*|κινητ\w*|ταυτοτητ\w*|εμενα|μου)\b", text)
    )


def _has_vote_exposure(text: str) -> bool:
    if _SELF_VIEW.search(text):
        return False
    for linkage in _VOTE_LINK_VERB.finditer(text):
        before, after = text[:linkage.start()], text[linkage.end():]
        right_vote = _VOTE_OBJECT.search(after[:90])
        left_votes = list(_VOTE_OBJECT.finditer(before))
        left_vote = left_votes[-1] if left_votes and len(before) - left_votes[-1].end() <= 45 else None
        if right_vote and (
            _LINK_DESTINATION.search(after[right_vote.end():]) or _LINK_SOURCE.search(before[-65:])
        ):
            return True
        if left_vote and _LINK_DESTINATION.search(after[:90]):
            return True
    return bool(_VOTE_EXPOSURE.search(text))


def _has_deletion_target(text: str) -> bool:
    for action in _DELETE_ACTION.finditer(text):
        for target in _DELETE_TARGET.finditer(text):
            between = text[action.end():target.start()] if action.end() <= target.start() else text[target.end():action.start()]
            distance = abs(target.start() - action.end()) if action.end() <= target.start() else abs(action.start() - target.end())
            if distance <= 65 and not _DELETE_CONTEXT_GAP.search(between):
                return True
    return False


def _forum_privacy_route(question: str) -> str | None:
    text = _privacy_match_text(question)
    if not _PRIVACY_ACTION_WORD.search(text):
        return None
    if _FORUM_WORD.search(text):
        return "forum"
    if _FEEDBACK_WORD.search(text):
        return "feedback"
    return None


_CLASSIFIER_MAX_CHARS = 500


def _eka63_topic(question: str) -> str | None:
    """Classify canonical topics in fixed precedence: specific facts, then anonymity.

    Topic matching uses folded, whitespace-normalized text with bill identifiers
    and leading bill qualifiers removed. The bill-content gate also checks the
    normalized original question. Anonymity requires an own-vote subject plus an
    exposure or secrecy signal; a user's own view is excluded.
    """
    # The API accepts at most 500 characters. Bound the regex work for every
    # caller: several patterns backtrack super-linearly on long repeated input.
    question = (question or "")[:_CLASSIFIER_MAX_CHARS]
    text = _privacy_match_text(question)
    raw_text = " ".join(
        _fold_accents((question or "").casefold()).replace("ς", "σ").split()
    )
    bill_content_question = bool(
        _LAW_REQUIREMENT.search(text) or _LAW_REQUIREMENT.search(raw_text)
    )

    # Specific existing topics take precedence over the broader vote privacy rule.
    if _RESULTS_WORD.search(text) and (
        _RESULTS_EXPOSURE.search(text) or _RESULTS_WINDOW.search(text)
    ):
        return "results_visibility"
    if _PRIVATE_KEY_PHRASE.search(text):
        return "private_key"
    if _ANDROID_DOWNLOAD.search(text) and not _ANDROID_PRIVACY_POLICY.search(text):
        return "android_download"
    if _has_deletion_target(text) and not bill_content_question:
        if not (_FORUM_WORD.search(text) or _FEEDBACK_WORD.search(text)
                or re.search(r"\b(?:banks?|hospitals?|τραπεζ\w*|νοσοκομ\w*)\b", text)):
            return "data_deletion"

    if (_has_own_vote_subject(text) and _has_vote_exposure(text)
            and not bill_content_question):
        return "anonymity"

    folded = " ".join(re.sub(r"[^\w]+", " ", _fold_accents(text)).split())
    for topic, patterns in _EKA63_TOPIC_PATTERNS.items():
        if topic in _EKA63_BILL_EXCLUDED_TOPICS and re.search(
            r"\b(?:bill|law|legislation)\b|\b(?:νομοσχ\w*|νομοθεσ\w*|νομοσ)\b", folded,
        ):
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
    eka63_topic = _eka63_topic(question)

    # Privacy intent must win over verification keyword scores, even when the
    # question also mentions phone numbers, storage, HLR or SMS.
    if eka63_topic == "anonymity":
        return resp(
            _FACTS["anonymity"]["el"],
            _FACTS["anonymity"]["en"],
            "anonymity",
        )

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
            "ροή επίδειξης, που δεν ελέγχει τη Διαύγεια. "
            "Ο ΑΔΑ αποθηκεύεται στην εγγραφή της χρησιμοποιημένης πρόσκλησης, με ένδειξη και χρόνο χρήσης. Αποθηκεύεται επίσης στην εγγραφή πρόσβασης εκπροσώπου μαζί με το token πρόσβασης, τον χρόνο λήξης, τον ρόλο, την Περιφέρεια και τον Δήμο (ονόματα και αναγνωριστικά) και την ονομασία φορέα.",
            "Representative verification is not open registration. It requires a "
            "valid admin-issued invite code that is unused and not expired, plus an "
            "ADA number that is verified on Diavgeia. An ADA number alone is not "
            "enough. After successful verification, a 24-hour access token is "
            "issued and the invite code is marked as used. The only exception is a "
            "restricted demonstration flow, which does not check Diavgeia. "
            "The ADA is stored in the redeemed invitation record with its usage status and time. It is also stored in the representative access record with the access token, expiry time, role, region and municipality (names and identifiers), and organisation label.",
            "representative_verification",
        )

    if eka63_topic == "results_visibility":
        return resp(
            "Στη σελίδα του νομοσχεδίου, η ορατότητα των αποτελεσμάτων ακολουθεί "
            "την κατάσταση του νομοσχεδίου. Σε νομοσχέδιο ACTIVE με την προεπιλεγμένη ρύθμιση "
            "κρυφών αποτελεσμάτων, οι μετρήσεις μπορεί να εμφανίζονται μηδενικές και "
            "σημειώνονται ως κρυφές μέχρι το νομοσχέδιο να περάσει σε κατάσταση "
            "με ορατά αποτελέσματα. Στις "
            "καταστάσεις WINDOW_24H, PARLIAMENT_VOTED και OPEN_END τα "
            "συγκεντρωτικά αποτελέσματα μπορεί να εμφανίζονται σύμφωνα με τους "
            "κανόνες ιδιωτικότητας. Αποτελέσματα με λιγότερες από 10 ψήφους δεν "
            "εμφανίζονται δημόσια· αποκρύπτονται επίσης μικρές επιμέρους ομάδες. "
            "Οι αποκρυμμένες αυτές τιμές είναι μη διαθέσιμες, όχι μηδενικές ψήφοι. "
            "Η δημόσια ορατότητα ελέγχεται και από αποθηκευμένη σήμανση ευαισθησίας, "
            "ανεξάρτητα από το παραγόμενο κείμενο. Νομοσχέδια που δεν είναι "
            "δημόσια δεν εμφανίζουν αποτελέσματα. Για τους τρέχοντες αριθμούς "
            "δείτε τη σελίδα του νομοσχεδίου.",
            "On the bill page, result visibility follows the bill status. For an ACTIVE bill with "
            "the default hidden-results setting, the counts may be shown as zero and "
            "marked as hidden until the bill enters a results-visible lifecycle "
            "state. In WINDOW_24H, PARLIAMENT_VOTED "
            "and OPEN_END status, aggregate results may be shown subject to privacy "
            "rules. Results with fewer than 10 votes are not shown publicly; small "
            "subgroups are also withheld. These withheld values are unavailable, "
            "not zero votes. Public visibility also checks a persisted sensitivity "
            "flag, independently of generated text. Bills that "
            "are not public do not show results. For current numbers, see the "
            "bill page.",
            "results_visibility",
        )

    if eka63_topic == "private_key":
        return resp(
            _FACTS["private_key"]["el"],
            _FACTS["private_key"]["en"],
            "private_key",
        )

    if "nullifier" in q or "μηδενισ" in q or "κατακερματισ" in q:
        return resp(
            "Το nullifier hash επιτρέπει στο σύστημα να ελέγχει μοναδικότητα "
            "χωρίς να αποθηκεύει τον αριθμό τηλεφώνου. Στη Beta παράγεται ως "
            "server-salted hash, επομένως το server salt είναι κρίσιμο μυστικό. "
            "Το Ed25519 χρησιμοποιείται για ψηφιακές υπογραφές ψήφων, όχι ως "
            "γεννήτρια του nullifier. "
            "Οι ψήφοι αποθηκεύονται ψευδώνυμα· συνδέονται με ψευδώνυμο nullifier, όχι με όνομα ή αριθμό τηλεφώνου. Ο αριθμός τηλεφώνου δεν αποθηκεύεται. Δείτε την πολιτική ιδιωτικότητας: https://ekklesia.gr/wiki/privacy.html.",
            "A nullifier hash lets the system enforce uniqueness without storing "
            "the phone number. In Beta it is generated as a server-salted hash, "
            "so the server salt is a critical secret. Ed25519 is used for vote "
            "signatures; it is not the mechanism that generates the nullifier hash. "
            "Votes are stored pseudonymously; linked to a pseudonymous nullifier, not to a name or phone number. The phone number is not stored. See the privacy page: https://ekklesia.gr/wiki/privacy.html.",
            "nullifier_hash",
        )

    if "cplm" in q or "liquid mirror" in q or "πολιτικό καθρέφ" in q:
        return resp(
            "Το CPLM (Citizens Political Liquid Mirror) είναι δημόσιο "
            "συγκεντρωτικό σήμα που δείχνει τη συνολική πολιτική θέση των "
            "συμμετεχόντων πολιτών με βάση τις ψήφους τους. Δεν αποκαλύπτει "
            "μεμονωμένες ψήφους ή ταυτότητες. Αποτελέσματα με λιγότερες από "
            "10 ψήφους δεν εμφανίζονται δημόσια· αποκρύπτονται επίσης μικρές "
            "επιμέρους ομάδες. "
            "Οι ψήφοι αποθηκεύονται ψευδώνυμα· συνδέονται με ψευδώνυμο nullifier, όχι με όνομα ή αριθμό τηλεφώνου. Ο αριθμός τηλεφώνου δεν αποθηκεύεται. Δείτε την πολιτική ιδιωτικότητας: https://ekklesia.gr/wiki/privacy.html.",
            "CPLM (Citizens Political Liquid Mirror) is a public "
            "aggregate signal showing the overall political position of "
            "participating citizens based on their votes. It does not reveal "
            "individual votes or identities. Results with fewer than 10 votes "
            "are not shown publicly; small subgroups are also withheld. "
            "Votes are stored pseudonymously; linked to a pseudonymous nullifier, not to a name or phone number. The phone number is not stored. See the privacy page: https://ekklesia.gr/wiki/privacy.html.",
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

    if eka63_topic == "android_download":
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
            "ενεργό το παράθυρο WINDOW_24H, η εφαρμογή επιτρέπει μία "
            "διόρθωση ψήφου μέσω της λειτουργίας διόρθωσης. Εκτός "
            "αυτού του παραθύρου η ψήφος δεν αλλάζει.",
            "You cannot vote twice on the same bill. In WINDOW_24H, the app allows "
            "one vote correction through the correction function. Outside that "
            "window, the vote cannot be changed.",
            "vote_correction",
        )

    return None


def _should_include_bills(question: str) -> bool:
    text = " ".join(re.sub(r"[^\w]+", " ", _match_text(question)).split())
    return bool(re.search(
        r"\b(?:gr\s+\d{4}|bills?|laws?|legislation|νομοσχ\w*|νομοθεσ\w*|νομο\w*)\b"
        r"|\bβουλ\w*", text,
    ))


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


# BUG-CHAT-20261013-01: a model answer claimed the platform was down / under
# maintenance although the API had just answered with HTTP 200. Such claims are
# never knowledge-base facts, so they are replaced.
#
# Detection is sentence based on lowercased, accent-free NFKD text with
# collapsed whitespace: a sentence must START with this platform as subject
# (optionally after "unfortunately"/"currently"), followed only by copula /
# time words and then an outage predicate. Denials ("isn't under maintenance",
# "δεν ισχύει ότι ..."), conditionals ("if the platform ..."), other subjects
# or qualifiers ("η πλατφόρμα της ΑΑΔΕ", "the iOS app", "η εφαρμογή της
# απόφασης") and statements about something else therefore do not match.
# Captures the terminator so questions ("?", Greek ";") can be skipped.
_OUTAGE_SENTENCE_SPLIT = re.compile(r"([.!?;·]+|\n[ \t]*(?:[-*•]|\d+[.)])[ \t]+)")
_OUTAGE_TIME = (
    r"(?:δυστυχως|unfortunately|currently|προς το παρον|αυτη τη στιγμη|at the moment|"
    r"right now|προσωρινα|temporarily|still)"
)
_OUTAGE_LEAD = r"(?:" + _OUTAGE_TIME + r",? )*"
_OUTAGE_SUBJECT = (
    r"(?:(?:η |ο |το |the )?(?:ekklesia(?:_gr)? )?"
    r"(?:πλατφορμα|ιστοτοπος|ιστοσελιδα|βοηθος|εφαρμογη|platform|website|site|assistant|app)"
    r"(?: (?:του |της )?ekklesia(?:_gr)?| εκκλησια(?: του εθνους)?)?"
    r"|(?:το )?ekklesia(?:_gr)?)"
)
_OUTAGE_FILLER = r"(?:(?:ειναι|βρισκεται|is|" + _OUTAGE_TIME[3:-1] + r") )*"
# "does not meet the needs/requirements" (EL and EN) is not unresponsiveness.
_NOT_MEETING_NEEDS = (
    r"(?!.*(?:αναγκ|απαιτησ|προσδοκ|κριτηρι|προδιαγραφ|needs|requirement|expectation|criteri|demand))"
)
# A reason clause after an ambiguous predicate only counts when it names an
# actual service outage cause; release, approval or requirement reasons
# ("unreleased iOS version", "App Store approval", "τεχνικές απαιτήσεις") do not.
_OUTAGE_CAUSE = (
    r"(?:\w+ ){0,3}(?:συντηρησ|βλαβ|διακοπ|δυσλειτουργ|τεχνικ\w* (?:προβλημ|βλαβ|δυσλειτουργ|σφαλμ)|"
    r"maintenance|outage|downtime|server|technical (?:problem|issue|failure|difficult|error))"
)
# Unambiguous outage statements: anything may follow.
_OUTAGE_STRONG = (
    # "δεν ανταποκρίνεται στις ανάγκες/απαιτήσεις" means "does not meet", not unresponsive.
    r"(?:(?:δεν ανταποκρινεται|not responding|isn't responding|is not responding)" + _NOT_MEETING_NEEDS + r"|"
    r"εκτος λειτουργιας|(?:υπο|σε) συντηρηση|under maintenance|down for maintenance|"
    r"experiencing an outage)(?!\w)"
)
# Ambiguous ones ("not available on iOS yet", "συντηρείται από εθελοντές") only
# count when the sentence ends right after them or only time words follow.
_OUTAGE_WEAK = (
    r"(?:δεν λειτουργει|δεν ειναι διαθεσιμ[ηο]|μη διαθεσιμ[ηο]|συντηρειται|unavailable|"
    r"not available|not working|isn't working|is not working|down)"
    r"(?: " + _OUTAGE_TIME + r")*(?: (?:λογω|εξαιτιας|due to|because of) " + _OUTAGE_CAUSE + r".*)?\s*$"
)
_OUTAGE_SENTENCE = re.compile(
    "^" + _OUTAGE_LEAD + _OUTAGE_SUBJECT + " " + _OUTAGE_FILLER + "(?:" + _OUTAGE_STRONG + "|" + _OUTAGE_WEAK + ")"
)


_GREEK_LETTER = re.compile(r"[\u0370-\u03ff]")


# Chat answers are short; bounding the inspected text keeps the guard linear
# even for adversarial model output.
_OUTAGE_MAX_CHARS = 8000


def _normalize_for_outage(text: str) -> str:
    # Per-character NFKD: whole-string NFKD reorders long combining-mark runs
    # quadratically (Codex review round 7); per character it stays linear.
    lowered = text[:_OUTAGE_MAX_CHARS].lower().replace("\u2019", "'")
    folded = "".join(
        base
        for ch in lowered
        for base in unicodedata.normalize("NFKD", ch)
        if not unicodedata.combining(base)
    )
    # Markdown emphasis/headings carry no meaning here.
    folded = re.sub(r"[*_#`>]+", " ", folded)
    # Keep the domain intact for the sentence split below.
    return folded.replace("ekklesia.gr", "ekklesia_gr")


def _claims_platform_outage(text: str) -> bool:
    """True when a sentence affirmatively claims the platform itself is down or in maintenance."""
    if not text:
        return False
    parts = _OUTAGE_SENTENCE_SPLIT.split(_normalize_for_outage(text))
    for index in range(0, len(parts), 2):
        terminator = parts[index + 1] if index + 1 < len(parts) else ""
        # "?" always ends a question; ";" is the Greek question mark but an
        # ordinary clause separator in English.
        if "?" in terminator or (";" in terminator and _GREEK_LETTER.search(parts[index])):
            continue  # a question, not an assertion
        # Plain line breaks wrap a sentence; they never start a new one.
        normalized = " ".join(parts[index].split())
        if normalized and _OUTAGE_SENTENCE.search(normalized):
            return True
    return False


def _outage_claim_response(question: str, lang: str, sources: list[dict]) -> dict:
    """Neutral reply instead of an invented outage claim; keeps the retrieved sources.

    The chat cannot verify platform health, so the reply neither claims an
    outage nor asserts that everything works.
    """
    answer = (
        "Δεν βρήκα επιβεβαιωμένη απάντηση σε αυτή την ερώτηση. Δεν έχω επιβεβαιωμένη "
        "πληροφορία για βλάβη ή συντήρηση της πλατφόρμας· δείτε τις πηγές παρακάτω ή το Wiki."
        if _is_greek(lang)
        else "I could not find a confirmed answer to this question. I have no confirmed "
        "information about an outage or maintenance of the platform; please see the sources below or the Wiki."
    )
    return {
        "question": question,
        "answer": _with_disclaimer(answer, lang),
        "model": "outage-guard",
        "sources": sources,
        "lang": lang,
    }


def _output_guard_response(question: str, lang: str) -> dict:
    """Neutral fail-closed reply; never echoes the rejected model text."""
    return {
        "question": question,
        "answer": _with_disclaimer(fail_closed_answer(lang), lang),
        "model": "output-guard",
        "sources": [],
        "lang": lang,
    }


@router.post("/ask", dependencies=[Depends(enforce_route_limit)])
@generate
async def ask_agent(
    request: Request,
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
):
    """Safety/canonical answers first, then a deterministic FAQ with disclaimer.

    Only AGENT_MODE=hybrid enables the legacy database and hybrid assistant path.
    """
    safety = _safety_response(req.question, req.lang)
    if safety:
        return safety

    canonical = _canonical_response(req.question, req.lang)
    if canonical:
        return canonical

    # The reviewed forum FAQ also handles forum privacy/deletion in hybrid mode.
    if _forum_privacy_route(req.question) == "forum":
        return _deterministic_response(req.question, req.lang)

    if os.getenv("AGENT_MODE") != "hybrid":
        return _deterministic_response(req.question, req.lang)

    context, bills, include_bills, kb_entries = await _build_context(req.question, req.lang, db)
    sources = _sources(
        kb_entries, bills, include_bills, req.lang, retained_record_count(context),
    )
    model_used = "assistant"

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
        if _claims_platform_outage(ollama_answer):
            logger.warning("[Hybrid] chat answer path=outage-guard (ollama claimed an outage)")
            return _outage_claim_response(req.question, req.lang, sources)

    # Step 2: If Ollama failed or gave poor answer → Claude fallback
    if _is_answer_poor(ollama_answer):
        claude_answer = await _claude_answer(req.question, context, req.lang)
        if claude_answer and is_unsafe_model_output(claude_answer):
            logger.warning("[Hybrid] Claude answer rejected by output guard")
            return _output_guard_response(req.question, req.lang)
        if claude_answer and _has_payment_link(claude_answer):
            logger.warning("[Hybrid] Claude answer carried a payment link; replaced")
            return _payments_paused_response(req.question, req.lang)
        if claude_answer and _claims_platform_outage(claude_answer):
            logger.warning("[Hybrid] chat answer path=outage-guard (claude claimed an outage)")
            return _outage_claim_response(req.question, req.lang, sources)
        if claude_answer:
            model_used = "assistant"
            logger.warning("[Hybrid] chat answer path=claude")
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
        logger.warning("[Hybrid] chat answer path=none (assistant unavailable)")
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

    logger.warning("[Hybrid] chat answer path=ollama")
    return {
        "question": req.question,
        "answer": ollama_answer,
        "model": model_used,
        "sources": sources,
        "lang": req.lang,
    }
