// @vitest-environment jsdom
import React, { act, Suspense } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import BillDetailPage from "./page";
import { RequestTimeoutError, requestTimeoutMessage } from "@/lib/request-deadline";

const context = vi.hoisted(() => ({ locale: "en", hasSigner: true, submit: vi.fn(), bill: {} as Record<string, unknown> }));
vi.mock("next-intl", () => ({ useLocale: () => context.locale }));
vi.mock("next/link", () => ({ default: ({ children }: { children: React.ReactNode }) => <span>{children}</span> }));
vi.mock("@/lib/api", () => ({
  ekklesia: {
    getBill: async () => ({ data: { id: "GR-9133", title_el: "Δοκιμή", status: "WINDOW_24H", ...context.bill } }),
    getResults: async () => ({ data: null }),
  },
  submitSignedVote: context.submit,
}));
vi.mock("@/lib/keystore", () => ({
  withSigner: async (submit: (signer: unknown) => Promise<unknown>) => submit(context.hasSigner ? { nullifier: "a".repeat(64), sign: vi.fn() } : null),
}));
vi.mock("@/components/StatusBadge", () => ({ default: () => null }));
vi.mock("@/components/RelevanceButtons", () => ({ default: () => null }));
vi.mock("@/components/BillResultReport", () => ({ default: () => null }));
vi.mock("@/components/QRCodeVoteStub", () => ({
  default: ({ onAuthenticated }: { onAuthenticated: (session: string) => void }) => (
    <button data-testid="qr-auth" onClick={() => onAuthenticated("t9133-qr-session")}>Authenticate QR</button>
  ),
}));

describe("bill correction feedback", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    context.hasSigner = true;
    context.locale = "en";
    context.bill = {};
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
    if (!context.hasSigner) {
      await act(async () => container.querySelector<HTMLButtonElement>('[data-testid="qr-auth"]')!.click());
    }
    const button = [...container.querySelectorAll("button")].find(
      item => item.textContent?.trim() === (language === "el" ? "Κατά" : "No"),
    );
    expect(button).toBeDefined();
    await act(async () => button!.click());
  }

  it.each(["el", "en"].flatMap(locale => ["PARLIAMENT", "DIAVGEIA", "UNKNOWN"].map(source => [locale, source]))) (
    "renders %s bill detail for %s with the correct source and separate editorial content", async (locale, source) => {
      context.locale = locale;
      context.bill = {
        source, title_el: "Αυθεντικός_τίτλος * Α", title_en: "Original_title * A",
        summary_short_el: "Η δική μας σύνοψη", summary_short_en: "Our summary", analysis_el: "Η δική μας ανάλυση",
        summary_long_el: source === "PARLIAMENT"
          ? "  Επίσημο_κείμενο * ακριβές — https://example.gr/\n\n".repeat(50)
            + "### Πλήρη έγγραφα\n- [PDF](https://www.hellenicparliament.gr/a.pdf)\n"
          : "Επίσημο_κείμενο * ακριβές — https://example.gr/",
        source_last_success: null, created_at: "2026-01-01T23:30:00",
        parliament_url: source === "PARLIAMENT" ? "https://www.hellenicparliament.gr/bill/fallback" : null,
        official_source_url: source === "DIAVGEIA" ? "https://diavgeia.gov.gr/decision/123" : null,
      };
      const params = Promise.resolve({ id: "GR-9133" });
      await act(async () => root.render(<Suspense><BillDetailPage params={params} /></Suspense>));
      expect(container.querySelector("h1")?.textContent).toBe(locale === "el" ? context.bill.title_el : context.bill.title_en);
      const link = container.querySelector<HTMLAnchorElement>('a[rel="noopener external"]');
      if (source === "PARLIAMENT") {
        expect(container.textContent).toContain(locale === "el"
          ? "Αναδημοσίευση από τη διαδικτυακή πύλη της Βουλής των Ελλήνων"
          : "Republished from the website of the Hellenic Parliament");
        expect(container.textContent).toContain((locale === "el" ? "Ημερομηνία: " : "Date: ") + "02/01/2026");
        expect(container.textContent).toContain(locale === "el" ? "Σύνοψη — ekklesia" : "Summary — ekklesia");
        expect(link?.href).toBe(context.bill.parliament_url);
        expect(link?.textContent).toBe(locale === "el" ? "Πρωτότυπο" : "Original");
        expect(link?.target).toBe("_blank");
      } else {
        expect(link).toBeNull();
        expect(container.textContent).not.toContain("Αναδημοσίευση");
        expect(container.textContent).not.toContain("Republished");
        if (source === "DIAVGEIA") expect(container.textContent).toContain(locale === "el" ? "Επίσημο κείμενο στη Διαύγεια" : "Official Diavgeia text");
      }
      const analysis = [...container.querySelectorAll("button")].find(node => node.textContent === (locale === "el" ? "Ανάλυση" : "Analysis"))!;
      await act(async () => analysis.click());
      expect(container.textContent).toContain(context.bill.summary_long_el);
      if (source === "PARLIAMENT") {
        expect(container.textContent).toContain(locale === "el" ? "Ανάλυση — ekklesia" : "Analysis — ekklesia");
      }
    });

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

  it.each(["el", "en"])("keeps voting retryable after a timeout in %s", async (language) => {
    context.submit.mockRejectedValue(new RequestTimeoutError());
    await clickVote(language);
    expect(container.textContent).toContain(requestTimeoutMessage(language === "el"));
    expect([...container.querySelectorAll("button")].some(button => button.disabled)).toBe(false);
  });

  it("shows a same-choice conflict without marking the correction as used or disabling a real change", async () => {
    const detail = "Η επιλογή είναι ίδια με την καταχωρημένη ψήφο. Η ψήφος δεν άλλαξε και η εφάπαξ διόρθωση παραμένει διαθέσιμη.";
    context.submit.mockResolvedValue({
      isCorrection: true,
      response: new Response(JSON.stringify({ detail }), { status: 409 }),
    });
    await clickVote("el");
    expect(container.textContent).toContain(detail);
    expect([...container.querySelectorAll("button")].some(button => button.disabled)).toBe(false);
    expect(container.textContent).not.toContain("Η διόρθωση έχει ήδη χρησιμοποιηθεί");
  });

  it.each(["el", "en"])("explains app correction recovery after a QR 409 in %s", async language => {
    context.hasSigner = false;
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: "Already voted. Correction available during 24h window.",
    }), { status: 409 }));
    vi.stubGlobal("fetch", fetchMock);
    await clickVote(language);
    expect(context.submit).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/v1/polis/qr-vote"), expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ session_id: "t9133-qr-session", bill_id: "GR-9133", vote: "NO" }),
    }));
    expect(container.textContent).toContain(language === "el"
      ? "Έχετε ήδη ψηφίσει για αυτό το νομοσχέδιο. Μπορείτε να αλλάξετε την ψήφο σας μία φορά μέσω της εφαρμογής στο 24ωρο παράθυρο διόρθωσης."
      : "You have already voted on this bill. You can change your vote once in the app during the 24-hour correction window.");
  });
});
