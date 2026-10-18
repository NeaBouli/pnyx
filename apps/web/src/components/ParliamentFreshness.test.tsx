import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import ParliamentFreshness from "./ParliamentFreshness";

describe("Parliament freshness", () => {
  afterEach(() => vi.useRealTimers());
  it.each(["el", "en"])("renders the update time and neutral blocked notice in %s", (locale) => {
    const html = renderToStaticMarkup(<ParliamentFreshness locale={locale} bill={{
      source: "PARLIAMENT", source_last_success: "2026-10-17T09:00:00+00:00", source_blocked: true,
    }} />);
    expect(html).toContain(locale === "el" ? "Τελευταία ενημέρωση:" : "Last updated:");
    expect(html).toContain('dateTime="2026-10-17T09:00:00+00:00"');
    expect(html).toContain(locale === "el" ? "Τα δεδομένα της Βουλής ενδέχεται να μην είναι ενημερωμένα"
      : "Parliament data may be outdated");
  });
  it("shows a warning after 48 hours even if an older payload says fresh", () => {
    vi.useFakeTimers().setSystemTime(new Date("2026-10-18T12:00:00Z"));
    const html = renderToStaticMarkup(<ParliamentFreshness locale="en" bill={{
      source_last_success: "2026-10-16T11:59:00Z", source_stale: false,
    }} />);
    expect(html).toContain("Parliament data may be outdated");
  });
  it("does not show the warning for a recent successful source", () => {
    vi.useFakeTimers().setSystemTime(new Date("2026-10-18T12:00:00Z"));
    const html = renderToStaticMarkup(<ParliamentFreshness locale="en" bill={{
      source_last_success: "2026-10-17T12:00:00Z", source_stale: false,
    }} />);
    expect(html).toContain("Last updated:");
    expect(html).not.toContain("outdated");
  });
  it("makes an unknown update visible and excludes other sources", () => {
    const unknown = renderToStaticMarkup(<ParliamentFreshness locale="en" bill={{}} />);
    expect(unknown).toContain("Unavailable");
    expect(unknown).toContain("Parliament data may be outdated");
    expect(renderToStaticMarkup(<ParliamentFreshness locale="el" bill={{ source: "DIAVGEIA" }} />)).toBe("");
  });
});
