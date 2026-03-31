"""
MOD-10: AI Bill Scraper
Scraped echte Gesetzentwürfe von hellenicparliament.gr
3-stufige Fallback-Kette + 3-stufige KI-Zusammenfassung

@ai-anchor MOD10_SCRAPER
@update-hint Anthropic API Key in .env: ANTHROPIC_API_KEY=sk-ant-...
"""
import os
import re
import json
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


# ── Fallback Chain ─────────────────────────────────────────────────────────────

async def fetch_with_fallback(url: str) -> Optional[str]:
    """
    3-stufige Fallback-Kette:
    1. Direkt HTTP
    2. Jina Reader (r.jina.ai)
    3. Fehler — None
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Ekklesia/1.0; +https://ekklesia.gr)",
        "Accept-Language": "el-GR,el;q=0.9,en;q=0.8",
    }

    # Stufe 1: Direkter Fetch
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200 and len(r.text) > 500:
                logger.info(f"[MOD-10] Direkt OK: {url[:60]}")
                return r.text
    except Exception as e:
        logger.warning(f"[MOD-10] Direkt fehlgeschlagen: {e}")

    # Stufe 2: Jina Reader
    try:
        jina_url = f"https://r.jina.ai/{url}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(jina_url, headers={"Accept": "text/plain"})
            if r.status_code == 200 and len(r.text) > 200:
                logger.info(f"[MOD-10] Jina OK: {url[:60]}")
                return r.text
    except Exception as e:
        logger.warning(f"[MOD-10] Jina fehlgeschlagen: {e}")

    logger.error(f"[MOD-10] Alle Stufen fehlgeschlagen: {url}")
    return None


def extract_bill_text(html: str) -> str:
    """Extrahiert relevanten Text aus HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["nav", "footer", "script", "style", "header"]):
        tag.decompose()

    main = (
        soup.find("main") or
        soup.find("article") or
        soup.find("div", class_=re.compile(r"content|main|body", re.I)) or
        soup.find("body")
    )

    text = main.get_text(separator="\n", strip=True) if main else soup.get_text()
    lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 20]
    return "\n".join(lines[:200])


# ── KI Zusammenfassung ─────────────────────────────────────────────────────────

async def generate_summaries(bill_text: str, title_el: str) -> dict:
    """
    3-stufige KI-Zusammenfassung via Claude Haiku.
    Returns: { pill_el, pill_en, summary_short_el/en, summary_long_el/en, categories }
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        logger.info("[MOD-10] Kein Anthropic API Key — Dry Run")
        return {
            "pill_el":          f"Νόμος: {title_el[:80]}",
            "pill_en":          f"Law: {title_el[:80]}",
            "summary_short_el": f"Σύνοψη για: {title_el}",
            "summary_short_en": f"Summary for: {title_el}",
            "summary_long_el":  bill_text[:500] if bill_text else "Δεν βρέθηκε κείμενο.",
            "summary_long_en":  "Full analysis not available in dry run.",
            "categories":       ["Νομοθεσία"],
        }

    prompt = f"""Αναλύσε αυτό το ελληνικό νομοσχέδιο και δώσε μου JSON με τα παρακάτω πεδία:

Τίτλος: {title_el}

Κείμενο:
{bill_text[:3000]}

Επέστρεψε ΜΟΝΟ έγκυρο JSON (χωρίς markdown):
{{
  "pill_el": "1 πρόταση (max 120 χαρακτήρες) που εξηγεί τι κάνει ο νόμος",
  "pill_en": "1 sentence (max 120 chars) explaining what the law does",
  "summary_short_el": "3 παράγραφοι που εξηγούν τα κύρια σημεία του νόμου",
  "summary_short_en": "3 paragraphs explaining the main points of the law",
  "summary_long_el": "Πλήρης ανάλυση: στόχοι, διατάξεις, επιπτώσεις, αντιδράσεις (min 300 λέξεις)",
  "summary_long_en": "Full analysis: goals, provisions, impacts, reactions (min 300 words)",
  "categories": ["κατηγορία1", "κατηγορία2"]
}}

