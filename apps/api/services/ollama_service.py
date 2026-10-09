"""
AI Services — Ollama + DeepL Integration
- Ollama llama3.2:3b: RAG Agent Q&A, English summaries
- DeepL Free API: EN↔EL translation (1M chars/month)
- Template fallback: when no content or services unavailable
"""
import httpx
import json
import logging
import math
import os
import re
from typing import Any, Mapping, Sequence

from services.agent_prompt import (
    UnsafeModelOutputError,
    build_agent_prompt,
    is_unsafe_model_output,
)

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "")
DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

# Batch jobs (summaries, scraper healing) keep the long generation timeout;
# the interactive citizen chat uses the bounded OLLAMA_TIMEOUT below.
OLLAMA_BATCH_TIMEOUT = 60.0
OLLAMA_TIMEOUT_DEFAULT = 20.0
OLLAMA_TIMEOUT_MIN = 1.0
OLLAMA_TIMEOUT_MAX = 120.0


def resolve_ollama_timeout(raw: str | None) -> float:
    """Parse OLLAMA_TIMEOUT seconds; unset, non-numeric, non-finite or
    out-of-range values fall back to the documented default (20s)."""
    if raw is None or not str(raw).strip():
        return OLLAMA_TIMEOUT_DEFAULT
    try:
        value = float(str(raw).strip())
    except ValueError:
        logger.warning("OLLAMA_TIMEOUT is not a number; using %.0fs", OLLAMA_TIMEOUT_DEFAULT)
        return OLLAMA_TIMEOUT_DEFAULT
    if not math.isfinite(value) or not OLLAMA_TIMEOUT_MIN <= value <= OLLAMA_TIMEOUT_MAX:
        logger.warning(
            "OLLAMA_TIMEOUT outside %.0f-%.0fs; using %.0fs",
            OLLAMA_TIMEOUT_MIN, OLLAMA_TIMEOUT_MAX, OLLAMA_TIMEOUT_DEFAULT,
        )
        return OLLAMA_TIMEOUT_DEFAULT
    return value


OLLAMA_TIMEOUT = resolve_ollama_timeout(os.getenv("OLLAMA_TIMEOUT"))


# ── DeepL Translation ────────────────────────────────────────────────────────

async def deepl_translate(text: str, target_lang: str, source_lang: str = "") -> str:
    """Translate text via DeepL Free API. Returns empty string on failure."""
    if not DEEPL_API_KEY or not text.strip():
        return ""
    try:
        params: dict = {
            "text": [text],
            "target_lang": target_lang.upper(),
        }
        if source_lang:
            params["source_lang"] = source_lang.upper()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                DEEPL_API_URL,
                headers={"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"},
                json=params,
            )
            resp.raise_for_status()
            translations = resp.json().get("translations", [])
            if translations:
                return translations[0].get("text", "").strip()
    except Exception as e:
        logger.warning("DeepL translation failed: %s", e)
    return ""


async def deepl_available() -> bool:
    """Check if DeepL API key is set and reachable."""
    if not DEEPL_API_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://api-free.deepl.com/v2/usage",
                headers={"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"},
            )
            return resp.status_code == 200
    except Exception:
        return False


# ── Ollama LLM ───────────────────────────────────────────────────────────────

async def ollama_generate(
    prompt: str, max_tokens: int = 500, system: str = "", timeout: float | None = None,
) -> str:
    """Send prompt to Ollama and return response.

    `system` travels in Ollama's separate system field so trusted rules never
    share a string with untrusted retrieval data. `timeout` is the httpx
    timeout in seconds (default: OLLAMA_BATCH_TIMEOUT).
    """
    payload: dict = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.2},
    }
    if system:
        payload["system"] = system
    try:
        async with httpx.AsyncClient(timeout=timeout or OLLAMA_BATCH_TIMEOUT) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as e:
        logger.warning("Ollama unavailable: %s", e)
        return ""


def _ollama_model_matches(available_models: list[str]) -> bool:
    """Accept exact model tags and base-name matches like llama3.2 vs llama3.2:3b."""
    requested = OLLAMA_MODEL.strip()
    requested_base = requested.split(":")[0]
    for model in available_models:
        name = model.strip()
        if name == requested or name.split(":")[0] == requested_base:
            return True
    return False


