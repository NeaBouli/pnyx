// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import el from "@/messages/el.json";
import en from "@/messages/en.json";
import BrowserKeyNotice from "./BrowserKeyNotice";

const state = vi.hoisted(() => ({ read: vi.fn(), locale: "el", pathname: "/el/bills" }));
vi.mock("@/lib/keystore", () => ({ readLocalIdentityKeyState: state.read }));
vi.mock("next/navigation", () => ({ usePathname: () => state.pathname }));
vi.mock("next-intl", () => ({
  useTranslations: () => (key: keyof typeof en.identity) => (state.locale === "el" ? el : en).identity[key],
}));

let root: Root;
let container: HTMLDivElement;
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Notice must stay local"); }));
  state.read.mockReset().mockResolvedValue("absent");
  state.locale = "el";
  state.pathname = "/el/bills";
  container = document.createElement("div");
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  expect(fetch).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});

it.each([undefined, false])("stays empty and does not read keys with enabled=%s", async (enabled) => {
  await act(async () => root.render(createElement(BrowserKeyNotice, { enabled })));
  expect(container.innerHTML).toBe("");
  expect(state.read).not.toHaveBeenCalled();
});

it.each([
  ["el", "Το κλειδί σας δεν βρίσκεται σε αυτόν τον περιηγητή — συνδεθείτε με την εφαρμογή (QR)"],
  ["en", "Your key is not on this browser — sign in with the app (QR)"],
])("links the confirmed absence notice to existing QR login in %s", async (locale, copy) => {
  state.locale = locale;
  await act(async () => root.render(createElement(BrowserKeyNotice, { enabled: true })));
  expect(container.querySelector('[role="status"]')?.textContent).toBe(copy);
  expect(container.querySelector("a")?.getAttribute("href")).toBe("/embed/qr-login.html");
});

it.each(["present", "unavailable"])("does not announce absence for %s", async (result) => {
  state.read.mockResolvedValue(result);
  await act(async () => root.render(createElement(BrowserKeyNotice, { enabled: true })));
  expect(container.innerHTML).toBe("");
});

it("waits for a successful check and suppresses a rejected check", async () => {
  let reject!: (error: Error) => void;
  state.read.mockReturnValue(new Promise((_, fail) => { reject = fail; }));
  await act(async () => root.render(createElement(BrowserKeyNotice, { enabled: true })));
  expect(container.innerHTML).toBe("");
  await act(async () => reject(new Error("Storage blocked")));
  expect(container.innerHTML).toBe("");
});

it("rechecks on navigation and hides the notice after finding a key", async () => {
  await act(async () => root.render(createElement(BrowserKeyNotice, { enabled: true })));
  expect(container.querySelector("a")).not.toBeNull();
  state.read.mockResolvedValue("present");
  state.pathname = "/el/results";
  await act(async () => root.render(createElement(BrowserKeyNotice, { enabled: true })));
  expect(state.read).toHaveBeenCalledTimes(2);
  expect(container.innerHTML).toBe("");
});

it("retries on foreground and ignores an older absence result", async () => {
  let finish!: (state: string) => void;
  state.read.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; })).mockResolvedValue("present");
  await act(async () => root.render(createElement(BrowserKeyNotice, { enabled: true })));
  await act(async () => document.dispatchEvent(new Event("visibilitychange")));
  await act(async () => finish("absent"));
  expect(state.read).toHaveBeenCalledTimes(2);
  expect(container.innerHTML).toBe("");
});

it("removes listeners and ignores an outstanding read when disabled", async () => {
  let finish!: (state: string) => void;
  state.read.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  await act(async () => root.render(createElement(BrowserKeyNotice, { enabled: true })));
  await act(async () => root.render(createElement(BrowserKeyNotice, { enabled: false })));
  await act(async () => {
    finish("absent");
    window.dispatchEvent(new Event("storage"));
    document.dispatchEvent(new Event("visibilitychange"));
  });
  expect(state.read).toHaveBeenCalledTimes(1);
  expect(container.innerHTML).toBe("");
});
