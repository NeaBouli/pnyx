#!/usr/bin/env python3
"""
NEA-301b: Ollama-based backfill for summary_short_el + pill_el.

Usage:
  python3 scripts/backfill_summary_ollama.py                    # dry-run, 10 bills
  python3 scripts/backfill_summary_ollama.py --limit 20         # dry-run, 20 bills
  python3 scripts/backfill_summary_ollama.py --source PARLIAMENT # only parliament
  python3 scripts/backfill_summary_ollama.py --apply --limit 50 # apply to 50 bills

Rules:
- --dry-run is DEFAULT (no DB writes)
- NEVER overwrite existing summary_short_el or non-empty pill_el
- Rate-limited: 5s between Ollama requests
- CSV audit log for every change
- Ollama model: qwen2.5:14b (better Greek) with llama3.2:3b fallback
"""
import argparse
import asyncio
import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL = "qwen2.5:14b"
RATE_LIMIT_SEC = 5
MAX_INPUT_CHARS = 2000

PROMPT_TEMPLATE = """Summarize this Greek law/decision. Respond ONLY in JSON, no other text.

Title: {title}
Text: {text}

JSON response:
{{"pill_el": "one Greek sentence, max 150 chars, what this is about", "summary_short_el": "2-3 Greek sentences, max 400 chars, key points"}}"""


def clean_input_text(text: str) -> str:
    """Remove HTML noise, markdown artifacts, URLs from summary_long_el."""
    if not text:
        return ""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"Image \d+:.*?\.pdf", "", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_INPUT_CHARS]


