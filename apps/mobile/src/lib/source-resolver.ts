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

const DOCUMENT_BLOCK_HEADING = "Πλήρη έγγραφα";
const PDF_MARKDOWN_LINE = /^-?\s*\[[^\]]+\]\(https?:\/\/[^)]+\.pdf[^)]*\)$/i;

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
  if (heading !== DOCUMENT_BLOCK_HEADING) return false;

  return lines.slice(1).every((line) => PDF_MARKDOWN_LINE.test(line));
}

function stripOfficialDocumentBlock(value: string): string {
  const output: string[] = [];
  let skippingDocuments = false;

  for (const rawLine of value.split(/\r?\n/)) {
    const line = rawLine.trim();
    const heading = line.replace(/^#{1,6}\s*/, "").trim();

    if (heading === DOCUMENT_BLOCK_HEADING) {
      skippingDocuments = true;
      continue;
    }
    if (skippingDocuments) {
      if (!line || PDF_MARKDOWN_LINE.test(line)) {
        continue;
      }
      skippingDocuments = false;
    }
    output.push(rawLine);
  }

  return output.join("\n");
}

export function cleanOfficialText(value?: string | null): string {
  if (!value || !value.trim() || value.includes("[unknown:") || isOfficialDocumentBlockOnly(value)) {
    return "";
  }
  const withoutDocumentBlock = stripOfficialDocumentBlock(String(value));
  const cleaned = withoutDocumentBlock
    .replace(/\[[^\]]*\]\(https?:\/\/[^)]*\)/g, "")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/^\s*-\s*/gm, "")
    .replace(/\]\(/g, " ")
    .replace(/(^|\s)>\s*/g, "$1")
    .replace(/[*_`]+/g, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\s+/g, " ")
    .trim();

  const badPatterns = [
    "Μετάβαση στο κύριο περιεχόμενο",
    "Ανοίξτε το μενού προσβασιμότητας",
    "Νομοθετική Διαδικασία",
    "Ημερ. Διάταξη Ολομέλειας",
    "Εβδομαδιαίο Δελτίο",
    "Εμφανίζονται τα σχέδια",
    "Εμφανίζονται τα ψηφισθέντα",
    "Κατατεθέντα Σ/Ν",
  ];
  if (badPatterns.some((pattern) => cleaned.includes(pattern))) {
    return "";
  }
  if (cleaned.startsWith("Αναζήτηση Τίτλος")) {
    return "";
  }
  return cleaned.slice(0, 1400);
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
