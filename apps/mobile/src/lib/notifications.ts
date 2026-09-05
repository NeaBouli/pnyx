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
} from "./notification-preferences";
import {
  createNotificationBadgeQueue,
  isNotificationResponsePayload,
  type BadgeAdapter,
} from "./notification-badge";

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

function incrementBadgeWhenEnabled(
  Notifications: NotificationsModule,
  templateId: unknown,
): Promise<void> {
  return badgeQueue.incrementWhenEnabled(Notifications, () =>
    isNotificationEnabled(SecureStore.getItemAsync, templateId),
  );
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
          try {
            await incrementBadgeWhenEnabled(Notifications, getTemplateId(data));
          } catch {}
        },
      );
    }
    void Notifications.registerTaskAsync(BACKGROUND_NOTIFICATION_TASK).catch(
      () => {},
    );

    Notifications.setNotificationHandler({
      handleNotification: async (notification: unknown) => {
        const templateId = getTemplateId(notification);
        const enabled = await isNotificationEnabled(
          SecureStore.getItemAsync,
          templateId,
        );
        if (!enabled) {
          return {
            shouldShowAlert: false,
            shouldShowBanner: false,
            shouldShowList: false,
            shouldPlaySound: false,
            shouldSetBadge: false,
          };
        }

        // The registered notification task performs the badge increment in
        // both foreground and background; this handler controls presentation.
        return {
          shouldShowAlert: true,
          shouldShowBanner: true,
          shouldShowList: true,
          shouldPlaySound: true,
          shouldSetBadge: true,
        };
      },
    });
  } catch {}
}

export async function clearNotificationBadge(): Promise<void> {
  if (IS_FDROID) return;

  try {
    const Notifications = require("expo-notifications") as NotificationsModule;
    await badgeQueue.clear(Notifications);
  } catch {}
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
