"""
MOD-10: AI Bill Scraper
Scraped echte Gesetzentwürfe von hellenicparliament.gr

KI Fallback-Kette (kein Konto, kein API Key nötig):
  L1: Ollama (self-hosted, Hetzner) — primär
  L2: Hugging Face Free Tier — fallback
  L3: Regel-basiertes Parsing — Notfall

Scraping Fallback-Kette:
  1. Direkt HTTP
  2. Jina Reader
  3. None

@ai-anchor MOD10_SCRAPER
@update-hint Ollama URL in .env: OLLAMA_URL=http://ollama:11434
@update-hint Ollama Modell: OLLAMA_MODEL=llama3.2:3b
"""
import os
import re
import hashlib
import logging
import httpx
from bs4 import BeautifulSoup
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from database import get_db
from models import ParliamentBill, BillStatus
from dependencies import verify_admin_key
from services.ollama_service import (
    OLLAMA_MODEL,
    OLLAMA_URL,
    ollama_available,
    ollama_json_generate,
)
from services.content_provenance import apply_generated_content, record_generated_content

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/scraper", tags=["MOD-10 AI Scraper"])

PARLIAMENT_BASE = "https://www.hellenicparliament.gr"

# ── KI Provider Konfiguration ─────────────────────────────────────────────────

HF_API_URL   = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
HF_API_KEY   = os.getenv("HF_API_KEY", "")


# ── Scraping Fallback-Kette ───────────────────────────────────────────────────

async def fetch_with_fallback(url: str) -> Optional[str]:
    """1. Direkt HTTP → 2. Jina Reader → 3. None"""
    headers = {
        "User-Agent": SCRAPE_USER_AGENT,
        "Accept-Language": "el-GR,el;q=0.9,en;q=0.8",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200 and len(r.text) > 500:
                logger.info(f"[MOD-10] Direkt OK: {url[:60]}")
                return r.text
    except Exception as e:
        logger.warning(f"[MOD-10] Direkt fehlgeschlagen: {e}")

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(f"https://r.jina.ai/{url}", headers={"Accept": "text/plain"})
            if r.status_code == 200 and len(r.text) > 200:
                logger.info(f"[MOD-10] Jina OK: {url[:60]}")
                return r.text
    except Exception as e:
        logger.warning(f"[MOD-10] Jina fehlgeschlagen: {e}")

    return None


def _is_nav_line(line: str) -> bool:
    """Detect navigation/boilerplate lines from parliament scraped text."""
    s = line.strip()
    # Markdown bullet links: "* [Link text](url...)"
    if re.match(r"^\*?\s*\[.+\]\(https?://", s):
        return True
    # Accessibility/skip-nav/cookie boilerplate
    if re.search(r"Μετάβαση στο κύριο|προσβασιμότητας|Ανοίξτε το μενού|Skip to|cookies.*hellenicparliament", s, re.I):
        return True
    # Section headings from parliament page navigation
    if re.match(r"^#\s*Κατατεθέντα Σχέδια", s):
        return True
    # Known parliament nav items
    _nav_keywords = (
        "Νομοθετική Διαδικασία", "Ημερ. Διάταξη", "Εβδομαδιαίο Δελτίο",
        "Κατατεθέντα Σ/Ν", "Επεξεργασία στις Επιτροπές", "Συζητήσεις & Ψήφιση",
        "Ψηφισθέντα Σ/Ν", "Ειδικές Διαδικασίες", "Κοινοβουλευτικού Ελέγχου",
        "Ημερήσιες Διατάξεις", "Ειδικές Ημερήσιες",
    )
    if any(kw in s for kw in _nav_keywords):
        return True
    return False


def extract_bill_text(html: str) -> str:
    """Extrahiert relevanten Text aus HTML oder Plain Text."""
    if not html.strip().startswith("<"):
        lines = [l.strip() for l in html.split("\n")
                 if l.strip() and len(l.strip()) > 20 and not _is_nav_line(l)]
        return "\n".join(lines[:200])

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["nav", "footer", "script", "style", "header"]):
        tag.decompose()

    main = (
        soup.find("main") or soup.find("article") or
        soup.find("div", class_=re.compile(r"content|main|body", re.I)) or
        soup.find("body")
    )
    text = main.get_text(separator="\n", strip=True) if main else soup.get_text()
    lines = [l.strip() for l in text.split("\n")
             if l.strip() and len(l.strip()) > 20 and not _is_nav_line(l)]
    return "\n".join(lines[:200])


