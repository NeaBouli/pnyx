"use client";

import { useEffect, useState } from "react";
import type { Bill } from "@/lib/api";

export default function ParliamentFreshness({ bill, locale }: { bill: Pick<Bill,
  "source" | "source_last_success" | "source_blocked" | "source_stale">; locale: string }) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    setNow(Date.now());
  }, [bill.source_last_success]);

  if (bill.source && bill.source !== "PARLIAMENT") return null;
  const el = locale === "el";
  const date = bill.source_last_success ? new Date(bill.source_last_success) : null;
  const known = date !== null && Number.isFinite(date.getTime());
  const outdated = bill.source_blocked || bill.source_stale || !known
    || (now !== null && now - date!.getTime() > 48 * 3600 * 1000);
  return (
    <div className="text-xs text-gray-600 my-2">
      <p>{el ? "Τελευταία ενημέρωση: " : "Last updated: "}
        {known ? <time dateTime={bill.source_last_success!}>{date!.toLocaleString(el ? "el-GR" : "en-GB", { timeZone: "Europe/Athens" })}</time>
          : (el ? "Μη διαθέσιμη" : "Unavailable")}</p>
      {outdated && <p>{el ? "Τα δεδομένα της Βουλής ενδέχεται να μην είναι ενημερωμένα"
        : "Parliament data may be outdated"}</p>}
    </div>
  );
}
