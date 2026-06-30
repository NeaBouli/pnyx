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

export interface OfficialDocumentLink {
  label: string;
  url: string;
}

export function officialDocumentLinks(value?: string | null): OfficialDocumentLink[] {
  if (!value) return [];
  const links: OfficialDocumentLink[] = [];
  const seen = new Set<string>();
  const markdownLink = /\[([^\]]+)\]\((https?:\/\/[^)]+\.pdf[^)]*)\)/gi;
  let match: RegExpExecArray | null;
  while ((match = markdownLink.exec(value)) !== null) {
    const rawLabel = match[1].replace(/[*_`#-]+/g, " ").replace(/\s+/g, " ").trim();
    const url = match[2].trim();
    if (!url || seen.has(url)) continue;
    seen.add(url);
    const filename = url.split("/").pop()?.split("?")[0] || "PDF";
    const label = rawLabel && rawLabel.toLowerCase() !== ".pdf"
      ? rawLabel
      : `Έγγραφο Βουλής (${filename})`;
    links.push({ label, url });
  }
  return links;
}

export function isOfficialDocumentBlockOnly(value?: string | null): boolean {
  if (!value) return false;
  const lines = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 2) return false;

  const heading = lines[0].replace(/^#{1,6}\s*/, "").trim();
  if (heading !== "Πλήρη έγγραφα") return false;

  return lines.slice(1).every((line) =>
    /^-?\s*\[[^\]]+\]\(https?:\/\/[^)]+\.pdf[^)]*\)$/i.test(line),
  );
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
