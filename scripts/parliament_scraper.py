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
import hmac
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


PARLIAMENT_BASE = "https://www.hellenicparliament.gr"
PARLIAMENT_API = f"{PARLIAMENT_BASE}/api.ashx"
USER_AGENT = "Mozilla/5.0 (compatible; Ekklesia/1.0; +https://ekklesia.gr)"
JINA_BASE = "https://r.jina.ai/"
DETAIL_DIRECT_TIMEOUT_SECONDS = 15
DETAIL_JINA_TIMEOUT_SECONDS = 20
PDF_JINA_TIMEOUT_SECONDS = 25
MAX_ENRICHED_BILLS = 5
MAX_PDF_TEXT_CANDIDATES = 1
ATTESTATION_ENV = "PARLIAMENT_IMPORT_ATTESTATION_KEY"

PARLIAMENT_PAGES = [
    f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/all-laws",
    f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Katatethenta-Nomosxedia",
    f"{PARLIAMENT_BASE}/Nomothetiko-Ergo/Psifisthenta-Nomoschedia",
]

DETAIL_FIELD_LABELS = (
    "Τίτλος",
    "Τύπος",
    "Υπουργείο",
    "Επιτροπή",
    "Φάση Επεξεργασίας",
    "Ημερ/νια Φάσης επεξεργασίας",
    "Ημ. Κατάθεσης",
    "Εισηγητές",
    "Σχετικές Συνεδριάσεις Επιτροπής",
)


@dataclass
class FetchResult:
    url: str
    status: int | None
    text: str
    error: str | None = None


