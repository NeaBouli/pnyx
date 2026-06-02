"""Official source URL helpers for Parliament/Diavgeia bills."""
import re
from typing import Any
from urllib.parse import quote

PARLIAMENT_PDF_RE = re.compile(
    r"https://www\.hellenicparliament\.gr/[^\s)\]]+?\.pdf",
    re.IGNORECASE,
)


def official_source_url(bill: Any) -> str | None:
    """Return the most readable official source URL for a bill."""

    source = bill.source or "PARLIAMENT"
    if source == "DIAVGEIA":
        if bill.diavgeia_ada:
            return f"https://diavgeia.gov.gr/decision/view/{quote(bill.diavgeia_ada, safe='')}"
        return bill.parliament_url

    for candidate in PARLIAMENT_PDF_RE.findall(bill.summary_long_el or ""):
        return candidate

    return bill.parliament_url
