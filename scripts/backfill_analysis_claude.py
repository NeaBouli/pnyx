#!/usr/bin/env python3
"""
Backfill summary_short_el + analysis_el from official Parliament PDFs via Claude.

Default is dry-run. Use --apply to write DB. This script is intentionally scoped
to explicit bill IDs; it does not batch all bills by default.
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
import urllib.request
from urllib.error import HTTPError, URLError


JINA_BASE = "https://r.jina.ai/"
MODEL = "claude-haiku-4-5-20251001"
MAX_INPUT_CHARS = 6000

ANALYSIS_LABELS = (
    "Αιτιολογική",
    "Εισηγητική",
    "Επιστημονικής",
    "Έκθεση της Επιτροπής",
    "Πρακτικό Έκθεση",
    "Ανάλυση Συνεπειών",
)
OFFICIAL_TEXT_LABELS = (
    "Διατάξεις Σχεδίου",
    "Διατάξεις Πρότασης",
    "Σχέδιο ή Πρόταση Νόμου",
    "Πρόταση Νόμου",
    "Σχέδιο Νόμου",
    "Ψηφισθέν Νομοσχέδιο",
    "Σ/Ν μετά",
)
SKIP_LABEL_PARTS = ("φωτοτυπη", "Τροπολογ")
MAX_FORUM_OFFICIAL_CHARS = 28000


def _read_env_file(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def _http_text(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ekklesia-analysis/1.0",
            "X-Respond-With": "markdown",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_pdf_links(markdown: str) -> list[dict[str, str]]:
    """Extract labeled PDF links from Jina markdown."""
    links: list[dict[str, str]] = []

    # Parliament pages render document links as image links:
    #   Αιτιολογική Έκθεση[![Image: .pdf](.../pdf.png)](.../file.pdf)
    # The label is plain text immediately before the PDF icon, not the link text.
    image_link_pattern = re.compile(
        r"([^\[\]\n]{0,180})"
        r"\[!\[([^\]]*)\]\(https?://[^)]*pdf\.png\)\]"
        r"\((https?://[^)]+\.pdf[^)]*)\)",
        re.IGNORECASE,
    )
    for match in image_link_pattern.finditer(markdown):
        prefix = re.sub(r"\s+", " ", match.group(1)).strip()
        prefix = prefix.rsplit(")", 1)[-1].strip()
        prefix = re.sub(r"^https?://\S+", "", prefix).strip()
        alt = re.sub(r"\s+", " ", match.group(2)).strip()
        alt = re.sub(r"^Image\s+\d+:\s*", "", alt).strip()
        alt = re.sub(r"^Image\s+\d+\s*", "", alt).strip()
        label = alt or prefix
        url = match.group(3).strip()
        if not any(existing["url"] == url for existing in links):
            links.append({"label": label, "url": url})

    pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)]+\.pdf[^)]*)\)", re.IGNORECASE)
    for match in pattern.finditer(markdown):
        label = re.sub(r"\s+", " ", match.group(1)).strip()
        url = match.group(2).strip()
        if not any(existing["url"] == url for existing in links):
            links.append({"label": label, "url": url})
    return links


def classify_pdf(label: str) -> str:
    if any(part.lower() in label.lower() for part in SKIP_LABEL_PARTS):
        return "skip"
    if any(part.lower() in label.lower() for part in OFFICIAL_TEXT_LABELS):
        return "official_text"
    if any(part.lower() in label.lower() for part in ANALYSIS_LABELS):
        return "analysis"
    return "unknown"


def choose_pdfs(links: list[dict[str, str]]) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    """Return the best PDF for analysis and the best PDF for official full text."""
    analysis = pdf_candidates(links, "analysis")
    official_text = pdf_candidates(links, "official_text")
    return (analysis[0] if analysis else None, official_text[0] if official_text else None)


def pdf_candidates(links: list[dict[str, str]], kind: str) -> list[dict[str, str]]:
    return [link for link in links if classify_pdf(link["label"]) == kind]


def fallback_pdf_candidates(links: list[dict[str, str]]) -> list[dict[str, str]]:
    """Use unclassified Parliament PDFs when labels are missing or rendered as '.pdf'."""
    return [link for link in links if classify_pdf(link["label"]) != "skip"]


def display_label(link: dict[str, str], index: int) -> str:
    label = re.sub(r"\s+", " ", link["label"]).strip()
    if not label or label.lower() == ".pdf":
        filename = link["url"].rsplit("/", 1)[-1].split("?", 1)[0]
        return f"Έγγραφο Βουλής {index} ({filename})"
    return label


def _looks_like_ocr_noise(line: str) -> bool:
    tokens = re.findall(r"[Α-ΩΆ-Ώα-ωά-ώA-Za-z0-9]+", line)
    if len(tokens) < 35:
        return False
    short_ratio = sum(1 for token in tokens if len(token) <= 2) / len(tokens)
    common = {"και", "της", "των", "στο", "στη", "στην", "για", "που", "από", "προς", "νόμου", "άρθρο"}
    common_ratio = sum(1 for token in tokens if token.lower() in common) / len(tokens)
    return short_ratio > 0.42 and common_ratio < 0.10


def clean_pdf_text(text: str) -> str:
    marker = "Markdown Content:"
    if marker in text:
        text = text.split(marker, 1)[1]
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line for line in text.splitlines() if not _looks_like_ocr_noise(line))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_table_of_contents(text: str) -> str:
    """Skip PDF table-of-contents sections when a second article body exists."""
    marker = "ΠΙΝΑΚΑΣ ΠΕΡΙΕΧΟΜΕΝΩΝ"
    if marker not in text:
        return text
    article_hits = [match.start() for match in re.finditer(r"Άρθρο\s+1\b", text)]
    if len(article_hits) < 2:
        return text
    body_start = article_hits[1]
    prefix_start = max(
        text.rfind("ΣΧΕΔΙΟ ΝΟΜΟΥ", 0, body_start),
        text.rfind("ΜΕΡΟΣ", 0, body_start),
        text.rfind("ΚΕΦΑΛΑΙΟ", 0, body_start),
    )
    if prefix_start >= 0 and body_start - prefix_start < 2500:
        body_start = prefix_start
    return text[body_start:].strip()


def is_readable_pdf_text(text: str) -> bool:
    """Reject empty Jina PDF output and obvious OCR garbage."""
    text = clean_pdf_text(text)
    if len(text) < 800:
        return False
    words = re.findall(r"[Α-ΩΆ-Ώα-ωά-ώ]{3,}", text)
    if len(words) < 120:
        return False
    common = {"και", "της", "των", "στο", "στη", "στην", "για", "που", "από", "προς", "νόμου", "άρθρο"}
    common_hits = sum(1 for word in words if word.lower() in common)
    if common_hits / max(len(words), 1) < 0.035:
        return False
    useful_markers = ("Άρθρο", "ΑΙΤΙΟΛΟΓΙΚΗ", "Αιτιολογική", "Σκοπός", "Προς τη Βουλή", "ΚΕΦΑΛΑΙΟ")
    return any(marker in text[:2500] for marker in useful_markers)


def build_documents_block(links: list[dict[str, str]]) -> str:
    lines = ["### Πλήρη έγγραφα"]
    seen: set[str] = set()
    visible_index = 1
    for doc in links:
        if doc["url"] in seen or classify_pdf(doc["label"]) == "skip":
            continue
        seen.add(doc["url"])
        label = display_label(doc, visible_index)
        visible_index += 1
        lines.append(f"- [{label}]({doc['url']})")
    return "\n".join(lines).strip()


def extract_useful_excerpt(text: str, max_chars: int = MAX_INPUT_CHARS) -> str:
    """Skip cover/TOC and return useful explanatory content."""
    text = clean_pdf_text(text)
    markers = [
        "Σκοπός",
        "Άρθρο 1",
        "Επί της αρχής",
        "Επί του άρθρου",
        "Αντικείμενο",
    ]
    starts = [text.find(marker) for marker in markers if text.find(marker) >= 0]
    start = min(starts) if starts else 0
    excerpt = text[start:start + max_chars]
    # Prefer ending on a sentence boundary.
    if len(excerpt) == max_chars:
        cut = max(excerpt.rfind("."), excerpt.rfind(";"), excerpt.rfind("·"))
        if cut > max_chars // 2:
            excerpt = excerpt[:cut + 1]
    return excerpt.strip()


def build_official_text_block(text: str, links: list[dict[str, str]], chosen: dict[str, str]) -> str:
    """Build an official-text block for forum/app rendering and source links."""
    text = strip_table_of_contents(clean_pdf_text(text))
    truncated = False
    if len(text) > MAX_FORUM_OFFICIAL_CHARS:
        limit_text = text[:MAX_FORUM_OFFICIAL_CHARS]
        cut = max(
            limit_text.rfind("\n\nΆρθρο"),
            limit_text.rfind("."),
            limit_text.rfind(";"),
            limit_text.rfind("·"),
        )
        text = limit_text[:cut + 1 if cut > 12000 else MAX_FORUM_OFFICIAL_CHARS].strip()
        truncated = True

    preferred_labels = (
        "Διατάξεις",
        "Σχέδιο",
        "Πρόταση",
        "Ψηφισθέν",
        "Σ/Ν μετά",
        "Αιτιολογική",
        "Εισηγητική",
        "Επιστημονικής",
        "Επιτροπής",
    )
    docs: list[dict[str, str]] = []
    for link in links:
        label = link["label"]
        if link["url"] == chosen["url"] or any(part in label for part in preferred_labels):
            docs.append(link)
        if len(docs) >= 5:
            break
    if chosen not in docs:
        docs.insert(0, chosen)

    heading = chosen["label"].strip() or "Έγγραφο Βουλής"
    lines = [
        f"### {heading}",
        text,
    ]
    if truncated:
        lines.extend([
            "",
            "_Το κείμενο συνεχίζεται στο πλήρες έγγραφο της Βουλής._",
        ])
    lines.extend([
        "",
        "### Πλήρη έγγραφα",
    ])
    seen: set[str] = set()
    for doc in docs:
        if doc["url"] in seen:
            continue
        seen.add(doc["url"])
        label = doc["label"].strip() or "Έγγραφο Βουλής"
        lines.append(f"- [{label}]({doc['url']})")
    return "\n".join(lines).strip()


def fetch_first_readable_pdf(candidates: list[dict[str, str]]) -> tuple[dict[str, str] | None, str]:
    for candidate in candidates:
        try:
            pdf_text = _http_text(f"{JINA_BASE}{candidate['url']}", timeout=60)
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"skip PDF {candidate['url']}: {exc}", file=sys.stderr)
            time.sleep(1.5)
            continue
        if is_readable_pdf_text(pdf_text):
            return candidate, pdf_text
        time.sleep(1.0)
    return None, ""


def call_claude(title: str, excerpt: str) -> tuple[dict, dict]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    prompt = f"""
Παρήγαγε αυστηρά πηγαία, ουδέτερη ελληνική σύνοψη και ανάλυση για το νομοθετικό κείμενο.