# ── L1: Ollama (self-hosted) ─────────────────────────────────────────────────

async def summarize_ollama(bill_text: str, title_el: str) -> Optional[dict]:
    """Ollama — primärer KI Provider. Kein API Key nötig."""
    prompt = f"""Αναλύσε αυτό το ελληνικό νομοσχέδιο. Επέστρεψε ΜΟΝΟ έγκυρο JSON:

Τίτλος: {title_el}
Κείμενο: {bill_text[:2000]}

{{
  "pill_el": "1 πρόταση max 120 χαρακτήρες",
  "pill_en": "1 sentence max 120 chars",
  "summary_short_el": "3 παράγραφοι με τα κύρια σημεία",
  "summary_short_en": "3 paragraphs with main points",
  "summary_long_el": "Πλήρης ανάλυση min 200 λέξεις",
  "summary_long_en": "Full analysis min 200 words",
  "categories": ["κατηγορία1"]
}}"""

    data = await ollama_json_generate(prompt, max_tokens=900)
    if not isinstance(data, dict):
        logger.warning("[MOD-10] Ollama returned non-object JSON for: %s", title_el[:40])
        return None

    required = {
        "pill_el", "pill_en", "summary_short_el", "summary_short_en",
        "summary_long_el", "summary_long_en", "categories",
    }
    if not required.issubset(data.keys()):
        logger.warning("[MOD-10] Ollama JSON missing required fields for: %s", title_el[:40])
        return None
    if not isinstance(data.get("categories"), list):
        data["categories"] = ["Νομοθεσία"]

    logger.info(f"[MOD-10] Ollama OK: {title_el[:40]}")
    return data


# ── L2: Hugging Face Free Tier ───────────────────────────────────────────────

async def summarize_huggingface(bill_text: str, title_el: str) -> Optional[dict]:
    """HuggingFace Free Tier — kein Konto nötig für Public Models."""
    prompt = f"Summarize this Greek law in JSON format. Title: {title_el}. Text: {bill_text[:1000]}"

    try:
        headers = {"Content-Type": "application/json"}
        if HF_API_KEY:
            headers["Authorization"] = f"Bearer {HF_API_KEY}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                HF_API_URL, headers=headers,
                json={"inputs": prompt, "parameters": {"max_new_tokens": 500}}
            )
            if r.status_code == 200:
                result = r.json()
                generated = result[0].get("generated_text", "") if isinstance(result, list) else ""
                logger.info(f"[MOD-10] HuggingFace OK: {title_el[:40]}")
                return {
                    "pill_el": f"Νόμος: {title_el[:100]}",
                    "pill_en": generated[:120] if generated else f"Law: {title_el[:100]}",
                    "summary_short_el": bill_text[:300],
                    "summary_short_en": generated[:500] if generated else "Summary unavailable.",
                    "summary_long_el": bill_text[:1000],
                    "summary_long_en": generated if generated else "Analysis unavailable.",
                    "categories": ["Νομοθεσία"],
                }
    except Exception as e:
        logger.warning(f"[MOD-10] HuggingFace fehlgeschlagen: {e}")
    return None


# ── L3: Regel-basiert (Notfall) ──────────────────────────────────────────────

