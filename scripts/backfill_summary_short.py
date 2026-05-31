"""
NEA-301: Backfill summary_short_el for PARLIAMENT bills only.

Usage:
  python3 scripts/backfill_summary_short.py --limit 20   # dry-run (default), 20 samples
  python3 scripts/backfill_summary_short.py --apply       # write to DB

Rules:
- PARLIAMENT source only (DIAVGEIA excluded — needs Ollama, NEA-301b)
- Only rows where summary_short_el IS NULL/empty AND summary_long_el IS NOT NULL/empty
- Never overwrite existing summary_short_el or pill_el
- CSV audit log written to /tmp/backfill_summary_audit.csv
"""
import argparse
import asyncio
import csv
import os
import re
import sys


# ─── Cleaning ────────────────────────────────────────────────────────────────

BOILERPLATE_PATTERNS = [
    r"Εμφανίζονται τα ψηφισθέντα.*?Κυβερνήσεως\.",
    r"Τ[οo] φωτοτυπημένο σ/ν.*?διορθώσεις",
    r"Τύπος\s+Σχέδιο νόμου",
    r"Φάση Επεξεργασίας.*?Νομοσχέδια",
    r"Ημερ/νια Φάσης επεξεργασίας\s*\d+/\d+/\d+",
    r"Ημ\.\s*Κατάθεσης\s*\d+/\d+/\d+",
    r"Ημ\.\s*Ψήφισης\s*\d+/\d+/\d+",
    r"Αιτιολογική Έκθεση\s*&?\s*Λοιπές Συνοδευτικές Εκθέσεις",
    r"Σχετικές Συνεδριάσεις Επιτροπής",
    r"Πρακτικό\s+Έκθεση της Επιτροπής",
    r"Έκθεση της Επιστημονικής Υπηρεσίας της Βουλής",
    r"Εισηγητές\s*$",
    r"Τροπολογίες\s*$",
    r"Image \d+:.*?\.pdf",
    r"Διαρκής Επιτροπή\s+\S.*?(?=\s{2}|\n|$)",
    r"Υπουργείο\s+\S.*?(?=\s{2}|\n|Επιτροπή)",
]

# Lines starting with these are metadata, not content
SKIP_LINE_PREFIXES = [
    "Τίτλος", "Υπουργείο", "Επιτροπή", "Αρ. Τροπολογίας",
    "Περιγραφή:", "ΦΕΚ", "ΑΔΑ", "τηλ", "Ταχ.", "e-mail",
    "Αρμόδιος", "ΘΕΜΑ:", "Αριθμ.", "Αρ. Πρωτ",
]


def clean_parliament_text(text: str) -> str:
    """Clean raw scraped parliament summary_long_el."""
    if not text:
        return ""

    # Remove markdown image links: ![alt](url)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    # Remove markdown links, keep text: [text](url) → text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    # Remove raw URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove boilerplate
    for pat in BOILERPLATE_PATTERNS:
        text = re.sub(pat, "", text, flags=re.IGNORECASE | re.DOTALL)
    # Remove ** bold markers
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove leading junk
    text = re.sub(r"^[\s\-\*\#>]+", "", text)

    return text


def is_skip_sentence(s: str) -> bool:
    """Return True if sentence is metadata/boilerplate."""
    stripped = s.strip()
    if len(stripped) < 20:
        return True
    for prefix in SKIP_LINE_PREFIXES:
        if stripped.startswith(prefix):
            return True
    # Skip date-only lines
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}", stripped):
        return True
    # Skip lines that are mostly numbers/IDs
    alpha_ratio = sum(1 for c in stripped if c.isalpha()) / max(len(stripped), 1)
    if alpha_ratio < 0.4:
        return True
    return False


# ─── Generators ──────────────────────────────────────────────────────────────

def generate_short_summary(title: str, long_summary: str) -> str:
    """Generate summary_short_el (max 400 chars) from cleaned text."""
    cleaned = clean_parliament_text(long_summary)
    if not cleaned or len(cleaned) < 30:
        return ""

    sentences = re.split(r"(?<=[.;·])\s+", cleaned)
    title_lower = (title or "").lower()[:50]

    parts = []
    chars = 0
    for s in sentences:
        s = s.strip()
        if is_skip_sentence(s):
            continue
        # Skip title repetition
        if title_lower and s.lower()[:40] == title_lower[:40]:
            continue
        parts.append(s)
        chars += len(s) + 1
        if chars >= 400:
            break

    if not parts:
        return ""

    result = " ".join(parts)
    if len(result) > 400:
        cut = result[:400].rfind(".")
        if cut > 80:
            result = result[:cut + 1]
        else:
            result = result[:397].rstrip() + "…"

    return result


