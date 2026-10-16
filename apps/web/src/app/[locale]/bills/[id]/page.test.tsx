// @vitest-environment jsdom
import React, { act, Suspense } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import BillDetailPage from "./page";

const context = vi.hoisted(() => ({ locale: "en", submit: vi.fn() }));
vi.mock("next-intl", () => ({ useLocale: () => context.locale }));
vi.mock("next/link", () => ({ default: ({ children }: { children: React.ReactNode }) => <span>{children}</span> }));
vi.mock("@/lib/api", () => ({
  ekklesia: {
    getBill: async () => ({ data: { id: "GR-9133", title_el: "Δοκιμή", status: "WINDOW_24H" } }),
    getResults: async () => ({ data: null }),
  },
  submitSignedVote: context.submit,
}));
vi.mock("@/lib/keystore", () => ({ getSigner: async () => ({ nullifier: "a".repeat(64), sign: vi.fn() }) }));
vi.mock("@/components/StatusBadge", () => ({ default: () => null }));
vi.mock("@/components/RelevanceButtons", () => ({ default: () => null }));
vi.mock("@/components/BillResultReport", () => ({ default: () => null }));
vi.mock("@/components/QRCodeVoteStub", () => ({ default: () => null }));

describe("bill correction feedback", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    context.submit.mockReset();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  });

  async function clickVote(language: string) {
    context.locale = language;
    const params = Promise.resolve({ id: "GR-9133" });
    await act(async () => root.render(<Suspense><BillDetailPage params={params} /></Suspense>));
    const button = [...container.querySelectorAll("button")].find(
      item => item.textContent?.trim() === (language === "el" ? "Κατά" : "No"),
    );
    expect(button).toBeDefined();
    await act(async () => button!.click());
  }

  it.each(["el", "en"])("shows the used correction message in %s after /correct returns 409", async language => {
    context.submit.mockResolvedValue({
      isCorrection: true,
      response: new Response(JSON.stringify({
        detail: "Η διόρθωση έχει ήδη χρησιμοποιηθεί — επιτρέπεται μόνο μία διόρθωση ανά ψηφοφορία.",
      }), { status: 409 }),
    });
    await clickVote(language);
    expect(context.submit).toHaveBeenCalledWith("GR-9133", "NO", expect.objectContaining({ nullifier: "a".repeat(64) }));
    expect(container.textContent).toContain(language === "el"
      ? "Η διόρθωση έχει ήδη χρησιμοποιηθεί. Επιτρέπεται μόνο μία διόρθωση ανά ψηφοφορία."
      : "You have already corrected this vote. Only one correction is allowed per vote.");
    expect([...container.querySelectorAll("button")].filter(button => button.disabled)).toHaveLength(4);
  });

  it("keeps a different correction conflict visible without claiming the correction was used", async () => {
    context.submit.mockResolvedValue({
      isCorrection: true,
      response: new Response(JSON.stringify({ detail: "Semaphore ZK lock" }), { status: 409 }),
    });
    await clickVote("en");
    expect(container.textContent).toContain("Semaphore ZK lock");
    expect(container.textContent).not.toContain("You have already corrected");
  });
});