def summarize_rule_based(bill_text: str, title_el: str) -> dict:
    """Kein KI, kein Netzwerk. Notfall-Fallback."""
    categories = []
    kw_map = {
        "Παιδεία":    ["σχολείο", "εκπαίδευση", "πανεπιστήμιο", "μαθητ"],
        "Υγεία":      ["υγεία", "νοσοκομείο", "γιατρός", "φάρμακο"],
        "Οικονομία":  ["φόρος", "οικονομία", "επιχείρηση", "επένδυση"],
        "Περιβάλλον": ["περιβάλλον", "κλίμα", "ενέργεια", "ανανεώσιμ"],
        "Εργασία":    ["εργασία", "μισθός", "εργαζόμενος", "ασφαλιστ"],
        "Ασφάλεια":   ["αστυνομία", "ασφάλεια", "στρατός", "άμυνα"],
    }
    text_lower = bill_text.lower()
    for cat, keywords in kw_map.items():
        if any(kw in text_lower for kw in keywords):
            categories.append(cat)
    if not categories:
        categories = ["Νομοθεσία"]

    sentences = re.split(r"[.!?]", bill_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    pill = sentences[0][:120] if sentences else title_el[:120]

    logger.info(f"[MOD-10] Regel-basiert für: {title_el[:40]}")
    return {
        "pill_el": pill,
        "pill_en": f"Law: {title_el[:100]}",
        "summary_short_el": "\n".join(sentences[:5]) if sentences else bill_text[:300],
        "summary_short_en": "Automated summary unavailable — rule-based fallback.",
        "summary_long_el": bill_text[:1500],
        "summary_long_en": "Full AI analysis unavailable. Rule-based extraction only.",
        "categories": categories[:3],
    }


# ── Provider Router ───────────────────────────────────────────────────────────

async def generate_summaries(bill_text: str, title_el: str) -> dict:
    """L1: Ollama → L2: HuggingFace → L3: Regel-basiert"""
    result = await summarize_ollama(bill_text, title_el)
    if result:
        result["_provider"] = "ollama"
        return result

    result = await summarize_huggingface(bill_text, title_el)
    if result:
        result["_provider"] = "huggingface"
        return result

    result = summarize_rule_based(bill_text, title_el)
    result["_provider"] = "rule_based"
    return result


# ── Parliament Scraper ────────────────────────────────────────────────────────

PARLIAMENT_API = "https://www.hellenicparliament.gr/api.ashx"

# Soft scraping config
SCRAPE_USER_AGENT = "ekklesia.gr/1.0 (civic-tech; +https://ekklesia.gr/wiki/api.html)"
SCRAPE_DELAY_SECONDS = 5
SCRAPE_MAX_REQUESTS = 20


def _has_official_activity_date(bill: dict) -> bool:
    """True when a scraped Parliament row has a usable official date."""
    return bool(bill.get("date") or bill.get("submitted_date"))


def _normalize_scraped_title(title: str | None) -> str:
    """Normalize scraped Parliament titles without shortening them."""
    return re.sub(r"\s+", " ", title or "").strip()


def _looks_truncated_title(title: str | None) -> bool:
    """Detect UI/source ellipsis titles that should not overwrite fuller titles."""
    normalized = _normalize_scraped_title(title)
    return normalized.endswith("...") or normalized.endswith("…")


def prefer_scraped_title(existing_title: str | None, candidate_title: str | None) -> str:
    """Prefer complete scraped titles, but keep existing full titles stable."""
    existing = _normalize_scraped_title(existing_title)
    candidate = _normalize_scraped_title(candidate_title)
    if not candidate:
        return existing
    if not existing:
        return candidate
    if _looks_truncated_title(existing) and not _looks_truncated_title(candidate):
        return candidate
    return existing


def _format_parliament_date(value: str | None) -> str | None:
    """Render scraper ISO dates as Greek user-facing dates without changing stored values."""
    if not value:
        return None
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{day}/{month}/{year}"


def _build_parliament_metadata_summary(
    *,
    title_el: str,
    bill_type: str | None = None,
    ministry: str | None = None,
    phase: str | None = None,
    submitted_date: str | None = None,
    vote_date: str | None = None,
) -> str:
    """Build a safe metadata-only summary when no real Parliament text is available."""
    facts: list[str] = []
    if bill_type:
        facts.append(f"Τύπος: {bill_type}")
    if ministry:
        facts.append(f"Υπουργείο: {ministry}")
    if phase:
        facts.append(f"Φάση: {phase}")
    submitted = _format_parliament_date(submitted_date)
    if submitted:
        facts.append(f"Ημερομηνία κατάθεσης: {submitted}")
    voted = _format_parliament_date(vote_date)
    if voted:
        facts.append(f"Ημερομηνία συζήτησης/ψήφισης: {voted}")

    lines = [f"Η Βουλή δημοσίευσε εγγραφή για: {title_el}."]
    if facts:
        lines.append("; ".join(facts) + ".")
    lines.append("Για το πλήρες περιεχόμενο δείτε τα επίσημα έγγραφα της Βουλής.")
    return "\n".join(lines)


def _build_parliament_metadata_pill(
    *,
    title_el: str,
    bill_type: str | None = None,
    ministry: str | None = None,
) -> str:
    """Build a short non-interpretive Parliament pill."""
    if bill_type and ministry:
        return f"{bill_type} — {ministry}"[:200]
    if bill_type:
        return bill_type[:200]
    return title_el[:200]


def _finalize_scraped_bills(
    bills: list[dict],
    *,
    limit: int,
    require_dates: bool = False,
) -> list[dict]:
    if not require_dates:
        return bills[:limit]

    dated = [bill for bill in bills if _has_official_activity_date(bill)]
    skipped = len(bills) - len(dated)
    if skipped:
        logger.warning(
            "[SCRAPER] Skipped %d undated Parliament fallback rows while require_dates=true",
            skipped,
        )
    return dated[:limit]


def _record_probe_error(probe_errors: list[str] | None, code: str) -> None:
    if probe_errors is not None and code not in probe_errors:
        probe_errors.append(code)


def _looks_like_access_denied_body(text: str) -> bool:
    lowered = text.lower()
    return (
        "access denied" in lowered
        or "authenticationrequirederror" in lowered
        or "blocked from performing anonymous queries" in lowered
        or "you don't have permission to access" in lowered
    )


async def _fetch_jina_markdown(url: str, probe_errors: list[str] | None = None) -> Optional[str]:
    """Fetch a URL via Jina Reader and return Markdown content."""
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(f"https://r.jina.ai/{url}", headers={"Accept": "text/plain"})
            if r.status_code == 401:
                _record_probe_error(probe_errors, "jina_http_401")
                return None
            if r.status_code == 200 and _looks_like_access_denied_body(r.text):
                _record_probe_error(probe_errors, "jina_target_access_denied")
                return None
            if r.status_code == 200 and len(r.text) > 200:
                return r.text
            if r.status_code != 200:
                _record_probe_error(probe_errors, f"jina_http_{r.status_code}")
    except Exception as e:
        _record_probe_error(probe_errors, "jina_error")
        logger.warning("[SCRAPER] Jina fetch failed for %s: %s", url[:60], e)
    return None


def _parse_parliament_markdown(md: str, source_url: str) -> list[dict]:
    """Parse Jina Markdown table rows into structured bill dicts.

    Handles Κατατεθέντα, Ψηφισθέντα, and all-laws table formats.
    Κατατεθέντα columns: Date | Title+Link | Type | Ministry | PDFs
    Ψηφισθέντα columns:  Date | Title+Link | PDFs
    all-laws columns:      Title+Link | Type | Date | Phase
    """
    bills = []
    is_katatethenta = "Katatethenta" in source_url
    is_all_laws = "all-laws" in source_url

    def _extract_pdf_links(cells: list[str]) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        joined = " ".join(cells)
        pattern = re.compile(
            r"\[!\[([^\]]*)\]\(https?://[^)]*pdf\.png\)\]"
            r"\((https?://[^)]+\.pdf[^)]*)\)",
            re.IGNORECASE,
        )
        for match in pattern.finditer(joined):
            label = re.sub(r"\s+", " ", match.group(1)).strip()
            label = re.sub(r"^Image\s+\d+:\s*", "", label).strip()
            url = match.group(2).strip()
            if not any(link["url"] == url for link in links):
                links.append({"label": label or "Έγγραφο Βουλής", "url": url})
        return links

    def _build_document_block(links: list[dict[str, str]]) -> str | None:
        if not links:
            return None
        lines = ["### Πλήρη έγγραφα"]
        for index, link in enumerate(links, start=1):
            filename = link["url"].rsplit("/", 1)[-1].split("?", 1)[0]
            label = f"Έγγραφο Βουλής {index} ({filename})"
            lines.append(f"- [{label}]({link['url']})")
        return "\n".join(lines)

    for line in md.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]

        if len(cells) < 2:
            continue

        # Skip header/separator rows
        if cells[0].startswith("---") or cells[0].startswith("Βρέθηκαν") or cells[0].startswith("[Ημ.") or cells[0].startswith("Εγγραφές"):
            continue
        if cells[0].startswith("[") and "SortBy" in cells[0]:
            continue

        if is_all_laws:
            title_cell = cells[0]
            date_cell = cells[2] if len(cells) > 2 else ""
        else:
            title_cell = cells[1] if len(cells) > 1 else ""
            date_cell = cells[0]

        # Parse date (DD/MM/YYYY)
        date_match = re.match(r"(\d{2})/(\d{2})/(\d{4})", date_cell)
        if not date_match:
            continue

        day, month, year = date_match.groups()
        row_date = f"{year}-{month}-{day}T00:00:00+00:00"

        # Parse title + URL
        title_match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", title_cell)
        if not title_match:
            continue

        title_el = _normalize_scraped_title(title_match.group(1))
        detail_url = title_match.group(2).strip()

        # Extract law_id from URL
        law_id_match = re.search(r"law_id=([a-f0-9-]+)", detail_url)
        law_id = law_id_match.group(1) if law_id_match else None

        # Parse metadata
        ministry = None
        bill_type = None
        phase = None
        if is_katatethenta and len(cells) > 3:
            bill_type = cells[2] if cells[2] and not cells[2].startswith("[") else None
            ministry = cells[3] if cells[3] and not cells[3].startswith("[") else None
        elif is_all_laws:
            bill_type = cells[1] if len(cells) > 1 and cells[1] and not cells[1].startswith("[") else None
            phase = cells[3] if len(cells) > 3 and cells[3] and not cells[3].startswith("[") else None

        pdf_cells: list[str] = []
        if not is_all_laws:
            pdf_cells = cells[4:] if is_katatethenta else cells[2:]
        document_block = _build_document_block(_extract_pdf_links(pdf_cells))

        # Generate stable bill ID
        if law_id:
            bill_id_short = law_id[:8]
        else:
            import hashlib
            bill_id_short = hashlib.sha256(title_el.encode()).hexdigest()[:8]

        bill_data = {
            "title_el": title_el,
            "url": detail_url if detail_url.startswith("http") else f"{PARLIAMENT_BASE}{detail_url}",
            "law_num": None,
            "ministry": ministry,
            "type": bill_type,
            "law_id": law_id,
            "phase": phase,
        }
        if document_block:
            bill_data["summary_long_el"] = document_block
        # Κατατεθέντα/all-laws pre-vote date = submitted_date.
        # Ψηφισθέντα and all-laws discussion/completion rows = parliament_vote_date.
        if is_katatethenta or (
            is_all_laws and phase and any(marker in phase for marker in ("Έτοιμα", "Επεξεργασία", "Κατατεθέν"))
        ):
            bill_data["submitted_date"] = row_date
            bill_data["date"] = None  # no vote date yet
        else:
            bill_data["date"] = row_date  # actual/planned vote or discussion date
            bill_data["submitted_date"] = None
        bill_data["pill_el"] = _build_parliament_metadata_pill(
            title_el=title_el,
            bill_type=bill_type,
            ministry=ministry,
        )
        bill_data["summary_short_el"] = _build_parliament_metadata_summary(
            title_el=title_el,
            bill_type=bill_type,
            ministry=ministry,
            phase=phase,
            submitted_date=bill_data.get("submitted_date"),
            vote_date=bill_data.get("date"),
        )
        bills.append(bill_data)

    return bills


