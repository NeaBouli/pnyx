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
function runtime(flavor = "direct", lastResponse: unknown = null, data = new Map<string, string>()) {
  let startup = Promise.resolve();
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
    // Observe the complete response consumer, including its durable write and
    // badge queue; receiving the response alone does not finish startup.
    getLastNotificationResponseAsync: vi.fn(() => ({
      then: (consume: (response: unknown) => Promise<void>) => {
        startup = Promise.resolve().then(() => consume(lastResponse));
        return startup;
      },
    })),
    addNotificationReceivedListener: vi.fn(),
    scheduleNotificationAsync: vi.fn(async (_request: unknown) => "local-id"),
  };
  const task = { isTaskDefined: () => false, defineTask: vi.fn() };
  const pushRegistration = {
    registerPushTokenIfNeeded: vi.fn(async () => "no-identity"),
  };
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
    if (id === "./push-registration") return pushRegistration;
    throw new Error(`Unexpected module ${id}`);
  });
  const source = readFileSync(new URL("./notifications.ts", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
  const exports: Record<string, any> = {};
  vm.runInNewContext(compiled, { exports, require: requireMock, process: { env: {} }, console: { ...console, warn } });
  return { exports, native, task, requireMock, data, storage, warn, pushRegistration, startup };
}

describe("notification runtime wiring", () => {
  it.each(["play", "direct"])("%s restores positive unread state and deduplicates delivery after a runtime restart", async (flavor) => {
    const payload = { template_id: "new_bill", bill_id: "restart-positive", local_display: "1", title: "New vote" };
    const response = { notification: { request: { content: { data: payload } } } };
    const first = runtime(flavor);
    await first.startup;
    await first.task.defineTask.mock.calls[0][1]({ data: { data: payload }, error: null });
    expect(first.native.scheduleNotificationAsync).toHaveBeenCalledTimes(1);
    expect(first.data.has(ledger.UNREAD_EVENTS_STORAGE_KEY)).toBe(true);

    const restarted = runtime(flavor, response, first.data);
    await restarted.startup;
    const unread = restarted.exports.getUnreadEventsStore() as ledger.UnreadEventsStore;
    expect(unread).not.toBe(first.exports.getUnreadEventsStore());
    expect(restarted.storage).not.toBe(first.storage);
    expect((await unread.list()).map((event) => event.id)).toEqual(["vote_open:restart-positive"]);
    expect(restarted.native.setBadgeCountAsync).toHaveBeenLastCalledWith(1);
    const reconciles = restarted.native.setBadgeCountAsync.mock.calls.length;
    restarted.native.addNotificationResponseReceivedListener.mock.calls[0][0](response);
    await vi.waitFor(() => expect(restarted.native.setBadgeCountAsync).toHaveBeenCalledTimes(reconciles + 1));
    await restarted.task.defineTask.mock.calls[0][1]({ data: { data: payload }, error: null });
    expect(await unread.unreadCount()).toBe(1);
    expect(restarted.native.scheduleNotificationAsync).not.toHaveBeenCalled();
    expect(restarted.native.getBadgeCountAsync).not.toHaveBeenCalled();
    expect(restarted.native.setBadgeCountAsync.mock.calls.every(([count]) => count === 1)).toBe(true);
  });

  it.each(["play", "direct"])("%s clears the last read event once and preserves its tombstone through cold-start and tap replay", async (flavor) => {
    const payload = { template_id: "vote_open", bill_id: "restart-read", local_display: "1", title: "New vote" };
    const response = { notification: { request: { content: { data: payload } } } };
    const first = runtime(flavor);
    await first.startup;
    await first.task.defineTask.mock.calls[0][1]({ data: { data: payload }, error: null });
    first.native.setBadgeCountAsync.mockClear();
    await expect(first.exports.markNotificationEventRead("vote_open:restart-read")).resolves.toBe(true);
    expect(first.native.setBadgeCountAsync).toHaveBeenCalledExactlyOnceWith(0);

    const restarted = runtime(flavor, response, first.data);
    await restarted.startup;
    const unread = restarted.exports.getUnreadEventsStore() as ledger.UnreadEventsStore;
    expect(await unread.list()).toEqual([]);
    // Use the awaited foreground handler as a queue barrier after the void tap
    // listener, so a zero-count assertion cannot precede replay processing.
    restarted.native.addNotificationResponseReceivedListener.mock.calls[0][0](response);
    await restarted.native.setNotificationHandler.mock.calls[0][0].handleNotification(response.notification);
    await restarted.exports.reconcileNotificationBadge();
    expect(await unread.unreadCount()).toBe(0);
    expect(await unread.ingest(payload)).toBe("duplicate");
    expect(restarted.native.scheduleNotificationAsync).not.toHaveBeenCalled();
    expect(restarted.native.setBadgeCountAsync).not.toHaveBeenCalled();
    expect(restarted.native.getBadgeCountAsync).not.toHaveBeenCalled();
    expect(first.native.setBadgeCountAsync).toHaveBeenCalledExactlyOnceWith(0);
  });

  it.each(["false", "reject"])("a launcher returning %s preserves the durable in-app ledger and later acknowledgement", async (failure) => {
    const payload = { template_id: "vote_result", bill_id: "restart-launcher" };
    const first = runtime();
    await first.startup;
    if (failure === "false") first.native.setBadgeCountAsync.mockResolvedValue(false);
    else first.native.setBadgeCountAsync.mockRejectedValue(new Error("launcher unsupported"));
    await first.native.setNotificationHandler.mock.calls[0][0].handleNotification({ request: { content: { data: payload } } });
    expect(first.native.setBadgeCountAsync).toHaveBeenCalledExactlyOnceWith(1);
    expect(await first.exports.getUnreadEventsStore().unreadCount()).toBe(1);

    const restarted = runtime("direct", null, first.data);
    await restarted.startup;
    const unread = restarted.exports.getUnreadEventsStore() as ledger.UnreadEventsStore;
    expect((await unread.list()).map((event) => event.id)).toEqual(["vote_result:restart-launcher"]);
    expect(restarted.native.setBadgeCountAsync).toHaveBeenCalledExactlyOnceWith(1);
    await expect(restarted.exports.markNotificationEventRead("vote_result:restart-launcher")).resolves.toBe(true);
    expect(await unread.unreadCount()).toBe(0);
    expect(restarted.native.setBadgeCountAsync).toHaveBeenLastCalledWith(0);
    const acknowledged = runtime("direct", null, restarted.data);
    await acknowledged.startup;
    expect(await acknowledged.exports.getUnreadEventsStore().ingest(payload)).toBe("duplicate");
    expect(await acknowledged.exports.getUnreadEventsStore().unreadCount()).toBe(0);
    expect(acknowledged.native.setBadgeCountAsync).not.toHaveBeenCalled();
  });

  it("F-Droid preserves local unread state and read tombstones across runtime restarts without native or push wiring", async () => {
    const payload = { template_id: "new_bill", bill_id: "fdroid-restart" };
    const first = runtime("fdroid");
    await first.exports.getUnreadEventsStore().ingest(payload);
    const restarted = runtime("fdroid", null, first.data);
    const unread = restarted.exports.getUnreadEventsStore() as ledger.UnreadEventsStore;
    expect((await unread.list()).map((event) => event.id)).toEqual(["vote_open:fdroid-restart"]);
    expect(await unread.ingest(payload)).toBe("duplicate");
    await expect(restarted.exports.markNotificationEventRead("vote_open:fdroid-restart")).resolves.toBe(true);
    const acknowledged = runtime("fdroid", null, first.data);
    expect(await acknowledged.exports.getUnreadEventsStore().ingest(payload)).toBe("duplicate");
    expect(await acknowledged.exports.getUnreadEventsStore().unreadCount()).toBe(0);
    for (const instance of [first, restarted, acknowledged]) {
      await instance.exports.reconcileNotificationBadge();
      await instance.exports.registerForPushNotifications();
      expect(instance.requireMock).not.toHaveBeenCalledWith("expo-notifications");
      expect(instance.requireMock).not.toHaveBeenCalledWith("expo-task-manager");
      expect(instance.native.setBadgeCountAsync).not.toHaveBeenCalled();
      expect(instance.native.scheduleNotificationAsync).not.toHaveBeenCalled();
      expect(instance.task.defineTask).not.toHaveBeenCalled();
      expect(instance.pushRegistration.registerPushTokenIfNeeded).not.toHaveBeenCalled();
    }
  });

  it("category read preserves unrelated events and reconciles a positive badge", async () => {
    const { exports, native } = runtime();
    const unread = exports.getUnreadEventsStore() as ledger.UnreadEventsStore;
    await unread.ingest({ template_id: "vote_open", bill_id: "ack-open" });
    await unread.ingest({ template_id: "vote_result", bill_id: "ack-result" });
    await exports.reconcileNotificationBadge();
    native.setBadgeCountAsync.mockClear();

    await exports.markNotificationCategoryRead("push_vote_open");

    expect((await unread.list()).map((event) => event.id)).toEqual(["vote_result:ack-result"]);
    expect(await unread.unreadCount()).toBe(1);
    expect(native.setBadgeCountAsync).toHaveBeenCalledExactlyOnceWith(1);
    expect(native.getBadgeCountAsync).not.toHaveBeenCalled();
  });

  it("all read durably empties the ledger and explicitly clears the native badge", async () => {
    const { exports, native, storage } = runtime();
    const unread = exports.getUnreadEventsStore() as ledger.UnreadEventsStore;
    await unread.ingest({ template_id: "vote_open", bill_id: "ack-open" });
    await unread.ingest({ template_id: "vote_result", bill_id: "ack-result" });
    await exports.reconcileNotificationBadge();
    native.setBadgeCountAsync.mockClear();

    await exports.markAllNotificationsRead();

    expect(await unread.list()).toEqual([]);
    expect(await unread.unreadCount()).toBe(0);
    expect(native.setBadgeCountAsync).toHaveBeenCalledExactlyOnceWith(0);
    expect(native.getBadgeCountAsync).not.toHaveBeenCalled();
    const restarted = ledger.createUnreadEventsStore(unreadStorage.createUnreadStorage({
      getItem: storage.getItemAsync,
      setItem: storage.setItemAsync,
    }));
    expect(await restarted.unreadCount()).toBe(0);
    expect(await restarted.ingest({ template_id: "vote_open", bill_id: "ack-open" })).toBe("duplicate");
    expect(await restarted.ingest({ template_id: "vote_result", bill_id: "ack-result" })).toBe("duplicate");
  });

  it.each(["event", "category", "all"])("a failed %s acknowledgement keeps events and never clears the native badge", async (scope) => {
    const { exports, native, storage, data } = runtime();
    const unread = exports.getUnreadEventsStore() as ledger.UnreadEventsStore;
    await unread.ingest({ template_id: "vote_open", bill_id: "ack-open" });
    await unread.ingest({ template_id: "vote_result", bill_id: "ack-result" });
    await exports.reconcileNotificationBadge();
    const before = Array.from(data.entries());
    native.setBadgeCountAsync.mockClear();
    storage.setItemAsync.mockRejectedValueOnce(new Error("ack storage failure"));
    const acknowledge = scope === "event"
      ? () => exports.markNotificationEventRead("vote_open:ack-open")
      : scope === "category"
        ? () => exports.markNotificationCategoryRead("push_vote_open")
        : () => exports.markAllNotificationsRead();

    await expect(acknowledge()).rejects.toThrow("ack storage failure");

    expect((await unread.list()).map((event) => event.id)).toEqual(["vote_open:ack-open", "vote_result:ack-result"]);
    expect(await unread.unreadCount()).toBe(2);
    expect(Array.from(data.entries())).toEqual(before);
    expect(native.setBadgeCountAsync).not.toHaveBeenCalled();
    expect(native.getBadgeCountAsync).not.toHaveBeenCalled();
  });

  it("retries one transient persistence failure before setting the badge", async () => {
    const { exports, native, storage, warn, startup } = runtime();
    await startup;
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
    const { exports, native, task, storage, warn, startup } = runtime("direct", boundary === "cold-start" ? response : null);
    if (boundary !== "cold-start") {
      await startup;
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
    const { exports, requireMock, pushRegistration } = runtime("fdroid");
    await exports.reconcileNotificationBadge();
    await exports.registerForPushNotifications();
    await exports.refreshUnreadFromPublicBills();
    expect(requireMock).not.toHaveBeenCalledWith("expo-notifications");
    expect(requireMock).not.toHaveBeenCalledWith("expo-task-manager");
    expect(pushRegistration.registerPushTokenIfNeeded).not.toHaveBeenCalled();
  });

  describe("data-only pushes (strict per-category opt-in)", () => {
    const dataOnly = (template_id: string, extra: Record<string, unknown> = {}) => ({
      template_id, title: "Νέο", body: "Κείμενο", local_display: "1", ...extra,
    });

    it("shows one local notification for an enabled category in the background", async () => {
      const { native, task } = runtime();
      const background = task.defineTask.mock.calls[0][1];
      await background({ data: { data: dataOnly("vote_24h", { bill_id: "GR-1" }) }, error: null });
      expect(native.scheduleNotificationAsync).toHaveBeenCalledTimes(1);
      const request = native.scheduleNotificationAsync.mock.calls[0][0] as any;
      expect(request.trigger).toBeNull();
      expect(request.content.title).toBe("Νέο");
      expect(request.content.data.local_display).toBeUndefined();
      expect(native.setBadgeCountAsync).toHaveBeenLastCalledWith(1);
    });

    it("never shows the same event twice (replay, foreground listener, own local notification)", async () => {
      const { native, task } = runtime();
      const background = task.defineTask.mock.calls[0][1];
      const payload = dataOnly("weekly_digest", { date: "2026-10-05" });
      await background({ data: { data: payload }, error: null });
      await background({ data: { data: payload }, error: null });
      native.addNotificationReceivedListener.mock.calls[0][0]({ request: { content: { data: payload } } });
      const local = (native.scheduleNotificationAsync.mock.calls[0][0] as any).content;
      const foreground = native.setNotificationHandler.mock.calls[0][0].handleNotification;
      await foreground({ request: { content: local } });
      await vi.waitFor(() => expect(native.scheduleNotificationAsync).toHaveBeenCalledTimes(1));
    });

    it("shows nothing when the category is disabled", async () => {
      const { native, task, data, exports } = runtime();
      data.set("push_system_update", "false");
      const background = task.defineTask.mock.calls[0][1];
      await background({ data: { data: dataOnly("system_update", { version: "1.0.34" }) }, error: null });
      expect(native.scheduleNotificationAsync).not.toHaveBeenCalled();
      expect(await exports.getUnreadEventsStore().unreadCount()).toBe(0);
    });

    it("does not add a local notification for visible pushes the OS already shows", async () => {
      const { native, task } = runtime();
      const background = task.defineTask.mock.calls[0][1];
      await background({ data: { data: { template_id: "new_bill", bill_id: "GR-2", title: "t", body: "b" } }, error: null });
      expect(native.scheduleNotificationAsync).not.toHaveBeenCalled();
    });

    it("builds local content only for flagged payloads with text", () => {
      const { exports } = runtime();
      expect(exports.localNotificationContent({ template_id: "vote_24h", title: "t" })).toBeNull();
      expect(exports.localNotificationContent({ template_id: "vote_24h", local_display: "1" })).toBeNull();
      expect(exports.localNotificationContent({ template_id: "vote_24h", local_display: "1", body: "b" }))
        .toEqual({ title: "ekklesia", body: "b", data: { template_id: "vote_24h", body: "b" } });
    });
  });
});
