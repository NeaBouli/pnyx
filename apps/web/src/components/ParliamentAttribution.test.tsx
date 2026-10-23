// @vitest-environment jsdom
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import ParliamentAttribution from "./ParliamentAttribution";

const bill = {
  source: "PARLIAMENT", source_last_success: "2026-07-16T21:30:00Z",
  created_at: "2026-01-01T23:30:00", official_source_url: "https://www.hellenicparliament.gr/bill/123",
  parliament_url: "https://www.hellenicparliament.gr/bill/fallback",
};

function render(overrides = {}, locale = "el") {
  const container = document.createElement("div");
  container.innerHTML = renderToStaticMarkup(<ParliamentAttribution bill={{ ...bill, ...overrides }} locale={locale} />);
  return container;
}

describe.each(["el", "en"])("Parliament attribution in %s", (locale) => {
  it("renders the exact attribution, Athens date and accessible external original link", () => {
    const node = render({}, locale);
    expect(node.textContent).toContain(locale === "el"
      ? "Αναδημοσίευση από τη διαδικτυακή πύλη της Βουλής των Ελλήνων"
      : "Republished from the website of the Hellenic Parliament");
    expect(node.textContent).toContain((locale === "el" ? "Ημερομηνία: " : "Date: ") + "17/07/2026");
    expect(node.querySelector("time")?.dateTime).toBe("2026-07-16T21:30:00.000Z");
    const link = node.querySelector("a")!;
    expect(link.textContent).toBe(locale === "el" ? "Πρωτότυπο" : "Original");
    expect(link.href).toBe(bill.official_source_url);
    expect(link.target).toBe("_blank");
    expect(link.rel).toBe("noopener external");
    expect(node.querySelector("[style], script")).toBeNull();
  });

  it.each([null, "", "invalid"])("uses UTC created_at when last success is %s, and the Parliament URL fallback", (source_last_success) => {
    const node = render({ source_last_success, official_source_url: null }, locale);
    expect(node.querySelector("time")?.textContent).toBe("02/01/2026");
    expect(node.querySelector("a")?.href).toBe(bill.parliament_url);
  });

  it.each(["DIAVGEIA", "UNKNOWN", null, undefined, ""])("does not attribute source %s to Parliament", (source) => {
    expect(render({ source }, locale).innerHTML).toBe("");
  });

  it("does not invent a date or a link for incomplete data", () => {
    const node = render({ source_last_success: null, created_at: null, official_source_url: null, parliament_url: null }, locale);
    expect(node.textContent).toContain(locale === "el" ? "Ημερομηνία: Μη διαθέσιμη" : "Date: Unavailable");
    expect(node.querySelector("time, a")).toBeNull();
  });

  it("rejects an executable source link", () => {
    expect(render({ official_source_url: "javascript:alert(1)" }, locale).querySelector("a")).toBeNull();
  });
});
