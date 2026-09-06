/**
 * notifications.ts — Push Token Registration (MOD-20)
 * Registers Expo Push Token with server after user verification.
 * Token is linked to nullifier_hash (anonymous — no PII).
 *
 * F-Droid: FCM disabled via BUILD_FLAVOR=fdroid environment variable.
 * Play Store: notifications fully enabled.
 */
import * as Device from "expo-device";
import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import Constants from "expo-constants";
import {
  isNotificationEnabled,
  type NotificationPreferenceKey,
} from "./notification-preferences";
import {
  createNotificationBadgeQueue,
  isNotificationResponsePayload,
  type BadgeAdapter,
} from "./notification-badge";
import {
  createUnreadEventsStore,
  canonicalTemplateId,
  extractPushData,
  type UnreadEventsStore,
} from "./unread-events";
import { fetchBills } from "./api";
import { createUnreadStorage } from "./unread-storage";

const API_BASE = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";
const TOKEN_KEY = "push_token";

// F-Droid build: no push notifications (FCM not allowed)
const IS_FDROID = Constants.expoConfig?.extra?.buildFlavor === "fdroid";

type NotificationsModule = BadgeAdapter & {
  registerTaskAsync: (taskName: string) => Promise<null>;
  setNotificationHandler: (handler: {
    handleNotification: (notification: unknown) => Promise<{
      shouldShowAlert: boolean;
      shouldShowBanner: boolean;
      shouldShowList: boolean;
      shouldPlaySound: boolean;
      shouldSetBadge: boolean;
    }>;
  }) => void;
  addNotificationResponseReceivedListener?: (
    listener: (response: unknown) => void,
  ) => { remove: () => void };
  getLastNotificationResponseAsync?: () => Promise<unknown>;
};

type TaskManagerModule = {
  defineTask: (
    taskName: string,
    handler: (event: { data: unknown; error: unknown }) => Promise<void>,
  ) => void;
  isTaskDefined: (taskName: string) => boolean;
};

const BACKGROUND_NOTIFICATION_TASK = "EKKLESIA-NOTIFICATION-BADGE";
const badgeQueue = createNotificationBadgeQueue();

// Persistent per-event unread ledger (GH290). Shared by pushes and the
// F-Droid foreground bill feed so both use the same canonical event IDs.
const unreadStore: UnreadEventsStore = createUnreadEventsStore(createUnreadStorage({
  getItem: (key) => SecureStore.getItemAsync(key),
  setItem: (key, value) => SecureStore.setItemAsync(key, value),
}));

export function getUnreadEventsStore(): UnreadEventsStore {
  return unreadStore;
}

async function ingestPushPayload(payload: unknown): Promise<void> {
  const data = extractPushData(payload);
  if (!data) return;
  await unreadStore.ingest(data);
}

async function persistPushAndReconcile(payload: unknown): Promise<void> {
  // Stable event IDs make a single retry safe, including an uncertain write result.
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      await ingestPushPayload(payload);
      await reconcileNotificationBadge();
      return;
    } catch {
      if (attempt === 1) {
        // Never log payloads, identifiers, or native storage error details.
        console.warn("Notification unread storage unavailable; event not acknowledged.");
      }
    }
  }
}

function getTemplateIdFromNotification(notification: unknown): unknown {
  if (!notification || typeof notification !== "object") return undefined;
  const request = (notification as { request?: unknown }).request;
  if (!request || typeof request !== "object") return undefined;
  const content = (request as { content?: unknown }).content;
  if (!content || typeof content !== "object") return undefined;
  const data = (content as { data?: unknown }).data;
  if (!data || typeof data !== "object") return undefined;
  return (data as { template_id?: unknown }).template_id;
}

function getTemplateId(payload: unknown, remainingDataStringDepth = 2): unknown {
  if (!payload || typeof payload !== "object") return undefined;
  const record = payload as Record<string, unknown>;
  if (typeof record.template_id === "string") return record.template_id;

  const notificationId = getTemplateIdFromNotification(record.notification);
  if (notificationId !== undefined) return notificationId;

  if (record.data && typeof record.data === "object") {
    const data = record.data as Record<string, unknown>;
    if (typeof data.template_id === "string") return data.template_id;
    if (
      remainingDataStringDepth > 0 &&
      typeof data.dataString === "string"
    ) {
      try {
        return getTemplateId(
          JSON.parse(data.dataString),
          remainingDataStringDepth - 1,
        );
      } catch {}
    }
  }

  return getTemplateIdFromNotification(payload);
}

