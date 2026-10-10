// @vitest-environment jsdom
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import QRCodeVoteStub from "./QRCodeVoteStub";
import LiveNotifications from "./LiveNotifications";
import NavHeader from "./NavHeader";

const locale = vi.hoisted(() => ({ value: "en" }));
vi.mock("next-intl", () => ({ useLocale: () => locale.value }));
vi.mock("next/navigation", () => ({ usePathname: () => `/${locale.value}/bills` }));
vi.mock("next/link", () => ({ default: ({ children, ...props }: React.ComponentProps<"a">) => <a {...props}>{children}</a> }));
vi.mock("next/image", () => ({ default: (props: React.ComponentProps<"img">) => <img {...props} /> }));

let root: Root;
let container: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({
    session_id: "SYNTHETIC", challenge: "SYNTHETIC", qr_data: "ekklesia://SYNTHETIC",
  }) })));
  container = document.createElement("div");
  root = createRoot(container);
});

describe("global Web landmarks and measured header text", () => {
  it.each(["el", "en"])("names the connected SSE region in %s without changing its stream or events", async (language) => {
    locale.value = language;
    const sources: FakeEventSource[] = [];
    class FakeEventSource {
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;
      close = vi.fn();
      constructor(public url: string) { sources.push(this); }
    }
    vi.stubGlobal("EventSource", FakeEventSource);
    await act(async () => { root.render(<LiveNotifications billId="SYNTHETIC" />); });
    expect(container.querySelector('[role="region"]')).toBeNull();
    expect(sources).toHaveLength(1);
    expect(sources[0].url).toMatch(/\/api\/v1\/notifications\/stream\?bill_id=SYNTHETIC$/);
    act(() => {
      sources[0].onopen?.();
      sources[0].onmessage?.({ data: JSON.stringify({ type: "new_bill", label_el: "Synthetic label", message_el: "Synthetic message", milestone: 10 }) });
    });
    const region = container.querySelector('[role="region"]');
    expect(region?.getAttribute("aria-label")).toBe(language === "el" ? "Ζωντανές ενημερώσεις" : "Live updates");
    expect(container.querySelector('[role="dialog"], [role="alert"]')).toBeNull();
    expect(region?.textContent).toContain("Live");
    expect(region?.textContent).toContain("Synthetic message");
    expect(region?.querySelector("p.text-gray-700")?.textContent).toBe("Synthetic label");
    expect(fetch).not.toHaveBeenCalled();
    act(() => { root.unmount(); });
    expect(sources[0].close).toHaveBeenCalledTimes(1);
    root = createRoot(container);
  });

  it.each(["el", "en"])("keeps navigation while darkening the measured brand caption in %s", (language) => {
    locale.value = language;
    container.innerHTML = renderToStaticMarkup(<NavHeader />);
    const caption = [...container.querySelectorAll("span")].find((node) => node.textContent === "του έθνους");
    expect(caption?.classList.contains("text-gray-600")).toBe(true);
    expect(container.querySelector("nav")?.getAttribute("aria-label")).toBe(language === "el" ? "Κύρια πλοήγηση" : "Main navigation");
    expect(container.querySelector(`a[href="/${language}/bills"]`)).not.toBeNull();
    expect(container.querySelector(`a[href="/${language === "el" ? "en" : "el"}/bills"]`)).not.toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });
});
afterEach(() => {
  act(() => root.unmount());
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("ready QR accessibility (real SVG, mocked session only)", () => {
  it.each(["el", "en"])("keeps a useful localized QR image and unchanged GET session flow in %s", async (language) => {
    locale.value = language;
    const authenticated = vi.fn();
    await act(async () => { root.render(<QRCodeVoteStub billId="SYNTHETIC" purpose="consensus" onAuthenticated={authenticated} />); });
    const svg = container.querySelector('svg[height="200"]');
    const name = language === "el" ? "Σκανάρετε με την εφαρμογή ekklesia" : "Scan with the ekklesia app";
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("role")).toBe("img");
    expect(svg?.getAttribute("aria-label")).toBe(name);
    expect(svg?.querySelector("title")?.textContent).toBe(name);
    expect(svg?.getAttribute("aria-hidden")).not.toBe("true");
    expect(container.querySelector('a[href="https://ekklesia.gr/#download"]')).not.toBeNull();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith("https://api.ekklesia.gr/api/v1/polis/qr-session?purpose=consensus&bill_id=SYNTHETIC");
    expect(authenticated).not.toHaveBeenCalled();
  });
});
