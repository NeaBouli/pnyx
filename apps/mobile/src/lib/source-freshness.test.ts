import { describe, expect, it } from "vitest";
import { parliamentFreshness } from "./source-freshness";

const now = Date.parse("2026-10-18T12:00:00Z");
describe("Parliament freshness for the next mobile release", () => {
  it.each(["el", "en"])("shows update and neutral blocked notice in %s", (locale) => {
    const result = parliamentFreshness({ source: "PARLIAMENT", source_last_success: "2026-10-18T11:00:00Z", source_blocked: true }, locale, now)!;
    expect(result.updated).toContain(locale === "el" ? "Τελευταία ενημέρωση:" : "Last updated:");
    expect(result.notice).toBe(locale === "el" ? "Τα δεδομένα της Βουλής ενδέχεται να μην είναι ενημερωμένα" : "Parliament data may be outdated");
  });
  it("shows stale or missing updates, hides the warning for current data, and excludes Diavgeia", () => {
    expect(parliamentFreshness({}, "en", now)?.updated).toContain("Unavailable");
    expect(parliamentFreshness({}, "en", now)?.notice).toBeTruthy();
    expect(parliamentFreshness({ source_last_success: "2026-10-16T11:59:00Z" }, "en", now)?.notice).toBeTruthy();
    expect(parliamentFreshness({ source_last_success: "2026-10-17T12:00:00Z" }, "en", now)?.notice).toBeNull();
    expect(parliamentFreshness({ source: "DIAVGEIA" }, "en", now)).toBeNull();
  });
});