async def scrape_parliament_bills(
    limit: int = 10,
    require_dates: bool = False,
    probe_errors: list[str] | None = None,
) -> list[dict]:
    """Fetches latest bills from hellenicparliament.gr.

    3-stage fallback chain:
      1. REST API (api.ashx?q=laws) — fastest, structured JSON
      2. Jina HTML scrape — if API returns 403 or fails
      3. Direct HTML parse — if Jina also fails
    Each fallback is logged. Total failure = empty list + log warning.
    Set require_dates=True for scheduled/monitor paths so title-only fallback
    rows cannot masquerade as a healthy source freshness check.
    """
    import asyncio
    from datetime import timezone as _tz

    bills = []
    fallback_used = None

    # ── Stage 1: REST API ────────────────────────────────────────────
    api_blocked = False
    try:
        request_count = 0
        async with httpx.AsyncClient(timeout=15.0) as client:
            for cat in ["%CE%BD", "%CE%BD%CE%BF"]:
                if request_count >= SCRAPE_MAX_REQUESTS:
                    break
                if request_count > 0:
                    await asyncio.sleep(SCRAPE_DELAY_SECONDS)
                request_count += 1
                r = await client.get(
                    PARLIAMENT_API, params={"q": "laws", "cat": cat},
                    headers={"User-Agent": SCRAPE_USER_AGENT,
                             "Accept": "application/json", "Accept-Language": "el-GR,el;q=0.9"},
                )
                if r.status_code == 403:
                    _record_probe_error(probe_errors, "api_http_403")
                    logger.warning("[SCRAPER] Stage 1 blocked (403) — falling back to Jina")
                    api_blocked = True
                    break
                if r.status_code != 200:
                    _record_probe_error(probe_errors, f"api_http_{r.status_code}")
                    continue
                data = r.json()
                for item in data.get("Data", []):
                    date_str = item.get("LawPhaseDate", "")
                    date = None
                    if date_str:
                        ts_match = re.search(r"/Date\((\d+)", date_str)
                        if ts_match:
                            date = datetime.fromtimestamp(int(ts_match.group(1)) / 1000, tz=_tz.utc).isoformat()
                    bills.append({
                        "title_el": _normalize_scraped_title(item.get("Title")),
                        "url": f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Anazitisi-Nomothetikon-Ergon?law_id={item.get('ID', '')}",
                        "date": date,
                        "law_num": item.get("LawNum"),
                        "ministry": item.get("Ministry"),
                        "type": item.get("Type"),
                    })
                if len(bills) >= limit:
                    break
    except Exception as e:
        _record_probe_error(probe_errors, "api_error")
        logger.warning("[SCRAPER] Stage 1 error: %s — falling back to Jina", e)
        api_blocked = True

    if bills:
        finalized = _finalize_scraped_bills(bills, limit=limit, require_dates=require_dates)
        if finalized or not require_dates:
            return finalized
        logger.warning("[SCRAPER] Stage 1 returned only undated rows — falling back to Jina")
        bills = []

    # ── Stage 2: Jina Markdown Scrape (current index + specific pages) ───────
    if api_blocked or not bills:
        fallback_used = "jina"
        try:
            jina_pages = [
                f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/all-laws",                 # current index
                f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Katatethenta-Nomosxedia",   # submitted
                f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Psifisthenta-Nomoschedia",  # voted
            ]
            merged: dict[str, dict] = {}
            for page_url in jina_pages:
                md = await _fetch_jina_markdown(page_url, probe_errors=probe_errors)
                if md:
                    parsed = _parse_parliament_markdown(md, page_url)
                    for item in parsed:
                        key = item.get("law_id") or item.get("url") or item.get("title_el")
                        if not key:
                            continue
                        if key not in merged:
                            merged[key] = item
                            continue
                        existing = merged[key]
                        preferred_title = prefer_scraped_title(
                            existing.get("title_el"),
                            item.get("title_el"),
                        )
                        if preferred_title != existing.get("title_el"):
                            existing["title_el"] = preferred_title
                        for field in (
                            "summary_long_el",
                            "submitted_date",
                            "date",
                            "ministry",
                            "type",
                            "phase",
                            "law_num",
                        ):
                            if item.get(field) and not existing.get(field):
                                existing[field] = item[field]
            bills = sorted(
                merged.values(),
                key=lambda item: item.get("date") or item.get("submitted_date") or "",
                reverse=True,
            )
            if bills:
                logger.info("[SCRAPER] Fallback 1→2: Jina returned %d bills from %d pages", len(bills), len(jina_pages))
                finalized = _finalize_scraped_bills(bills, limit=limit, require_dates=require_dates)
                if finalized or not require_dates:
                    return finalized
                logger.warning("[SCRAPER] Stage 2 returned only undated rows — falling back to direct HTML")
                bills = []
        except Exception as e:
            _record_probe_error(probe_errors, "jina_stage_error")
            logger.warning("[SCRAPER] Stage 2 (Jina) error: %s — falling back to direct HTML", e)

    # ── Stage 3: Direct HTML parse (no proxy) ────────────────────────
    if not bills:
        fallback_used = "direct_html"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Psifisthenta-Nomoschedia",
                    headers={"User-Agent": SCRAPE_USER_AGENT, "Accept-Language": "el-GR,el;q=0.9"},
                )
                if r.status_code == 200:
                    if _looks_like_access_denied_body(r.text):
                        _record_probe_error(probe_errors, "direct_html_access_denied")
                        return _finalize_scraped_bills(bills, limit=limit, require_dates=require_dates)
                    soup = BeautifulSoup(r.text, "html.parser")
                    for link in soup.find_all("a", href=True):
                        text = link.get_text(strip=True)
                        href = link.get("href", "")
                        if len(text) > 20 and any(kw in text.lower() for kw in ["νόμος", "νομοσχέδιο", "ν.", "κύρωση"]):
                            full_url = href if href.startswith("http") else f"{PARLIAMENT_BASE}{href}"
                            bills.append({"title_el": _normalize_scraped_title(text), "url": full_url, "date": None})
                        if len(bills) >= limit:
                            break
                    if bills:
                        logger.info("[SCRAPER] Fallback 2→3: Direct HTML returned %d bills", len(bills))
                else:
                    _record_probe_error(probe_errors, f"direct_html_http_{r.status_code}")
        except Exception as e:
            _record_probe_error(probe_errors, "direct_html_error")
            logger.warning("[SCRAPER] Stage 3 (direct HTML) error: %s", e)

    if not bills:
        logger.warning("[SCRAPER] ALL 3 STAGES FAILED — 0 bills. Next run in 6-12h.")

    return _finalize_scraped_bills(bills, limit=limit, require_dates=require_dates)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/jobs")