Κατηγορίες (επίλεξε 1-3): Παιδεία, Υγεία, Οικονομία, Περιβάλλον, Εργασία, Ασφάλεια, Δικαιοσύνη, Τεχνολογία, Αγροτικά, Άμυνα, Κοινωνική Πολιτική, Φορολογία, Νομοθεσία"""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = message.content[0].text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)
        logger.info(f"[MOD-10] KI Zusammenfassung OK für: {title_el[:40]}")
        return data

    except Exception as e:
        logger.error(f"[MOD-10] KI Fehler: {e}")
        return {
            "pill_el":          f"Νόμος: {title_el[:80]}",
            "pill_en":          f"Law: {title_el[:80]}",
            "summary_short_el": f"Σύνοψη για: {title_el}",
            "summary_short_en": f"Summary for: {title_el}",
            "summary_long_el":  bill_text[:500],
            "summary_long_en":  "Analysis unavailable.",
            "categories":       ["Νομοθεσία"],
        }


# ── Hellenic Parliament Scraper ────────────────────────────────────────────────

async def scrape_parliament_bills(limit: int = 10) -> list[dict]:
    """Scraped aktuelle Gesetzentwürfe von hellenicparliament.gr"""
    urls_to_try = [
        f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Psifisthenta-Nomoschedia",
        f"{PARLIAMENT_BASE}/Vouli-ton-Ellinon/ToKtirio/",
    ]

    bills = []

    for url in urls_to_try:
        html = await fetch_with_fallback(url)
        if not html:
            continue

        if not html.strip().startswith("<"):
            # Plain text (Jina Reader)
            lines = [l.strip() for l in html.split("\n") if l.strip()]
            for line in lines[:100]:
                if len(line) > 20 and any(kw in line.lower() for kw in ["νόμος", "νομοσχέδιο", "τροποποίηση", "ν."]):
                    bills.append({
                        "title_el": line[:200],
                        "url":      url,
                        "date":     None,
                    })
                if len(bills) >= limit:
                    break
        else:
            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=True)
            for link in links:
                text = link.get_text(strip=True)
                href = link.get("href", "")
                if len(text) > 20 and any(kw in text.lower() for kw in ["νόμος", "νομοσχέδιο", "τροποποίηση", "ν."]):
                    full_url = href if href.startswith("http") else f"{PARLIAMENT_BASE}{href}"
                    bills.append({
                        "title_el": text[:200],
                        "url":      full_url,
                        "date":     None,
                    })
                if len(bills) >= limit:
                    break

        if bills:
            break

    return bills[:limit]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/test")
async def test_scraper():
    """Testet den Scraper ohne DB-Schreibzugriff."""
    bills = await scrape_parliament_bills(limit=5)
    return {
        "status": "ok",
        "bills_found": len(bills),
        "sample": bills[:3],
        "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "message": "Dry Run" if not os.getenv("ANTHROPIC_API_KEY") else "KI aktiv"
    }


@router.post("/fetch")
async def fetch_and_store(
    url: str = Query(..., description="URL des Gesetzentwurfs"),
    title_el: str = Query(..., description="Griechischer Titel"),
    bill_id: str = Query(..., description="Bill ID (z.B. GR-2025-0042)"),
    admin_key: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Scraped eine Bill-URL, generiert KI-Zusammenfassung, speichert in DB.
    Admin-geschützt.
    """
    if admin_key != os.environ.get("ADMIN_KEY", "dev-admin-key"):
        raise HTTPException(403, "Ungültiger Admin-Key")

    existing = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Bill {bill_id} existiert bereits")

    html = await fetch_with_fallback(url)
    if not html:
        raise HTTPException(422, "Konnte URL nicht abrufen")

    text = extract_bill_text(html)
    summaries = await generate_summaries(text, title_el)

    bill = ParliamentBill(
        id=bill_id,
        title_el=title_el,
        title_en=summaries.get("pill_en", "")[:200],
        pill_el=summaries.get("pill_el"),
        pill_en=summaries.get("pill_en"),
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
        "success":  True,
        "bill_id":  bill_id,
        "title_el": title_el,
        "pill_el":  summaries.get("pill_el"),
        "categories": summaries.get("categories"),
        "status":   "ANNOUNCED",
    }


@router.get("/parliament/latest")
async def get_latest_from_parliament(limit: int = Query(10, le=20)):
    """Scraped aktuelle Gesetzentwürfe von hellenicparliament.gr."""
    bills = await scrape_parliament_bills(limit=limit)
    return {
        "source": "hellenicparliament.gr",
        "count":  len(bills),
        "bills":  bills,
    }
