"""
Ollama LLM Service — llama3.2:3b
Provides: bill summaries, divergence explanations, citizen Q&A
"""
import httpx
import logging
import os

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


async def ollama_generate(prompt: str, max_tokens: int = 500) -> str:
    """Send prompt to Ollama and return response."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as e:
        logger.warning("Ollama unavailable: %s", e)
        return ""


async def ollama_available() -> bool:
    """Check if Ollama is reachable and model loaded."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return OLLAMA_MODEL in models or any(OLLAMA_MODEL.split(":")[0] in m for m in models)
    except Exception:
        return False


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
    """Deterministic structured summary from bill metadata. No hallucination."""
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
            "συγχρονιστεί από τη Βουλή των Ελλήνων (hellenicparliament.gr)."
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
            "is synced from the Hellenic Parliament (hellenicparliament.gr)."
        )
        return "\n".join(lines)


async def summarize_bill(
    title: str, content: str = "", lang: str = "el",
    pill: str = "", status: str = "", categories: list[str] | None = None,
) -> str:
    """
    Generate bill summary.
    - If real content (>500 chars) exists: use Ollama for AI summary.
    - Otherwise: structured template from metadata (no hallucination).
    """
    cats = categories or []

    # Only use Ollama when we have substantial real text
    if content and len(content) > 500 and await ollama_available():
        prompt = (
            "Summarize this Greek law in 4-5 sentences. "
            "Write ONLY in {'Greek' if lang == 'el' else 'English'}. "
            "Be specific, no jargon.\n\n"
            f"Title: {title}\n"
            f"Text: {content[:2000]}\n\n"
            "Summary:"
        )
        result = await ollama_generate(prompt, max_tokens=400)
        if result and len(result) > 50:
            return result

    # Fallback: reliable template (always correct, never hallucinates)
    return _template_summary(title, pill, status, cats, lang)


async def explain_divergence(
    bill_title: str, citizen_pct: float, parliament_result: str, lang: str = "el"
) -> str:
    """Explain why citizens and parliament voted differently."""
    if lang == "el":
        prompt = (
            "Εξήγησε σύντομα γιατί η γνώμη των πολιτών διαφέρει από την απόφαση της Βουλής.\n\n"
            f"Νόμος: {bill_title}\n"
            f"Πολίτες υπέρ: {citizen_pct:.0f}%\n"
            f"Βουλή: {parliament_result}\n\n"
            "Εξήγηση (2-3 προτάσεις):"
        )
    else:
        prompt = (
            "Briefly explain why citizens and parliament voted differently.\n\n"
            f"Law: {bill_title}\n"
            f"Citizens in favor: {citizen_pct:.0f}%\n"
            f"Parliament: {parliament_result}\n\n"
            "Explanation (2-3 sentences):"
        )
    return await ollama_generate(prompt, max_tokens=150)


async def answer_citizen_question(question: str, context: str, lang: str = "el") -> str:
    """Answer a citizen question using DB context (RAG)."""
    if lang == "el":
        prompt = (
            "Είσαι βοηθός της πλατφόρμας εκκλησία.\n"
            "Απάντησε στην ερώτηση βάσει των δεδομένων. Απλά ελληνικά, σύντομα.\n"
            "Αν δεν ξέρεις, πες ότι δεν έχεις αρκετά δεδομένα.\n\n"
            f"Δεδομένα:\n{context}\n\n"
            f"Ερώτηση: {question}\n\n"
            "Απάντηση:"
        )
    else:
        prompt = (
            "You are an assistant for the ekklesia platform.\n"
            "Answer the question based on the data. Plain English, concise.\n"
            "If you don't know, say you don't have enough data.\n\n"
            f"Data:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )
    return await ollama_generate(prompt, max_tokens=300)
