// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { fileURLToPath, URL as NodeURL } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import AnalyticsPage from "@/app/[locale]/analytics/page";
import MPPage from "@/app/[locale]/mp/page";

const bill = {
  bill_id: "GR-IMPORTED", title_el: "*Επίσημος* _τίτλος_ ".repeat(30), source: "PARLIAMENT",
  parliament_url: "https://www.hellenicparliament.gr/bill", created_at: "2026-01-01T23:30:00",
  divergence_score: 0.5, divergence_pct: 50, pill_el: "Σύνοψη εφαρμογής",
};
vi.mock("next-intl", () => ({ useLocale: () => "el" }));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: React.ComponentProps<"a">) => <a href={href} {...rest}>{children}</a> }));
vi.mock("@/lib/api", () => ({
  analytics: { overview: async () => ({}), trends: async () => ({}), topDivergence: async () => ({ data: [bill] }) },
  exportUrls: {},
  mp: { ranking: async () => ({ ranking: [{ party_abbr: "A" }] }), compare: async () => ({ comparisons: [bill] }) },
}));
afterEach(() => document.body.replaceChildren());

describe.each(["analytics", "mp"])("web %s Parliament titles", page => {
  it("renders the entire title with source, date and a separate Original link", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    try {
      await act(async () => root.render(page === "analytics" ? <AnalyticsPage /> : <MPPage />));
      if (page === "mp") await act(async () => container.querySelector<HTMLButtonElement>("button")!.click());
      expect(container.textContent).toContain(bill.title_el);
      expect(container.textContent).toContain("Αναδημοσίευση");
      expect(container.querySelector("time")?.textContent).toBe("02/01/2026");
      const original = container.querySelector<HTMLAnchorElement>('a[rel="noopener external"]')!;
      expect(original.href).toBe(bill.parliament_url);
      expect(original.parentElement?.closest("a")).toBeNull();
    } finally {
      await act(async () => root.unmount());
    }
  });
});

function embed(kind: "vote" | "results", overrides = {}) {
  const widget = document.createElement("div");
  const loader = document.createElement("div");
  widget.id = "widget"; loader.id = "loader";
  document.body.replaceChildren(widget, loader);
  const ctx = vm.createContext({ document, URL, URLSearchParams, window: { location: { search: "?lang=el" }, addEventListener: vi.fn() }, setInterval: vi.fn() });
  const read = (name: string) => readFileSync(fileURLToPath(new NodeURL("../../../../docs/assets/js/", import.meta.url)) + `embed-${name}.js`, "utf8");
  vm.runInContext(read("ui"), ctx);
  vm.runInContext(read(kind), ctx);
  ctx.render({ ...bill, ...overrides }, {});
  return widget;
}
describe.each(["vote", "results"] as const)("static %s embed Parliament content", kind => {
  it("preserves official titles and displays attribution, source date and Original", () => {
    const widget = embed(kind);
    expect(widget.querySelector(".title")?.textContent).toBe(bill.title_el);
    expect(widget.textContent).toContain("Αναδημοσίευση");
    expect(widget.textContent).toContain("Ημερομηνία: 02/01/2026");
    expect(widget.querySelector<HTMLAnchorElement>('a[rel="noopener external"]')?.href).toBe(bill.parliament_url);
    if (kind === "vote") expect(widget.textContent).toContain("Σύνοψη — ekklesia");
  });
  it("does not attribute local proposals with a legacy source default", () => {
    expect(embed(kind, { parliament_url: null }).textContent).not.toContain("Αναδημοσίευση");
  });
  it.each(["http://www.hellenicparliament.gr/", "https://www.hellenicparliament.gr@evil.example/", "https://evil.example/", "https://www.hellenicparliament.gr:443/"])("omits unsafe originals %s while retaining attribution", official_source_url => {
    const widget = embed(kind, { official_source_url });
    expect(widget.textContent).toContain("Αναδημοσίευση");
    expect(widget.querySelector('a[rel="noopener external"]')).toBeNull();
  });
});