def generate_pill(title: str, long_summary: str) -> str:
    """Generate pill_el (max 200 chars) — first clean sentence or title."""
    cleaned = clean_parliament_text(long_summary)

    if cleaned:
        sentences = re.split(r"(?<=[.;·])\s+", cleaned)
        for s in sentences:
            s = s.strip()
            if is_skip_sentence(s):
                continue
            if (title or "").lower()[:30] and s.lower().startswith((title or "").lower()[:30]):
                continue
            if len(s) <= 200:
                return s
            return s[:197] + "…"

    # Fallback: title
    if title:
        return title[:200] if len(title) <= 200 else title[:197] + "…"
    return ""


# ─── Main ────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="NEA-301: Backfill summary_short_el (PARLIAMENT only)")
    parser.add_argument("--apply", action="store_true", help="Write to DB (default: dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="Limit bills (0=all)")
    args = parser.parse_args()

    dry_run = not args.apply

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env.production")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if line.startswith("DATABASE_URL="):
                        db_url = line.split("=", 1)[1].strip().strip('"')
                        break
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    import asyncpg
    conn = await asyncpg.connect(db_url)

    # PARLIAMENT only — DIAVGEIA excluded
    query = """
        SELECT id, title_el, summary_long_el, summary_short_el, pill_el, source, status
        FROM parliament_bills
        WHERE source = 'PARLIAMENT'
        AND summary_long_el IS NOT NULL AND summary_long_el != ''
        AND (summary_short_el IS NULL OR summary_short_el = '')
        ORDER BY created_at DESC
    """
    if args.limit > 0:
        query += f" LIMIT {args.limit}"

    rows = await conn.fetch(query)

    print(f"{'DRY-RUN' if dry_run else 'APPLY'} mode — PARLIAMENT bills only")
    print(f"Bills to process: {len(rows)}")
    print("=" * 80)

    csv_path = "/tmp/backfill_summary_audit.csv"
    csv_file = open(csv_path, "w", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)
    writer.writerow(["bill_id", "status", "long_el_len", "short_el_generated", "pill_el_generated", "action"])

    updated = 0
    skipped = 0

    for row in rows:
        bill_id = row["id"]
        title = row["title_el"] or ""
        long_el = row["summary_long_el"] or ""
        existing_short = row["summary_short_el"]
        existing_pill = row["pill_el"]

        # Safety: never overwrite
        if existing_short and existing_short.strip():
            writer.writerow([bill_id, row["status"], len(long_el), "", "", "SKIP_HAS_SHORT"])
            skipped += 1
            continue

        short = generate_short_summary(title, long_el)
        pill = None
        if not existing_pill or not existing_pill.strip():
            pill = generate_pill(title, long_el)

        if not short:
            writer.writerow([bill_id, row["status"], len(long_el), "", "", "SKIP_NO_CONTENT"])
            skipped += 1
            continue

        writer.writerow([bill_id, row["status"], len(long_el), short[:200], pill[:120] if pill else "", "UPDATE" if not dry_run else "DRY_RUN"])

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

    csv_file.close()
    print(f"\nResults: {updated} would update, {skipped} skipped")
    print(f"CSV audit: {csv_path}")

    # Show samples
    if dry_run:
        csv_file = open(csv_path, "r", encoding="utf-8")
        reader = csv.reader(csv_file)
        next(reader)  # skip header
        print(f"\n{'=' * 80}")
        print("SAMPLES:")
        print("=" * 80)
        shown = 0
        for r in reader:
            if r[5] == "DRY_RUN" and shown < 20:
                print(f"\n--- {r[0]} [{r[1]}] ({r[2]} chars long)")
                print(f"  Short: {r[3]}")
                print(f"  Pill:  {r[4] if r[4] else '(keep existing)'}")
                shown += 1
        csv_file.close()
        print(f"\n{'=' * 80}")
        print(f"DRY-RUN complete. To apply: python3 scripts/backfill_summary_short.py --apply")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
