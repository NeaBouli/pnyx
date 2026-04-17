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
@update-hint Ollama Modell: OLLAMA_MODEL=llama3.2 oder mistral oder qwen2.5
"""
import os
import re
import json
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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/scraper", tags=["MOD-10 AI Scraper"])

PARLIAMENT_BASE = "https://www.hellenicparliament.gr"

# ── KI Provider Konfiguration ─────────────────────────────────────────────────

OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
HF_API_URL   = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
HF_API_KEY   = os.getenv("HF_API_KEY", "")


# ── Scraping Fallback-Kette ───────────────────────────────────────────────────

async def fetch_with_fallback(url: str) -> Optional[str]:
    """1. Direkt HTTP → 2. Jina Reader → 3. None"""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Ekklesia/1.0; +https://ekklesia.gr)",
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


def extract_bill_text(html: str) -> str:
    """Extrahiert relevanten Text aus HTML oder Plain Text."""
    if not html.strip().startswith("<"):
        lines = [l.strip() for l in html.split("\n") if l.strip() and len(l.strip()) > 20]
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
    lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 20]
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

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}
            )
            r.raise_for_status()
            raw = r.json().get("response", "")
            raw = re.sub(r"```json|```", "", raw).strip()
            data = json.loads(raw)
            logger.info(f"[MOD-10] Ollama OK: {title_el[:40]}")
            return data
    except Exception as e:
        logger.warning(f"[MOD-10] Ollama fehlgeschlagen: {e}")
        return None


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


async def scrape_parliament_bills(limit: int = 10) -> list[dict]:
    """Fetches latest bills from hellenicparliament.gr official REST API.

    Uses the Open Data API (api.ashx?q=laws) instead of HTML scraping.
    Categories: ν = Σχέδιο νόμου (bill), νο = Νόμος (law), πν = Πρόταση νόμου (proposal).
    """
    bills = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Fetch recent bills (Σχέδια νόμου + ψηφισθέντα)
            for cat in ["%CE%BD", "%CE%BD%CE%BF"]:  # ν (bills), νο (laws)
                r = await client.get(
                    PARLIAMENT_API, params={"q": "laws", "cat": cat},
                    headers={"User-Agent": "Mozilla/5.0 (compatible; Ekklesia/1.0; +https://ekklesia.gr)",
                             "Accept": "application/json", "Accept-Language": "el-GR,el;q=0.9"},
                )
                if r.status_code == 403:
                    logger.warning("[MOD-10] Parliament API blocked (403) — datacenter IP restricted")
                    break
                if r.status_code != 200:
                    continue
                data = r.json()
                for item in data.get("Data", []):
                    # Parse .NET date format /Date(1775595600000+0300)/
                    date_str = item.get("LawPhaseDate", "")
                    date = None
                    if date_str:
                        ts_match = re.search(r"/Date\((\d+)", date_str)
                        if ts_match:
                            date = datetime.fromtimestamp(int(ts_match.group(1)) / 1000).isoformat()
                    bills.append({
                        "title_el": item.get("Title", "")[:200],
                        "url": f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Anazitisi-Nomothetikon-Ergon?law_id={item.get('ID', '')}",
                        "date": date,
                        "law_num": item.get("LawNum"),
                        "ministry": item.get("Ministry"),
                        "type": item.get("Type"),
                    })
                if len(bills) >= limit:
                    break
    except Exception as e:
        logger.warning(f"[MOD-10] Parliament API error: {e}")
        # Fallback: try HTML scraping via Jina Reader
        html = await fetch_with_fallback(f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Psifisthenta-Nomoschedia")
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                text = link.get_text(strip=True)
                href = link.get("href", "")
                if len(text) > 20 and any(kw in text.lower() for kw in ["νόμος", "νομοσχέδιο", "ν."]):
                    full_url = href if href.startswith("http") else f"{PARLIAMENT_BASE}{href}"
                    bills.append({"title_el": text[:200], "url": full_url, "date": None})
                if len(bills) >= limit:
                    break

    return bills[:limit]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def scraper_status():
    """Status aller KI-Provider."""
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass

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
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass

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


@router.post("/fetch")
async def fetch_and_store(
    url: str = Query(...), title_el: str = Query(...),
    bill_id: str = Query(...), admin_key: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Scraped URL → KI Zusammenfassung → DB. Admin-geschützt."""
    if admin_key != os.environ.get("ADMIN_KEY", "dev-admin-key"):
        raise HTTPException(403, "Ungültiger Admin-Key")

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
    vote_date: str | None = None  # ISO format


class BillImportRequest(BaseModel):
    admin_key: str
    bills: List[BillImportItem]


@router.post("/import")
async def import_parliament_bills(
    req: BillImportRequest,
    db: AsyncSession = Depends(get_db)
):
    """Bulk import structured bill data.
    Called by GitHub Actions scraper workflow which fetches from
    hellenicparliament.gr API (GitHub IPs are not blocked).
    Accepts pre-structured JSON, stores new bills, skips duplicates.
    """
    if req.admin_key != os.environ.get("ADMIN_KEY", "dev-admin-key"):
        raise HTTPException(403, "Ungültiger Admin-Key")

    imported = 0
    skipped = 0

    for item in req.bills:
        existing = await db.execute(
            select(ParliamentBill).where(ParliamentBill.id == item.bill_id)
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        summaries = summarize_rule_based(item.title_el, item.title_el)
        date = None
        if item.vote_date:
            try:
                date = datetime.fromisoformat(item.vote_date)
            except ValueError:
                pass

        bill = ParliamentBill(
            id=item.bill_id, title_el=item.title_el,
            pill_el=f"Ν. {item.law_num}: {item.title_el[:100]}" if item.law_num else item.title_el[:120],
            pill_en=f"Law {item.law_num}: {item.ministry[:80]}" if item.law_num else "",
            summary_short_el=f"Νόμος {item.law_num} — {item.ministry}. {item.title_el}" if item.law_num else item.title_el,
            summary_short_en=f"Law {item.law_num} by {item.ministry}." if item.law_num else "",
            categories=summaries.get("categories", ["Νομοθεσία"]),
            status=BillStatus.ANNOUNCED,
            parliament_vote_date=date,
        )
        db.add(bill)
        imported += 1

    await db.commit()
    logger.info(f"[MOD-10] Import: {imported} new, {skipped} skipped")
    return {"success": True, "imported": imported, "skipped": skipped}
