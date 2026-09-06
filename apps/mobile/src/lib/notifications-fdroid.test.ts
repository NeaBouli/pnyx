/**
 * F-Droid flavor guarantees: the expo-notifications native module is never
 * touched, pushes are disabled, and the foreground bill-feed fallback works.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("react-native", () => ({ Platform: { OS: "android" } }));
vi.mock("expo-device", () => ({ isDevice: true, modelName: "test" }));
vi.mock("expo-constants", () => ({
  default: { expoConfig: { extra: { buildFlavor: "fdroid" } } },
}));

const mockSecureStoreData = new Map<string, string>();
vi.mock("expo-secure-store", () => ({
  getItemAsync: async (key: string) => mockSecureStoreData.get(key) ?? null,
  setItemAsync: async (key: string, value: string) => {
    mockSecureStoreData.set(key, value);
  },
  deleteItemAsync: async (key: string) => {
    mockSecureStoreData.delete(key);
  },
}));

const mockFetchBills = vi.fn();
vi.mock("../lib/api", () => ({
  fetchBills: (...args: unknown[]) => mockFetchBills(...args),
}));

// Tripwire: fail loudly if the F-Droid path ever touches the native module.
vi.mock("expo-notifications", () => {
  throw new Error("expo-notifications must not load in F-Droid builds");
});

async function loadNotifications() {
  return import("./notifications");
}

describe("F-Droid flavor", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetModules();
    mockSecureStoreData.clear();
    mockFetchBills.mockReset();
  });
  afterEach(() => vi.useRealTimers());

  it("never requires expo-notifications for registration or badges", async () => {
    const notifications = await loadNotifications();
    await expect(
      notifications.registerForPushNotifications(),
    ).resolves.toBeNull();
    await expect(
      notifications.reconcileNotificationBadge(),
    ).resolves.toBeUndefined();
    await expect(
      notifications.markNotificationEventRead("vote_open:x"),
    ).resolves.toBe(false);
    await expect(
      notifications.markAllNotificationsRead(),
    ).resolves.toBeUndefined();
  });

  it("ingests unread events from the public bill feed on foreground", async () => {
    const notifications = await loadNotifications();
    mockFetchBills.mockResolvedValue([{ id: "b1", status: "ACTIVE", title_el: "Παλιό" }]);

    // First foreground run only seeds the baseline — no flooding.
    await notifications.refreshUnreadFromPublicBills();
    expect(mockFetchBills).toHaveBeenCalledWith({ limit: 50 });
    expect(await notifications.getUnreadEventsStore().unreadCount()).toBe(0);

    await notifications.refreshUnreadFromPublicBills();
    expect(mockFetchBills).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(60_000);

    // A later run surfaces only transitions and genuinely new bills.
    mockFetchBills.mockResolvedValue([
      { id: "b1", status: "PARLIAMENT_VOTED", title_el: "Παλιό" },
      { id: "b2", status: "ACTIVE", title_el: "Νέο" },
    ]);
    await notifications.refreshUnreadFromPublicBills();
    const events = await notifications.getUnreadEventsStore().list();
    expect(events.map((e) => e.id)).toEqual(["vote_result:b1", "vote_open:b2"]);
  });

  it("shares an in-flight foreground refresh", async () => {
    const notifications = await loadNotifications();
    let finish!: (bills: unknown[]) => void;
    mockFetchBills.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const first = notifications.refreshUnreadFromPublicBills();
    const second = notifications.refreshUnreadFromPublicBills();
    expect(mockFetchBills).toHaveBeenCalledTimes(1);
    finish([]);
    await Promise.all([first, second]);
    expect(await notifications.getUnreadEventsStore().unreadCount()).toBe(0);
  });

  it("keeps unread state without any native module when the feed fails", async () => {
    const notifications = await loadNotifications();
    mockFetchBills.mockRejectedValue(new Error("offline"));
    await expect(
      notifications.refreshUnreadFromPublicBills(),
    ).resolves.toBeUndefined();

    const store = notifications.getUnreadEventsStore();
    expect(
      await store.ingest({ template_id: "new_bill", bill_id: "b9", title: "T", body: "B" }),
    ).toBe("added");
    expect(await store.unreadCount()).toBe(1);
  });
});
