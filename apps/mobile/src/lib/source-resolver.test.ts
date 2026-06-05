/**
 * Golden Path Regression Test: Source Resolution
 * Protects: VoteScreen + ResultScreen source link cascade
 * Risk: Option-E regression (forum fallback was removed once)
 */
import { describe, it, expect } from "vitest";
import { resolveSource, isPdfUrl, sourceLabel } from "./source-resolver";

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