def call_ollama(prompt: str, retries: int = 2) -> dict | None:
    """Call Ollama API, return parsed JSON or None. Retries on failure."""
    for attempt in range(retries):
        data = json.dumps({
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 800, "temperature": 0.2},
        }).encode()

        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=300)
            result = json.loads(resp.read()).get("response", "").strip()

            # Try strict JSON parse first
            json_match = re.search(r"\{[^{}]*\}", result, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    pill = parsed.get("pill_el", "").strip()
                    short = parsed.get("summary_short_el", "").strip()
                    if pill and short:
                        return {"pill_el": pill[:200], "summary_short_el": short[:400]}
                except json.JSONDecodeError:
                    pass

            # Fallback: extract pill_el and summary_short_el from free text
            pill_match = re.search(r'"pill_el"\s*:\s*"([^"]{10,200})"', result)
            short_match = re.search(r'"summary_short_el"\s*:\s*"([^"]{20,500})"', result)
            if pill_match and short_match:
                return {"pill_el": pill_match.group(1), "summary_short_el": short_match.group(1)}

            print(f"    Attempt {attempt+1}: no valid JSON in response ({len(result)} chars)")
        except Exception as e:
            print(f"    Attempt {attempt+1} error: {e}")

        if attempt < retries - 1:
            time.sleep(3)

    return None


SENTENCE_ENDINGS = re.compile(r"[.;!?·…]")


def trim_to_sentence(text: str, max_chars: int) -> str:
    """Trim text to last complete sentence within max_chars."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_chars and SENTENCE_ENDINGS.search(text[-1:]):
        return text

    truncated = text[:max_chars]
    # Find last sentence-ending punctuation
    for i in range(len(truncated) - 1, -1, -1):
        if SENTENCE_ENDINGS.match(truncated[i]):
            return truncated[:i + 1]

    # No sentence boundary found — reject
    return ""


REJECT_PATTERNS = [
    r"δεν υπάρχουν πληροφορίες",
    r"ως AI",
    r"δεν μπορώ",
    r"https?://",
    r"<[a-z]",
    r"\!\[",
    r"\*\*",
]


def validate_output(pill: str, short: str, title: str) -> str | None:
    """Return rejection reason or None if valid."""
    if not short or len(short) < 20:
        return "summary too short"
    if len(short) > 500:
        return "summary too long"
    if pill and len(pill) > 200:
        return "pill too long"
    # Must end on sentence boundary
    if not SENTENCE_ENDINGS.search(short[-1:]):
        return "summary does not end on sentence boundary"
    for pat in REJECT_PATTERNS:
        if re.search(pat, short, re.IGNORECASE):
            return f"rejected pattern: {pat}"
        if pill and re.search(pat, pill, re.IGNORECASE):
            return f"rejected pattern in pill: {pat}"
    # Reject if summary just repeats the title
    if title and short.strip().lower()[:40] == title.strip().lower()[:40]:
        return "summary repeats title"
    return None


async def main():
    parser = argparse.ArgumentParser(description="NEA-301b: Ollama backfill summary_short_el")
    parser.add_argument("--apply", action="store_true", help="Write to DB (default: dry-run)")
    parser.add_argument("--limit", type=int, default=10, help="Limit bills (default 10)")
    parser.add_argument("--source", choices=["PARLIAMENT", "DIAVGEIA", "ALL"], default="ALL")
    args = parser.parse_args()

    dry_run = not args.apply

    db_url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    import asyncpg
    conn = await asyncpg.connect(db_url)

    # Build query
    conditions = [
        "summary_long_el IS NOT NULL",
        "summary_long_el != ''",
        "(summary_short_el IS NULL OR summary_short_el = '')",
        "id NOT LIKE 'DEMO%'",
        "id NOT LIKE 'TEST%'",
        "id NOT IN ('GR-1b8eab9a', 'GR-9f7ad85a')",  # flagged for manual review
    ]
    if args.source != "ALL":
        conditions.append(f"source = '{args.source}'")

    query = f"""
        SELECT id, title_el, summary_long_el, summary_short_el, pill_el, source, status
        FROM parliament_bills
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC
        LIMIT {args.limit}
    """

    rows = await conn.fetch(query)
    print(f"{'DRY-RUN' if dry_run else 'APPLY'} mode — {args.source} — {len(rows)} bills")
    print("=" * 80)

    # CSV audit
    csv_path = "/tmp/backfill_ollama_audit.csv"
    csv_file = open(csv_path, "w", newline="", encoding="utf-8", buffering=1)
    writer = csv.writer(csv_file)
    writer.writerow(["bill_id", "source", "status", "pill_el", "summary_short_el", "action", "model"])

    updated = 0
    skipped = 0
    errors = 0

    for i, row in enumerate(rows):
        bill_id = row["id"]
        title = row["title_el"] or ""
        long_el = row["summary_long_el"] or ""
        existing_short = row["summary_short_el"]
        existing_pill = row["pill_el"]

        # Safety: never overwrite
        if existing_short and existing_short.strip():
            writer.writerow([bill_id, row["source"], row["status"], "", "", "SKIP_EXISTS", ""])
            skipped += 1
            continue

        print(f"\n[{i+1}/{len(rows)}] {bill_id} [{row['source']}/{row['status']}]", flush=True)
        print(f"  Title: {title[:70]}", flush=True)

        cleaned = clean_input_text(long_el)
        if len(cleaned) < 30:
            writer.writerow([bill_id, row["source"], row["status"], "", "", "SKIP_SHORT", ""])
            skipped += 1
            print("  SKIP: text too short after cleaning")
            continue

        prompt = PROMPT_TEMPLATE.format(title=title[:200], text=cleaned)

        result = call_ollama(prompt)
        model_used = MODEL

        if not result:
            writer.writerow([bill_id, row["source"], row["status"], "", "", "ERROR", model_used])
            errors += 1
            print("  ERROR: both models failed")
            time.sleep(RATE_LIMIT_SEC)
            continue

        pill = result["pill_el"]
        short = trim_to_sentence(result["summary_short_el"], 400)
        pill = trim_to_sentence(pill, 200) if pill else pill

        # Validate
        rejection = validate_output(pill, short, title)
        if rejection:
            writer.writerow([bill_id, row["source"], row["status"], "", "", f"REJECTED: {rejection}", model_used])
            errors += 1
            print(f"  REJECTED: {rejection}")
            time.sleep(RATE_LIMIT_SEC)
            continue

        # Don't overwrite existing pill
        if existing_pill and existing_pill.strip():
            pill = None

        print(f"  Pill:  {pill[:100] if pill else '(keep existing)'}")
        print(f"  Short: {short[:150]}", flush=True)

        writer.writerow([bill_id, row["source"], row["status"],
                         pill if pill else "", short,
                         "UPDATE" if not dry_run else "DRY_RUN", model_used])

        if not dry_run:
            if pill:
                await conn.execute(
                    "UPDATE parliament_bills SET summary_short_el = $1, pill_el = $2 WHERE id = $3 AND (summary_short_el IS NULL OR summary_short_el = '')",
                    short, pill, bill_id,
                )
            else:
                await conn.execute(
                    "UPDATE parliament_bills SET summary_short_el = $1 WHERE id = $2 AND (summary_short_el IS NULL OR summary_short_el = '')",
                    short, bill_id,
                )

        updated += 1
        time.sleep(RATE_LIMIT_SEC)

    csv_file.close()

    print(f"\n{'=' * 80}")
    print(f"Results: {updated} {'updated' if not dry_run else 'would update'}, {skipped} skipped, {errors} errors")
    print(f"CSV audit: {csv_path}")

    if dry_run:
        print(f"\nDRY-RUN complete. To apply: python3 scripts/backfill_summary_ollama.py --apply --limit {args.limit}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
