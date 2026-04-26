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


async def summarize_bill(
    title: str, content: str = "", lang: str = "el",
    pill: str = "", status: str = "", categories: list[str] | None = None,
) -> str:
    """Generate plain-language summary of a parliamentary bill."""
    cats = ", ".join(categories) if categories else ""

    if lang == "el":
        if content and len(content) > 100:
            prompt = (
                "Είσαι ειδικός σε ελληνική νομοθεσία που εξηγεί νόμους σε απλούς πολίτες.\n"
                "Εξήγησε τι ρυθμίζει αυτός ο νόμος σε 4-5 προτάσεις.\n\n"
                f"Τίτλος: {title}\n"
                f"Κείμενο: {content[:2000]}\n\n"
                "Ανάλυση σε απλά ελληνικά:"
            )
        else:
            prompt = (
                "Είσαι ειδικός σε ελληνική νομοθεσία.\n"
                "Βάσει του τίτλου αυτού του νόμου, εξήγησε σε 4-5 προτάσεις:\n"
                "1. Τι πιθανώς ρυθμίζει αυτός ο νόμος\n"
                "2. Ποιους πολίτες αφορά\n"
                "3. Ποια η πιθανή επίπτωση στην καθημερινή ζωή\n\n"
                f"Νόμος: {title}\n"
                + (f"Σύνοψη: {pill}\n" if pill else "")
                + (f"Κατηγορίες: {cats}\n" if cats else "")
                + (f"Κατάσταση: {status}\n" if status else "")
                + "\nΑνάλυση σε απλά ελληνικά:"
            )
    else:
        if content and len(content) > 100:
            prompt = (
                "You are a Greek legislation expert explaining laws to ordinary citizens.\n"
                "Explain what this law regulates in 4-5 sentences.\n\n"
                f"Title: {title}\n"
                f"Content: {content[:2000]}\n\n"
                "Analysis in plain English:"
            )
        else:
            prompt = (
                "You are a Greek legislation expert.\n"
                "Based on this law's title, explain in 4-5 sentences:\n"
                "1. What this law likely regulates\n"
                "2. Which citizens it affects\n"
                "3. What impact it may have on daily life\n\n"
                f"Law: {title}\n"
                + (f"Summary: {pill}\n" if pill else "")
                + (f"Categories: {cats}\n" if cats else "")
                + (f"Status: {status}\n" if status else "")
                + "\nAnalysis in plain English:"
            )
    return await ollama_generate(prompt, max_tokens=400)


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