async def ollama_available() -> bool:
    """Check if Ollama is reachable and model loaded."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return _ollama_model_matches(models)
    except Exception:
        return False


def _parse_ollama_json(raw: str) -> Any | None:
    """Parse Ollama JSON mode responses, tolerating markdown fences and short prefaces."""
    cleaned = re.sub(r"```(?:json)?|```", "", raw or "", flags=re.IGNORECASE).strip()
    if not cleaned:
        return None

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None


async def ollama_json_generate(prompt: str, max_tokens: int = 500) -> Any | None:
    """Send a JSON-only prompt to Ollama and return parsed JSON data."""
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_BATCH_TIMEOUT) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"num_predict": max_tokens, "temperature": 0.1},
                },
            )
            resp.raise_for_status()
            return _parse_ollama_json(resp.json().get("response", ""))
    except Exception as e:
        logger.warning("Ollama JSON generation failed: %s", e)
        return None


# ── Bill Summaries ───────────────────────────────────────────────────────────

_STATUS_MAP_EL = {
    "ACTIVE": "Ανοιχτή ψηφοφορία",
    "ANNOUNCED": "Ανακοινωθέν",
    "WINDOW_24H": "24ωρο παράθυρο πριν τη Βουλή",
    "PARLIAMENT_VOTED": "Η Βουλή αποφάσισε",
    "OPEN_END": "Αρχείο — ανοιχτή συμμετοχή",
}

_STATUS_MAP_EN = {
    "ACTIVE": "Open for voting",
    "ANNOUNCED": "Announced",
    "WINDOW_24H": "24h window before Parliament vote",
    "PARLIAMENT_VOTED": "Parliament has decided",
    "OPEN_END": "Archive — open participation",
}


def _template_summary(
    title: str, pill: str, status: str, categories: list[str], lang: str,
) -> str:
    """Deterministic structured summary from bill metadata."""
    if lang == "el":
        lines = [f"**Νομοσχέδιο:** {title}"]
        if pill:
            lines.append(f"**Σύντομη περιγραφή:** {pill}")
        if categories:
            lines.append(f"**Θεματικές κατηγορίες:** {', '.join(categories)}")
        if status:
            lines.append(f"**Κατάσταση:** {_STATUS_MAP_EL.get(status, status)}")
        lines.append("")
        lines.append(
            "Πλήρης ανάλυση θα είναι διαθέσιμη μόλις το επίσημο κείμενο "
            "συγχρονιστεί από τη Βουλή των Ελλήνων."
        )
        return "\n".join(lines)
    else:
        lines = [f"**Bill:** {title}"]
        if pill:
            lines.append(f"**Brief description:** {pill}")
        if categories:
            lines.append(f"**Categories:** {', '.join(categories)}")
        if status:
            lines.append(f"**Status:** {_STATUS_MAP_EN.get(status, status)}")
        lines.append("")
        lines.append(
            "Full analysis will be available once the official text "
            "is synced from the Hellenic Parliament."
        )
        return "\n".join(lines)


async def summarize_bill(
    title: str, content: str = "", lang: str = "el",
    pill: str = "", status: str = "", categories: list[str] | None = None,
) -> str:
    """
    Generate bill summary. Strategy:
    1. If real content (>500 chars): Ollama EN summary → DeepL EN→EL
    2. If no content but DeepL available: template + DeepL translation
    3. Fallback: static template (always correct, no hallucination)
    """
    cats = categories or []

    # Strategy 1: Real content → Ollama (English) → DeepL (→ Greek)
    if content and len(content) > 500 and await ollama_available():
        prompt = (
            "You are a Greek legislation expert. Summarize this law in 4-5 sentences.\n"
            "Be specific about what it regulates, who it affects, and its impact.\n"
            "Write ONLY in English.\n\n"
            f"Title: {title}\n"
            f"Text: {content[:2000]}\n\n"
            "Summary:"
        )
        en_summary = await ollama_generate(prompt, max_tokens=400)
        if en_summary and len(en_summary) > 50:
            if lang == "el":
                el_summary = await deepl_translate(en_summary, "EL", "EN")
                if el_summary:
                    return el_summary
            return en_summary

    # Strategy 2: No content, but DeepL → translate title/pill for EN version
    if lang == "en" and DEEPL_API_KEY:
        en_title = await deepl_translate(title, "EN", "EL")
        en_pill = await deepl_translate(pill, "EN", "EL") if pill else ""
        if en_title:
            return _template_summary(en_title, en_pill, status, cats, "en")

    # Strategy 3: Fallback template (always works)
    return _template_summary(title, pill, status, cats, lang)


# ── Divergence Explanation ───────────────────────────────────────────────────

async def explain_divergence(
    bill_title: str, citizen_pct: float, parliament_result: str, lang: str = "el",
) -> str:
    """Explain why citizens and parliament voted differently."""
    # Generate in English (Ollama is better at EN)
    prompt = (
        "Briefly explain in 2-3 sentences why citizens and parliament "
        "may have voted differently on this law.\n\n"
        f"Law: {bill_title}\n"
        f"Citizens in favor: {citizen_pct:.0f}%\n"
        f"Parliament: {parliament_result}\n\n"
        "Explanation:"
    )
    en_result = await ollama_generate(prompt, max_tokens=150)
    if not en_result:
        return ""

    if lang == "el" and DEEPL_API_KEY:
        el_result = await deepl_translate(en_result, "EL", "EN")
        if el_result:
            return el_result

    return en_result


# ── RAG Agent Q&A ────────────────────────────────────────────────────────────

_DISCLAIMER_EL = (
    "\n\n---\n"
    "⚠️ Αυτή η πλατφόρμα δεν είναι κρατική υπηρεσία. "
    "Οι ψηφοφορίες δεν έχουν νομική δεσμευτικότητα. "
    "Είναι μια ανεξάρτητη πρωτοβουλία πολιτών για διαφάνεια "
    "και εκπαίδευση στη δημοκρατική συμμετοχή."
)

_DISCLAIMER_EN = (
    "\n\n---\n"
    "⚠️ This is not a government platform. "
    "Votes have no legal binding force. "
    "This is an independent citizen initiative for transparency "
    "and democratic education."
)


_JSON_TEXT_KEYS = ("content", "answer", "text", "response", "message")
_JSON_TEXT_PREFIX = re.compile(r'^\{\s*"(?:%s)"\s*:\s*"' % "|".join(_JSON_TEXT_KEYS))


def _unwrap_json_answer(answer: str) -> str:
    """Return the prose when a model wraps its answer as {"content": "..."}.

    The prompt shows reference data as JSON lines, and small models sometimes
    mirror that shape. Plain-text answers are returned unchanged.
    """
    text = (answer or "").strip()
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    if not stripped.startswith("{"):
        return answer
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        for key in _JSON_TEXT_KEYS:
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return answer
    # Truncated object (num_predict cut-off): keep the text of the first field.
    match = _JSON_TEXT_PREFIX.match(stripped)
    if not match:
        return answer
    body = stripped[match.end():]
    body = re.sub(r'"\s*,?\s*(?:"[^"]*"\s*:.*)?\}?\s*$', "", body, flags=re.S)
    try:
        return json.loads(f'"{body}"').strip()
    except json.JSONDecodeError:
        return body.replace('\\"', '"').replace("\\n", "\n").strip()


async def answer_citizen_question(
    question: str,
    context: str | Sequence[Mapping[str, Any]] | None,
    lang: str = "el",
) -> str:
    """
    Answer a citizen question using DB context.
    Strategy: if question is Greek → translate to EN → Ollama → translate back.

    `context` is untrusted retrieval data (records from agent._build_context).
    It is serialised by services.agent_prompt, the same builder the Claude
    fallback uses. Raises UnsafeModelOutputError if the raw model answer trips
    the output guard, before any translation can blur it.
    """
    # Translate Greek question to English for better Ollama performance
    en_question = question
    if lang == "el" and DEEPL_API_KEY:
        translated = await deepl_translate(question, "EN", "EL")
        if translated:
            en_question = translated

    # Context records stay structured and untranslated: the router cites
    # exactly these records (source/id), so they must reach the model as-is.
    from datetime import datetime as _dt
    agent_prompt = build_agent_prompt(en_question, context, _dt.now())
    en_answer = await ollama_generate(
        agent_prompt.user, max_tokens=300, system=agent_prompt.system,
        timeout=OLLAMA_TIMEOUT,
    )
    if is_unsafe_model_output(en_answer):
        logger.warning("[Agent] Ollama answer rejected by output guard")
        raise UnsafeModelOutputError("ollama")

    # Some answers come back as {"content": "..."}; keep only the prose.
    en_answer = _unwrap_json_answer(en_answer)

    # Clean Ollama warmup artifacts
    if en_answer:
        lines = en_answer.split("\n")
        clean = [l for l in lines if not (len(l) < 40 and any(x in l.lower() for x in ["great!", "excellent!", "two years", "let me", "here's"]))]
        en_answer = "\n".join(clean).strip()
    if not en_answer:
        return ""

    # Translate back to Greek
    if lang == "el" and DEEPL_API_KEY:
        el_answer = await deepl_translate(en_answer, "EL", "EN")
        if el_answer:
            return el_answer + _DISCLAIMER_EL

    disclaimer = _DISCLAIMER_EL if lang == "el" else _DISCLAIMER_EN
    return en_answer + disclaimer