if (!IS_FDROID) {
  // Only import and configure notifications for Play Store builds
  try {
    const Notifications = require("expo-notifications") as NotificationsModule;
    const TaskManager = require("expo-task-manager") as TaskManagerModule;

    if (!TaskManager.isTaskDefined(BACKGROUND_NOTIFICATION_TASK)) {
      TaskManager.defineTask(
        BACKGROUND_NOTIFICATION_TASK,
        async ({ data, error }) => {
          if (error || isNotificationResponsePayload(data)) return;
          await persistPushAndReconcile(data);
        },
      );
    }
    void Notifications.registerTaskAsync(BACKGROUND_NOTIFICATION_TASK).catch(
      () => {},
    );

    // Taps replay the same payload as delivery; the ledger deduplicates.
    Notifications.addNotificationResponseReceivedListener?.((response) => {
      void persistPushAndReconcile(response);
    });
    // A tap that launches a terminated app can precede listener registration.
    // Replaying it is safe because the same stable ID remains tombstoned after acknowledgement.
    void Notifications.getLastNotificationResponseAsync?.()
      .then(persistPushAndReconcile).catch(() => {
        console.warn("Notification cold-start response unavailable.");
      });

    Notifications.setNotificationHandler({
      handleNotification: async (notification: unknown) => {
        const templateId = getTemplateId(notification);
        const enabled = canonicalTemplateId(templateId) !== null && await isNotificationEnabled(
          SecureStore.getItemAsync,
          templateId,
        ).catch(() => false);
        if (!enabled) {
          return {
            shouldShowAlert: false,
            shouldShowBanner: false,
            shouldShowList: false,
            shouldPlaySound: false,
            shouldSetBadge: false,
          };
        }

        await persistPushAndReconcile(notification);
        return {
          shouldShowAlert: true,
          shouldShowBanner: true,
          shouldShowList: true,
          shouldPlaySound: true,
          // Only the ledger sets the absolute count, never a replayed payload.
          shouldSetBadge: false,
        };
      },
    });
  } catch {}
}

/** Reconcile the native launcher badge with the unread ledger. */
export async function reconcileNotificationBadge(): Promise<void> {
  if (IS_FDROID) return;

  try {
    const Notifications = require("expo-notifications") as NotificationsModule;
    await badgeQueue.set(Notifications, () => unreadStore.unreadCount());
  } catch {}
}

/** Explicit per-event acknowledgement; reconciles the badge afterwards. */
export async function markNotificationEventRead(id: string): Promise<boolean> {
  const marked = await unreadStore.markRead(id);
  await reconcileNotificationBadge();
  return marked;
}

/**
 * Category/master toggles acknowledge only their own events; unrelated
 * categories stay unread.
 */
export async function markNotificationCategoryRead(
  category: NotificationPreferenceKey,
): Promise<void> {
  await unreadStore.markCategoryRead(category);
  await reconcileNotificationBadge();
}

export async function markAllNotificationsRead(): Promise<void> {
  await unreadStore.markAllRead();
  await reconcileNotificationBadge();
}

/**
 * F-Droid fallback: no push/FCM, so unread bill events are ingested from the
 * public bill feed on foreground. The first snapshot only seeds the baseline
 * (old bills never flood in as new); later runs add only new bills and
 * status transitions. Never claims background delivery.
 */
let feedRefresh: Promise<void> | null = null;
let lastFeedRefreshAt: number | null = null;

export async function refreshUnreadFromPublicBills(): Promise<void> {
  if (!IS_FDROID) return;
  if (feedRefresh) return feedRefresh;
  const now = Date.now();
  if (lastFeedRefreshAt !== null && now >= lastFeedRefreshAt && now - lastFeedRefreshAt < 60_000) return;
  lastFeedRefreshAt = now;
  feedRefresh = (async () => {
    try {
      const bills = await fetchBills({ limit: 50 });
      await unreadStore.refreshFromBills(bills);
    } catch {}
  })();
  try {
    await feedRefresh;
  } finally { feedRefresh = null; }
}

export async function registerForPushNotifications(): Promise<string | null> {
  // F-Droid: skip entirely — no FCM
  if (IS_FDROID) {
    console.log("[notifications] F-Droid build — push disabled");
    return null;
  }

  if (!Device.isDevice) return null;

  const Notifications = require("expo-notifications");

  const { status: existing } = await Notifications.getPermissionsAsync();
  let finalStatus = existing;

  if (existing !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== "granted") return null;

  const tokenData = await Notifications.getExpoPushTokenAsync({
    projectId: "f6cfa7b1-ff85-4020-ac35-94d3774615fd",
  });
  const token = tokenData.data;

  // Store locally
  await SecureStore.setItemAsync(TOKEN_KEY, token);

  // Register with server (anonymous)
  try {
    await fetch(`${API_BASE}/api/v1/notify/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        device_id: `${Platform.OS}-${Device.modelName || "unknown"}`,
        platform: Platform.OS,
      }),
    });
  } catch {}

  return token;
}

export async function getPushToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN_KEY);
}
