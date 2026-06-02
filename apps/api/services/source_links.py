"""Official source URL helpers for Parliament/Diavgeia bills."""
import re
from typing import Any
from urllib.parse import quote

PARLIAMENT_PDF_RE = re.compile(
    r"https://www\.hellenicparliament\.gr/[^\s)\]]+?\.pdf",
    re.IGNORECASE,
)


def _get(bill: Any, key: str) -> Any:
    if isinstance(bill, dict):
        return bill.get(key)
    return getattr(bill, key, None)


def official_source_url(bill: Any) -> str | None:
    """Return the most readable official source URL for a bill."""

    source = _get(bill, "source") or "PARLIAMENT"
    parliament_url = _get(bill, "parliament_url")
    if source == "DIAVGEIA":
        ada = _get(bill, "diavgeia_ada")
        if ada:
            return f"https://diavgeia.gov.gr/decision/view/{quote(ada, safe='')}"
        if parliament_url and "/decision/view/" in parliament_url:
            return parliament_url
        return None

    for candidate in PARLIAMENT_PDF_RE.findall(_get(bill, "summary_long_el") or ""):
        return candidate

    return None
