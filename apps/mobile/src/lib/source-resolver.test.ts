/**
 * Golden Path Regression Test: Source Resolution
 * Protects: VoteScreen + ResultScreen source link cascade
 * Risk: Option-E regression (forum fallback was removed once)
 */
import { describe, it, expect } from "vitest";
import {
  cleanOfficialText,
  officialDocumentLinks,
  resolveSource,
  isPdfUrl,
  sourceLabel,
  isOfficialDocumentBlockOnly,
} from "./source-resolver";

describe("resolveSource — Golden Path", () => {
  it("official wins when both present", () => {
    const r = resolveSource("https://parliament.gr/doc.pdf", "https://pnyx.ekklesia.gr/t/132");
    expect(r.kind).toBe("official");
    expect(r.url).toBe("https://parliament.gr/doc.pdf");
  });

  it("forum fallback when official is null", () => {
    const r = resolveSource(null, "https://pnyx.ekklesia.gr/t/132");
    expect(r.kind).toBe("forum");
    expect(r.url).toBe("https://pnyx.ekklesia.gr/t/132");
  });

  it("forum fallback when official is empty string", () => {
    const r = resolveSource("", "https://pnyx.ekklesia.gr/t/131");
    expect(r.kind).toBe("forum");
    expect(r.url).toBe("https://pnyx.ekklesia.gr/t/131");
  });

  it("none when both null", () => {
    const r = resolveSource(null, null);
    expect(r.kind).toBe("none");
    expect(r.url).toBe("");
  });

  it("none when both empty", () => {
    const r = resolveSource("", "");
    expect(r.kind).toBe("none");
    expect(r.url).toBe("");
  });

  it("none when both undefined", () => {
    const r = resolveSource(undefined, undefined);
    expect(r.kind).toBe("none");
    expect(r.url).toBe("");
  });

  it("trims whitespace", () => {
    const r = resolveSource("  ", "  https://pnyx.ekklesia.gr/t/1  ");
    expect(r.kind).toBe("forum");
    expect(r.url).toBe("https://pnyx.ekklesia.gr/t/1");
  });
});

describe("isPdfUrl", () => {
  it("detects .pdf", () => expect(isPdfUrl("https://x.gr/doc.pdf")).toBe(true));
  it("detects .PDF (case insensitive)", () => expect(isPdfUrl("https://x.gr/DOC.PDF")).toBe(true));
  it("rejects html", () => expect(isPdfUrl("https://x.gr/page")).toBe(false));
  it("handles empty", () => expect(isPdfUrl("")).toBe(false));
});

describe("sourceLabel", () => {
  it("DIAVGEIA always gets Διαύγεια label", () => {
    expect(sourceLabel("DIAVGEIA", "official", "https://diavgeia.gov.gr/x")).toBe("Πηγή — Διαύγεια");
  });

  it("forum kind gets forum label", () => {
    expect(sourceLabel("PARLIAMENT", "forum", "https://pnyx.ekklesia.gr/t/1")).toBe("Διαβάστε & συζητήστε στο Φόρουμ");
  });

  it("PDF URL gets PDF label", () => {
    expect(sourceLabel("PARLIAMENT", "official", "https://x.gr/doc.pdf")).toBe("Πηγή — Βουλή (PDF)");
  });

  it("default is Βουλή", () => {
    expect(sourceLabel("PARLIAMENT", "official", "https://x.gr/page")).toBe("Πηγή — Βουλή των Ελλήνων");
  });
});

describe("officialDocumentLinks", () => {
  it("extracts parliament PDF markdown links", () => {
    const links = officialDocumentLinks(`
### Πλήρη έγγραφα
- [Διατάξεις Σχεδίου ή Πρότασης Νόμου](https://www.hellenicparliament.gr/UserFiles/doc.pdf)
`);
    expect(links).toEqual([
      {
        label: "Διατάξεις Σχεδίου ή Πρότασης Νόμου",
        url: "https://www.hellenicparliament.gr/UserFiles/doc.pdf",
      },
    ]);
  });

  it("deduplicates links", () => {
    const links = officialDocumentLinks(
      "[Α](https://x.gr/a.pdf)\n[Α ξανά](https://x.gr/a.pdf)",
    );
    expect(links).toHaveLength(1);
  });

  it("uses filename when label is only .pdf", () => {
    const links = officialDocumentLinks("[.pdf](https://x.gr/13313922.pdf)");
    expect(links[0].label).toBe("Έγγραφο Βουλής (13313922.pdf)");
  });

  it("ignores non-PDF links", () => {
    expect(officialDocumentLinks("[Topic](https://pnyx.ekklesia.gr/t/1)")).toEqual([]);
  });
});

