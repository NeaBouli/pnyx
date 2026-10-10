// @vitest-environment jsdom
import React, { act, StrictMode } from "react";
import { hydrateRoot, type Root } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PublishedResult } from "@/lib/api";
import ResultsClient from "./ResultsClient";

const context = vi.hoisted(() => ({ locale: "en", getPublishedResults: vi.fn() }));
vi.mock("next-intl", () => ({ useLocale: () => context.locale }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a>,
}));
vi.mock("@/lib/api", () => ({ ekklesia: { getPublishedResults: context.getPublishedResults } }));

function result(id: string, total: number, divergence: number | ""): PublishedResult {
  return {
    bill_id: id, title_el: `Τίτλος ${id}`, title_en: `Title ${id}`, status: "PARLIAMENT_VOTED",
    parliament_vote_date: "2026-10-01", parliament_result: "YES", citizen_yes: total, citizen_no: 0,
    citizen_abstain: 0, citizen_unknown: 0, citizen_total: total, yes_pct: 100, no_pct: 0, abstain_pct: 0,
    divergence_score: divergence,
  };
}

const SEED = [result("LOW", 2, 0.1), result("HIGH", 5, 0.9), result("NONE", 9, "")];

describe("ResultsClient first-page SSR seed", () => {
  let container: HTMLDivElement;
  let root: Root | null;

  beforeEach(() => {
    context.locale = "en";
    context.getPublishedResults.mockReset();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = null;
  });
  afterEach(async () => {
    if (root) await act(async () => root!.unmount());
    container.remove();
  });

  async function serverThenHydrate(initial: PublishedResult[] | null) {
    const tree = <StrictMode><ResultsClient initial={initial} /></StrictMode>;
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

  it("renders seeded results in the server HTML and hydrates without a mount fetch", async () => {
    const { html, errors } = await serverThenHydrate(SEED);
    expect(html).toContain("Title HIGH");
    expect(html).not.toContain("Loading...");
    expect(errors).toEqual([]);
    expect(context.getPublishedResults).not.toHaveBeenCalled();
    expect(titles()).toEqual(["Title NONE", "Title HIGH", "Title LOW"]);
  });

  it("keeps local filter and sort controls working on seeded data", async () => {
    await serverThenHydrate(SEED);
    const high = [...container.querySelectorAll("button")].find((node) => node.textContent === "High divergence")!;
    await act(async () => high.click());
    expect(titles()).toEqual(["Title HIGH"]);
    const all = [...container.querySelectorAll("button")].find((node) => node.textContent === "All")!;
    await act(async () => all.click());
    const select = container.querySelector("select")!;
    await act(async () => {
      select.value = "divergence";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(titles()).toEqual(["Title HIGH", "Title LOW", "Title NONE"]);
    expect(container.querySelector('a[href="/en/bills/HIGH"]')).not.toBeNull();
    expect(context.getPublishedResults).not.toHaveBeenCalled();
  });

  it("renders Greek titles for el", async () => {
    context.locale = "el";
    const { html } = await serverThenHydrate(SEED);
    expect(html).toContain("Τίτλος HIGH");
    expect(html).toContain("Αποτελέσματα");
  });

  it("shows a seeded empty export as empty", async () => {
    const { html } = await serverThenHydrate([]);
    expect(html).toContain("No results yet.");
    expect(context.getPublishedResults).not.toHaveBeenCalled();
  });

  it("falls back to one client fetch of the same export after a server failure", async () => {
    context.getPublishedResults.mockResolvedValue({ data: { count: 1, data: [result("CLIENT", 1, "")] } });
    const { html, errors } = await serverThenHydrate(null);
    expect(html).toContain("Loading...");
    expect(html).not.toContain("No results yet.");
    expect(errors).toEqual([]);
    expect(context.getPublishedResults).toHaveBeenCalledWith(1);
    expect(titles()).toEqual(["Title CLIENT"]);
  });

  it("shows the error when the client fallback also fails", async () => {
    context.getPublishedResults.mockRejectedValue(new Error("down"));
    await serverThenHydrate(null);
    expect(container.textContent).toContain("Failed to load results.");
    expect(container.textContent).not.toContain("No results yet.");
  });

  it.each([
    ["el", "12.345", "Ψήφοι"],
    ["en", "12,345", "Votes"],
  ])("formats large %s vote totals with the route locale, not the runtime default", async (locale, total, label) => {
    // Server (Node) and browser disagree on the default locale; an implicit
    // toLocaleString() would render different text on each side.
    const original = Number.prototype.toLocaleString;
    const withDefault = (fallback: string) => function (this: number, locales?: Intl.LocalesArgument, options?: Intl.NumberFormatOptions) {
      return original.call(this, locales ?? fallback, options);
    };
    context.locale = locale;
    const big = [result("BIG", 12_000, 0.1), result("MORE", 345, "")];
    const tree = <StrictMode><ResultsClient initial={big} /></StrictMode>;
    const errors: unknown[] = [];
    try {
      Number.prototype.toLocaleString = withDefault("de-CH");
      container.innerHTML = renderToString(tree);
      Number.prototype.toLocaleString = withDefault("hi-IN");
      await act(async () => {
        root = hydrateRoot(container, tree, { onRecoverableError: (error) => errors.push(error) });
      });
    } finally {
      Number.prototype.toLocaleString = original;
    }
    expect(errors).toEqual([]);
    const stat = [...container.querySelectorAll("div")].find((node) => node.textContent === label)!;
    expect(stat.previousElementSibling!.textContent).toBe(total);
  });
});

