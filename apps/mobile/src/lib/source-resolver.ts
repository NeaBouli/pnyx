/**
 * Golden Path: Source resolution logic for bill detail screens.
 * Extracted for testability — VoteScreen + ResultScreen use these.
 *
 * Priority: official_source_url → forum_topic_url → none
 */

export type SourceKind = "official" | "forum" | "none";

export interface SourceResolution {
  url: string;
  kind: SourceKind;
}

export function resolveSource(
  officialSourceUrl?: string | null,
  forumTopicUrl?: string | null,
): SourceResolution {
  const official = officialSourceUrl?.trim() || "";
  const forum = forumTopicUrl?.trim() || "";

  if (official) return { url: official, kind: "official" };
  if (forum) return { url: forum, kind: "forum" };
  return { url: "", kind: "none" };
}

export function isPdfUrl(url: string): boolean {
  return !!url && url.toLowerCase().includes(".pdf");
}

export function sourceLabel(
  source: string,
  kind: SourceKind,
  url: string,
): string {
  if (source === "DIAVGEIA") return "Πηγή — Διαύγεια";
  if (kind === "forum") return "Διαβάστε & συζητήστε στο Φόρουμ";
  if (isPdfUrl(url)) return "Πηγή — Βουλή (PDF)";
  return "Πηγή — Βουλή των Ελλήνων";
}

// ─── 24h Correction Banner ─────────────────────────────────────────────────

export interface CorrectionBannerState {
  visible: boolean;
  text: string;
  style: "available" | "used" | "none";
}

export function correctionBanner(
  billStatus: string,
  isCorrected: boolean,
): CorrectionBannerState {
  if (billStatus !== "WINDOW_24H") {
    return { visible: false, text: "", style: "none" };
  }
  if (isCorrected) {
    return {
      visible: true,
      text: "Έχετε χρησιμοποιήσει το δικαίωμα της μίας διόρθωσης της ψήφου σας.",
      style: "used",
    };
  }
  return {
    visible: true,
    text: "Τελευταίες 24 ώρες — μπορείτε να διορθώσετε την ψήφο σας (μία φορά)",
    style: "available",
  };
}
