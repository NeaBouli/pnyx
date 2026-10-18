type SourceFreshness = {
  source?: string | null;
  source_last_success?: string | null;
  source_blocked?: boolean;
  source_stale?: boolean;
};

// Ready for the next app release; current BillsScreen uses Greek.
export function parliamentFreshness(bill: SourceFreshness, locale = "el", now = Date.now()) {
  if (bill.source && bill.source !== "PARLIAMENT") return null;
  const el = locale === "el";
  const date = bill.source_last_success ? new Date(bill.source_last_success) : null;
  const known = date !== null && Number.isFinite(date.getTime());
  const outdated = bill.source_blocked || bill.source_stale || !known
    || now - date!.getTime() > 48 * 3600 * 1000;
  return {
    updated: (el ? "Τελευταία ενημέρωση: " : "Last updated: ")
      + (known ? date!.toLocaleString(el ? "el-GR" : "en-GB", { timeZone: "Europe/Athens" })
        : (el ? "Μη διαθέσιμη" : "Unavailable")),
    notice: outdated ? (el ? "Τα δεδομένα της Βουλής ενδέχεται να μην είναι ενημερωμένα"
      : "Parliament data may be outdated") : null,
  };
}
