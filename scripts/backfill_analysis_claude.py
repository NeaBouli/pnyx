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


JINA_BASE = "https://r.jina.ai/"
MODEL = "claude-haiku-4-5-20251001"
MAX_INPUT_CHARS = 6000

GOOD_LABELS = (
    "Αιτιολογική Έκθεση",
    "Έκθεση Επιστημονικής Υπηρεσίας",
    "Πρακτικό Έκθεση της Επιτροπής",
)
PRIMARY_LABEL = "Αιτιολογική Έκθεση"
SKIP_LABEL_PARTS = ("φωτοτυπη", "Τροπολογ")


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
        r"([^\[\]\n]{2,160})"
        r"\[!\[[^\]]*\.pdf[^\]]*\]\(https?://[^)]*pdf\.png\)\]"
        r"\((https?://[^)]+\.pdf[^)]*)\)",
        re.IGNORECASE,
    )
    for match in image_link_pattern.finditer(markdown):
        label = re.sub(r"\s+", " ", match.group(1)).strip()
        label = label.rsplit(")", 1)[-1].strip()
        label = re.sub(r"^https?://\S+", "", label).strip()
        url = match.group(2).strip()
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
    if PRIMARY_LABEL.lower() in label.lower():
        return "primary"
    if any(good.lower() in label.lower() for good in GOOD_LABELS):
        return "good"
    return "unknown"


def choose_pdf(links: list[dict[str, str]]) -> dict[str, str] | None:
    primary = [link for link in links if classify_pdf(link["label"]) == "primary"]
    if primary:
        return primary[0]
    good = [link for link in links if classify_pdf(link["label"]) == "good"]
    return good[0] if good else None


def clean_pdf_text(text: str) -> str:
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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


def build_official_text_block(excerpt: str, links: list[dict[str, str]], chosen: dict[str, str]) -> str:
    """Build a compact official-text block for forum rendering and source links."""
    text = excerpt.strip()
    if len(text) > 3200:
        cut = max(text[:3200].rfind("."), text[:3200].rfind(";"), text[:3200].rfind("·"))
        text = text[:cut + 1 if cut > 1200 else 3200].strip()

    preferred_labels = (
        "Αιτιολογική",
        "Επιστημονικής",
        "Επιτροπής",
        "Ψηφισθέν",
        "Σ/Ν μετά",
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

    lines = [
        "### Αιτιολογική Έκθεση — κύρια σημεία",
        text,
        "",
        "### Πλήρη έγγραφα",
    ]
    seen: set[str] = set()
    for doc in docs:
        if doc["url"] in seen:
            continue
        seen.add(doc["url"])
        label = doc["label"].strip() or "Έγγραφο Βουλής"
        lines.append(f"- [{label}]({doc['url']})")
    return "\n".join(lines).strip()


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

        page_md = _http_text(f"{JINA_BASE}{row['parliament_url']}", timeout=90)
        links = extract_pdf_links(page_md)
        chosen = choose_pdf(links)
        if not chosen:
            print(f"{bill_id}: no readable GOOD PDF found")
            continue

        pdf_text = _http_text(f"{JINA_BASE}{chosen['url']}", timeout=180)
        excerpt = extract_useful_excerpt(pdf_text)
        official_text = build_official_text_block(excerpt, links, chosen)
        if args.official_only:
            result = {
                "summary_short_el": row["summary_short_el"] or "",
                "analysis_el": row["analysis_el"] or "",
                "quality_notes": ["official-only refresh"],
            }
            usage = {}
            errors = []
        else:
            result, usage = call_claude(row["title_el"] or bill_id, excerpt)
            errors = validate_result(result, excerpt)

        preview = {
            "bill_id": bill_id,
            "title_el": row["title_el"],
            "chosen_pdf": chosen,
            "pdf_links": links,
            "input_chars": len(excerpt),
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
            f.write(f"PDF: [{chosen['label']}]({chosen['url']})\n\n")
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
