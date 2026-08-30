// @vitest-environment jsdom
import React, { act, StrictMode } from "react";
import { createRoot, hydrateRoot, type Root } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SSOVerifyPage from "./page";

const context = vi.hoisted(() => ({
  params: new URLSearchParams(), locale: "en", sign: vi.fn(() => "synthetic-signature"),
}));
vi.mock("next/navigation", () => ({ useSearchParams: () => context.params }));
vi.mock("next-intl", () => ({ useLocale: () => context.locale }));
vi.mock("@/lib/crypto", () => ({ signPayload: context.sign }));
vi.mock("next/image", () => ({ default: ({ alt }: { alt: string }) => <span>{alt}</span> }));
vi.mock("qrcode.react", () => ({ QRCodeSVG: ({ value }: { value: string }) => <span data-qr={value} /> }));

function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("forum SSO lifecycle", () => {
  let container: HTMLDivElement;
  let root: Root;
  let fetchMock: ReturnType<typeof vi.fn>;

  function params(nonce = "nonce-A", target = "https://pnyx.ekklesia.gr/session/sso_login") {
    context.params = new URLSearchParams({ nonce, return_url: target });
  }

  async function render(strict = false) {
    await act(async () => root.render(strict ? <StrictMode><SSOVerifyPage /></StrictMode> : <SSOVerifyPage />));
  }

  async function tick(ms: number) {
    await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
  }

  async function click(text: string) {
    const button = [...container.querySelectorAll("button")].find((item) => item.textContent === text);
    expect(button).toBeDefined();
    await act(async () => button!.click());
  }

  function keys() {
    localStorage.setItem("ekklesia_public_key", "synthetic-public");
    localStorage.setItem("ekklesia_private_key", "synthetic-private");
  }

  function stalledRequest(_url: string, options?: RequestInit): Promise<Response> {
    return new Promise((_resolve, reject) => {
      options?.signal?.addEventListener("abort", () => reject(options.signal!.reason), { once: true });
    });
  }

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    fetchMock = vi.fn(() => Promise.reject(new Error("Unexpected test request")));
    vi.stubGlobal("fetch", fetchMock);
    localStorage.clear();
    history.replaceState({}, "", "/");
    params();
    context.locale = "en";
    context.sign.mockClear();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("rejects missing parameters including retry without sending requests", async () => {
    context.params = new URLSearchParams();
    keys();
    await render();
    expect(container.textContent).toContain("Invalid link");
    await click("Try again");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(context.sign).not.toHaveBeenCalled();
  });

  it("hydrates the checking state without reading browser keys on the server", async () => {
    keys();
    const storage = vi.spyOn(Storage.prototype, "getItem");
    const html = renderToString(<SSOVerifyPage />);
    expect(html).toContain("Checking...");
    expect(storage).not.toHaveBeenCalled();
    await act(async () => root.unmount());
    container.innerHTML = html;
    fetchMock.mockResolvedValue(response({ redirect_url: "#authenticated" }));
    const recover = vi.fn();
    await act(async () => { root = hydrateRoot(container, <SSOVerifyPage />, { onRecoverableError: recover }); });
    expect(recover).not.toHaveBeenCalled();
    expect(container.textContent).toContain("Login successful");
  });

  it("signs the same challenge and sends no private key or return URL", async () => {
    keys();
    fetchMock.mockResolvedValue(response({ redirect_url: "#authenticated" }));
    await render();
    expect(context.sign).toHaveBeenCalledWith("synthetic-private", "discourse_sso:nonce-A:synthetic-public");
    const payload = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(payload).toEqual({ nonce: "nonce-A", public_key_hex: "synthetic-public", signature_hex: "synthetic-signature" });
    expect(JSON.stringify(fetchMock.mock.calls)).not.toContain("synthetic-private");
    await tick(800);
    expect(window.location.hash).toBe("#authenticated");
  });

  it.each([404, 410])("preserves signed callback error %s", async (status) => {
    keys();
    fetchMock.mockResolvedValue(response({}, status));
    await render();
    expect(container.textContent).toContain(status === 404 ? "Identity not found" : "Session expired");
  });

  it.each([false, true])("offers retry after a stalled initial request (browser keys: %s)", async (signed) => {
    if (signed) keys();
    fetchMock.mockImplementationOnce(stalledRequest).mockResolvedValue(response(signed
      ? { redirect_url: "#authenticated" }
      : { session_id: "session-B", qr_data: "ekklesia://forum?session=B" }));
    await render(true);
    await tick(15000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("Try again");
    await click("Try again");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(container.textContent).not.toContain("Request timed out");
    if (signed) expect(container.textContent).toContain("Login successful");
    else expect(container.querySelector("[data-qr]")).not.toBeNull();
  });

  it("offers retry when QR completion stalls after authentication", async () => {
    fetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes("purpose=")) return Promise.resolve(response({ session_id: "session-A", qr_data: "ekklesia://forum" }));
      if (url.includes("qr-complete")) return stalledRequest(url, options);
      return Promise.resolve(response({ status: "authenticated" }));
    });
    await render();
    await tick(17500);
    expect(container.textContent).toContain("Try again");
    expect(fetchMock.mock.calls.filter((call) => call[0].includes("qr-complete"))).toHaveLength(1);
    await click("Try again");
    expect(container.querySelector("[data-qr]")).not.toBeNull();
    expect(window.location.hash).toBe("");
  });

  it("creates the existing forum QR purpose and supports failed-creation retry", async () => {
    fetchMock.mockResolvedValueOnce(response({}, 503)).mockResolvedValue(response({ session_id: "session-B", qr_data: "ekklesia://forum?session=B" }));
    await render();
    expect(container.textContent).toContain("HTTP 503");
    await click("Try again");
    expect(fetchMock.mock.calls[0][0]).toContain("/qr-session?purpose=forum_login");
    expect(container.querySelector("[data-qr]")?.getAttribute("data-qr")).toContain("session=B");
  });

  it("expires the QR after five minutes and creates a new session", async () => {
    fetchMock.mockImplementation((url: string) => Promise.resolve(response(url.includes("purpose=")
      ? { session_id: "session-A", qr_data: "ekklesia://forum?session=A" } : { status: "pending" })));
    await render();
    await tick(300000);
    expect(container.textContent).toContain("New QR code");
    await click("New QR code");
    expect(container.querySelector("[data-qr]")).not.toBeNull();
  });

  it("ignores old QR creation responses after the nonce changes", async () => {
    const old = deferred<Response>();
    fetchMock.mockReturnValueOnce(old.promise).mockResolvedValue(response({ session_id: "session-B", qr_data: "ekklesia://forum?session=B" }));
    await render();
    params("nonce-B");
    await render();
    await act(async () => old.resolve(response({ session_id: "session-A", qr_data: "ekklesia://forum?session=A" })));
    expect(container.querySelector("[data-qr]")?.getAttribute("data-qr")).toContain("session=B");
  });

  it("does not complete old polls under a new nonce", async () => {
    const pending = deferred<Response>();
    fetchMock.mockImplementation((url: string) => {
      if (url.includes("purpose=")) return Promise.resolve(response({ session_id: context.params.get("nonce"), qr_data: "ekklesia://forum" }));
      return pending.promise.then((res) => res.clone());
    });
    await render();
    await tick(2500);
    params("nonce-B");
    await render();
    await act(async () => pending.resolve(response({ status: "authenticated" })));
    expect(fetchMock.mock.calls.filter((call) => call[0].includes("qr-complete"))).toHaveLength(0);
  });

  it("completes concurrent authenticated polls once", async () => {
    const pending = deferred<Response>();
    fetchMock.mockImplementation((url: string) => {
      if (url.includes("purpose=")) return Promise.resolve(response({ session_id: "session-A", qr_data: "ekklesia://forum" }));
      if (url.includes("qr-complete")) return Promise.resolve(response({ redirect_url: "#authenticated" }));
      return pending.promise.then((res) => res.clone());
    });
    await render();
    await tick(5000);
    await act(async () => pending.resolve(response({ status: "authenticated" })));
    const complete = fetchMock.mock.calls.filter((call) => call[0].includes("qr-complete"));
    expect(complete).toHaveLength(1);
    expect(JSON.parse(complete[0][1].body)).toEqual({ nonce: "nonce-A", session_id: "session-A" });
  });

  it("rejects a poll response that arrives after local expiry", async () => {
    const pending = deferred<Response>();
    fetchMock.mockImplementation((url: string) => url.includes("purpose=")
      ? Promise.resolve(response({ session_id: "session-A", qr_data: "ekklesia://forum" })) : pending.promise.then((res) => res.clone()));
    await render();
    await tick(300000);
    await act(async () => pending.resolve(response({ status: "authenticated" })));
    expect(container.textContent).toContain("New QR code");
    expect(fetchMock.mock.calls.filter((call) => call[0].includes("qr-complete"))).toHaveLength(0);
  });

  it("cancels a queued redirect after the nonce changes", async () => {
    keys();
    fetchMock.mockResolvedValueOnce(response({ redirect_url: "#old-session" })).mockResolvedValue(response({}, 410));
    await render();
    params("nonce-B");
    await render();
    await tick(800);
    expect(window.location.hash).toBe("");
    expect(container.textContent).toContain("Session expired");
  });

  it("sends only one signed callback during StrictMode effect replay", async () => {
    keys();
    fetchMock.mockImplementation(() => Promise.resolve(response({ redirect_url: "#authenticated" })));
    await render(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(context.sign).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("Login successful");
  });

  it("creates only one QR session during StrictMode effect replay", async () => {
    fetchMock.mockImplementation((url: string) => Promise.resolve(response(url.includes("purpose=")
      ? { session_id: "session-A", qr_data: "ekklesia://forum" } : { status: "pending" })));
    await render(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(container.querySelector("[data-qr]")).not.toBeNull();
    await tick(2500);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("starts the QR flow when browser keys disappear before retry", async () => {
    keys();
    fetchMock.mockResolvedValueOnce(response({}, 404)).mockResolvedValueOnce(response({ session_id: "session-A", qr_data: "ekklesia://forum" }));
    await render();
    localStorage.clear();
    await click("Try again");
    expect(container.querySelector("[data-qr]")).not.toBeNull();
    expect(context.sign).toHaveBeenCalledTimes(1);
  });

  it("invalidates old work when only return_url changes", async () => {
    keys();
    const old = deferred<Response>();
    fetchMock.mockReturnValueOnce(old.promise).mockResolvedValueOnce(response({}, 410));
    await render();
    params("nonce-A", "https://pnyx.ekklesia.gr/changed");
    await render();
    await act(async () => old.resolve(response({ redirect_url: "#old-session" })));
    await tick(800);
    expect(window.location.hash).toBe("");
    expect(container.textContent).toContain("Session expired");
  });

  it("does not restart requests or extend QR lifetime on locale changes", async () => {
    fetchMock.mockImplementation((url: string) => Promise.resolve(response(url.includes("purpose=")
      ? { session_id: "session-A", qr_data: "ekklesia://forum" } : { status: "pending" })));
    await render();
    await tick(200000);
    context.locale = "el";
    await render();
    await tick(100000);
    expect(container.textContent).toContain("Νέος κωδικός QR");
    expect(fetchMock.mock.calls.filter((call) => call[0].includes("purpose="))).toHaveLength(1);
  });

  it("ignores late completion after unmount", async () => {
    const complete = deferred<Response>();
    fetchMock.mockImplementation((url: string) => {
      if (url.includes("purpose=")) return Promise.resolve(response({ session_id: "session-A", qr_data: "ekklesia://forum" }));
      if (url.includes("qr-complete")) return complete.promise;
      return Promise.resolve(response({ status: "authenticated" }));
    });
    await render();
    await tick(2500);
    await act(async () => root.render(null));
    await act(async () => complete.resolve(response({ redirect_url: "#stale" })));
    await tick(800);
    expect(window.location.hash).toBe("");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("preserves QR completion failure and creates a fresh session on retry", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.includes("purpose=")) return Promise.resolve(response({ session_id: "session-A", qr_data: "ekklesia://forum" }));
      if (url.includes("qr-complete")) return Promise.resolve(response({ detail: "expired nonce" }, 410));
      return Promise.resolve(response({ status: "authenticated" }));
    });
    await render();
    await tick(2500);
    expect(container.textContent).toContain("expired nonce");
    await click("Try again");
    expect(fetchMock.mock.calls.filter((call) => call[0].includes("purpose="))).toHaveLength(2);
    expect(container.querySelector("[data-qr]")).not.toBeNull();
  });

  it.each([null, {}, { session_id: {}, qr_data: "ekklesia://forum" }])("handles malformed QR creation payload %j", async (data) => {
    fetchMock.mockResolvedValue(response(data));
    await render();
    expect(container.textContent).toContain("Invalid QR session");
    expect(container.querySelector("[data-qr]")).toBeNull();
  });

  it("handles signed success without a redirect without consuming the body twice", async () => {
    keys();
    fetchMock.mockResolvedValue(response({}));
    await render();
    expect(container.textContent).toContain("Error 200");
    expect(container.textContent).not.toContain("Body");
    expect(container.textContent).not.toContain("Login successful");
  });

  it("allows mobile QR login when browser storage is unavailable", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new DOMException("Storage unavailable"); });
    fetchMock.mockResolvedValue(response({ session_id: "session-A", qr_data: "ekklesia://forum" }));
    await render();
    expect(container.querySelector("[data-qr]")).not.toBeNull();
    expect(context.sign).not.toHaveBeenCalled();
  });

  it("recovers from a failed poll and respects a server-reported expiry", async () => {
    fetchMock.mockResolvedValueOnce(response({ session_id: "session-A", qr_data: "ekklesia://forum" }))
      .mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(response({ status: "expired" }));
    await render();
    await tick(2500);
    expect(container.querySelector("[data-qr]")).not.toBeNull();
    await tick(2500);
    expect(container.textContent).toContain("New QR code");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("ignores the expired attempt's late poll after retry creates a new QR", async () => {
    const oldPoll = deferred<Response>();
    let creation = 0;
    fetchMock.mockImplementation((url: string) => {
      if (url.includes("purpose=")) {
        creation += 1;
        return Promise.resolve(response({ session_id: `session-${creation}`, qr_data: `ekklesia://forum?session=${creation}` }));
      }
      return oldPoll.promise.then((res) => res.clone());
    });
    await render();
    await tick(300000);
    await click("New QR code");
    await act(async () => oldPoll.resolve(response({ status: "authenticated" })));
    expect(container.querySelector("[data-qr]")?.getAttribute("data-qr")).toContain("session=2");
    expect(fetchMock.mock.calls.filter((call) => call[0].includes("qr-complete"))).toHaveLength(0);
  });
});
