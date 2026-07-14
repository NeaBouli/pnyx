const ACCESS_DENIAL_PATTERNS = [
  "you don't have permission to access",
  "errors.edgesuite.net",
];

const PARLIAMENT_BOILERPLATE_PATTERNS = [
  "Μετάβαση στο κύριο περιεχόμενο",
  "Ανοίξτε το μενού προσβασιμότητας",
  "Νομοθετική Διαδικασία",
  "Ημερ. Διάταξη Ολομέλειας",
  "Εβδομαδιαίο Δελτίο",
  "Εμφανίζονται τα σχέδια",
  "Εμφανίζονται τα ψηφισθέντα",
];

export function cleanOfficialText(value?: string | null): string {
  if (!value?.trim() || value.includes("[unknown:")) return "";

  const text = value.trim();
  if (PARLIAMENT_BOILERPLATE_PATTERNS.some((pattern) => text.includes(pattern))) {
    return "";
  }

  const lowered = text.toLowerCase();
  if (
    ACCESS_DENIAL_PATTERNS.some((pattern) => lowered.includes(pattern))
    || (lowered.includes("access denied") && lowered.includes("reference #"))
  ) {
    const documentBlockIndex = text.indexOf("### Πλήρη έγγραφα");
    return documentBlockIndex >= 0 ? text.slice(documentBlockIndex).trim() : "";
  }

  return text;
}