def _verified_ssl_context() -> ssl.SSLContext:
    """Return a CA-verified TLS context without weakening hostname checks."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


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
        with urllib.request.urlopen(req, timeout=timeout, context=_verified_ssl_context()) as resp:
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
        or "you don't have permission to access" in lowered
        or "errors.edgesuite.net" in lowered
        or "authenticationrequirederror" in lowered
        or "blocked from performing anonymous queries" in lowered
    )


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _looks_truncated_title(value: str | None) -> bool:
    return _normalize_text(value).endswith(("...", "…"))


def prefer_complete_title(current: str | None, candidate: str | None) -> str:
    """Accept only a longer title that continues the same official title stem."""
    current_text = _normalize_text(current)
    candidate_text = _normalize_text(candidate)
    if not current_text or not candidate_text:
        return current_text or candidate_text
    if not _looks_truncated_title(current_text) or _looks_truncated_title(candidate_text):
        return current_text

    stem = re.sub(r"(?:\.\.\.|…)$", "", current_text).rstrip()
    comparison = stem[: min(len(stem), 80)]
    if len(candidate_text) <= len(stem) or not candidate_text.startswith(comparison):
        return current_text
    return candidate_text


def detail_matches_bill(current: str | None, candidate: str | None) -> bool:
    """Bind detail-page enrichment to the same official bill title."""
    current_text = _normalize_text(current)
    candidate_text = _normalize_text(candidate)
    if not current_text or not candidate_text or _looks_truncated_title(candidate_text):
        return False

    if current_text == candidate_text:
        return True
    if not _looks_truncated_title(current_text):
        return False

    stem = re.sub(r"(?:\.\.\.|…)$", "", current_text).rstrip()
    comparison = stem[: min(len(stem), 80)]
    return len(candidate_text) > len(stem) and candidate_text.startswith(comparison)


def _markdown_label(line: str) -> str:
    return re.sub(r"^[#>*_`\-\s]+|[*_`\s]+$", "", line).strip()


class _DetailHTMLParser(HTMLParser):
    """Render official detail HTML into the same line-oriented form as Jina Markdown."""

    _BLOCK_TAGS = frozenset({
        "article", "br", "dd", "div", "dl", "dt", "h1", "h2", "h3", "h4",
        "li", "p", "section", "td", "th", "tr",
    })

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.anchor_href: str | None = None
        self.anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")
        if tag == "a":
            self.anchor_href = dict(attrs).get("href")
            self.anchor_text = []
        elif tag == "img" and self.anchor_href:
            alt = dict(attrs).get("alt")
            if alt:
                self.anchor_text.append(alt)

    def handle_data(self, data: str) -> None:
        if self.anchor_href is not None:
            self.anchor_text.append(data)
        else:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.anchor_href is not None:
            label = _normalize_text(" ".join(self.anchor_text)) or "Έγγραφο Βουλής"
            url = urllib.parse.urljoin(PARLIAMENT_BASE, self.anchor_href)
            self.parts.append(f"[{label}]({url})")
            self.anchor_href = None
            self.anchor_text = []
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def rendered(self) -> str:
        lines = (_normalize_text(line) for line in "".join(self.parts).splitlines())
        return "\n".join(line for line in lines if line)


def detail_html_to_markdown(value: str) -> str:
    parser = _DetailHTMLParser()
    parser.feed(value)
    parser.close()
    return parser.rendered()


def _detail_field(markdown: str, label: str) -> str | None:
    lines = markdown.splitlines()
    for index, raw in enumerate(lines):
        normalized = _markdown_label(raw)
        if normalized == label:
            values: list[str] = []
            for following in lines[index + 1:]:
                value = _markdown_label(following)
                if not value:
                    continue
                if value in DETAIL_FIELD_LABELS:
                    break
                if (
                    "![" in following
                    or (value.startswith("[") and "](" in value)
                    or value.startswith(("Title:", "URL Source:", "Markdown Content:"))
                ):
                    break
                values.append(value)
            result = _normalize_text(" ".join(values))
            return result or None
        prefix = f"{label}:"
        if normalized.startswith(prefix):
            result = _normalize_text(normalized[len(prefix):])
            return result or None
    return None


def _inline_detail_fields(markdown: str) -> dict[str, str]:
    """Parse the compact field sequence currently emitted by Jina.

    The official detail page sometimes collapses all ``dt``/``dd`` pairs onto
    one line. Keep this fallback deliberately strict: every captured value is
    bounded by the next official label, and the caller still binds the title
    to the bill before accepting any enrichment.
    """
    compact = _normalize_text(markdown)
    match = re.search(
        r"(?:^|\s)Τίτλος\s+(?P<title>.{1,1000}?)"
        r"Τύπος\s+(?P<type>.{1,200}?)"
        r"Υπουργείο\s+(?P<ministry>.{1,300}?)"
        r"Επιτροπή\s+(?P<committee>.{1,500}?)"
        r"Φάση Επεξεργασίας\s+(?P<phase>.{1,300}?)"
        r"Ημερ/νια Φάσης επεξεργασίας(?:\s+|$)",
        compact,
    )
    if not match:
        return {}
    return {
        key: _normalize_text(value)
        for key, value in match.groupdict().items()
        if value and _normalize_text(value)
    }


def _extract_labeled_pdf_links(markdown: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    pattern = re.compile(
        r"([^\[\]\n]{0,180})"
        r"\[!\[([^\]]*)\]\(https?://[^)]*pdf\.png\)\]"
        r"\((https?://(?:www\.)?hellenicparliament\.gr/[^)]+\.pdf[^)]*)\)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(markdown):
        prefix = _normalize_text(match.group(1)).rsplit(")", 1)[-1].strip()
        alt = re.sub(r"^Image(?:\s+\d+)?:\s*", "", _normalize_text(match.group(2))).strip()
        label = alt if alt and alt.lower() != ".pdf" else prefix
        url = match.group(3).strip()
        if not any(existing["url"] == url for existing in links):
            links.append({"label": label or "Έγγραφο Βουλής", "url": url})

    simple_link_pattern = re.compile(
        r"\[([^\]]+)\]\((https?://(?:www\.)?hellenicparliament\.gr/[^)]+\.pdf[^)]*)\)",
        re.IGNORECASE,
    )
    for match in simple_link_pattern.finditer(markdown):
        label = _normalize_text(match.group(1))
        url = match.group(2).strip()
        if not any(existing["url"] == url for existing in links):
            links.append({"label": label or "Έγγραφο Βουλής", "url": url})

    for url in _extract_pdf_urls(markdown):
        if not any(existing["url"] == url for existing in links):
            links.append({"label": "Έγγραφο Βουλής", "url": url})
    return links


def parse_detail_markdown(markdown: str) -> dict[str, Any]:
    """Extract only explicit labeled facts from one official Parliament detail page."""
    inline = _inline_detail_fields(markdown)
    return {
        "title_el": _detail_field(markdown, "Τίτλος") or inline.get("title"),
        "type": _detail_field(markdown, "Τύπος") or inline.get("type"),
        "ministry": _detail_field(markdown, "Υπουργείο") or inline.get("ministry"),
        "phase": _detail_field(markdown, "Φάση Επεξεργασίας") or inline.get("phase"),
        "pdf_links": _extract_labeled_pdf_links(markdown),
    }


def _labeled_document_block(links: list[dict[str, str]]) -> str | None:
    if not links:
        return None
    lines = ["### Πλήρη έγγραφα"]
    for index, link in enumerate(links, start=1):
        filename = link["url"].rsplit("/", 1)[-1].split("?", 1)[0]
        label = _normalize_text(link.get("label"))
        if not label or label == "Έγγραφο Βουλής":
            label = f"Έγγραφο Βουλής {index} ({filename})"
        lines.append(f"- [{label}]({link['url']})")
    return "\n".join(lines)


def enrich_bill_from_detail(bill: dict[str, Any], markdown: str) -> list[dict[str, str]]:
    detail = parse_detail_markdown(markdown)
    if not detail_matches_bill(bill.get("title_el"), detail.get("title_el")):
        return []

    preferred = prefer_complete_title(bill.get("title_el"), detail.get("title_el"))
    if preferred != bill.get("title_el"):
        bill["title_el"] = preferred
    for field in ("type", "ministry", "phase"):
        if detail.get(field):
            bill[field] = detail[field]

    links = detail.get("pdf_links") or []
    if links:
        document_block = _labeled_document_block(links)
        if not bill.get("summary_long_el") or str(bill["summary_long_el"]).startswith("### Πλήρη έγγραφα"):
            bill["summary_long_el"] = document_block

    bill["pill_el"] = _metadata_pill(
        title_el=bill["title_el"],
        bill_type=bill.get("type"),
        ministry=bill.get("ministry"),
    )
    bill["summary_short_el"] = _metadata_summary(
        title_el=bill["title_el"],
        bill_type=bill.get("type"),
        ministry=bill.get("ministry"),
        phase=bill.get("phase"),
        submitted_date=bill.get("submitted_date"),
        vote_date=bill.get("vote_date"),
    )
    return links


def _clean_jina_pdf_text(raw: str) -> str:
    if "Markdown Content:" in raw:
        raw = raw.split("Markdown Content:", 1)[1]
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", raw)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^[#>*_`\-]+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _is_readable_official_pdf_text(text: str) -> bool:
    if not text or _access_blocked(text):
        return False
    cleaned = _clean_jina_pdf_text(text)
    if len(cleaned) < 800:
        return False
    greek_words = re.findall(r"[Α-ΩΆ-Ώα-ωά-ώ]{3,}", cleaned)
    if len(greek_words) < 100:
        return False
    markers = ("Σκοπός", "Αντικείμενο", "Άρθρο", "ΑΙΤΙΟΛΟΓΙΚΗ", "Αιτιολογική", "Προς τη Βουλή")
    return any(marker in cleaned[:3500] for marker in markers)


def _extractive_summary(text: str) -> str | None:
    cleaned = _clean_jina_pdf_text(text)
    starts = [cleaned.find(marker) for marker in ("Σκοπός", "Αντικείμενο", "Άρθρο 1")]
    starts = [start for start in starts if start >= 0]
    excerpt = cleaned[min(starts):] if starts else cleaned
    excerpt = re.sub(r"^(?:Σκοπός|Αντικείμενο|Άρθρο\s+1)\s*", "", excerpt, count=1)
    excerpt = _normalize_text(excerpt)
    sentences = re.findall(r".+?[.;·](?:\s|$)", excerpt)
    candidate = " ".join(sentence.strip() for sentence in sentences[:3]).strip()
    if len(candidate) < 80:
        candidate = excerpt[:500].strip()
    if len(candidate) > 500:
        cut = max(candidate[:500].rfind("."), candidate[:500].rfind(";"), candidate[:500].rfind("·"))
        candidate = candidate[:cut + 1 if cut >= 120 else 497].rstrip()
        if not candidate.endswith((".", ";", "·")):
            candidate += "…"
    return candidate if len(candidate) >= 80 else None


def enrich_bill_from_pdf_text(bill: dict[str, Any], raw_text: str, source_url: str) -> bool:
    """Attach verified extractive text; never invent or paraphrase official content."""
    if not _is_readable_official_pdf_text(raw_text):
        return False
    official_text = _clean_jina_pdf_text(raw_text)[:12000].strip()
    summary = _extractive_summary(official_text)
    if not summary:
        return False
    document_block = bill.get("summary_long_el") or ""
    bill["summary_short_el"] = summary
    bill["summary_long_el"] = official_text
    if document_block.startswith("### Πλήρη έγγραφα"):
        bill["summary_long_el"] += f"\n\n{document_block.strip()}"
    bill["official_text_verified"] = True
    bill["official_text_source_url"] = source_url
    return True


def official_text_attestation_message(bill: dict[str, Any]) -> bytes:
    """Versioned evidence envelope; keep byte-for-byte aligned with the API verifier."""
    fields = (
        "v1",
        str(bill.get("bill_id") or ""),
        str(bill.get("law_id") or ""),
        str(bill.get("url") or ""),
        str(bill.get("official_text_source_url") or ""),
        hashlib.sha256(str(bill.get("summary_short_el") or "").encode("utf-8")).hexdigest(),
        hashlib.sha256(str(bill.get("summary_long_el") or "").encode("utf-8")).hexdigest(),
    )
    return "\n".join(fields).encode("utf-8")


def attest_verified_official_text(bill: dict[str, Any], key: str) -> None:
    if not bill.get("official_text_verified"):
        return
    if len(key) < 32:
        raise ValueError("Parliament import attestation key must be at least 32 characters")
    bill["official_text_attestation"] = hmac.new(
        key.encode("utf-8"),
        official_text_attestation_message(bill),
        hashlib.sha256,
    ).hexdigest()


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


def _detail_markdown_for_bill(bill: dict[str, Any]) -> str | None:
    url = str(bill.get("url") or "")
    if not url.startswith(f"{PARLIAMENT_BASE}/") or "law_id=" not in url:
        return None

    direct = _http_get(url, accept="text/html", timeout=DETAIL_DIRECT_TIMEOUT_SECONDS)
    if direct.status == 200 and direct.text and not _access_blocked(direct.text):
        rendered = detail_html_to_markdown(direct.text) if direct.text.lstrip().startswith("<") else direct.text
        direct_detail = parse_detail_markdown(rendered)
        if detail_matches_bill(bill.get("title_el"), direct_detail.get("title_el")):
            return rendered

    jina = _http_get(f"{JINA_BASE}{url}", accept="text/plain", timeout=DETAIL_JINA_TIMEOUT_SECONDS)
    if jina.status == 200 and jina.text and not _access_blocked(jina.text):
        jina_detail = parse_detail_markdown(jina.text)
        if detail_matches_bill(bill.get("title_el"), jina_detail.get("title_el")):
            return jina.text
    return None


def _pdf_candidate_order(links: list[dict[str, str]]) -> list[dict[str, str]]:
    preferred_markers = (
        "αιτιολογ",
        "ανάλυση συνεπειών",
        "σχέδιο νόμου",
        "διατάξεις",
        "εισηγητικ",
    )
    return sorted(
        links,
        key=lambda link: 0 if any(marker in link["label"].lower() for marker in preferred_markers) else 1,
    )


def enrich_bill_from_official_sources(bill: dict[str, Any]) -> None:
    """Best-effort enrichment. Failure leaves the already safe metadata/PDF fallback intact."""
    detail_markdown = _detail_markdown_for_bill(bill)
    if not detail_markdown:
        return

    links = enrich_bill_from_detail(bill, detail_markdown)
    for link in _pdf_candidate_order(links)[:MAX_PDF_TEXT_CANDIDATES]:
        time.sleep(0.5)
        result = _http_get(
            f"{JINA_BASE}{link['url']}",
            accept="text/plain",
            timeout=PDF_JINA_TIMEOUT_SECONDS,
        )
        if result.status == 200 and result.text and enrich_bill_from_pdf_text(
            bill,
            result.text,
            link["url"],
        ):
            return


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
    for bill in bills[: min(limit, MAX_ENRICHED_BILLS)]:
        enrich_bill_from_official_sources(bill)
    return bills[:limit], errors


def normalize_server_fallback_payload(
    payload: dict[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Validate and normalize the canonical Production freshness response.

    The server response uses ``date`` for Parliament vote/discussion dates and
    does not expose the workflow's stable ``bill_id``. Never pass it directly
    to the import endpoint.
    """
    if payload.get("source_status") != "ok":
        raise ValueError("server fallback did not prove an available source")
    try:
        dated_count = int(payload.get("dated_count") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("server fallback returned an invalid dated_count") from exc
    if dated_count < 1:
        raise ValueError("server fallback returned no dated bills")

    raw_bills = payload.get("bills")
    if not isinstance(raw_bills, list) or not raw_bills:
        raise ValueError("server fallback returned no bill records")

    normalized: list[dict[str, Any]] = []
    for raw in raw_bills[:limit]:
        if not isinstance(raw, dict):
            continue
        submitted_date = raw.get("submitted_date")
        vote_date = raw.get("vote_date") or raw.get("date")
        if not submitted_date and not vote_date:
            continue

        bill = _finalize_bill(
            title_el=str(raw.get("title_el") or ""),
            url=str(raw.get("url") or ""),
            law_id=raw.get("law_id"),
            law_num=raw.get("law_num"),
            ministry=raw.get("ministry"),
            bill_type=raw.get("type"),
            phase=raw.get("phase"),
            submitted_date=submitted_date,
            vote_date=vote_date,
        )
        if bill is None:
            continue

        for field in ("pill_el", "summary_short_el", "summary_long_el"):
            value = raw.get(field)
            if isinstance(value, str) and value.strip():
                bill[field] = value
        normalized.append(bill)

    if not normalized:
        raise ValueError("server fallback records failed date/title validation")
    return normalized


def fetch_server_fallback(url: str, *, limit: int) -> list[dict[str, Any]]:
    """Fetch the canonical server probe only after runner-side sources fail."""
    result = _http_get(url, accept="application/json", timeout=45)
    if result.status != 200 or not result.text or _access_blocked(result.text):
        raise ValueError(f"server fallback unavailable: {result.error or result.status}")
    try:
        payload = json.loads(result.text)
    except json.JSONDecodeError as exc:
        raise ValueError("server fallback returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("server fallback returned an invalid payload")
    return normalize_server_fallback_payload(payload, limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--fallback-url")
    args = parser.parse_args()

    bills, errors = scrape(args.limit)
    if not bills and args.fallback_url:
        try:
            bills = fetch_server_fallback(args.fallback_url, limit=args.limit)
            print(f"Production freshness fallback returned {len(bills)} dated bills")
        except ValueError as exc:
            errors.append(f"production_fallback_failed:{exc}")
    if any(bill.get("official_text_verified") for bill in bills):
        attestation_key = os.getenv(ATTESTATION_ENV, "")
        if len(attestation_key) < 32:
            print(f"ERROR: {ATTESTATION_ENV} is missing or too short", file=sys.stderr)
            return 3
        for bill in bills:
            attest_verified_official_text(bill, attestation_key)
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
