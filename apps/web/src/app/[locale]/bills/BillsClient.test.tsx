// @vitest-environment jsdom
import React, { act, StrictMode } from "react";
import { hydrateRoot, type Root } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Bill } from "@/lib/api";
import type { InitialBills } from "@/lib/initial-data";
import BillsClient from "./BillsClient";

const context = vi.hoisted(() => ({
  params: new URLSearchParams(), locale: "en",
  getBills: vi.fn(), periferias: vi.fn(), dimoi: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useSearchParams: () => context.params }));
vi.mock("next-intl", () => ({ useLocale: () => context.locale }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a>,
}));
vi.mock("@/components/RelevanceButtons", () => ({ default: () => <span data-relevance /> }));
vi.mock("@/lib/api", () => ({
  ekklesia: { getBills: context.getBills },
  municipal: { periferias: context.periferias, dimoi: context.dimoi },
}));

function bill(id: string, status = "ACTIVE"): Bill {
  return {
    id, source: "PARLIAMENT", parliament_url: "https://www.hellenicparliament.gr/bill", title_el: `Τίτλος ${id}`, title_en: `Title ${id}`, pill_el: null, pill_en: null,
    summary_short_el: null, summary_short_en: null, summary_long_el: null, summary_long_en: null,
    categories: null, party_votes_parliament: null, status, parliament_vote_date: null,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

// Loading skeleton line; StatusBadge also uses animate-pulse, so match the skeleton itself.
const SKELETON = "h-4 bg-gray-200 rounded w-3/4";
const DEFAULT = { limit: 11, offset: 0, include_institutional: true };

describe("BillsClient first-page SSR seed", () => {
  let container: HTMLDivElement;
  let root: Root | null;

  beforeEach(() => {
    context.params = new URLSearchParams();
    context.locale = "en";
    context.getBills.mockReset();
    context.periferias.mockReset().mockResolvedValue([]);
    context.dimoi.mockReset().mockResolvedValue([]);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = null;
  });
  afterEach(async () => {
    if (root) await act(async () => root!.unmount());
    container.remove();
  });

  async function serverThenHydrate(initial: InitialBills | null, strict = false) {
    const tree = strict ? <StrictMode><BillsClient initial={initial} /></StrictMode> : <BillsClient initial={initial} />;
    const html = renderToString(tree);
    container.innerHTML = html;
    const errors: unknown[] = [];
    await act(async () => {
      root = hydrateRoot(container, tree, { onRecoverableError: (error) => errors.push(error) });
    });
    return { html, errors };
  }

  function titles() {
    return [...container.querySelectorAll("h2")].map((node) => node.textContent);
  }

  // Last match: the status tab "All" follows the governance "All".
  async function click(text: string) {
    const button = [...container.querySelectorAll("button")].findLast((node) => node.textContent === text);
    expect(button).toBeDefined();
    await act(async () => button!.click());
  }

  it("puts seeded cards into the server HTML and hydrates without a mount fetch", async () => {
    const { html, errors } = await serverThenHydrate({ status: "", bills: [bill("A"), bill("B")] }, true);
    expect(html).toContain("Title A");
    expect(html).toContain("Last updated:");
    expect(html).toContain("Parliament data may be outdated");
    expect(html).not.toContain(SKELETON);
    expect(errors).toEqual([]);
    expect(titles()).toEqual(["Title A", "Title B"]);
    expect(context.getBills).not.toHaveBeenCalled();
  });

  it("renders Greek titles and labels for el", async () => {
    context.locale = "el";
    const { html } = await serverThenHydrate({ status: "", bills: [bill("A")] });
    expect(html).toContain("Τίτλος A");
    expect(html).toContain("Νομοσχέδια");
    expect(context.getBills).not.toHaveBeenCalled();
  });

  it.each(["el", "en"])("hydrates attribution only on Parliament cards in %s, with independent external links", async locale => {
    context.locale = locale;
    const rows = ["PARLIAMENT", "DIAVGEIA", "UNKNOWN"].map(source => ({
      ...bill(source), source, parliament_url: source === "PARLIAMENT" ? "https://www.hellenicparliament.gr/bill" : null, title_el: `Αυθεντικός_τίτλος * ${source}`,
      summary_short_el: "Η δική μας σύνοψη", summary_short_en: "Our summary",
      source_last_success: "2026-07-16T21:30:00Z", created_at: "2026-01-01T00:00:00Z",
      official_source_url: source === "PARLIAMENT" ? "https://www.hellenicparliament.gr/bill/123" : "https://diavgeia.gov.gr/decision/123",
    }));
    const { errors } = await serverThenHydrate({ status: "", bills: rows });
    expect(errors).toEqual([]);
    const cards = [...container.querySelectorAll("article")];
    expect(cards).toHaveLength(3);
    // A stretched anchor covers summary, badges and background for every source.
    for (const card of cards) {
      const cardLink = card.querySelector("h2 a")!;
      expect(cardLink.classList.contains("after:inset-0")).toBe(true);
      expect(cardLink.classList.contains("after:absolute")).toBe(true);
      expect(card.classList.contains("relative")).toBe(true);
      expect(cardLink.querySelector("a, button")).toBeNull();
      expect(card.querySelector("[data-relevance]")?.parentElement?.classList.contains("z-10")).toBe(true);
    }
    expect(cards[0].querySelector("h2")?.textContent).toBe(locale === "el" ? rows[0].title_el : rows[0].title_en);
    expect(cards[0].textContent).toContain(locale === "el"
      ? "Αναδημοσίευση από τη διαδικτυακή πύλη της Βουλής των Ελλήνων"
      : "Republished from the website of the Hellenic Parliament");
    expect(cards[0].textContent).toContain((locale === "el" ? "Ημερομηνία: " : "Date: ") + "17/07/2026");
    expect(cards[0].textContent).toContain(locale === "el" ? "Σύνοψη — ekklesia" : "Summary — ekklesia");
    const link = cards[0].querySelector<HTMLAnchorElement>('a[rel="noopener external"]')!;
    expect(link.textContent).toBe(locale === "el" ? "Πρωτότυπο" : "Original");
    expect(link.href).toBe(rows[0].official_source_url);
    expect(link.target).toBe("_blank");
    expect(link.classList.contains("z-10")).toBe(true);
    expect(link.parentElement?.closest("a")).toBeNull();
    expect(cards[1].textContent).toContain("ΔΙΑΥΓΕΙΑ");
    for (const card of cards.slice(1)) {
      expect(card.querySelector('a[rel="noopener external"]')).toBeNull();
      expect(card.textContent).not.toContain("Republished");
      expect(card.textContent).not.toContain("Αναδημοσίευση");
    }
  });

  it("uses a seed only for the matching URL status", async () => {
    context.params = new URLSearchParams({ status: "OPEN_END" });
    await serverThenHydrate({ status: "OPEN_END", bills: [bill("A", "OPEN_END")] });
    expect(context.getBills).not.toHaveBeenCalled();
    expect(titles()).toEqual(["Title A"]);
  });

  it("ignores a seed for a different query and fetches the current one", async () => {
    context.params = new URLSearchParams({ status: "ACTIVE" });
    context.getBills.mockResolvedValue({ data: [bill("FRESH")] });
    const { html } = await serverThenHydrate({ status: "", bills: [bill("STALE")] });
    expect(html).not.toContain("Title STALE");
    expect(html).toContain(SKELETON);
    expect(context.getBills).toHaveBeenCalledWith({ ...DEFAULT, status: "ACTIVE" });
    expect(titles()).toEqual(["Title FRESH"]);
  });

  it("falls back to the client fetch when the server prefetch failed", async () => {
    context.getBills.mockResolvedValue({ data: [bill("CLIENT")] });
    const { html, errors } = await serverThenHydrate(null);
    expect(html).toContain(SKELETON);
    expect(html).not.toContain("No bills found");
    expect(errors).toEqual([]);
    expect(context.getBills).toHaveBeenCalledTimes(1);
    expect(context.getBills).toHaveBeenCalledWith(DEFAULT);
    expect(titles()).toEqual(["Title CLIENT"]);
  });

  it("shows the API error when both server and client fetch fail", async () => {
    context.getBills.mockRejectedValue(new Error("down"));
    await serverThenHydrate(null);
    expect(container.textContent).toContain("API connection error");
    expect(container.textContent).not.toContain("No bills found");
  });

  it("shows a seeded empty success as empty without fetching", async () => {
    const { html } = await serverThenHydrate({ status: "", bills: [] });
    expect(html).toContain("No bills found");
    expect(context.getBills).not.toHaveBeenCalled();
  });

  it("keeps status changes race-safe and refetches when returning to the seeded query", async () => {
    const active = deferred<{ data: Bill[] }>();
    const archive = deferred<{ data: Bill[] }>();
    const back = deferred<{ data: Bill[] }>();
    context.getBills.mockReturnValueOnce(active.promise).mockReturnValueOnce(archive.promise).mockReturnValueOnce(back.promise);
    await serverThenHydrate({ status: "", bills: [bill("SEED")] });

    await click("Open");
    expect(context.getBills).toHaveBeenLastCalledWith({ ...DEFAULT, status: "ACTIVE" });
    expect(container.querySelector("div.animate-pulse")).not.toBeNull();
    await click("Archive");
    expect(context.getBills).toHaveBeenLastCalledWith({ ...DEFAULT, status: "OPEN_END" });

    await act(async () => archive.resolve({ data: [bill("ARCHIVE", "OPEN_END")] }));
    await act(async () => active.resolve({ data: [bill("LATE_ACTIVE")] }));
    expect(titles()).toEqual(["Title ARCHIVE"]);

    await click("All");
    expect(context.getBills).toHaveBeenCalledTimes(3);
    expect(context.getBills).toHaveBeenLastCalledWith(DEFAULT);
    expect(container.querySelector("div.animate-pulse")).not.toBeNull();
    await act(async () => back.resolve({ data: [bill("REFRESHED")] }));
    expect(titles()).toEqual(["Title REFRESHED"]);
  });

  it("fetches the next page from a full seeded first page", async () => {
    const seed = Array.from({ length: 11 }, (_, index) => bill(`S${index}`));
    context.getBills.mockResolvedValue({ data: [bill("P2")] });
    await serverThenHydrate({ status: "", bills: seed });
    expect(titles()).toHaveLength(10);
    await click("▶");
    expect(context.getBills).toHaveBeenCalledWith({ ...DEFAULT, offset: 10 });
    expect(titles()).toEqual(["Title P2"]);
  });

  it("fetches for a search and governance change after a seed", async () => {
    context.getBills.mockResolvedValue({ data: [bill("NATIONAL")] });
    await serverThenHydrate({ status: "", bills: [bill("SEED")] });
    await click("Nationwide / Parliament");
    expect(context.getBills).toHaveBeenCalledWith({ ...DEFAULT, governance: "NATIONAL" });
    expect(titles()).toEqual(["Title NATIONAL"]);
  });
});