Κανόνες:
- Χρησιμοποίησε μόνο πληροφορίες που υπάρχουν στο κείμενο.
- Μην εφευρίσκεις έννοιες, φορείς, κινδύνους ή συνέπειες.
- Γράψε σε άψογα ελληνικά, επίσημο αλλά κατανοητό ύφος.
- Απόφυγε πολιτική αξιολόγηση.
- Επέστρεψε ΜΟΝΟ JSON.

Τίτλος:
{title}

Κείμενο:
{excerpt}

JSON schema:
{{
  "summary_short_el": "1-3 προτάσεις, έως περίπου 450 χαρακτήρες",
  "analysis_el": "5-8 προτάσεις, ουσιαστικά διαφορετικές από τη σύνοψη",
  "quality_notes": ["σύντομες σημειώσεις ποιότητας"]
}}
""".strip()

    payload = {
        "model": MODEL,
        "max_tokens": 1400,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = json.loads(resp.read())
    elapsed = time.time() - started
    content = "".join(block.get("text", "") for block in raw.get("content", []) if block.get("type") == "text")
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise RuntimeError(f"Claude response did not contain JSON: {content[:300]}")
    parsed = json.loads(match.group(0))
    usage = raw.get("usage", {})
    usage["elapsed_sec"] = round(elapsed, 2)
    return parsed, usage


def validate_result(result: dict, excerpt: str) -> list[str]:
    errors: list[str] = []
    short = (result.get("summary_short_el") or "").strip()
    analysis = (result.get("analysis_el") or "").strip()
    if len(short) < 40:
        errors.append("summary_short_el too short")
    if len(short) > 600:
        errors.append("summary_short_el too long")
    if len(analysis) < 250:
        errors.append("analysis_el too short")
    if short == analysis or short in analysis:
        errors.append("analysis_el is not distinct")
    forbidden = ("αθέμιτων παρόχων", "αποτείνει", "πρότυποι αυτοί")
    for word in forbidden:
        if word in short or word in analysis:
            errors.append(f"known bad phrase: {word}")
    if "ως AI" in analysis or "δεν μπορώ" in analysis:
        errors.append("AI disclaimer leaked")
    return errors


async def main() -> None:
    parser = argparse.ArgumentParser(description="Claude analysis_el backfill for explicit Parliament bills")
    parser.add_argument("--bill-id", action="append", required=True, help="Bill ID to process. Can be repeated.")
    parser.add_argument("--apply", action="store_true", help="Write summary_short_el + analysis_el to DB")
    parser.add_argument("--official-only", action="store_true", help="Only refresh summary_long_el official text/PDF block")
    parser.add_argument("--out-dir", default="/tmp", help="Preview output directory")
    args = parser.parse_args()

    _read_env_file("/opt/ekklesia/.env.production")
    _read_env_file(os.path.join(os.path.dirname(__file__), "..", ".env.production"))

    db_url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    import asyncpg
    conn = await asyncpg.connect(db_url)

    os.makedirs(args.out_dir, exist_ok=True)
    for bill_id in args.bill_id:
        row = await conn.fetchrow(
            """
            SELECT id, title_el, parliament_url, summary_short_el, analysis_el
            FROM parliament_bills
            WHERE id=$1 AND source='PARLIAMENT'
            """,
            bill_id,
        )
        if not row:
            print(f"{bill_id}: not found or not PARLIAMENT")
            continue
        if not row["parliament_url"]:
            print(f"{bill_id}: no parliament_url, skip")
            continue

        try:
            page_md = _http_text(f"{JINA_BASE}{row['parliament_url']}", timeout=90)
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"{bill_id}: skip Parliament page: {exc}", file=sys.stderr)
            time.sleep(2)
            continue
        links = extract_pdf_links(page_md)
        analysis_candidates = pdf_candidates(links, "analysis")
        official_candidates = pdf_candidates(links, "official_text")
        fallback_candidates = fallback_pdf_candidates(links)
        if not analysis_candidates and not official_candidates and not fallback_candidates:
            print(f"{bill_id}: no readable Parliament document PDF found")
            continue

        official_pdf, official_pdf_text = fetch_first_readable_pdf(official_candidates)
        if not official_pdf:
            official_pdf, official_pdf_text = fetch_first_readable_pdf(fallback_candidates)

        analysis_pdf, analysis_pdf_text = fetch_first_readable_pdf(analysis_candidates)
        if not analysis_pdf:
            analysis_pdf, analysis_pdf_text = fetch_first_readable_pdf(fallback_candidates)
        if not official_pdf and analysis_pdf:
            official_pdf = analysis_pdf
            official_pdf_text = analysis_pdf_text

        excerpt = extract_useful_excerpt(analysis_pdf_text or official_pdf_text)
        official_text = (
            build_official_text_block(official_pdf_text, links, official_pdf)
            if official_pdf and official_pdf_text
            else build_documents_block(links)
        )
        if args.official_only:
            result = {
                "summary_short_el": row["summary_short_el"] or "",
                "analysis_el": row["analysis_el"] or "",
                "quality_notes": ["official-only refresh"],
            }
            usage = {}
            errors = []
        else:
            if not excerpt:
                print(f"{bill_id}: no readable text for Claude analysis; use --official-only for PDF links")
                continue
            result, usage = call_claude(row["title_el"] or bill_id, excerpt)
            errors = validate_result(result, excerpt)

        preview = {
            "bill_id": bill_id,
            "title_el": row["title_el"],
            "analysis_pdf": analysis_pdf,
            "official_pdf": official_pdf,
            "pdf_links": links,
            "input_chars": len(excerpt),
            "official_pdf_chars": len(clean_pdf_text(official_pdf_text)),
            "official_text_chars": len(official_text),
            "apply": bool(args.apply),
            "result": result,
            "official_text_el": official_text,
            "usage": usage,
            "validation_errors": errors,
        }
        json_path = os.path.join(args.out_dir, f"claude_analysis_{bill_id}.json")
        md_path = os.path.join(args.out_dir, f"claude_analysis_{bill_id}.md")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(preview, f, ensure_ascii=False, indent=2)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {bill_id}\n\n")
            if analysis_pdf:
                f.write(f"Analysis PDF: [{analysis_pdf['label']}]({analysis_pdf['url']})\n\n")
            if official_pdf:
                f.write(f"Official PDF: [{official_pdf['label']}]({official_pdf['url']})\n\n")
            f.write(f"Input chars: {len(excerpt)}\n\n")
            f.write("## Σύνοψη\n")
            f.write((result.get("summary_short_el") or "").strip() + "\n\n")
            f.write("## Ανάλυση\n")
            f.write((result.get("analysis_el") or "").strip() + "\n\n")
            f.write("## Επίσημο κείμενο και έγγραφα\n")
            f.write(official_text + "\n\n")
            f.write(f"Validation errors: {errors or 'none'}\n")
            f.write(f"Usage: {usage}\n")

        print(f"{bill_id}: preview {json_path}")
        if errors:
            print(f"{bill_id}: validation errors, not applying: {errors}")
            continue
        if args.apply:
            if args.official_only:
                await conn.execute(
                    """
                    UPDATE parliament_bills
                    SET summary_long_el=$1, updated_at=NOW()
                    WHERE id=$2
                    """,
                    official_text,
                    bill_id,
                )
            else:
                await conn.execute(
                    """
                    UPDATE parliament_bills
                    SET summary_short_el=$1, analysis_el=$2, summary_long_el=$3, updated_at=NOW()
                    WHERE id=$4
                    """,
                    (result.get("summary_short_el") or "").strip(),
                    (result.get("analysis_el") or "").strip(),
                    official_text,
                    bill_id,
                )
            print(f"{bill_id}: DB updated")
        else:
            print(f"{bill_id}: dry-run only")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
