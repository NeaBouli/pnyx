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