describe("isOfficialDocumentBlockOnly", () => {
  it("detects PDF-only parliament document blocks", () => {
    expect(isOfficialDocumentBlockOnly(`
### Πλήρη έγγραφα
- [Έγγραφο Βουλής 1 (13338120.pdf)](https://www.hellenicparliament.gr/UserFiles/13338120.pdf)
- [Έγγραφο Βουλής 2 (13338121.pdf)](https://www.hellenicparliament.gr/UserFiles/13338121.pdf)
`)).toBe(true);
  });

  it("does not treat real text plus document links as PDF-only", () => {
    expect(isOfficialDocumentBlockOnly(`
### Αιτιολογική Έκθεση
Το σχέδιο νόμου ρυθμίζει ουσιαστικά ζητήματα.

### Πλήρη έγγραφα
- [Έγγραφο Βουλής](https://www.hellenicparliament.gr/UserFiles/13338120.pdf)
`)).toBe(false);
  });

  it("does not treat arbitrary PDF links as a parliament document block", () => {
    expect(isOfficialDocumentBlockOnly("[Έγγραφο](https://x.gr/a.pdf)")).toBe(false);
  });
});

describe("cleanOfficialText", () => {
  it("returns empty text for PDF-only document blocks", () => {
    expect(cleanOfficialText(`
### Πλήρη έγγραφα
- [Έγγραφο Βουλής 1 (13338120.pdf)](https://www.hellenicparliament.gr/UserFiles/13338120.pdf)
`)).toBe("");
  });

  it("removes the appended PDF document block but keeps official text", () => {
    const value = `
Το σχέδιο νόμου περιλαμβάνει επίσημο κείμενο για ενημέρωση των πολιτών.

### Πλήρη έγγραφα
- [Έγγραφο Βουλής 1 (13338120.pdf)](https://www.hellenicparliament.gr/UserFiles/13338120.pdf)
- [Έγγραφο Βουλής 2 (13338121.pdf)](https://www.hellenicparliament.gr/UserFiles/13338121.pdf)
`;

    expect(cleanOfficialText(value)).toBe(
      "Το σχέδιο νόμου περιλαμβάνει επίσημο κείμενο για ενημέρωση των πολιτών.",
    );
    expect(officialDocumentLinks(value)).toHaveLength(2);
  });

  it("hides old Parliament search-boilerplate text", () => {
    expect(cleanOfficialText(
      "Αναζήτηση Τίτλος Ενίσχυση της εφαρμογής της ισότητας της αμοιβής",
    )).toBe("");
  });
});

// ─── GH#102: 24h Correction Banner ─────────────────────────────────────────

import { correctionBanner } from "./source-resolver";

describe("correctionBanner — Golden Path GH#102", () => {
  it("WINDOW_24H + not corrected → available text", () => {
    const r = correctionBanner("WINDOW_24H", false);
    expect(r.visible).toBe(true);
    expect(r.style).toBe("available");
    expect(r.text).toContain("μπορείτε να διορθώσετε");
  });

  it("WINDOW_24H + already corrected → used text", () => {
    const r = correctionBanner("WINDOW_24H", true);
    expect(r.visible).toBe(true);
    expect(r.style).toBe("used");
    expect(r.text).toContain("χρησιμοποιήσει");
  });

  it("ACTIVE → no banner", () => {
    const r = correctionBanner("ACTIVE", false);
    expect(r.visible).toBe(false);
  });

  it("PARLIAMENT_VOTED → no banner", () => {
    const r = correctionBanner("PARLIAMENT_VOTED", true);
    expect(r.visible).toBe(false);
  });

  it("OPEN_END → no banner", () => {
    const r = correctionBanner("OPEN_END", false);
    expect(r.visible).toBe(false);
  });
});
