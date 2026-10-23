"""Official source URL helpers for Parliament/Diavgeia bills."""
import re
from typing import Any
from urllib.parse import quote, urlsplit

PARLIAMENT_PDF_RE = re.compile(
    r"https://www\.hellenicparliament\.gr/[^\s)\]]+?\.pdf",
    re.IGNORECASE,
)


def _get(bill: Any, key: str) -> Any:
    if isinstance(bill, dict):
        return bill.get(key)
    return getattr(bill, key, None)


def _parliament_url(value: str | None) -> str | None:
    """Accept exact official HTTPS hosts without credentials or explicit ports."""
    if not value or re.search(r"[\\\s\x00-\x1f\x7f]", value):
        return None
    try:
        url = urlsplit(value)
        if (url.scheme == "https" and url.netloc.lower() in {
            "www.hellenicparliament.gr", "hellenicparliament.gr",
        }):
            return value
    except ValueError:
        pass
    return None


def official_source_url(bill: Any) -> str | None:
    """Return the most readable official source URL for a bill."""

    source = _get(bill, "source")
    parliament_url = _get(bill, "parliament_url")
    if source == "DIAVGEIA":
        ada = _get(bill, "diavgeia_ada")
        if ada:
            return f"https://diavgeia.gov.gr/decision/view/{quote(ada, safe='')}"
        if parliament_url and "/decision/view/" in parliament_url:
            return parliament_url
        return None

    if source == "PARLIAMENT":
        for candidate in PARLIAMENT_PDF_RE.findall(_get(bill, "summary_long_el") or ""):
            if _parliament_url(candidate):
                return candidate

    return None


def parliament_attribution_fields(bill: Any) -> dict:
    """Carry per-bill provenance and its republication date into public projections."""
    created_at = _get(bill, "created_at")
    source = _get(bill, "source")
    parliament_url = _get(bill, "parliament_url")
    return {
        "source": source,
        "parliament_url": _parliament_url(parliament_url) if source == "PARLIAMENT" else parliament_url,
        "official_source_url": official_source_url(bill),
        "created_at": created_at.isoformat() if created_at else None,
    }