async def scraper_jobs():
    """Status aller Scraper-Jobs (Redis-backed)."""
    from services.scraper_state import get_all_states
    names = [
        "parliament", "diavgeia_municipal", "notify_new_bills", "notify_results",
        "forum_sync", "bill_lifecycle", "cplm_refresh", "greek_topics",
    ]
    try:
        states = await get_all_states(names)
    except Exception:
        states = [{"name": n, "status": "unknown", "error_count": 0} for n in names]
    return {"scrapers": states}


@router.get("/status")
async def scraper_status():
    """Status aller KI-Provider."""
    ollama_ok = await ollama_available()

    return {
        "providers": {
            "ollama":      {"status": "active" if ollama_ok else "offline", "url": OLLAMA_URL, "model": OLLAMA_MODEL},
            "huggingface": {"status": "active" if HF_API_KEY else "free_tier"},
            "rule_based":  {"status": "always_available"},
        },
        "active_provider": "ollama" if ollama_ok else ("huggingface" if HF_API_KEY else "rule_based"),
    }


@router.get("/test")
async def test_scraper():
    """Testet Scraper + KI Provider ohne DB."""
    bills = await scrape_parliament_bills(limit=3)
    ollama_ok = await ollama_available()

    return {
        "scraper":        {"bills_found": len(bills), "sample": bills[:2]},
        "ai_provider":    "ollama" if ollama_ok else "rule_based",
        "ollama_running": ollama_ok,
        "ollama_url":     OLLAMA_URL,
        "ollama_model":   OLLAMA_MODEL,
    }


