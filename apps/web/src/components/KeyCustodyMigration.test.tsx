// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const custody = vi.hoisted(() => ({ migrate: vi.fn(), rotate: vi.fn() }));
vi.mock("@/lib/keystore", () => ({ migrateLegacyWebKey: custody.migrate, rotateMigratedWebKey: custody.rotate }));
import KeyCustodyMigration from "./KeyCustodyMigration";
let root: Root;

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  root = createRoot(document.createElement("div"));
  custody.migrate.mockReset().mockResolvedValue("not_needed");
  custody.rotate.mockReset().mockResolvedValue("not_needed");
});
afterEach(async () => {
  await act(async () => root.unmount());
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it.each(["migrated", "not_needed"])("waits for successful custody migration (%s) before rotation", async (result) => {
  let finish!: (result: string) => void;
  custody.migrate.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  await act(async () => root.render(createElement(KeyCustodyMigration)));
  expect(custody.rotate).not.toHaveBeenCalled();
  await act(async () => finish(result));
  expect(custody.rotate).toHaveBeenCalledTimes(1);
});

it.each(["unsupported", "key_not_current", "retry_later", "no_legacy"])("does not rotate after custody outcome %s", async (result) => {
  custody.migrate.mockResolvedValue(result);
  await act(async () => root.render(createElement(KeyCustodyMigration)));
  expect(custody.rotate).not.toHaveBeenCalled();
});

it("retries an uncertain rotation on foreground after one minute, then stops after confirmation", async () => {
  const info = vi.spyOn(console, "info").mockImplementation(() => {});
  custody.rotate.mockResolvedValueOnce("retry_later").mockResolvedValue("already_rotated");
  await act(async () => root.render(createElement(KeyCustodyMigration)));
  await act(async () => window.dispatchEvent(new Event("online")));
  expect(custody.rotate).toHaveBeenCalledTimes(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); window.dispatchEvent(new Event("online")); });
  expect(custody.rotate).toHaveBeenCalledTimes(2);
  expect(info.mock.calls).toEqual([["[keystore] identity rotation", "already_rotated"]]);
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); document.dispatchEvent(new Event("visibilitychange")); });
  expect(custody.rotate).toHaveBeenCalledTimes(2);
});

it("retries a storage read failure without remounting, then recovers the pending swap", async () => {
  custody.migrate.mockResolvedValueOnce("retry_later").mockResolvedValue("not_needed");
  custody.rotate.mockResolvedValue("already_rotated");
  vi.spyOn(console, "info").mockImplementation(() => {});
  await act(async () => root.render(createElement(KeyCustodyMigration)));
  expect(custody.rotate).not.toHaveBeenCalled();
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
  expect(custody.migrate).toHaveBeenCalledTimes(2);
  expect(custody.rotate).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
});

it("backs off pending recovery retries and cancels the timer on unmount", async () => {
  custody.rotate.mockResolvedValue("retry_later");
  await act(async () => root.render(createElement(KeyCustodyMigration)));
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
  expect(custody.rotate).toHaveBeenCalledTimes(2);
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
  expect(custody.rotate).toHaveBeenCalledTimes(2);
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
  expect(custody.rotate).toHaveBeenCalledTimes(3);
  await act(async () => root.render(null));
  expect(vi.getTimerCount()).toBe(0);
});
