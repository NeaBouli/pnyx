"""Fixed predicate shared by the public metadata index and request queries.

Changing this policy requires rebuilding the partial index in a migration.
Only developer-owned constants are inlined, never request values.
"""
PUBLIC_BILL_INDEX = "idx_bills_public_metadata"
SENSITIVE_PATTERN = r"αμκα|α\.μ\.κ\.α|amka|ασθεν|εοπυυ|eopyy"
PUBLIC_BILL_INDEX_PREDICATE = (
    "admin_hidden IS NOT TRUE AND NOT (source = 'DIAVGEIA' AND ("
    + " OR ".join(
        f"lower(coalesce({column}, '')) ~ '{SENSITIVE_PATTERN}'"
        for column in ("title_el", "summary_short_el", "summary_long_el")
    ) + "))"
)
