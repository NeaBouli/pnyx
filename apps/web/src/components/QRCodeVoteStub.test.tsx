import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import QRCodeVoteStub from "./QRCodeVoteStub";

const locale = vi.hoisted(() => ({ value: "en" }));
vi.mock("next-intl", () => ({ useLocale: () => locale.value }));

describe("QR initial render", () => {
  it.each(["en", "el"])("starts loading without an authentication claim in %s", (language) => {
    locale.value = language;
    const authenticated = vi.fn();
    const html = renderToStaticMarkup(<QRCodeVoteStub billId="SYNTHETIC" onAuthenticated={authenticated} />);
    expect(html).toContain(language === "el" ? "Φόρτωση κωδικού QR" : "Loading QR code");
    expect(html).not.toContain("Successfully authenticated");
    expect(authenticated).not.toHaveBeenCalled();
  });
});
