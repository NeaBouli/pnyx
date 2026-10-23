import { describe, expect, it } from "vitest";
import { hasParliamentProvenance, parliamentOriginalUrl } from "./parliament-source";

const official = "https://www.hellenicparliament.gr/bill/123";
const decision = "https://diavgeia.gov.gr/decision/view/123";

describe("Parliament attribution classification", () => {
  it.each([
    { name: "scraper import", bill: { source: "PARLIAMENT", parliament_url: official }, expected: official },
    { name: "official PDF", bill: { source: "PARLIAMENT", official_source_url: official }, expected: official },
    { name: "official host with query", bill: { source: "PARLIAMENT", parliament_url: "https://hellenicparliament.gr?bill=123" }, expected: "https://hellenicparliament.gr?bill=123" },
    { name: "admin proposal with default workflow", bill: { source: "PARLIAMENT" }, expected: null },
    { name: "Diavgeia decision", bill: { source: "DIAVGEIA", official_source_url: decision }, expected: null },
    { name: "Diavgeia with Parliament URL", bill: { source: "DIAVGEIA", parliament_url: official }, expected: null },
    { name: "unknown source with Parliament URL", bill: { source: "UNKNOWN", parliament_url: official }, expected: null },
    { name: "missing source with Parliament URL", bill: { parliament_url: official }, expected: null },
    { name: "foreign URL", bill: { source: "PARLIAMENT", parliament_url: "https://evil.example/bill" }, expected: null },
    { name: "malformed URL", bill: { source: "PARLIAMENT", official_source_url: "not a url" }, expected: null },
    { name: "HTTP URL", bill: { source: "PARLIAMENT", parliament_url: "http://www.hellenicparliament.gr/bill" }, expected: null },
    { name: "credentials", bill: { source: "PARLIAMENT", parliament_url: "https://user@www.hellenicparliament.gr/bill" }, expected: null },
    { name: "explicit default port", bill: { source: "PARLIAMENT", parliament_url: "https://www.hellenicparliament.gr:443/bill" }, expected: null },
    { name: "encoded hostname", bill: { source: "PARLIAMENT", parliament_url: "https://%77ww.hellenicparliament.gr/bill" }, expected: null },
    { name: "safe fallback", bill: { source: "PARLIAMENT", official_source_url: "https://evil.example/", parliament_url: official }, expected: official },
  ])("$name", ({ bill, expected }) => {
    expect(hasParliamentProvenance(bill)).toBe(expected !== null);
    expect(parliamentOriginalUrl(bill)).toBe(expected);
  });
});
