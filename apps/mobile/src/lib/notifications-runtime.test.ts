import { readFileSync } from "node:fs";
import vm from "node:vm";
import { URL } from "node:url";
import ts from "typescript";
import { describe, expect, it, vi } from "vitest";
import * as preferences from "./notification-preferences";
import * as badge from "./notification-badge";
import * as ledger from "./unread-events";
import * as unreadStorage from "./unread-storage";

// Execute the actual CommonJS require branches, which vi.mock cannot intercept.
function runtime(flavor = "direct", lastResponse: unknown = null) {
  const data = new Map<string, string>();
  const storage = {
    getItemAsync: vi.fn(async (key: string) => data.get(key) ?? null),
    setItemAsync: vi.fn(async (key: string, value: string) => { data.set(key, value); }),
  };
  const warn = vi.fn();
  const native = {
    registerTaskAsync: vi.fn(async () => null),
    getBadgeCountAsync: vi.fn(async () => 99),
    setBadgeCountAsync: vi.fn(async (_count: number) => true),
    setNotificationHandler: vi.fn(),
    addNotificationResponseReceivedListener: vi.fn(),
    getLastNotificationResponseAsync: vi.fn(async () => lastResponse),
  };
  const task = { isTaskDefined: () => false, defineTask: vi.fn() };
  const requireMock = vi.fn((id: string): unknown => {
    if (id === "expo-notifications") {
      if (flavor === "fdroid") throw new Error("Forbidden native module");
      return native;
    }
    if (id === "expo-task-manager") return task;
    if (id === "expo-device") return { isDevice: false };
    if (id === "react-native") return { Platform: { OS: "android" } };
    if (id === "expo-constants") return { expoConfig: { extra: { buildFlavor: flavor } } };
    if (id === "expo-secure-store") return storage;
    if (id === "./notification-preferences") return preferences;
    if (id === "./notification-badge") return badge;
    if (id === "./unread-events") return ledger;
    if (id === "./unread-storage") return unreadStorage;
    if (id === "./api") return { fetchBills: async () => [] };
    throw new Error(`Unexpected module ${id}`);
  });
  const source = readFileSync(new URL("./notifications.ts", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
  const exports: Record<string, any> = {};
  vm.runInNewContext(compiled, { exports, require: requireMock, process: { env: {} }, console: { ...console, warn } });
  return { exports, native, task, requireMock, data, storage, warn };
}

describe("notification runtime wiring", () => {
  it("retries one transient persistence failure before setting the badge", async () => {
    const { exports, native, storage, warn } = runtime();
    await vi.waitFor(() => expect(native.setBadgeCountAsync).toHaveBeenCalled());
    native.setBadgeCountAsync.mockClear();
    storage.setItemAsync.mockRejectedValueOnce(new Error("private native details"));
    const foreground = native.setNotificationHandler.mock.calls[0][0].handleNotification;
    const presentation = await foreground({ request: { content: { data: { template_id: "new_bill", bill_id: "retry-1" } } } });
    expect(presentation.shouldShowBanner).toBe(true);
    expect(await exports.getUnreadEventsStore().unreadCount()).toBe(1);
    expect(native.setBadgeCountAsync).toHaveBeenLastCalledWith(1);
    expect(warn).not.toHaveBeenCalled();
  });

  it.each(["foreground", "background", "tap", "cold-start"])("bounds %s persistence failures and does not reconcile stale counts", async (boundary) => {
    const payload = { template_id: "new_bill", bill_id: "private-bill-id" };
    const notification = { request: { content: { data: payload } } };
    const response = { notification };
    const { exports, native, task, storage, warn } = runtime("direct", boundary === "cold-start" ? response : null);
    if (boundary !== "cold-start") {
      await vi.waitFor(() => expect(native.setBadgeCountAsync).toHaveBeenCalled());
    }
    native.setBadgeCountAsync.mockClear();
    storage.setItemAsync.mockRejectedValue(new Error("private native details"));
    if (boundary === "foreground") {
      const result = await native.setNotificationHandler.mock.calls[0][0].handleNotification(notification);
      expect(result.shouldShowBanner).toBe(true);
    } else if (boundary === "background") {
      await task.defineTask.mock.calls[0][1]({ data: { data: payload }, error: null });
    } else if (boundary === "tap") {
      native.addNotificationResponseReceivedListener.mock.calls[0][0](response);
    }
    await vi.waitFor(() => expect(warn).toHaveBeenCalledTimes(1));
    expect(storage.setItemAsync).toHaveBeenCalledTimes(2);
    expect(native.setBadgeCountAsync).not.toHaveBeenCalled();
    expect(await exports.getUnreadEventsStore().unreadCount()).toBe(0);
    expect(warn).toHaveBeenCalledWith("Notification unread storage unavailable; event not acknowledged.");
  });
  it("recovers a cold-start tap and deduplicates its later listener replay", async () => {
    const response = { notification: { request: { content: { data: { template_id: "result", bill_id: "b-cold" } } } } };
    const { exports, native } = runtime("direct", response);
    await vi.waitFor(async () => expect(await exports.getUnreadEventsStore().unreadCount()).toBe(1));
    await exports.markNotificationEventRead("vote_result:b-cold");
    native.addNotificationResponseReceivedListener.mock.calls[0][0](response);
    await vi.waitFor(() => expect(native.setBadgeCountAsync).toHaveBeenLastCalledWith(0));
    expect(await exports.getUnreadEventsStore().unreadCount()).toBe(0);
  });
  it("uses one absolute badge for foreground/background/tap replay", async () => {
    const { exports, native, task } = runtime();
    const payload = { template_id: "new_bill", bill_id: "DIAV-Ρ9Ζ546ΜΤΛΒ-Η" };
    const notification = { request: { content: { data: payload } } };
    const foreground = native.setNotificationHandler.mock.calls[0][0].handleNotification;
    const background = task.defineTask.mock.calls[0][1];
    const presentation = await foreground(notification);
    await background({ data: { data: payload }, error: null });
    native.addNotificationResponseReceivedListener.mock.calls[0][0]({ notification });
    await exports.reconcileNotificationBadge();
    expect(await exports.getUnreadEventsStore().unreadCount()).toBe(1);
    expect(native.setBadgeCountAsync).toHaveBeenLastCalledWith(1);
    expect(native.getBadgeCountAsync).not.toHaveBeenCalled();
    expect(presentation.shouldSetBadge).toBe(false);
    await exports.markNotificationEventRead(`vote_open:${payload.bill_id}`);
    await background({ data: { data: payload }, error: null });
    expect(native.setBadgeCountAsync).toHaveBeenLastCalledWith(0);
  });

  it("isolates native errors and does not record disabled categories", async () => {
    const { exports, native, data } = runtime();
    data.set("push_vote_open", "false");
    const foreground = native.setNotificationHandler.mock.calls[0][0].handleNotification;
    const presentation = await foreground({ request: { content: { data: { template_id: "vote_open", bill_id: "b1" } } } });
    expect(presentation.shouldShowBanner).toBe(false);
    expect(await exports.getUnreadEventsStore().unreadCount()).toBe(0);
    native.setBadgeCountAsync.mockRejectedValueOnce(new Error("launcher unsupported"));
    await expect(exports.reconcileNotificationBadge()).resolves.toBeUndefined();
  });

  it("never requires FCM/native notifications in F-Droid", async () => {
    const { exports, requireMock } = runtime("fdroid");
    await exports.reconcileNotificationBadge();
    await exports.registerForPushNotifications();
    await exports.refreshUnreadFromPublicBills();
    expect(requireMock).not.toHaveBeenCalledWith("expo-notifications");
    expect(requireMock).not.toHaveBeenCalledWith("expo-task-manager");
  });
});