@router.get("/parliament/latest")
async def get_latest_from_parliament(limit: int = Query(10, le=20)):
    """Scraped aktuelle Gesetzentwürfe von hellenicparliament.gr."""
    bills = await scrape_parliament_bills(limit=limit)
    return {"source": "hellenicparliament.gr", "count": len(bills), "bills": bills}


@router.get("/parliament/freshness")
async def get_parliament_freshness_probe(limit: int = Query(20, le=20)):
    """Strict Parliament source probe for monitor freshness checks."""
    probe_errors: list[str] = []
    bills = await scrape_parliament_bills(limit=limit, require_dates=True, probe_errors=probe_errors)
    dates = [
        bill.get("date") or bill.get("submitted_date")
        for bill in bills
        if bill.get("date") or bill.get("submitted_date")
    ]
    source_status = "ok" if dates else "empty"
    if not dates and any("403" in error or "access_denied" in error or "401" in error for error in probe_errors):
        source_status = "blocked"
    return {
        "source": "hellenicparliament.gr",
        "source_status": source_status,
        "probe_errors": probe_errors,
        "count": len(bills),
        "dated_count": len(dates),
        "source_latest": max(dates) if dates else None,
        "bills": bills,
    }


@router.post("/fetch")
async def fetch_and_store(
    url: str = Query(...), title_el: str = Query(...),
    bill_id: str = Query(...),
    _auth: bool = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db)
):
    """Scraped URL → KI Zusammenfassung → DB. Admin-geschützt."""

    existing = await db.execute(select(ParliamentBill).where(ParliamentBill.id == bill_id))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Bill {bill_id} existiert bereits")

    html = await fetch_with_fallback(url)
    if not html:
        raise HTTPException(422, "Konnte URL nicht abrufen")

    text = extract_bill_text(html)
    summaries = await generate_summaries(text, title_el)

    bill = ParliamentBill(
        id=bill_id, title_el=title_el,
        title_en=summaries.get("pill_en", "")[:200],
        pill_el=summaries.get("pill_el"), pill_en=summaries.get("pill_en"),
        summary_short_el=summaries.get("summary_short_el"),
        summary_short_en=summaries.get("summary_short_en"),
        summary_long_el=summaries.get("summary_long_el"),
        summary_long_en=summaries.get("summary_long_en"),
        categories=summaries.get("categories", []),
        status=BillStatus.ANNOUNCED,
    )
    record_generated_content(bill, "pill_el", summaries.get("pill_el"))
    record_generated_content(
        bill, "summary_short_el", summaries.get("summary_short_el")
    )
    db.add(bill)
    await db.commit()

    return {
        "success": True, "bill_id": bill_id,
        "pill_el": summaries.get("pill_el"),
        "provider": summaries.get("_provider"),
        "categories": summaries.get("categories"),
    }


