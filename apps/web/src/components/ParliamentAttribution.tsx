import { hasParliamentProvenance, parliamentOriginalUrl } from "../lib/parliament-source";
import type { Bill } from "@/lib/api";

export type AttributionBill = Pick<Bill,
  "source" | "source_last_success" | "created_at" | "official_source_url" | "parliament_url">;

export default function ParliamentAttribution({ bill, locale }: { bill: AttributionBill; locale: string }) {
  if (!hasParliamentProvenance(bill)) return null;
  const el = locale === "el";
  // The API's legacy naive timestamps are UTC, irrespective of the reader's timezone.
  const date = [bill.source_last_success, bill.created_at].flatMap((value) => {
    if (!value) return [];
    const parsed = new Date(value.includes("T") && !/(Z|[+-]\d{2}:?\d{2})$/i.test(value) ? `${value}Z` : value);
    return Number.isFinite(parsed.getTime()) ? [parsed] : [];
  })[0];
  const url = parliamentOriginalUrl(bill);
  return (
    <div className="my-2 text-xs leading-relaxed text-gray-600">
      <p>{el ? "Αναδημοσίευση από τη διαδικτυακή πύλη της Βουλής των Ελλήνων"
        : "Republished from the website of the Hellenic Parliament"}</p>
      <p>
        {el ? "Ημερομηνία: " : "Date: "}
        {date ? <time dateTime={date.toISOString()}>{date.toLocaleDateString("en-GB", {
          timeZone: "Europe/Athens", day: "2-digit", month: "2-digit", year: "numeric",
        })}</time> : (el ? "Μη διαθέσιμη" : "Unavailable")}
        {url && <>{" · "}<a href={url} target="_blank" rel="noopener external"
          className="relative z-10 text-blue-700 underline underline-offset-2 hover:text-blue-800">
          {el ? "Πρωτότυπο" : "Original"}
        </a></>}
      </p>
    </div>
  );
}
