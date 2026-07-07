#!/usr/bin/env python3
"""Fetch Greek Parliament bills for the GitHub Actions import job.

The production server can be blocked by the Parliament WAF. This script is
designed for GitHub Actions and keeps the output shape close to the API
server's canonical scraper: stable IDs, dates, source URL, safe metadata
summary, and official PDF document blocks when available.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PARLIAMENT_BASE = "https://www.hellenicparliament.gr"
PARLIAMENT_API = f"{PARLIAMENT_BASE}/api.ashx"
USER_AGENT = "Mozilla/5.0 (compatible; Ekklesia/1.0; +https://ekklesia.gr)"
JINA_BASE = "https://r.jina.ai/"

PARLIAMENT_PAGES = [
    f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/all-laws",
    f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Katatethenta-Nomosxedia",
    f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Psifisthenta-Nomoschedia",
]


@dataclass
class FetchResult:
    url: str
    status: int | None
    text: str
    error: str | None = None


def _http_get(url: str, *, accept: str = "*/*", timeout: int = 30) -> FetchResult:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "el-GR,el;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return FetchResult(
                url=url,
                status=resp.status,
                text=resp.read().decode(charset, errors="replace"),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return FetchResult(url=url, status=exc.code, text=body, error=f"http_{exc.code}")
    except Exception as exc:
        return FetchResult(url=url, status=None, text="", error=type(exc).__name__)


def _access_blocked(text: str) -> bool:
    lowered = text.lower()
    return (
        "access denied" in lowered
        or "authenticationrequirederror" in lowered
        or "blocked from performing anonymous queries" in lowered
    )


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _parse_ddmmyyyy(value: str | None) -> str | None:
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", value or "")
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{month}-{day}T00:00:00+00:00"


def _parse_ms_date(value: str | None) -> str | None:
    match = re.search(r"/Date\((\d+)", value or "")
    if not match:
        return None
    return datetime.fromtimestamp(
        int(match.group(1)) / 1000,
        tz=timezone.utc,
    ).isoformat()


def _format_el_date(value: str | None) -> str | None:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    if not match:
        return None
    year, month, day = match.groups()
    return f"{day}/{month}/{year}"


def _stable_bill_id(*, law_num: str | None, law_id: str | None, title_el: str) -> str:
    if law_num:
        return f"GR-{law_num}".replace(" ", "-")[:50]
    if law_id:
        return f"GR-{law_id[:8]}"
    digest = hashlib.sha256(title_el.encode("utf-8")).hexdigest()[:8]
    return f"GR-AUTO-{digest}"


def _metadata_summary(
    *,
    title_el: str,
    bill_type: str | None = None,
    ministry: str | None = None,
    phase: str | None = None,
    submitted_date: str | None = None,
    vote_date: str | None = None,
) -> str:
    facts: list[str] = []
    if bill_type:
        facts.append(f"Τύπος: {bill_type}")
    if ministry:
        facts.append(f"Υπουργείο: {ministry}")
    if phase:
        facts.append(f"Φάση: {phase}")
    submitted = _format_el_date(submitted_date)
    if submitted:
        facts.append(f"Ημερομηνία κατάθεσης: {submitted}")
    voted = _format_el_date(vote_date)
    if voted:
        facts.append(f"Ημερομηνία συζήτησης/ψήφισης: {voted}")

    lines = [f"Η Βουλή δημοσίευσε εγγραφή για: {title_el}."]
    if facts:
        lines.append("; ".join(facts) + ".")
    lines.append("Για το πλήρες περιεχόμενο δείτε τα επίσημα έγγραφα της Βουλής.")
    return "\n".join(lines)


def _metadata_pill(*, title_el: str, bill_type: str | None, ministry: str | None) -> str:
    if bill_type and ministry:
        return f"{bill_type} — {ministry}"[:200]
    if bill_type:
        return bill_type[:200]
    return title_el[:200]


def _document_block(pdf_urls: list[str]) -> str | None:
    unique: list[str] = []
    for url in pdf_urls:
        if url not in unique:
            unique.append(url)
    if not unique:
        return None
    lines = ["### Πλήρη έγγραφα"]
    for index, url in enumerate(unique, start=1):
        filename = url.rsplit("/", 1)[-1].split("?", 1)[0]
        lines.append(f"- [Έγγραφο Βουλής {index} ({filename})]({url})")
    return "\n".join(lines)


def _finalize_bill(
    *,
    title_el: str,
    url: str,
    law_id: str | None = None,
    law_num: str | None = None,
    ministry: str | None = None,
    bill_type: str | None = None,
    phase: str | None = None,
    submitted_date: str | None = None,
    vote_date: str | None = None,
    pdf_urls: list[str] | None = None,
) -> dict[str, Any] | None:
    title_el = _normalize_text(title_el)
    if len(title_el) < 10:
        return None
    law_id = _normalize_text(law_id) or None
    law_num = _normalize_text(law_num) or None
    ministry = _normalize_text(ministry) or None
    bill_type = _normalize_text(bill_type) or None
    phase = _normalize_text(phase) or None
    submitted_date = submitted_date or None
    vote_date = vote_date or None
    if not submitted_date and not vote_date:
        return None

    if url.startswith("/"):
        url = f"{PARLIAMENT_BASE}{url}"
    document_block = _document_block(pdf_urls or [])
    return {
        "bill_id": _stable_bill_id(law_num=law_num, law_id=law_id, title_el=title_el),
        "title_el": title_el,
        "law_id": law_id,
        "law_num": law_num or "",
        "ministry": ministry or "",
        "type": bill_type,
        "phase": phase,
        "url": url,
        "submitted_date": submitted_date,
        "vote_date": vote_date,
        "pill_el": _metadata_pill(title_el=title_el, bill_type=bill_type, ministry=ministry),
        "summary_short_el": _metadata_summary(
            title_el=title_el,
            bill_type=bill_type,
            ministry=ministry,
            phase=phase,
            submitted_date=submitted_date,
            vote_date=vote_date,
        ),
        "summary_long_el": document_block,
    }


def _law_id_from_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    value = query.get("law_id", [None])[0]
    if value:
        return value
    match = re.search(r"law_id=([a-f0-9-]{8,})", url, re.IGNORECASE)
    return match.group(1) if match else None


def parse_api_payload(text: str) -> list[dict[str, Any]]:
    data = json.loads(text)
    bills: list[dict[str, Any]] = []
    for item in data.get("Data", []):
        title = item.get("Title") or ""
        law_id = item.get("ID") or None
        law_num = item.get("LawNum") or ""
        vote_date = _parse_ms_date(item.get("LawPhaseDate"))
        url = f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Anazitisi-Nomothetikou-Ergou?law_id={law_id or ''}"
        bill = _finalize_bill(
            title_el=title,
            url=url,
            law_id=law_id,
            law_num=law_num,
            ministry=item.get("Ministry"),
            bill_type=item.get("Type"),
            phase=item.get("Phase") or item.get("LawPhase"),
            vote_date=vote_date,
        )
        if bill:
            bills.append(bill)
    return bills


def _extract_pdf_urls(text: str) -> list[str]:
    return re.findall(r"https?://(?:www\.)?hellenicparliament\.gr/[^)\s\"']+?\.pdf(?:\?[^)\s\"']*)?", text, re.IGNORECASE)


def parse_markdown_table(md: str, source_url: str) -> list[dict[str, Any]]:
    bills: list[dict[str, Any]] = []
    is_katatethenta = "Katatethenta" in source_url
    is_all_laws = "all-laws" in source_url

    for raw_line in md.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        if len(cells) < 2:
            continue
        first = cells[0]
        if first.startswith("---") or first.startswith("Βρέθηκαν") or first.startswith("[Ημ.") or first.startswith("Εγγραφές"):
            continue
        if first.startswith("[") and "SortBy" in first:
            continue

        if is_all_laws:
            title_cell = cells[0]
            date_cell = cells[2] if len(cells) > 2 else ""
        else:
            title_cell = cells[1] if len(cells) > 1 else ""
            date_cell = cells[0]

        row_date = _parse_ddmmyyyy(date_cell)
        if not row_date:
            continue
        title_match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", title_cell)
        if not title_match:
            continue
        title = title_match.group(1)
        url = title_match.group(2).strip()
        bill_type = None
        ministry = None
        phase = None
        if is_katatethenta and len(cells) > 3:
            bill_type = cells[2] if cells[2] and not cells[2].startswith("[") else None
            ministry = cells[3] if cells[3] and not cells[3].startswith("[") else None
        elif is_all_laws:
            bill_type = cells[1] if len(cells) > 1 and cells[1] and not cells[1].startswith("[") else None
            phase = cells[3] if len(cells) > 3 and cells[3] and not cells[3].startswith("[") else None

        submitted_date = None
        vote_date = None
        if is_katatethenta or (
            is_all_laws and phase and any(marker in phase for marker in ("Έτοιμα", "Επεξεργασία", "Κατατεθέν"))
        ):
            submitted_date = row_date
        else:
            vote_date = row_date

        bill = _finalize_bill(
            title_el=title,
            url=url,
            law_id=_law_id_from_url(url),
            bill_type=bill_type,
            ministry=ministry,
            phase=phase,
            submitted_date=submitted_date,
            vote_date=vote_date,
            pdf_urls=_extract_pdf_urls(" ".join(cells[2:])),
        )
        if bill:
            bills.append(bill)
    return bills


def parse_html_page(text: str, source_url: str) -> list[dict[str, Any]]:
    rows = re.findall(r"<tr\b[^>]*>.*?</tr>", text, flags=re.IGNORECASE | re.DOTALL)
    if not rows:
        rows = re.findall(
            r"(<a\b[^>]+href=[\"'][^\"']*law_id=[^\"']+[\"'][^>]*>.*?</a>.{0,2200})",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    bills: list[dict[str, Any]] = []
    for row in rows:
        anchor = re.search(
            r"<a\b[^>]+href=[\"']([^\"']*law_id=[^\"']+)[\"'][^>]*>(.*?)</a>",
            row,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not anchor:
            continue
        url = html.unescape(anchor.group(1))
        title = re.sub(r"<[^>]+>", " ", anchor.group(2))
        text_row = _normalize_text(re.sub(r"<[^>]+>", " ", row))
        row_date = _parse_ddmmyyyy(text_row)
        if not row_date:
            continue
        pdf_urls = _extract_pdf_urls(html.unescape(row))
        phase = None
        for marker in ("Κατατεθέντα", "Επεξεργασία στις Επιτροπές", "Συζήτηση και Ψήφιση", "Ολοκλήρωση"):
            if marker in text_row:
                phase = marker
                break
        submitted_date = row_date if phase != "Ολοκλήρωση" else None
        vote_date = row_date if phase == "Ολοκλήρωση" else None
        bill = _finalize_bill(
            title_el=title,
            url=url,
            law_id=_law_id_from_url(url),
            phase=phase,
            submitted_date=submitted_date,
            vote_date=vote_date,
            pdf_urls=pdf_urls,
        )
        if bill:
            bills.append(bill)
    return bills


def _merge_bills(existing: dict[str, dict[str, Any]], items: list[dict[str, Any]]) -> None:
    for item in items:
        key = item.get("law_id") or item.get("url") or item["bill_id"]
        if key not in existing:
            existing[key] = item
            continue
        target = existing[key]
        if target["title_el"].endswith(("...", "…")) and not item["title_el"].endswith(("...", "…")):
            target["title_el"] = item["title_el"]
        for field in (
            "law_num",
            "ministry",
            "type",
            "phase",
            "url",
            "submitted_date",
            "vote_date",
            "pill_el",
            "summary_short_el",
            "summary_long_el",
        ):
            if item.get(field) and not target.get(field):
                target[field] = item[field]


def scrape(limit: int) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    merged: dict[str, dict[str, Any]] = {}

    for cat in ("%CE%BD", "%CE%BD%CE%BF"):
        url = f"{PARLIAMENT_API}?q=laws&cat={cat}"
        result = _http_get(url, accept="application/json")
        if result.status == 200 and result.text and not _access_blocked(result.text):
            try:
                _merge_bills(merged, parse_api_payload(result.text))
            except Exception as exc:
                errors.append(f"api_parse_error:{cat}:{type(exc).__name__}")
        else:
            errors.append(f"api_blocked_or_unavailable:{cat}:{result.error or result.status}")

    for page in PARLIAMENT_PAGES:
        direct = _http_get(page, accept="text/html")
        if direct.status == 200 and direct.text and not _access_blocked(direct.text):
            _merge_bills(merged, parse_html_page(direct.text, page))
        else:
            errors.append(f"direct_blocked_or_unavailable:{page.rsplit('/', 1)[-1]}:{direct.error or direct.status}")

        time.sleep(1)
        jina = _http_get(f"{JINA_BASE}{page}", accept="text/plain")
        if jina.status == 200 and jina.text and not _access_blocked(jina.text):
            _merge_bills(merged, parse_markdown_table(jina.text, page))
        else:
            errors.append(f"jina_blocked_or_unavailable:{page.rsplit('/', 1)[-1]}:{jina.error or jina.status}")

    bills = sorted(
        merged.values(),
        key=lambda bill: bill.get("vote_date") or bill.get("submitted_date") or "",
        reverse=True,
    )
    return bills[:limit], errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-empty", action="store_true")
    args = parser.parse_args()

    bills, errors = scrape(args.limit)
    Path(args.output).write_text(json.dumps(bills, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fetched {len(bills)} Parliament bills")
    if errors:
        print("Source diagnostics:")
        for error in errors[:20]:
            print(f"- {error}")
    if not bills and not args.allow_empty:
        print("ERROR: no dated Parliament bills fetched from any source", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