from pydantic import BaseModel
from typing import List


class BillImportItem(BaseModel):
    bill_id: str
    title_el: str
    ministry: str = ""
    law_num: str = ""
    law_id: str | None = None
    url: str | None = None
    type: str | None = None
    phase: str | None = None
    submitted_date: str | None = None  # ISO format
    vote_date: str | None = None  # ISO format
    pill_el: str | None = None
    summary_short_el: str | None = None
    summary_long_el: str | None = None


class BillImportRequest(BaseModel):
    admin_key: str
    bills: List[BillImportItem]


@router.post("/import")
async def import_parliament_bills(
    req: BillImportRequest,
    _auth: bool = Depends(verify_admin_key),
    db: AsyncSession = Depends(get_db)
):
    """Bulk import structured bill data.
    Called by GitHub Actions scraper workflow which fetches from
    hellenicparliament.gr API (GitHub IPs are not blocked).
    Accepts pre-structured JSON, stores new bills, skips duplicates.
    """

    imported = 0
    updated = 0
    skipped = 0

    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).replace(tzinfo=None)
        except ValueError:
            return None

    for item in req.bills:
        title = (item.title_el or "").strip()
        if not title or len(title) < 10:
            skipped += 1
            continue

        existing = await db.execute(
            select(ParliamentBill).where(ParliamentBill.id == item.bill_id)
        )
        existing_bill = existing.scalar_one_or_none()

        vote_date = _parse_date(item.vote_date)
        submitted_date = _parse_date(item.submitted_date)
        pill_el = item.pill_el or _build_parliament_metadata_pill(
            title_el=title,
            bill_type=item.type,
            ministry=item.ministry or None,
        )
        summary_short_el = item.summary_short_el or _build_parliament_metadata_summary(
            title_el=title,
            bill_type=item.type,
            ministry=item.ministry or None,
            phase=item.phase,
            submitted_date=item.submitted_date,
            vote_date=item.vote_date,
        )

        if existing_bill:
            changed = False
            preferred_title = prefer_scraped_title(existing_bill.title_el, title)
            if preferred_title and preferred_title != existing_bill.title_el:
                existing_bill.title_el = preferred_title
                changed = True
            if item.url and existing_bill.parliament_url != item.url:
                existing_bill.parliament_url = item.url
                changed = True
            if submitted_date and existing_bill.submitted_date != submitted_date:
                existing_bill.submitted_date = submitted_date
                changed = True
            if vote_date and existing_bill.parliament_vote_date != vote_date:
                existing_bill.parliament_vote_date = vote_date
                changed = True
            if apply_generated_content(existing_bill, "pill_el", pill_el):
                changed = True
            if apply_generated_content(existing_bill, "summary_short_el", summary_short_el):
                changed = True
            if item.summary_long_el and not existing_bill.summary_long_el:
                existing_bill.summary_long_el = item.summary_long_el
                changed = True
            if item.ministry and not existing_bill.categories:
                existing_bill.categories = [item.ministry]
                changed = True
            if changed:
                updated += 1
            else:
                skipped += 1
            continue

        if not submitted_date and not vote_date:
            skipped += 1
            continue

        summaries = summarize_rule_based(item.title_el, item.title_el)
        bill = ParliamentBill(
            id=item.bill_id, title_el=title,
            pill_el=pill_el,
            pill_en=f"Law {item.law_num}: {item.ministry[:80]}" if item.law_num else "",
            summary_short_el=summary_short_el,
            summary_short_en=f"Law {item.law_num} by {item.ministry}." if item.law_num else "",
            summary_long_el=item.summary_long_el,
            categories=summaries.get("categories", ["Νομοθεσία"]),
            status=BillStatus.ANNOUNCED,
            parliament_url=item.url,
            parliament_vote_date=vote_date,
            submitted_date=submitted_date,
        )
        record_generated_content(bill, "pill_el", pill_el)
        record_generated_content(bill, "summary_short_el", summary_short_el)
        db.add(bill)
        imported += 1

    await db.commit()
    logger.info(f"[MOD-10] Import: {imported} new, {updated} updated, {skipped} skipped")
    return {"success": True, "imported": imported, "updated": updated, "skipped": skipped}
