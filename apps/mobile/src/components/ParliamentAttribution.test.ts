import type React from "react";
import { describe, expect, it, vi } from "vitest";
import ParliamentAttribution, { type AttributionBill } from "./ParliamentAttribution";

const native = vi.hoisted(() => ({ openURL: vi.fn() }));
vi.mock("react-native", () => ({
  View: "View", Text: "Text", TouchableOpacity: "TouchableOpacity",
  StyleSheet: { create: (styles: unknown) => styles }, Linking: { openURL: native.openURL },
}));

type Node = React.ReactElement<{ children?: React.ReactNode; accessibilityRole?: string; onPress?: (event: unknown) => void }>;
function nodes(value: React.ReactNode): Node[] {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== "object" || !("props" in value)) return [];
  const node = value as Node;
  return [node, ...nodes(node.props.children)];
}
function text(value: React.ReactNode): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(text).join("");
  return value && typeof value === "object" && "props" in value ? text((value as Node).props.children) : "";
}

const bill: AttributionBill = {
  source: "PARLIAMENT", source_last_success: "2026-07-16T21:30:00Z", created_at: "2026-01-01T23:30:00",
  official_source_url: "https://www.hellenicparliament.gr/bill/123",
  parliament_url: "https://www.hellenicparliament.gr/bill/fallback",
};

const NEGATIVE = ["http://www.hellenicparliament.gr/bill/123", "https://evil.example/", "https://www.hellenicparliament.gr@evil.example/", "https://evil.example@www.hellenicparliament.gr/", "https://user:pass@www.hellenicparliament.gr/", "https://www.hellenicparliament.gr:443/", "https://www.hellenicparliament.gr:444/", "https://www.hellenicparliament.gr.evil.example/", "https://www.hellenicparliament.gr./", "//www.hellenicparliament.gr/", "javascript:alert(1)", "not a url", "https://www.hellenicparliament.gr\\@evil.example/", "https://www.hellenicparliament.gr\n.evil.example/"];

describe.each(["el", "en"])("native Parliament attribution in %s", (locale) => {
  it("renders the exact attribution and Athens date, and opens Original externally without card navigation", () => {
    const tree = ParliamentAttribution({ bill, locale });
    expect(text(tree)).toContain(locale === "el"
      ? "Αναδημοσίευση από τη διαδικτυακή πύλη της Βουλής των Ελλήνων"
      : "Republished from the website of the Hellenic Parliament");
    expect(text(tree)).toContain((locale === "el" ? "Ημερομηνία: " : "Date: ") + "17/07/2026");
    const link = nodes(tree).find(node => node.props.accessibilityRole === "link")!;
    expect(text(link)).toBe(locale === "el" ? "Πρωτότυπο" : "Original");
    const stopPropagation = vi.fn();
    link.props.onPress!({ stopPropagation });
    expect(stopPropagation).toHaveBeenCalledOnce();
    expect(native.openURL).toHaveBeenLastCalledWith(bill.official_source_url);
  });

  it.each([null, "", "invalid"])("uses UTC created_at when last success is %s, and the Parliament URL fallback", (source_last_success) => {
    const tree = ParliamentAttribution({ bill: { ...bill, source_last_success, official_source_url: null }, locale });
    expect(text(tree)).toContain("02/01/2026");
    nodes(tree).find(node => node.props.accessibilityRole === "link")!.props.onPress!({ stopPropagation: vi.fn() });
    expect(native.openURL).toHaveBeenLastCalledWith(bill.parliament_url);
  });

  it.each(["DIAVGEIA", "UNKNOWN", null, undefined, ""])("does not attribute source %s to Parliament", (source) => {
    expect(ParliamentAttribution({ bill: { ...bill, source, official_source_url: null, parliament_url: null }, locale })).toBeNull();
  });

  it("does not invent missing dates or links", () => {
    const tree = ParliamentAttribution({ bill: { source: "PARLIAMENT", parliament_url: "http://hellenicparliament.gr/bill" }, locale });
    expect(text(tree)).toContain(locale === "el" ? "Ημερομηνία: Μη διαθέσιμη" : "Date: Unavailable");
    expect(nodes(tree).some(node => node.props.accessibilityRole === "link")).toBe(false);
  });

  it("rejects executable source links", () => {
    const tree = ParliamentAttribution({ bill: { ...bill, official_source_url: "javascript:alert(1)" }, locale });
    expect(nodes(tree).some(node => node.props.accessibilityRole === "link")).toBe(false);
  });

  it("does not attribute a legacy admin proposal merely because source defaulted to PARLIAMENT", () => {
    expect(ParliamentAttribution({ bill: { source: "PARLIAMENT" }, locale })).toBeNull();
  });
  it.each(["https://hellenicparliament.gr/bill", "https://www.hellenicparliament.gr/bill"])("classifies an imported bill or official URL %s without relying on source", url => {
    const tree = ParliamentAttribution({ bill: { source: "LOCAL", parliament_url: url }, locale });
    expect(text(tree)).toContain(locale === "el" ? "Αναδημοσίευση" : "Republished");
    nodes(tree).find(node => node.props.accessibilityRole === "link")!.props.onPress!({ stopPropagation: vi.fn() });
    expect(native.openURL).toHaveBeenLastCalledWith(url);
  });
  it.each(NEGATIVE)("omits unsafe Original %s but retains the text attribution", official_source_url => {
    const tree = ParliamentAttribution({ bill: { ...bill, official_source_url }, locale });
    expect(nodes(tree).some(node => node.props.accessibilityRole === "link")).toBe(false);
    expect(text(tree)).toContain(locale === "el" ? "Αναδημοσίευση" : "Republished");
  });
});
